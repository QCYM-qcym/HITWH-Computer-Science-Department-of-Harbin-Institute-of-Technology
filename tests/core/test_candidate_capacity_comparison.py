"""Readonly capacity admission on freshly fabricated zero-weight AE packages."""
from collections import Counter
from copy import deepcopy
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from .test_candidate_ae_capacity_artifacts import (upstream,make_run,SOURCE,OLD,NEW,
    read,write,reseal,FILES)
from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun

SLOTS=('current_ae13','current_ae13_capacity492','history_ae26_h15','history_ae26_h30')


def api(): return importlib.import_module('traffic_anomaly.candidate_capacity_comparison')


@pytest.fixture
def packages(upstream,tmp_path,monkeypatch):
    values={}
    for slot,profile,method,window in [(SLOTS[0],OLD,'current_ae',None),(SLOTS[1],NEW,'current_ae',None),
        (SLOTS[2],OLD,'history_ae',15),(SLOTS[3],OLD,'history_ae',30)]:
        package,_=make_run(upstream,tmp_path,monkeypatch,profile,method,window,name=slot.replace('_','-'))
        values[slot]=package[0]
    return values,*upstream


def compare(packages,slots=SLOTS,source=SOURCE):
    return api().compare_candidate_ae_capacity_runs([packages[0][slot] for slot in slots],
            *packages[1:],source_fixture=source)


def reject(callback,code=None):
    with pytest.raises(api().CandidateCapacityComparisonError) as caught: callback()
    if code is not None: assert caught.value.code==code
    assert str(caught.value)==caught.value.code and '/' not in str(caught.value)
    return caught.value.code


def snapshot(packages):
    return {path:(path.read_bytes(),path.stat().st_mtime_ns) for directory in [*packages[0].values(),*packages[1:]] for path in directory.iterdir()}


def test_four_slots_order_materials_pairs_and_original_saved_metrics(packages):
    before=snapshot(packages)
    report=compare(packages,tuple(reversed(SLOTS)))
    assert report['comparison_profile_id']=='c17-i1-g13u-ae-capacity-comparison-context-v1'
    assert report['status']=='DATA_QUALIFICATION_ALIGNED'
    assert report['included_slots']==list(SLOTS) and report['missing_slots']==[]
    assert [row['slot'] for row in report['runs']]==list(SLOTS)
    assert [row['parameter_count'] for row in report['runs']]==[288,492,509,509]
    design=report['control_design']
    assert design['controls_materials_complete'] is True
    assert design['same_hidden_width_control_present'] is True
    assert design['same_hidden_width_pairs']==[[SLOTS[0],SLOTS[2]],[SLOTS[0],SLOTS[3]]]
    assert design['near_parameter_count_pairs']==[[SLOTS[1],SLOTS[2]],[SLOTS[1],SLOTS[3]]]
    assert design['near_count']==dict(absolute_difference=17,relative_difference=17/509,
        tolerance=.05,status='PREDEFINED_COUNT_ONLY')
    assert design['no_history_input'] is True
    assert report['shared_context']['minute_count']==144
    assert report['shared_context']['test_denominators_by_policy']['P_U']['calendar_test_minutes']==36
    for row in report['runs']:
        from traffic_anomaly.candidate_ae_run_artifacts import verify_candidate_ae_run
        original=verify_candidate_ae_run(packages[0][row['slot']],*packages[1:],source_fixture=SOURCE)
        assert row['threshold']==original['threshold'] and row['policies']==original['policies']
        assert row['actual_five_artifacts']==original['artifacts']
    assert snapshot(packages)==before
    assert str(packages[1]) not in json.dumps(report)
    for name in ('capacity_control','history_causal_attribution','cross_model_score_scale'):
        assert report['limitations'][name]=='NOT_COMPARABLE'
    assert report['limitations']['ranking']==report['limitations']['statistical_significance']=='NOT_PERFORMED'


@pytest.mark.parametrize('slots',[(SLOTS[1],SLOTS[2]),(SLOTS[1],SLOTS[3]),
    (SLOTS[0],SLOTS[1],SLOTS[2]),(SLOTS[1],SLOTS[2],SLOTS[3])])
def test_allowed_subsets_reference_only_present_pairs(packages,slots):
    report=compare(packages,slots)
    assert report['included_slots']==[slot for slot in SLOTS if slot in slots]
    assert report['missing_slots']==[slot for slot in SLOTS if slot not in slots]
    assert not report['control_design']['controls_materials_complete']
    assert report['control_design']['same_hidden_width_control_present']==(SLOTS[0] in slots)
    assert report['control_design']['same_hidden_width_pairs']==[[SLOTS[0],slot] for slot in SLOTS[2:] if SLOTS[0] in slots and slot in slots]
    assert report['control_design']['near_parameter_count_pairs']==[[SLOTS[1],slot] for slot in SLOTS[2:] if slot in slots]


@pytest.mark.parametrize('slots',[(SLOTS[0],SLOTS[1]),(SLOTS[2],SLOTS[3]),(SLOTS[0],SLOTS[2])])
def test_new_and_history_are_both_mandatory(packages,slots):
    reject(lambda:compare(packages,slots),'REQUIRED_CAPACITY_CONTROLS_MISSING')


def test_source_is_required_before_any_admission(packages,monkeypatch):
    m=api()
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',lambda *a,**k:pytest.fail('loaded absent source'))
    reject(lambda:compare(packages,source=None),'SOURCE_REQUIRED')


@pytest.mark.parametrize('kind',['empty','one','five','generator','wrong_type','family_spec'])
def test_explicit_bounded_directory_container_before_reads(packages,monkeypatch,kind):
    m=api();values=list(packages[0].values())
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun
    requested={'empty':[],'one':values[:1],'five':values+values[:1],'generator':iter(values),
        'wrong_type':[True,values[1]],'family_spec':[CandidateComparisonRun('iforest',values[0]),values[1]]}[kind]
    monkeypatch.setattr(Path,'open',lambda *a,**k:pytest.fail('read before shape rejection'))
    reject(lambda:m.compare_candidate_ae_capacity_runs(requested,*packages[1:],source_fixture=SOURCE))


def test_duplicate_directory_alias_before_admission(packages,monkeypatch):
    m=api();path=packages[0][SLOTS[1]]
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',lambda *a,**k:pytest.fail('loaded alias'))
    reject(lambda:m.compare_candidate_ae_capacity_runs([path,path/'..'/path.name],*packages[1:],source_fixture=SOURCE),'DUPLICATE_RUN_DIRECTORY')


@pytest.mark.parametrize('field',['run_id','slot'])
def test_duplicate_run_id_or_slot_with_distinct_paths(packages,tmp_path,monkeypatch,field):
    target=tmp_path/'another'
    shutil.copytree(packages[0][SLOTS[1]],target)
    if field=='slot':
        for name in FILES:
            value=read(target/name);common=value['binding'] if name=='weights.json' else value
            common['run_id']='another-id';write(target/name,value)
        reseal((target,*packages[1:]))
    reject(lambda:api().compare_candidate_ae_capacity_runs([packages[0][SLOTS[1]],target],*packages[1:],source_fixture=SOURCE),
        'DUPLICATE_RUN_ID' if field=='run_id' else 'DUPLICATE_RUN_SLOT')


def test_actual_manifest_extra_read_identity_join(packages,monkeypatch):
    m=api();actual=m.load_verified_candidate_ae_run;changed=[]
    target=packages[0][SLOTS[1]]
    def mutate(run,*a,**k):
        if Path(run)==target and not changed:
            for name in FILES:
                value=read(target/name);common=value['binding'] if name=='weights.json' else value
                common['run_id']='changed-during-read';write(target/name,value)
            reseal((target,*packages[1:]));changed.append(True)
        return actual(run,*a,**k)
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',mutate)
    reject(lambda:compare(packages),'CHANGED_DURING_COMPARISON')


@pytest.mark.parametrize('kind',['wrong_verifier','wrong_profile','window_swap','scope_upgrade','proof_upgrade',
    'bool_count','float_count','negative_population','metric_nan','metric_bool','bad_null_reason'])
def test_admitted_report_contradictions_reject(packages,monkeypatch,kind):
    m=api();actual=m.load_verified_candidate_ae_run;target=packages[0][SLOTS[2]]
    def changed(run,*a,**k):
        value=actual(run,*a,**k)
        if Path(run)!=target:return value
        report=value.report_dict();scores=value.scores_dict()
        if kind=='wrong_verifier': report['verifier_profile_id']='c17-i1-g13u-ae-capacity-run-verifier-v1'
        elif kind=='wrong_profile':report['model_profile_id']=NEW
        elif kind=='window_swap':report['history_window']=30
        elif kind=='scope_upgrade':report['scope']='MODEL_AUTHENTICATED'
        elif kind=='proof_upgrade':report['checks']['model_score_replay']='VERIFIED'
        elif kind=='bool_count':report['fit_count']=True
        elif kind=='float_count':report['score_valid_count']=24.
        elif kind=='negative_population':report['policies']['P_U']['unknown_minutes']=-1
        elif kind=='metric_nan':report['policies']['P_U']['metrics']['fpr']=float('nan')
        elif kind=='metric_bool':report['policies']['P_U']['metrics']['fpr']=False
        else:report['policies']['P_U']['undefined_reasons']={'precision':'private reason'}
        return VerifiedCandidateRun(report,scores)
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',changed)
    reject(lambda:compare(packages))


@pytest.mark.parametrize('key',['timestamps','segment_ids','partitions','current_input_valid','common_valid',
    'score_valid','history_invalid_reason','fit_indices','calibration_indices'])
def test_same_counts_do_not_replace_full_axes_and_indices(packages,monkeypatch,key):
    m=api();actual=m.load_verified_candidate_ae_run;target=packages[0][SLOTS[3]]
    baseline=actual(target,*packages[1:],source_fixture=SOURCE)
    report=baseline.report_dict();scores=baseline.scores_dict()
    if key in ('fit_indices','calibration_indices'):
        # Mutate before the extra read, and explicitly rebind the fault-injected
        # snapshot to those bytes so this tests qualification rather than TOCTOU.
        manifest=read(target/'manifest.json');manifest[key][0]-=1;write(target/'manifest.json',manifest)
        payload=(target/'manifest.json').read_bytes()
        import hashlib
        report['artifacts']['manifest.json']=dict(sha256=hashlib.sha256(payload).hexdigest(),byte_count=len(payload))
    elif key=='history_invalid_reason':scores[key]['15'][0]='gap'
    elif key in ('common_valid','score_valid'):
        scores[key][0]=not scores[key][0];scores[key][30]=not scores[key][30]
    elif key=='current_input_valid':scores[key][0]=not scores[key][0]
    else:scores[key][0]='changed-identity'
    def changed(run,*a,**k):
        return VerifiedCandidateRun(report,scores) if Path(run)==target else actual(run,*a,**k)
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',changed)
    reject(lambda:compare(packages))


def test_single_admission_each_manifest_twice_other_package_payload_once(packages,monkeypatch):
    m=api();actual=m.load_verified_candidate_ae_run;loads=Counter();opens=Counter();original=Path.open
    def load(run,*a,**k):loads[Path(run)]+=1;return actual(run,*a,**k)
    def opening(path,*a,**k):
        if any(path.parent==directory for directory in packages[0].values()):opens[path]+=1
        return original(path,*a,**k)
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',load)
    monkeypatch.setattr(Path,'open',opening)
    compare(packages)
    assert set(loads)==set(packages[0].values()) and all(n==1 for n in loads.values())
    assert all(n==(2 if path.name=='manifest.json' else 1) for path,n in opens.items())


def test_report_result_does_not_alias_admitted_snapshot(packages,monkeypatch):
    m=api();actual=m.load_verified_candidate_ae_run;values=[]
    def capture(*a,**k):value=actual(*a,**k);values.append(value);return value
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',capture)
    result=compare(packages)
    before=[(v.report_dict(),v.scores_dict()) for v in values]
    result['runs'][0]['policies']['P_U']['normal_minutes']=999
    result['shared_context']['feature_names'][0]='changed'
    assert [(v.report_dict(),v.scores_dict()) for v in values]==before


def test_classic_old_ae_subset_still_valid_and_new_rejected(packages):
    from traffic_anomaly.candidate_comparison import compare_candidate_runs,CandidateComparisonRun,CandidateComparisonError,SLOT_ORDER
    old=[CandidateComparisonRun('autoencoder',packages[0][slot]) for slot in (SLOTS[0],SLOTS[2],SLOTS[3])]
    classic=compare_candidate_runs(old,*packages[1:],source_fixture=SOURCE)
    assert classic['comparison_profile_id']=='c17-i1-g13u-comparison-context-v1'
    assert SLOT_ORDER==('iforest_current13','current_ae13','history_ae26_h15','history_ae26_h30')
    with pytest.raises(CandidateComparisonError):
        compare_candidate_runs([old[0],CandidateComparisonRun('autoencoder',packages[0][SLOTS[1]])],*packages[1:],source_fixture=SOURCE)


def test_capacity_report_contract_rejects_unknown_fields_and_preserves_nulls(packages):
    contract=importlib.import_module('traffic_anomaly.candidate_capacity_contract')
    result=compare(packages)
    contract.validate_capacity_report(result)
    for path in [(),('runs',0),('shared_context',),('control_design',),('runs',0,'policies','P_U')]:
        changed=deepcopy(result);target=changed
        for key in path:target=target[key]
        target['private_extra']='unwanted'
        with pytest.raises(contract.CandidateCapacityComparisonError):contract.validate_capacity_report(changed)


def test_fresh_child_comparison_has_no_models_or_training(packages):
    script='''import builtins,json,sys
original=builtins.__import__
def guarded(name,*a,**k):
 assert name.split('.')[0] not in {'torch','sklearn','joblib'},name
 return original(name,*a,**k)
builtins.__import__=guarded
from traffic_anomaly.candidate_capacity_comparison import compare_candidate_ae_capacity_runs
report=compare_candidate_ae_capacity_runs(sys.argv[4:],sys.argv[1],sys.argv[2],source_fixture=sys.argv[3])
assert report['control_design']['controls_materials_complete']
assert report['limitations']['model_execution']=='NOT_CHECKED'
print(json.dumps({'status':report['status']}))
'''
    result=subprocess.run([sys.executable,'-X','utf8','-c',script,*map(str,packages[1:]),str(SOURCE),
        *map(str,packages[0].values())],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'status':'DATA_QUALIFICATION_ALIGNED'}


@pytest.mark.parametrize('kind',['provenance','preprocessing_state','selected_policy','feature_order','windows'])
def test_same_counts_do_not_replace_bound_upstream_context(packages,monkeypatch,kind):
    m=api();actual=m.load_verified_candidate_ae_run;target=packages[0][SLOTS[3]]
    baseline=actual(target,*packages[1:],source_fixture=SOURCE)
    report=baseline.report_dict();scores=baseline.scores_dict();manifest=read(target/'manifest.json')
    if kind=='provenance':manifest['provenance']['preprocess']['sha256']='0'*64
    elif kind=='preprocessing_state':manifest['preprocessing_state']['mean'][0]+=1.
    elif kind=='selected_policy':manifest['selected_policy']='P_B';report['selected_policy']='P_B'
    elif kind=='feature_order':manifest['feature_names'].reverse()
    else:manifest['qualification_windows']=[15]
    for key in ('provenance','preprocessing_state','selected_policy','feature_names','qualification_windows'):
        scores[key]=deepcopy(manifest[key])
    write(target/'manifest.json',manifest)
    from .test_candidate_comparison import digest
    report['artifacts']['manifest.json']=digest(target/'manifest.json')
    def changed(run,*a,**k):
        return VerifiedCandidateRun(report,scores) if Path(run)==target else actual(run,*a,**k)
    monkeypatch.setattr(m,'load_verified_candidate_ae_run',changed)
    reject(lambda:compare(packages),'INCOMPARABLE_UPSTREAM')


def test_if_style_artifact_layout_is_not_an_ae_package(packages,tmp_path):
    target=tmp_path/'if-style'
    shutil.copytree(packages[0][SLOTS[0]],target)
    (target/'weights.json').rename(target/'weights.bin')
    reject(lambda:api().compare_candidate_ae_capacity_runs([packages[0][SLOTS[1]],target],*packages[1:],source_fixture=SOURCE))


def test_contract_wrong_nested_types_are_always_fixed_errors(packages):
    contract=importlib.import_module('traffic_anomaly.candidate_capacity_contract')
    original=compare(packages)
    cases=[(('runs',0),value) for value in (None,False,1,'private',[])]
    cases+=[(('runs',0,'runtime','torch_num_threads'),True),
        (('runs',0,'calibration','sample_count'),6.),(('runs',0,'threshold'),False),
        (('control_design','near_count','absolute_difference'),17.),
        (('shared_context','five_provenance','source_fixture','byte_count'),213497.),
        (('runs',0,'actual_five_artifacts','weights.json','byte_count'),True)]
    for path,value in cases:
        changed=deepcopy(original);parent=changed
        for key in path[:-1]:parent=parent[key]
        parent[path[-1]]=value
        with pytest.raises(contract.CandidateCapacityComparisonError):contract.validate_capacity_report(changed)


def test_distinct_thresholds_null_reasons_and_zero_metrics_are_preserved(packages):
    from .test_candidate_comparison import rewrite_predictions
    rewrite_predictions(packages[0][SLOTS[1]],*packages[1:],all_zero=True)
    rewrite_predictions(packages[0][SLOTS[2]],*packages[1:],all_zero=False)
    report=compare(packages,(SLOTS[1],SLOTS[2]))
    current,history=report['runs']
    assert current['threshold']==0. and history['threshold']==5.95
    assert current['policies']['P_U']['metrics']['precision'] is None
    assert current['policies']['P_U']['metrics']['fpr']==0.
    assert current['policies']['P_U']['metrics']['fnr']==1.
    assert current['policies']['P_U']['undefined_reasons']=={'precision':'No positive predictions on scored normal or attack test minutes.'}
    assert current['policies']['P_U']['confusion_counts']!=history['policies']['P_U']['confusion_counts']
    assert current['calibration']['equal_count']==6 and history['calibration']['equal_count']==0


def test_declared_runtime_differences_are_limits_not_alignment_failure(packages):
    from .test_candidate_comparison import change_common
    change_common(packages[0][SLOTS[1]],lambda d:d.update(library_versions=dict(python='0.1-declared',numpy='0.2-declared',torch='0.3-declared'),
        runtime=dict(device='cpu',torch_num_threads=2,torch_num_interop_threads=3)))
    report=compare(packages)
    assert report['limitations']['execution_controls']=='DECLARED_EXECUTION_CONTROLS_DIFFER'


def test_actual_source_bytes_must_replay(packages,tmp_path):
    other=tmp_path/'other-source.json';other.write_bytes(SOURCE.read_bytes()+b'\n')
    reject(lambda:compare(packages,source=other),'INTEGRITY_MISMATCH')


@pytest.mark.parametrize('ending,size,sha',[
    ('LF',205567,'0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff'),
    ('CRLF',213497,'6f42399eabb07dc218eac19f4d648e57eb360a0c7167968ca1770733ea8649b2')])
def test_fabricated_capacity_group_for_both_fixed_source_encodings(tmp_path,monkeypatch,ending,size,sha):
    from . import test_candidate_ae_capacity_artifacts as fixtures
    from traffic_anomaly.candidate_record_cli import _run as record_run
    from traffic_anomaly.candidate_cli import _run as input_run
    import hashlib
    # Only construct the two predeclared synthetic fixtures. Production never
    # normalizes input bytes and continues to bind exact source identities.
    payload=SOURCE.read_bytes().replace(b'\r\n',b'\n')
    if ending=='CRLF':payload=payload.replace(b'\n',b'\r\n')
    assert len(payload)==size and hashlib.sha256(payload).hexdigest()==sha
    source=tmp_path/'fixed-source.json';source.write_bytes(payload)
    records,inputs=tmp_path/'records',tmp_path/'inputs'
    record_run(source,'P_U',records);input_run(records/'minute-fixture.json',inputs)
    monkeypatch.setattr(fixtures,'SOURCE',source)
    paths=[]
    for slot,profile,method,window in [(SLOTS[0],OLD,'current_ae',None),(SLOTS[1],NEW,'current_ae',None),
        (SLOTS[2],OLD,'history_ae',15),(SLOTS[3],OLD,'history_ae',30)]:
        package,_=make_run((records,inputs),tmp_path,monkeypatch,profile,method,window,name=slot.replace('_','-'))
        paths.append(package[0])
    result=api().compare_candidate_ae_capacity_runs(paths,records,inputs,source_fixture=source)
    assert result['included_slots']==list(SLOTS)
    assert result['shared_context']['five_provenance']['source_fixture']==dict(sha256=sha,byte_count=size)
