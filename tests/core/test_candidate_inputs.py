"""Hand-computed candidate inputs; never consume real CSVs or model scores."""
import importlib
import json
import numpy as np
import pytest


def module():
    return importlib.import_module('traffic_anomaly.candidate_inputs')


def batch(values, *, space='prepared', valid=None, segments=None, partitions=None, offsets=None):
    m = module()
    x = np.asarray(values, dtype=float)
    if x.ndim == 1:
        x = np.repeat(x[:, None], 13, axis=1)
    n = len(x)
    stamps = np.datetime64('2026-01-01T00:00', 'us') + np.asarray(range(n) if offsets is None else offsets)*np.timedelta64(1,'m')
    return m.CandidateMinuteBatch(stamps, x,
        np.ones(n,bool) if valid is None else np.asarray(valid,bool),
        np.repeat('s0',n) if segments is None else np.array(segments),
        np.repeat('train',n) if partitions is None else np.array(partitions), value_space=space)


def test_history_uses_past_median_mad_and_signed_current():
    h = module().build_candidate_history(batch([1,3,9,-1]),window=2,epsilon=1)
    assert h.valid.tolist() == [False,False,True,True]
    np.testing.assert_allclose(h.residual[2], [3.5]*13)  # past 1/3: median2,MAD1
    np.testing.assert_allclose(h.residual[3], [-1.75]*13) # past 3/9: median6,MAD3
    assert h.joined.shape == (4,26)
    assert np.isnan(h.joined[:2]).all()
    np.testing.assert_array_equal(h.joined[2,:13], [9]*13)


def test_current_and_future_never_enter_earlier_history():
    a = module().build_candidate_history(batch([1,3,5,7,9]),window=2,epsilon=1)
    b = module().build_candidate_history(batch([1,3,5,7000,9000]),window=2,epsilon=1)
    np.testing.assert_array_equal(a.residual[:3],b.residual[:3])
    assert b.residual[3,0] == 3498  # uses past3/5 -> (7000-4)/2


@pytest.mark.parametrize('window',[15,30])
def test_constant_history_needs_exactly_window_prior_minutes(window):
    h = module().build_candidate_history(batch([2]*window+[3]),window=window,epsilon=.5)
    assert h.valid.sum() == 1 and h.valid[-1]
    np.testing.assert_array_equal(h.residual[-1],[2]*13)


@pytest.mark.parametrize('kind',['gap','segment','partition','invalid'])
def test_boundaries_restart_full_history(kind):
    kwargs={}
    if kind=='gap': kwargs['offsets']=[0,1,2,4,5,6]
    if kind=='segment': kwargs['segments']=['a']*3+['b']*3
    if kind=='partition': kwargs['partitions']=['train']*3+['validation']*3
    if kind=='invalid': kwargs['valid']=[True,True,False,True,True,True]
    h=module().build_candidate_history(batch([1,2,3,4,5,6],**kwargs),window=2,epsilon=1)
    assert h.valid[3:5].tolist()==[False,False]
    assert h.valid[-1]
    assert h.invalid_reason[3] in ('gap','boundary','invalid_input')


def test_raw_values_cannot_be_mistaken_for_prepared_history():
    with pytest.raises(ValueError):
        module().build_candidate_history(batch([1,2,3],space='raw'),window=2,epsilon=1)


@pytest.mark.parametrize('epsilon',[0,-1,float('nan'),float('inf'),True])
def test_invalid_epsilon_rejected(epsilon):
    with pytest.raises(ValueError):
        module().build_candidate_history(batch([1,2,3]),window=2,epsilon=epsilon)


def test_float_overflow_is_invalid_and_resets_next_history():
    h=module().build_candidate_history(batch([0,0,1e308,0,0,1]),window=2,epsilon=1e-10)
    assert not h.valid[2] and h.invalid_reason[2]=='nonfinite_history'
    assert not h.valid[3] and not h.valid[4] and h.valid[5]
    assert np.isnan(h.residual[2]).all()


def test_fit_is_training_only_and_requires_prior_normal_history():
    b=batch([0,3,8,1e12,1e13,1e14],space='raw',partitions=['train']*3+['test']*3)
    p=module().CandidatePreprocessor().fit(b,np.ones(6,bool),window=1)
    np.testing.assert_allclose(p.mean,[ (np.log(4)+np.log(9))/2 ]*13)
    assert p.n_samples_seen==2
    q=module().CandidatePreprocessor().fit(b,np.array([False,True,True,True,True,True]),window=1)
    assert q.n_samples_seen==1
    np.testing.assert_allclose(q.mean,[np.log(9)]*13)


def test_transform_keeps_invalid_axis_and_supports_negative_prepared_values():
    b=batch([0,3,8,1],space='raw',valid=[True,True,True,False])
    p=module().CandidatePreprocessor().fit(b,np.ones(4,bool),window=1)
    z=p.transform(b)
    assert z.value_space=='prepared' and z.values[0,0]<0
    np.testing.assert_array_equal(z.timestamps,b.timestamps)
    assert np.isnan(z.values[-1]).all() and not z.row_valid[-1]


def test_empty_training_eligibility_cannot_fit():
    with pytest.raises(ValueError):
        module().CandidatePreprocessor().fit(batch([1]*30,space='raw'),np.ones(30,bool))


def test_mathematically_constant_training_columns_get_unit_scale_and_zero():
    b=batch([5]*7,space='raw')
    p=module().CandidatePreprocessor().fit(b,np.ones(7,bool),window=1)
    np.testing.assert_array_equal(p.scale,[1]*13)
    np.testing.assert_array_equal(p.transform(b).values,np.zeros((7,13)))


def test_nonfinite_mad_denominator_cannot_be_valid_zero():
    h=module().build_candidate_history(batch([-1e308,1e308,1e308,0,0,1]),window=2,epsilon=1e308)
    assert not h.valid[2]
    assert h.invalid_reason[2]=='nonfinite_history' and np.isnan(h.residual[2]).all()
    assert not h.valid[3] and not h.valid[4] and h.valid[5]


def test_saved_preprocessor_reload_and_version_order_rejection(tmp_path):
    m=module(); b=batch([0,3,8],space='raw')
    p=m.CandidatePreprocessor().fit(b,np.ones(3,bool),window=1)
    path=tmp_path/'state.json'; p.save(path)
    np.testing.assert_array_equal(p.transform(b).values,m.CandidatePreprocessor.load(path).transform(b).values)
    with pytest.raises(FileExistsError): p.save(path)
    data=json.loads(path.read_text('utf-8')); data['feature_names'].reverse()
    path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError): m.CandidatePreprocessor.load(path)


def test_preparation_uses_common_history_and_test_current_labels_only():
    m=module(); roles=np.repeat(['train','validation','calibration','test'],36)
    b=batch(np.tile(np.arange(36),4),space='raw',partitions=roles)
    normal=np.ones(144,bool); normal[108:113]=False
    r=m.prepare_candidate_inputs(b,normal)
    assert r.common_valid.sum()==24
    assert r.training_normal.sum()==6 and r.calibration_normal.sum()==6
    assert r.test_normal.sum()==6  # earlier attack/unknown must stay in history
    assert r.preprocessor.n_samples_seen==6
    q=m.prepare_candidate_inputs(b,np.ones(144,bool))
    np.testing.assert_array_equal(r.histories[30].joined,q.histories[30].joined)
    np.testing.assert_array_equal(r.common_valid,q.common_valid)


def test_batch_rejects_wrong_width_order_labels_time_and_nonfinite():
    m=module(); b=batch([1,2,3])
    args=dict(timestamps=b.timestamps,values=b.values,row_valid=b.row_valid,
              segment_ids=b.segment_ids,partitions=b.partitions,value_space='prepared')
    for changes in [dict(values=np.ones((3,12))),dict(feature_names=tuple(reversed(m.G13U_FEATURE_NAMES))),
                    dict(feature_names=m.G13U_FEATURE_NAMES[:-1]+('Label',)),
                    dict(timestamps=b.timestamps[::-1]),dict(row_valid=np.ones(2,bool)),
                    dict(row_valid=[1,1,1]),dict(values=np.full((3,13),np.inf)),
                    dict(partitions=['test','train','test']),dict(evidence_kind='REAL')]:
        with pytest.raises(ValueError): m.CandidateMinuteBatch(**(args|changes))


def test_batches_own_readonly_arrays_and_reject_production_contract():
    b=batch([1,2,3]); assert not b.values.flags.writeable
    with pytest.raises(ValueError): b.values[0,0]=10
    from traffic_anomaly.contracts import MinuteBatch
    with pytest.raises(ValueError):
        MinuteBatch(b.timestamps.astype('datetime64[ns]'),b.values,b.feature_names,b.row_valid,np.zeros(3,np.int64))
