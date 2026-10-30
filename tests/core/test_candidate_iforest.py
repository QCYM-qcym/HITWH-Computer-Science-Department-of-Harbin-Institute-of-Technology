"""Synthetic current13 IF engineering; no real data or effect assumptions."""
from dataclasses import replace
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts, _array_mapping
from traffic_anomaly.candidate_cli import _run as numeric_run
from traffic_anomaly.candidate_record_cli import _run as record_run

SOURCE=Path(__file__).parents[1]/'fixtures'/'g13u-records-v1.json'


@pytest.fixture
def snapshot(tmp_path):
    record_run(SOURCE,'P_U',tmp_path/'records')
    numeric_run(tmp_path/'records'/'minute-fixture.json',tmp_path/'inputs')
    return load_verified_candidate_artifacts(tmp_path/'records',tmp_path/'inputs',source_fixture=SOURCE)


def changed_arrays(snapshot, **changes):
    values={key:snapshot._arrays[key] for key in snapshot._arrays}
    values.update(changes)
    return replace(snapshot,_arrays=_array_mapping(values))


def compute(snapshot):
    from traffic_anomaly.candidate_iforest import compute_synthetic_candidate_if
    return compute_synthetic_candidate_if(snapshot)


def test_actual_if_uses_six_training_minutes_and_preserves_full_axis(snapshot):
    result=compute(snapshot)
    assert result.fit_indices==tuple(range(30,36))
    assert result.calibration_indices==tuple(range(102,108))
    assert result.model.n_features_in_==13 and len(result.model.estimators_)==16
    assert result.configuration['parameter_status']=='ENGINEERING_TOY_ONLY'
    assert result.configuration['max_samples']==6
    assert result.model.get_params()['n_jobs']==1
    assert result.model.get_params()['random_state']==42
    assert result.scores.shape==(144,) and result.score_valid.dtype==bool
    assert result.score_valid.sum()==24
    assert np.isnan(result.scores[~result.score_valid]).all()
    assert not result.alarms[~result.score_valid].any()
    expected=-result.model.score_samples(snapshot.current_values[result.score_valid].astype(np.float32))
    np.testing.assert_array_equal(result.scores[result.score_valid],expected)
    threshold=np.quantile(result.scores[list(result.calibration_indices)],.99,method='linear')
    assert result.threshold==threshold
    np.testing.assert_array_equal(result.alarms[result.score_valid],result.scores[result.score_valid]>threshold)
    assert result.evaluation['policies']['P_U']['normal_minutes']==4
    assert result.evaluation['policies']['P_B']['normal_minutes']==5
    assert result.evaluation['policies']['P_A']['normal_minutes']==4


def test_fit_receives_only_training_normal_common_rows(snapshot,monkeypatch):
    import sklearn.ensemble
    captured={}
    class SpyForest:
        def __init__(self,**kwargs):captured['config']=kwargs
        def fit(self,x):captured['fit']=x.copy();return self
        def score_samples(self,x):return -np.sum(np.asarray(x,float)**2,axis=1)*1e-5-.5
    monkeypatch.setattr(sklearn.ensemble,'IsolationForest',SpyForest)
    compute(snapshot)
    expected=snapshot.current_values[snapshot.training_normal].astype(np.float32)
    np.testing.assert_array_equal(captured['fit'],expected)
    assert captured['fit'].shape==(6,13)
    assert captured['config']['max_samples']==6


def test_test_values_do_not_select_fit_or_threshold(snapshot):
    baseline=compute(snapshot)
    values=snapshot.current_values.copy()
    values[snapshot.partitions=='test']+=1234
    modified=compute(changed_arrays(snapshot,current_values=values))
    assert baseline.fit_indices==modified.fit_indices
    assert baseline.threshold==modified.threshold
    np.testing.assert_array_equal(baseline.model.estimators_[0].tree_.threshold,
                                  modified.model.estimators_[0].tree_.threshold)


def test_no_preprocessing_fit_or_second_file_read(snapshot,monkeypatch):
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor
    def forbidden(*args,**kwargs):raise AssertionError('must consume the loaded snapshot')
    monkeypatch.setattr(CandidatePreprocessor,'fit',forbidden)
    monkeypatch.setattr(Path,'open',forbidden)
    assert compute(snapshot).score_valid.sum()==24


def test_missing_source_replay_is_not_sufficient_for_candidate_execution(snapshot):
    report=snapshot.report_dict();report['checks']['source_replay']='NOT_PROVIDED'
    from traffic_anomaly.candidate_iforest import CandidateIFError
    with pytest.raises(CandidateIFError):compute(replace(snapshot,report=report))


@pytest.mark.parametrize('change',['empty_train','empty_calibration','training_test_row','float32_overflow'])
def test_invalid_model_inputs_fail_explicitly(snapshot,change):
    from traffic_anomaly.candidate_iforest import CandidateIFError
    if change=='empty_train':bad=changed_arrays(snapshot,training_normal=np.zeros(144,bool))
    elif change=='empty_calibration':bad=changed_arrays(snapshot,calibration_normal=np.zeros(144,bool))
    elif change=='training_test_row':
        mask=snapshot.training_normal.copy();mask[140]=True
        bad=changed_arrays(snapshot,training_normal=mask)
    else:
        values=snapshot.current_values.copy();values[140,0]=1e39
        bad=changed_arrays(snapshot,current_values=values)
    with pytest.raises(CandidateIFError) as exc:compute(bad)
    assert str(exc.value)==exc.value.code and 'candidate' not in str(exc.value).lower()


def test_linear_q99_and_strict_boundary_with_nextafter():
    from traffic_anomaly.candidate_iforest import calibrate_candidate_scores
    scores=np.array([0.,1.,2.,3.,0.,0.,0.,np.nan])
    valid=np.array([True]*7+[False]);cal=np.array([True]*4+[False]*4)
    threshold,_,metadata=calibrate_candidate_scores(scores,valid,cal)
    assert threshold==pytest.approx(2.97)
    scores[4:7]=[threshold,np.nextafter(threshold,np.inf),np.nextafter(threshold,-np.inf)]
    again,alarms,metadata=calibrate_candidate_scores(scores,valid,cal)
    assert again==threshold and alarms[4:8].tolist()==[False,True,False,False]
    assert metadata['sample_count']==4 and metadata['order_position_zero_based']==pytest.approx(2.97)
    assert metadata['strictly_above_count']==1


@pytest.mark.parametrize('scores,cal',[(np.array([5.,5.]),np.array([True,False])),
                                      (np.array([2.,2.,2.]),np.array([True,True,True]))])
def test_single_or_tied_calibration_is_defined_without_false_alarm(scores,cal):
    from traffic_anomaly.candidate_iforest import calibrate_candidate_scores
    threshold,alarms,meta=calibrate_candidate_scores(scores,np.ones(len(scores),bool),cal)
    assert threshold==scores[0] and not alarms.any()
    assert meta['equal_count']==int(cal.sum())


@pytest.mark.parametrize('change',['empty','nonfinite','integer_mask','misaligned','invalid_nonnull'])
def test_bad_calibration_or_score_arrays_are_rejected(change):
    from traffic_anomaly.candidate_iforest import CandidateIFError,calibrate_candidate_scores
    scores=np.array([0.,1.,np.nan]);valid=np.array([True,True,False]);cal=np.array([True,True,False])
    if change=='empty':cal[:]=False
    elif change=='nonfinite':scores[0]=np.inf
    elif change=='integer_mask':cal=cal.astype(int)
    elif change=='misaligned':valid=valid[:2]
    else:scores[2]=0
    with pytest.raises(CandidateIFError):calibrate_candidate_scores(scores,valid,cal)


def test_same_saved_model_replays_and_changed_state_is_rejected(snapshot):
    from traffic_anomaly.candidate_iforest import CandidateIFError,replay_saved_candidate_if
    result=compute(snapshot)
    reloaded=copy.deepcopy(result.model)
    replay_saved_candidate_if(snapshot,result,reloaded)
    reloaded.set_params(random_state=999)
    with pytest.raises(CandidateIFError):replay_saved_candidate_if(snapshot,result,reloaded)


def test_fixed_seed_is_repeatable_on_same_snapshot(snapshot):
    first,second=compute(snapshot),compute(snapshot)
    np.testing.assert_array_equal(first.scores,second.scores)
    np.testing.assert_array_equal(first.alarms,second.alarms)
    assert first.threshold==second.threshold
