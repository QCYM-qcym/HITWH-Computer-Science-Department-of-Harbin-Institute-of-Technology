"""Stored AE consistency, with adversarial resealing and explicit proof limits."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

SOURCE=Path(__file__).parents[1]/'fixtures/g13u-records-v1.json'
FILES=('manifest.json','model-state.json','scores.json','evaluation.json','weights.json')


def read(p):return json.loads(p.read_text('utf-8'))
def write(p,v):p.write_text(json.dumps(v,sort_keys=True,allow_nan=False)+'\n','utf-8')
def digest(p):
    data=p.read_bytes()
    return dict(sha256=hashlib.sha256(data).hexdigest(),byte_count=len(data))


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    # Setup is artificial execution, separate from the read-only verifier under test.
    from traffic_anomaly.candidate_record_cli import _run as records_run
    from traffic_anomaly.candidate_cli import _run as inputs_run
    from traffic_anomaly.candidate_ae_cli import run_synthetic_candidate_ae
    base=tmp_path_factory.mktemp('ae-run-verifier');records=base/'records';inputs=base/'inputs'
    records_run(SOURCE,'P_U',records);inputs_run(records/'minute-fixture.json',inputs)
    result={}
    for method,window in [('current_ae',None),('history_ae',15),('history_ae',30)]:
        run=base/f'run-{window}'
        run_synthetic_candidate_ae(records,inputs,SOURCE,f'toy-{window}',run,method=method,history_window=window)
        result[window]=(run,records,inputs)
    return result


@pytest.fixture
def package(originals,tmp_path):
    result=tuple(tmp_path/p.name for p in originals[None])
    for a,b in zip(originals[None],result):shutil.copytree(a,b)
    return result


def verify(package,source=SOURCE):
    from traffic_anomaly.candidate_ae_run_artifacts import verify_candidate_ae_run
    return verify_candidate_ae_run(*package,source_fixture=source)


def reject(package):
    from traffic_anomaly.candidate_ae_run_artifacts import CandidateAERunArtifactError
    with pytest.raises(CandidateAERunArtifactError) as caught:verify(package)
    assert str(caught.value)==caught.value.code
    assert all(str(p) not in str(caught.value) for p in package)
    return caught.value.code


def reseal(package):
    run=package[0];state=read(run/'model-state.json');state['weights']=digest(run/'weights.json');write(run/'model-state.json',state)
    evaluation=read(run/'evaluation.json');evaluation['scores']=digest(run/'scores.json');write(run/'evaluation.json',evaluation)
    manifest=read(run/'manifest.json');manifest['artifacts']={n:digest(run/n) for n in FILES if n!='manifest.json'};write(run/'manifest.json',manifest)


def mutate(package,name,path,value):
    p=package[0]/name;data=read(p);target=data
    for key in path[:-1]:target=target[key]
    target[path[-1]]=value;write(p,data);reseal(package)


@pytest.mark.parametrize('window',[None,15,30])
def test_three_modes_readonly_and_model_proof_scope(originals,window):
    package=originals[window];paths=[SOURCE,*(p for d in package for p in d.iterdir())]
    before={p:(digest(p),p.stat().st_mtime_ns) for p in paths}
    report=verify(package)
    assert report['status']=='VERIFIED' and report['scope']=='STORED_ARTIFACT_CONSISTENCY_ONLY'
    assert report['history_window']==window and report['minute_count']==144 and report['score_valid_count']==24
    assert report['fit_count']==report['calibration_count']==6
    for name in ('model_score_replay','training_execution','training_loss_replay'):
        assert report['checks'][name]=='NOT_CHECKED'
    assert report['checks']['network_reconstruction']=='NOT_PERFORMED'
    assert report['checks']['model_origin']=='NOT_AUTHENTICATED'
    assert report['checks']['weights_json_structure']=='VERIFIED'
    assert report['checks']['library_versions']=='DECLARATION_CONSISTENT_ONLY'
    assert {p:(digest(p),p.stat().st_mtime_ns) for p in paths}==before
    assert all(str(p) not in json.dumps(report) for p in package)


@pytest.mark.parametrize('field,value',[
    ('scope','REAL_DATA'),('schema_version',True),('model_profile_id','other'),
    ('selected_policy','P_B'),('qualification_windows',[15.0,30]),('feature_names',['wrong']*13),
    ('value_space','raw'),('provenance',{}),('preprocessing_state',{}),
    ('run_id','../outside'),('run_id','x'*65),('runtime',{'device':'cpu','torch_num_threads':True,'torch_num_interop_threads':2}),
    ('runtime',{'device':'cuda','torch_num_threads':1,'torch_num_interop_threads':2}),
    ('library_versions',{'python':'3.14','numpy':'2','torch':'a'*65})])
def test_globally_consistent_wrong_binding_cannot_self_certify(package,field,value):
    for name in FILES:
        p=package[0]/name;document=read(p)
        target=document['binding'] if name=='weights.json' else document
        target[field]=value;write(p,document)
    reseal(package);reject(package)


@pytest.mark.parametrize('key,value',[('epochs',6),('input_width',26),('history_window',15),
    ('optimizer_cpu_guard','DISABLED'),('parameter_count',True),('quantile',.98)])
def test_globally_resealed_configuration_must_match_fixed_protocol(package,key,value):
    for name in FILES:
        p=package[0]/name;document=read(p);target=document['binding'] if name=='weights.json' else document
        target['configuration'][key]=value
        target['configuration_sha256']=hashlib.sha256(json.dumps(target['configuration'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        write(p,document)
    reseal(package);reject(package)


@pytest.mark.parametrize('name,path,value',[
    ('scores.json',['scores',0],0.),('scores.json',['alarms',0],False),
    ('scores.json',['current_reconstruction_mse',0],0.),('scores.json',['history_deviation_reconstruction_mse',0],0.),
    ('scores.json',['score_valid',30],1),('scores.json',['common_valid',30],False),
    ('scores.json',['current_reconstruction_mse',30],-1.),('scores.json',['scores',30],True),
    ('scores.json',['history_deviation_reconstruction_mse',30],0.),
    ('scores.json',['history_deviation_reconstruction_mse_status'],'APPLICABLE'),
    ('scores.json',['threshold'],0.),('scores.json',['calibration','quantile'],.98),
    ('scores.json',['partitions',30],'test'),('scores.json',['timestamps',30],'2099-01-01T00:00:00.000000'),
    ('scores.json',['history_invalid_reason','15',0],None),
    ('model-state.json',['fit_indices',0],True),('model-state.json',['calibration_indices',0],30),
    ('model-state.json',['training_losses',0],False),('manifest.json',['training_losses',0],-1.),
    ('evaluation.json',['evaluation','policies','P_U','normal_minutes'],5),
    ('evaluation.json',['evaluation','policies','P_U','metrics','precision'],0.),
    ('weights.json',['parameters','0.bias','shape'],[8.0]),
    ('weights.json',['parameters','0.bias','values',0],.1),
    ('weights.json',['parameters','0.bias','values',0],True),
    ('weights.json',['parameters','0.bias','dtype'],'float64'),
])
def test_semantic_corruption_rejected_after_every_digest_is_resealed(package,name,path,value):
    mutate(package,name,path,value);reject(package)


def test_history_channels_use_asymmetric_exact_half_weight(originals,tmp_path):
    package=tuple(tmp_path/p.name for p in originals[15])
    for a,b in zip(originals[15],package):shutil.copytree(a,b)
    _forge_predictions(package,1.,3.)
    assert verify(package)['threshold']==2.
    mutate(package,'scores.json',['history_deviation_reconstruction_mse',30],4.)
    reject(package)


def _forge_predictions(package,current,history):
    # Deliberately unrelated to saved model: only stored arithmetic is being certified.
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
    from traffic_anomaly.candidate_evaluation import evaluate_candidate_predictions
    snap=load_verified_candidate_artifacts(package[1],package[2],source_fixture=SOURCE)
    p=package[0]/'scores.json';d=read(p)
    score=current if history is None else .5*current+.5*history
    for name,val in [('scores',score),('current_reconstruction_mse',current),('history_deviation_reconstruction_mse',history)]:
        d[name]=[val if valid else None for valid in snap.common_valid]
    d['threshold']=float(score);d['alarms']=[False if valid else None for valid in snap.common_valid]
    d['calibration'].update(strictly_above_count=0,equal_count=6);write(p,d)
    p=package[0]/'evaluation.json';e=read(p);e['threshold']=d['threshold'];e['calibration']=d['calibration']
    e['evaluation']=evaluate_candidate_predictions(labels=snap.labels,partitions=snap.partitions,
        score_valid=snap.common_valid,alarms=np.zeros(144,bool),source_attack_label_present=snap.source_attack_label_present,
        score_origin_policy=snap.report['selected_policy']);write(p,e);reseal(package)


def test_coherent_fabricated_predictions_and_valid_weights_are_not_model_authentication(package):
    _forge_predictions(package,0.,None)
    mutate(package,'weights.json',['parameters','0.bias','values',0],.5)
    report=verify(package)
    assert report['threshold']==0. and report['checks']['model_score_replay']=='NOT_CHECKED'
    assert report['checks']['model_origin']=='NOT_AUTHENTICATED'


def test_declared_versions_threads_and_losses_do_not_prove_runtime(package):
    for name in FILES:
        p=package[0]/name;d=read(p);target=d['binding'] if name=='weights.json' else d
        target['library_versions']={'python':'0.0','numpy':'0.0','torch':'0.0'}
        target['runtime']={'device':'cpu','torch_num_threads':1,'torch_num_interop_threads':1}
        if name in ('manifest.json','model-state.json'):d['training_losses']=[1.]*5
        write(p,d)
    reseal(package);report=verify(package)
    assert report['declared_runtime']['torch_num_threads']==1
    assert report['checks']['training_loss_replay']=='NOT_CHECKED'


@pytest.mark.parametrize('name',FILES)
def test_duplicate_keys_in_complete_package_are_rejected(package,name):
    p=package[0]/name;p.write_text(p.read_text('utf-8').replace('"schema_version": 1','"schema_version": 1, "schema_version": 1',1),'utf-8')
    # Reseal would parse away duplicate keys in manifest/state, so refusal may include byte identity.
    reject(package)


def test_total_and_individual_limits_before_json_decode(package,monkeypatch):
    from traffic_anomaly import candidate_ae_run_artifacts as m
    monkeypatch.setattr(m,'MAX_TOTAL_BYTES',sum(p.stat().st_size for p in package[0].iterdir())-1)
    assert reject(package)=='RESOURCE_LIMIT'
    monkeypatch.setattr(m,'MAX_TOTAL_BYTES',32*1024*1024)
    monkeypatch.setattr(m,'MAX_WEIGHTS_BYTES',1)
    assert reject(package)=='RESOURCE_LIMIT'


def test_exact_files_and_ordinary_paths(package):
    (package[0]/'sidecar.json').write_text('{}','utf-8');reject(package)


def test_payload_read_once_and_no_model_actions(package,monkeypatch):
    from traffic_anomaly import candidate_autoencoder as ae,candidate_ae_weights as weights
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor
    def forbidden(*a,**kw):raise AssertionError('forbidden execution')
    for name in ('compute_synthetic_candidate_ae','replay_candidate_ae'):monkeypatch.setattr(ae,name,forbidden)
    for name in ('build_candidate_ae_network','rebuild_candidate_ae_from_json'):monkeypatch.setattr(weights,name,forbidden)
    monkeypatch.setattr(CandidatePreprocessor,'fit',forbidden)
    expected={SOURCE.resolve(),*(p.resolve() for d in package for p in d.iterdir())}
    counts=Counter();original=Path.open
    def track(path,*a,**kw):
        if path.resolve() in expected:counts[path.resolve()]+=1
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'open',track)
    assert verify(package)['status']=='VERIFIED'
    assert set(counts)==expected and all(v==1 for v in counts.values())
