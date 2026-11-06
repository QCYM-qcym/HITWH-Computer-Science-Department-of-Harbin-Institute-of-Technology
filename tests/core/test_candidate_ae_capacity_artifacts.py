"""Fabricated fixed-source package fixtures, never an actual trained492 run."""
import builtins
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from traffic_anomaly.candidate_ae_profiles import (MODEL_PROFILE_ID as OLD,
    CAPACITY492_MODEL_PROFILE_ID as NEW,resolve_candidate_ae_configuration)
from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
from traffic_anomaly.candidate_record_cli import _run as records_run
from traffic_anomaly.candidate_cli import _run as inputs_run
from .test_candidate_ae_cli import install_stub_pipeline,COMMON_KEYS
from .test_candidate_ae_run_artifacts import read,write,reseal,FILES

SOURCE=Path(__file__).parents[1]/'fixtures/g13u-records-v1.json'
NEW_VERIFIER='c17-i1-g13u-ae-capacity-run-verifier-v1'


@pytest.fixture
def upstream(tmp_path):
    records,inputs=tmp_path/'records',tmp_path/'inputs'
    records_run(SOURCE,'P_U',records)
    inputs_run(records/'minute-fixture.json',inputs)
    return records,inputs


def fixture_pipeline(monkeypatch):
    module,calls=install_stub_pipeline(monkeypatch)
    original=module.compute_synthetic_candidate_ae
    def compute(snapshot,*,method,history_window=None,model_profile_id=OLD):
        result=original(snapshot,method=method,history_window=history_window)
        result.configuration=resolve_candidate_ae_configuration(method,history_window,model_profile_id=model_profile_id)
        calls.append(('requested_profile',model_profile_id))
        return result
    def encode(model,binding):
        # Deliberately zero weights and fabricated scores: structural fixture,
        # not claimed to be the output of training or model-score replay.
        shape=binding['configuration']['architecture']
        parameters={}
        for i,(left,right) in enumerate(zip(shape,shape[1:])):
            parameters[f'{i*2}.weight']=dict(dtype='float32',shape=[right,left],values=[0.]* (right*left))
            parameters[f'{i*2}.bias']=dict(dtype='float32',shape=[right],values=[0.]*right)
        return dict(schema_version=1,format='candidate-ae-json-weights-v1',binding=binding,parameters=parameters)
    monkeypatch.setattr(module,'compute_synthetic_candidate_ae',compute)
    monkeypatch.setattr(module,'encode_candidate_ae_weights',encode)
    return module,calls


def make_run(upstream,tmp_path,monkeypatch,profile=NEW,method='current_ae',window=None,name='fabricated-run'):
    module,calls=fixture_pipeline(monkeypatch)
    output=tmp_path/name
    module.run_synthetic_candidate_ae(*upstream,SOURCE,name,output,method=method,
                                    history_window=window,model_profile_id=profile)
    return (output,*upstream),calls


def verify(package,source=SOURCE):
    from traffic_anomaly.candidate_ae_run_artifacts import verify_candidate_ae_run
    return verify_candidate_ae_run(*package,source_fixture=source)


def test_fixed_identity_matches_reference_and_bundled_bytes():
    from traffic_anomaly import candidate_ae_profiles as profiles
    root=Path(__file__).parents[2]
    bundled=root/'src/backend/traffic_api/candidate_demo/g13u-records-v1.json'
    allowed={
        ('6f42399eabb07dc218eac19f4d648e57eb360a0c7167968ca1770733ea8649b2',213497),
        ('0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff',205567),
    }
    for payload in (SOURCE.read_bytes(),bundled.read_bytes()):
        identity=dict(sha256=hashlib.sha256(payload).hexdigest(),byte_count=len(payload))
        assert (identity['sha256'],identity['byte_count']) in allowed
        assert profiles.capacity492_source_binding_matches(
            dict(checks=dict(source_replay='VERIFIED'),source_fixture=identity),dict(source_fixture=identity))


@pytest.mark.parametrize('sha,size,accepted',[
    ('6f42399eabb07dc218eac19f4d648e57eb360a0c7167968ca1770733ea8649b2',213497,True),
    ('0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff',205567,True),
    ('6f42399eabb07dc218eac19f4d648e57eb360a0c7167968ca1770733ea8649b2',205567,False),
    ('0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff',213497,False),
    ('0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff',205567.,False),
    ('0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff',True,False),
    ('0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff',205568,False),
    ('0'*64,205567,False),
])
def test_fixed_source_identity_accepts_only_predeclared_pairs(sha,size,accepted):
    from traffic_anomaly.candidate_ae_profiles import capacity492_source_binding_matches
    identity=dict(sha256=sha,byte_count=size)
    assert capacity492_source_binding_matches(
        dict(checks=dict(source_replay='VERIFIED'),source_fixture=identity),dict(source_fixture=dict(identity))) is accepted


@pytest.mark.parametrize('reverse',[False,True])
def test_fixed_source_identity_report_and_provenance_must_be_same_pair(reverse):
    from traffic_anomaly.candidate_ae_profiles import capacity492_source_binding_matches
    identities=[dict(sha256='6f42399eabb07dc218eac19f4d648e57eb360a0c7167968ca1770733ea8649b2',byte_count=213497),
        dict(sha256='0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff',byte_count=205567)]
    if reverse:identities.reverse()
    assert not capacity492_source_binding_matches(
        dict(checks=dict(source_replay='VERIFIED'),source_fixture=identities[0]),dict(source_fixture=identities[1]))


@pytest.mark.parametrize('profile',[None,True,[],{},'unknown'])
def test_unknown_request_profile_rejected_before_paths_or_compute(tmp_path,monkeypatch,profile):
    from traffic_anomaly import candidate_ae_cli as m
    monkeypatch.setattr(m,'compute_synthetic_candidate_ae',lambda *a,**k:pytest.fail('computed'))
    with pytest.raises(m._CLIError,match='INVALID_MODEL_PROFILE'):
        m.run_synthetic_candidate_ae(None,None,None,'toy',tmp_path/'out',method='current_ae',model_profile_id=profile)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('method,window',[('history_ae',15),('history_ae',30),('current_ae',15),('current_ae',False)])
def test_new_profile_method_window_rejects_before_loader_or_output(tmp_path,monkeypatch,method,window):
    from traffic_anomaly import candidate_ae_cli as m
    monkeypatch.setattr(m,'load_verified_candidate_artifacts',lambda *a,**k:pytest.fail('loaded'))
    with pytest.raises(m._CLIError,match='INVALID_METHOD_WINDOW'):
        m.run_synthetic_candidate_ae(None,None,None,'toy',tmp_path/'out',method=method,history_window=window,model_profile_id=NEW)


def test_new_execution_source_missing_is_safe_before_output(upstream,tmp_path,monkeypatch):
    from traffic_anomaly import candidate_ae_cli as m
    monkeypatch.setattr(m,'compute_synthetic_candidate_ae',lambda *a,**k:pytest.fail('computed'))
    with pytest.raises(m._CLIError,match='SOURCE_REQUIRED'):
        m.run_synthetic_candidate_ae(*upstream,None,'toy',tmp_path/'out',method='current_ae',model_profile_id=NEW)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('change',['unverified','provenance_hash','report_hash','float_bytes'])
def test_fixed_source_uses_loader_bound_report_and_provenance(upstream,tmp_path,monkeypatch,change):
    from traffic_anomaly import candidate_ae_cli as m
    snapshot=load_verified_candidate_artifacts(*upstream,source_fixture=SOURCE)
    report=snapshot.report_dict()
    provenance={key:dict(value) for key,value in snapshot.provenance.items()}
    if change=='unverified': report['checks']['source_replay']='NOT_PROVIDED'
    elif change=='provenance_hash': provenance['source_fixture']['sha256']='0'*64
    elif change=='report_hash': report['source_fixture']['sha256']='0'*64
    else: provenance['source_fixture']['byte_count']=213497.
    monkeypatch.setattr(m,'load_verified_candidate_artifacts',lambda *a,**k:replace(snapshot,report=report,provenance=provenance))
    monkeypatch.setattr(m,'compute_synthetic_candidate_ae',lambda *a,**k:pytest.fail('computed'))
    with pytest.raises(m._CLIError) as caught:
        m.run_synthetic_candidate_ae(*upstream,SOURCE,'toy',tmp_path/'out',method='current_ae',model_profile_id=NEW)
    assert str(caught.value)==('SOURCE_NOT_VERIFIED' if change=='unverified' else 'FIXED_SOURCE_MISMATCH')
    assert not (tmp_path/'out').exists()


def test_replayed_different_source_rejected_but_old_profile_unrestricted(tmp_path,monkeypatch):
    other=tmp_path/'other-fixture.json'
    other.write_bytes(SOURCE.read_bytes()+b'\n')
    records,inputs=tmp_path/'other-records',tmp_path/'other-inputs'
    records_run(other,'P_U',records);inputs_run(records/'minute-fixture.json',inputs)
    module,_=fixture_pipeline(monkeypatch)
    with pytest.raises(module._CLIError,match='FIXED_SOURCE_MISMATCH'):
        module.run_synthetic_candidate_ae(records,inputs,other,'toy',tmp_path/'new',method='current_ae',model_profile_id=NEW)
    assert not (tmp_path/'new').exists()
    module.run_synthetic_candidate_ae(records,inputs,other,'old',tmp_path/'old',method='current_ae')
    assert read(tmp_path/'old'/'manifest.json')['model_profile_id']==OLD


def test_profile_written_to_all_five_files_and_readonly_verifier(upstream,tmp_path,monkeypatch):
    package,calls=make_run(upstream,tmp_path,monkeypatch)
    assert ('requested_profile',NEW) in calls
    for name in FILES:
        document=read(package[0]/name)
        common=document['binding'] if name=='weights.json' else document
        assert common['model_profile_id']==common['configuration']['model_profile_id']==NEW
        assert common['configuration']['architecture']==[13,14,3,14,13]
        assert common['configuration']['parameter_count']==492
        encoded=json.dumps(common['configuration'],sort_keys=True,separators=(',',':')).encode()
        assert common['configuration_sha256']==hashlib.sha256(encoded).hexdigest()
    scores=read(package[0]/'scores.json')
    assert scores['history_deviation_reconstruction_mse_status']=='NOT_APPLICABLE'
    assert scores['history_deviation_reconstruction_mse']==[None]*144
    report=verify(package)
    assert report['verifier_profile_id']==NEW_VERIFIER and report['model_profile_id']==NEW
    assert report['checks']['source_replay']=='VERIFIED'
    assert report['checks']['model_origin']=='NOT_AUTHENTICATED'
    assert report['checks']['training_execution']==report['checks']['model_score_replay']=='NOT_CHECKED'
    assert report['checks']['network_reconstruction']=='NOT_PERFORMED'


def test_new_verifier_requires_source_before_loader(upstream,tmp_path,monkeypatch):
    package,_=make_run(upstream,tmp_path,monkeypatch)
    from traffic_anomaly import candidate_ae_run_artifacts as m
    monkeypatch.setattr(m,'load_verified_candidate_artifacts',lambda *a,**k:pytest.fail('loaded without source'))
    with pytest.raises(m.CandidateAERunArtifactError,match='SOURCE_REQUIRED'): verify(package,None)


@pytest.mark.parametrize('mutation',['profile','architecture','epochs','optimizer','profile_type'])
def test_result_full_config_must_match_request_before_weights_or_complete(upstream,tmp_path,monkeypatch,mutation):
    module,_=fixture_pipeline(monkeypatch)
    original=module.compute_synthetic_candidate_ae
    def changed(*a,**k):
        result=original(*a,**k)
        if mutation=='profile': result.configuration['model_profile_id']=OLD
        elif mutation=='architecture': result.configuration.update(architecture=[13,8,3,8,13],parameter_count=288)
        elif mutation=='epochs': result.configuration['epochs']=5.
        elif mutation=='optimizer': result.configuration['learning_rate']=.1
        else: result.configuration['model_profile_id']=True
        return result
    monkeypatch.setattr(module,'compute_synthetic_candidate_ae',changed)
    monkeypatch.setattr(module,'encode_candidate_ae_weights',lambda *a:pytest.fail('encoded bad config'))
    with pytest.raises(module._CLIError,match='INVALID_MODEL_RESULT'):
        module.run_synthetic_candidate_ae(*upstream,SOURCE,'toy',tmp_path/'out',method='current_ae',model_profile_id=NEW)
    assert not (tmp_path/'out'/'manifest.json').exists()


@pytest.mark.parametrize('name',FILES)
def test_one_file_profile_mismatch_rejected_after_reseal(upstream,tmp_path,monkeypatch,name):
    package,_=make_run(upstream,tmp_path,monkeypatch)
    document=read(package[0]/name)
    target=document['binding'] if name=='weights.json' else document
    target['model_profile_id']=OLD
    write(package[0]/name,document);reseal(package)
    from traffic_anomaly.candidate_ae_run_artifacts import CandidateAERunArtifactError
    with pytest.raises(CandidateAERunArtifactError): verify(package)


@pytest.mark.parametrize('kind',['new_id_old_config','old_id_new_config','new_id_old_shapes','float_count'])
def test_globally_resealed_profile_config_and_weight_mismatch(upstream,tmp_path,monkeypatch,kind):
    package,_=make_run(upstream,tmp_path,monkeypatch)
    for name in FILES:
        document=read(package[0]/name);target=document['binding'] if name=='weights.json' else document
        if kind=='new_id_old_config': target['configuration']=resolve_candidate_ae_configuration('current_ae')
        elif kind=='old_id_new_config': target['model_profile_id']=OLD
        elif kind=='float_count': target['configuration']['parameter_count']=492.
        elif name=='weights.json':
            for key,entry in document['parameters'].items():
                entry['shape']=[8 if value==14 else value for value in entry['shape']]
                entry['values']=[0.]*int(np.prod(entry['shape']))
        target['configuration_sha256']=hashlib.sha256(json.dumps(target['configuration'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        write(package[0]/name,document)
    reseal(package)
    from traffic_anomaly.candidate_ae_run_artifacts import CandidateAERunArtifactError
    with pytest.raises(CandidateAERunArtifactError): verify(package)


def test_new_verifier_actual_child_import_guard_no_model_or_rebuild(upstream,tmp_path,monkeypatch):
    package,_=make_run(upstream,tmp_path,monkeypatch)
    before={p:(p.read_bytes(),p.stat().st_mtime_ns) for d in package for p in d.iterdir()}
    script='''import builtins,sys,json
original=builtins.__import__
def guarded(name,*a,**k):
 assert name.split('.')[0] not in {'torch','sklearn','joblib'},name
 return original(name,*a,**k)
builtins.__import__=guarded
from traffic_anomaly import candidate_ae_weights as weights,candidate_autoencoder as ae
def blocked(*a,**k): raise AssertionError('model execution')
for name in ('build_candidate_ae_network','rebuild_candidate_ae_from_json'): setattr(weights,name,blocked)
for name in ('compute_synthetic_candidate_ae','replay_candidate_ae'): setattr(ae,name,blocked)
from traffic_anomaly.candidate_ae_run_artifacts import verify_candidate_ae_run
report=verify_candidate_ae_run(*sys.argv[1:4],source_fixture=sys.argv[4])
assert report['verifier_profile_id']=='c17-i1-g13u-ae-capacity-run-verifier-v1'
assert report['checks']['model_score_replay']=='NOT_CHECKED'
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
from traffic_anomaly.candidate_ae_verify_cli import main
arguments=['--run',sys.argv[1],'--records',sys.argv[2],'--inputs',sys.argv[3]]
out,err=StringIO(),StringIO()
with redirect_stdout(out),redirect_stderr(err):
 status=main(arguments+['--source-fixture',sys.argv[4]])
assert status==0 and err.getvalue()==''
assert json.loads(out.getvalue())['verifier_profile_id']=='c17-i1-g13u-ae-capacity-run-verifier-v1'
out,err=StringIO(),StringIO()
with redirect_stdout(out),redirect_stderr(err): status=main(arguments)
assert status==2 and out.getvalue()==''
assert json.loads(err.getvalue())=={'error':'SOURCE_REQUIRED'}
print(json.dumps({'status':report['status']}))
'''
    result=subprocess.run([sys.executable,'-X','utf8','-c',script,*map(str,package),str(SOURCE)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'status':'VERIFIED'}
    assert {p:(p.read_bytes(),p.stat().st_mtime_ns) for d in package for p in d.iterdir()}==before


def test_old_default_and_optional_source_keep_old_verifier(upstream,tmp_path,monkeypatch):
    package,_=make_run(upstream,tmp_path,monkeypatch,profile=OLD)
    report=verify(package,None)
    assert report['verifier_profile_id']=='c17-i1-g13u-ae-run-verifier-v1'
    assert report['model_profile_id']==OLD and report['checks']['source_replay']=='NOT_PROVIDED'


def test_classic_comparison_rejects_new_capacity_package(upstream,tmp_path,monkeypatch):
    package,_=make_run(upstream,tmp_path,monkeypatch)
    old,_=make_run(upstream,tmp_path,monkeypatch,profile=OLD,name='fabricated-old')
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun,compare_candidate_runs,CandidateComparisonError
    with pytest.raises(CandidateComparisonError):
        compare_candidate_runs([CandidateComparisonRun('autoencoder',package[0]),CandidateComparisonRun('autoencoder',old[0])],
                               *upstream,source_fixture=SOURCE)


@pytest.mark.parametrize('explicit',[False,True])
def test_cli_model_profile_default_and_explicit_forwarding(upstream,tmp_path,monkeypatch,capsys,explicit):
    from traffic_anomaly import candidate_ae_cli as m
    observed=[]
    def run(*a,**kwargs): observed.append(kwargs);return {'status':'COMPLETE'}
    monkeypatch.setattr(m,'run_synthetic_candidate_ae',run)
    arguments=['--records',str(upstream[0]),'--inputs',str(upstream[1]),'--source-fixture',str(SOURCE),
        '--run-id','toy','--output',str(tmp_path/'out'),'--method','current_ae']
    if explicit: arguments+=['--model-profile',NEW]
    assert m.main(arguments)==0
    assert observed[0]['model_profile_id']==(NEW if explicit else OLD)


@pytest.mark.parametrize('configuration',[[],None,np.zeros(3)])
def test_nonmapping_result_configuration_has_safe_model_result_error(upstream,tmp_path,monkeypatch,configuration):
    module,_=fixture_pipeline(monkeypatch)
    original=module.compute_synthetic_candidate_ae
    def changed(*a,**k):
        result=original(*a,**k);result.configuration=configuration;return result
    monkeypatch.setattr(module,'compute_synthetic_candidate_ae',changed)
    with pytest.raises(module._CLIError,match='INVALID_MODEL_RESULT'):
        module.run_synthetic_candidate_ae(*upstream,SOURCE,'toy',tmp_path/'out',method='current_ae',model_profile_id=NEW)
    assert not (tmp_path/'out'/'manifest.json').exists()


@pytest.mark.parametrize('change',['unverified','provenance','report'])
def test_new_verifier_independently_checks_fixed_source_binding(upstream,tmp_path,monkeypatch,change):
    package,_=make_run(upstream,tmp_path,monkeypatch)
    from traffic_anomaly import candidate_ae_run_artifacts as m
    snapshot=load_verified_candidate_artifacts(*upstream,source_fixture=SOURCE)
    report=snapshot.report_dict();provenance={key:dict(value) for key,value in snapshot.provenance.items()}
    if change=='unverified': report['checks']['source_replay']='NOT_PROVIDED'
    elif change=='provenance': provenance['source_fixture']['sha256']='0'*64
    else: report['source_fixture']['byte_count']=213497.
    monkeypatch.setattr(m,'load_verified_candidate_artifacts',lambda *a,**k:replace(snapshot,report=report,provenance=provenance))
    with pytest.raises(m.CandidateAERunArtifactError,match='FIXED_SOURCE_MISMATCH'): verify(package)


def test_new_verifier_all_payloads_read_once_no_extra_source_hash(upstream,tmp_path,monkeypatch):
    package,_=make_run(upstream,tmp_path,monkeypatch)
    expected={SOURCE.resolve(),*(path.resolve() for directory in package for path in directory.iterdir())}
    original=Path.open;counts=Counter()
    def track(path,*a,**k):
        if path.resolve() in expected: counts[path.resolve()]+=1
        return original(path,*a,**k)
    monkeypatch.setattr(Path,'open',track)
    assert verify(package)['status']=='VERIFIED'
    assert set(counts)==expected and all(value==1 for value in counts.values())


@pytest.mark.parametrize('extra',[['--model-profile','unknown'],['--model-profile',NEW,'--history-window','15']])
def test_cli_invalid_profile_combination_before_load(upstream,tmp_path,monkeypatch,capsys,extra):
    from traffic_anomaly import candidate_ae_cli as m
    monkeypatch.setattr(m,'load_verified_candidate_artifacts',lambda *a,**k:pytest.fail('loaded invalid request'))
    arguments=['--records',str(upstream[0]),'--inputs',str(upstream[1]),'--source-fixture',str(SOURCE),
        '--run-id','toy','--output',str(tmp_path/'out'),'--method','current_ae',*extra]
    assert m.main(arguments)==2
    assert json.loads(capsys.readouterr().err)['error'] in ('INVALID_ARGUMENTS','INVALID_METHOD_WINDOW')
    assert not (tmp_path/'out').exists()


def test_self_consistent_old_result_wrong_requested_method_rejected_before_versions(upstream,tmp_path,monkeypatch):
    module,_=fixture_pipeline(monkeypatch)
    original=module.compute_synthetic_candidate_ae
    def changed(*a,**k):
        result=original(*a,**k)
        result.configuration=resolve_candidate_ae_configuration('history_ae',15)
        return result
    monkeypatch.setattr(module,'compute_synthetic_candidate_ae',changed)
    monkeypatch.setattr(module,'_versions',lambda:pytest.fail('wrong request reached runtime declarations'))
    with pytest.raises(module._CLIError,match='INVALID_MODEL_RESULT'):
        module.run_synthetic_candidate_ae(*upstream,SOURCE,'toy',tmp_path/'out',method='current_ae')
    assert not (tmp_path/'out'/'manifest.json').exists()
