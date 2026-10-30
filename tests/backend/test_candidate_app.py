"""Transport tests use hand-written consumer snapshots, never model training.

The two-row values exercise consumer shapes, not artifact/source certification.
"""
from dataclasses import FrozenInstanceError, replace
import importlib
import importlib.util
import json
from pathlib import Path
from types import MappingProxyType

from fastapi.testclient import TestClient
import numpy as np
import pytest

from traffic_anomaly.candidate_artifacts import (
    VerifiedCandidateArtifacts, VerifiedCandidateHistory, _array_mapping, _deep_freeze,
    VERIFIER_PROFILE_ID as INPUT_VERIFIER,
)
from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun


def api():
    name = 'traffic_api.candidate_app'
    assert importlib.util.find_spec(name) is not None, 'isolated candidate HTTP factory is required'
    return importlib.import_module(name)


def pair(slot='if', run_id=None, source=True):
    from traffic_anomaly.candidate_iforest import MODEL_PROFILE_ID as IF_PROFILE
    from traffic_anomaly.candidate_autoencoder import MODEL_PROFILE_ID as AE_PROFILE
    from traffic_anomaly.candidate_run_artifacts import VERIFIER_PROFILE_ID as IF_VERIFIER
    from traffic_anomaly.candidate_ae_run_artifacts import VERIFIER_PROFILE_ID as AE_VERIFIER
    from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
    proof = 'VERIFIED' if source else 'NOT_PROVIDED'
    stamps = ['2026-01-01T00:00:00.000000', '2026-01-01T00:30:00.000000']
    current, common = np.zeros((2,13)), np.array([False, True])
    residual = np.array([[np.nan]*13, [0.]*13])
    provenance = {key: {'sha256': 'a'*64, 'byte_count': 1} for key in
        ('record_manifest','input_manifest','source_fixture','minute_fixture','preprocess')}
    state = {'handwritten': True}
    arrays = _array_mapping(dict(timestamps=np.array(stamps, dtype='datetime64[us]'),
        segment_ids=np.array(['synthetic']*2), partitions=np.array(['train']*2),
        row_valid=np.ones(2, dtype=bool), raw_valid=np.ones(2, dtype=bool), common_valid=common,
        raw_values=current+1, current_values=current, source_attack_label_present=np.zeros(2, dtype=bool)))
    histories = {h: VerifiedCandidateHistory(_array_mapping(dict(residual=residual, valid=common)),
        ('warmup',None)) for h in (15,30)}
    input_report = dict(schema_version=1, status='VERIFIED', evidence_kind='SYNTHETIC_ONLY',
        policy_status='AUDIT_ONLY', time_basis='synthetic_source_clock',
        scope='synthetic_internal_consistency_not_source_authentication_or_research_validation',
        verifier_profile_id=INPUT_VERIFIER, selected_policy='P_U', minute_count=2,
        windows=[15,30], dimensions={'current':13,'joined':26}, checks={'source_replay':proof})
    inputs = VerifiedCandidateArtifacts(_deep_freeze(input_report), _deep_freeze(provenance),
        _deep_freeze(state), arrays, MappingProxyType(histories),
        _deep_freeze({p:['normal']*2 for p in ('P_U','P_B','P_A')}), _array_mapping({}))
    shared = dict(schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        run_id=run_id or 'handwritten-'+slot, selected_policy='P_U',
        model_profile_id=IF_PROFILE if slot=='if' else AE_PROFILE)
    report = dict(shared, status='VERIFIED', scope='STORED_ARTIFACT_CONSISTENCY_ONLY',
        verifier_profile_id=IF_VERIFIER if slot=='if' else AE_VERIFIER,
        minute_count=2, score_valid_count=1, threshold=.5, checks={'source_replay':proof},
        artifacts={'evaluation.json':{'sha256':'b'*64,'byte_count':300}})
    scores = dict(shared, scope='ENGINEERING_TOY_ONLY', time_basis='synthetic_source_clock',
        score_direction='HIGHER_IS_MORE_ANOMALOUS', provenance=provenance, preprocessing_state=state,
        feature_names=list(G13U_FEATURE_NAMES), value_space='prepared', qualification_windows=[15,30],
        timestamps=stamps, segment_ids=['synthetic']*2, partitions=['train']*2,
        current_input_valid=[True]*2, common_valid=[False,True], score_valid=[False,True],
        scores=[None,.4], alarms=[None,False], threshold=.5,
        history_invalid_reason={'15':['warmup',None],'30':['warmup',None]})
    if slot!='if':
        window = None if slot=='current' else int(slot.removeprefix('h'))
        method = 'current_ae' if window is None else 'history_ae'
        report.update(method=method,history_window=window)
        scores.update(configuration={'method':method,'history_window':window},
            current_reconstruction_mse=[None,.4],
            history_deviation_reconstruction_mse=[None,None if window is None else .4],
            history_deviation_reconstruction_mse_status='NOT_APPLICABLE' if window is None else 'APPLICABLE')
    return VerifiedCandidateRun(report,scores), inputs


def build(*pairs):
    module=api()
    return module.create_candidate_app([module.CandidateRegistration(*value) for value in (pairs or [pair()])])


def failure(response,status,code):
    assert response.status_code==status
    assert response.json()=={'error':code}
    assert all(text not in response.text for text in ('private','Traceback','RuntimeWarning'))
    assert 'location' not in response.headers


def test_catalog_fixed_allowlist_all_slots_and_no_paths():
    pairs=[pair(slot) for slot in ('if','current','h15','h30')]
    result=TestClient(build(*pairs)).get('/candidate/v1/runs')
    assert result.status_code==200
    expected=[]
    for (run,inputs),slot in zip(pairs,('if','current','h15','h30')):
        expected.append(dict(run_id=run.report['run_id'],model_profile_id=run.report['model_profile_id'],
            method='iforest' if slot=='if' else run.report['method'],
            history_window=None if slot=='if' else run.report['history_window'], selected_policy='P_U',
            minute_count=2,score_valid_count=1,source_replay=dict(run='VERIFIED',inputs='VERIFIED',combined='VERIFIED')))
    assert result.json()==dict(schema_version=1,evidence_kind='SYNTHETIC_ONLY',policy_status='AUDIT_ONLY',
        scope='SYNTHETIC_SAVED_RUN_INSPECTION_ONLY',items=expected)


def test_registration_wrapper_and_collection_are_frozen():
    module=api(); registration=module.CandidateRegistration(*pair())
    with pytest.raises(FrozenInstanceError): registration.run=None
    assert not hasattr(registration,'__dict__')
    registrations=[registration]; app=module.create_candidate_app(registrations)
    registrations.clear(); registrations.append(module.CandidateRegistration(*pair('h15')))
    client=TestClient(app)
    assert [item['run_id'] for item in client.get('/candidate/v1/runs').json()['items']]==['handwritten-if']
    failure(client.get('/candidate/v1/runs/handwritten-h15/series'),404,'RUN_NOT_FOUND')


@pytest.mark.parametrize('kind',['empty','too_many','generator','mapping','none','wrong_item','wrong_run','wrong_inputs','duplicate'])
def test_invalid_registration_shape_is_rejected_safely(kind):
    module=api(); registration=module.CandidateRegistration(*pair())
    values={'empty':[],'too_many':[registration]*5,'generator':iter([registration]),'mapping':{},
        'none':None,'wrong_item':[object()],'wrong_run':[module.CandidateRegistration(None,registration.inputs)],
        'wrong_inputs':[module.CandidateRegistration(registration.run,None)],'duplicate':[registration]*2}
    with pytest.raises(module.CandidateRegistrationError,match='^INVALID_REGISTRATION$'):
        module.create_candidate_app(values[kind])


@pytest.mark.parametrize('field,value',[('evidence_kind','private-real'),('selected_policy','P_A'),
    ('scope','private-production'),('minute_count',3)])
def test_registration_pair_incompatibility_is_rejected(field,value):
    module=api(); run,inputs=pair(); report=inputs.report_dict(); report[field]=value
    inputs=replace(inputs,report=_deep_freeze(report))
    with pytest.raises(module.CandidateRegistrationError,match='^INVALID_REGISTRATION$'):
        module.create_candidate_app([module.CandidateRegistration(run,inputs)])


def test_tuple_registration_and_weaker_source_proof():
    module=api();run,inputs=pair(); report=inputs.report_dict();report['checks']['source_replay']='NOT_PROVIDED'
    inputs=replace(inputs,report=_deep_freeze(report))
    app=module.create_candidate_app((module.CandidateRegistration(run,inputs),))
    item=TestClient(app).get('/candidate/v1/runs').json()['items'][0]
    assert item['source_replay']==dict(run='VERIFIED',inputs='NOT_PROVIDED',combined='NOT_PROVIDED')


@pytest.mark.parametrize('slot,window',[('current',15),('current',False),
    ('h15',True),('h15',False),('h15','15'),('h15',{'private-path':'not-a-window'}),
    ('h15',14),('h15',31),('h15',None)])
def test_catalog_history_window_requires_exact_applicable_enum(slot,window):
    module=api();run,inputs=pair(slot)
    report,scores=run.report_dict(),run.scores_dict()
    report['history_window']=window
    scores['configuration']['history_window']=window
    altered=VerifiedCandidateRun(report,scores)
    with pytest.raises(module.CandidateRegistrationError,match='^INVALID_REGISTRATION$'):
        module.create_candidate_app([module.CandidateRegistration(altered,inputs)])


@pytest.mark.parametrize('slot',['if','current','h15','h30'])
def test_http_matches_pure_series_and_details_including_nulls(slot):
    from traffic_anomaly.candidate_details import candidate_minute_detail
    from traffic_anomaly.candidate_series import candidate_series_page
    run,inputs=pair(slot); client=TestClient(build((run,inputs)));base='/candidate/v1/runs/'+run.report['run_id']
    for params in ({},{'page':'2','page_size':'1'},{'page':'5'}, {'start':'2026-01-01T00:00','end':'2026-01-01T00:30'}):
        expected=candidate_series_page(run,**{k:int(v) if k in ('page','page_size') else v for k,v in params.items()})
        response=client.get(base+'/series',params=params)
        assert response.status_code==200 and response.json()==expected
    for timestamp in ('2026-01-01T00:00','2026-01-01T00:30'):
        response=client.get(base+'/detail',params={'timestamp':timestamp})
        assert response.status_code==200 and response.json()==candidate_minute_detail(run,inputs,timestamp)


@pytest.mark.parametrize('path', ['/docs','/redoc','/openapi.json','/docs/oauth2-redirect','/api/v1/runs',
    '/candidate/v1/runs/','/candidate/v1/runs/handwritten-if/series/','/private-unknown'])
def test_automatic_and_production_routes_are_disabled(path):
    failure(TestClient(build()).get(path,follow_redirects=False),404,'NOT_FOUND')


@pytest.mark.parametrize('method',['POST','PUT','DELETE','PATCH','OPTIONS'])
def test_no_write_routes_and_safe_allow_header(method):
    response=TestClient(build()).request(method,'/candidate/v1/runs',json={'path':'private-secret'})
    failure(response,405,'METHOD_NOT_ALLOWED')
    assert response.headers['allow']=='GET'


@pytest.mark.parametrize('suffix', ['', '/series', '/detail?timestamp=2026-01-01T00:00'])
def test_unknown_ids_and_routes(suffix):
    response=TestClient(build()).get('/candidate/v1/runs/private-missing'+suffix)
    failure(response,404,'NOT_FOUND' if suffix=='' else 'RUN_NOT_FOUND')


@pytest.mark.parametrize('route,query', [('runs','path=private-secret'),('runs','page=1'),
    ('series','file=private-secret'),('series','page=1&page=2'),('series','page=1&%70age=2'),
    ('series','start=a&start=b'),('series','page=-1'),('series','page=%2B1'),('series','page=1.0'),
    ('series','page=True'),('series','page='),('series','page=%EF%BC%91'),('series','page=0'),
    ('series','page_size=1001'),('series','page_size=0'),('series','start=2026-01-01T24:00'),
    ('series','end=2026-01-01T00:30Z'),('detail',''),('detail','timestamp=2026-01-01T00:00&path=private-secret'),
    ('detail','timestamp=2026-01-01T00:00&timestamp=2026-01-01T00:30'),('detail','timestamp=private-invalid')])
def test_strict_decoded_query_keys_and_values(route,query):
    path='/candidate/v1/runs'+('' if route=='runs' else '/handwritten-if/'+route)
    failure(TestClient(build()).get(path+'?'+query),422,'INVALID_QUERY')


def test_absent_minute_and_positive_ascii_paging():
    client=TestClient(build());base='/candidate/v1/runs/handwritten-if'
    failure(client.get(base+'/detail?timestamp=2026-01-01T00:01'),404,'MINUTE_NOT_FOUND')
    result=client.get(base+'/series?page=0002&page_size=01')
    assert result.status_code==200 and result.json()['page']==2 and result.json()['returned']==1


@pytest.mark.parametrize('route',['runs','series','detail'])
def test_success_is_exact_utf8_json_lf_and_capped(route,monkeypatch):
    module=api();client=TestClient(build())
    path='/candidate/v1/runs'+('' if route=='runs' else '/handwritten-if/'+route)
    if route=='detail':path+='?timestamp=2026-01-01T00:00'
    response=client.get(path)
    payload=(json.dumps(response.json(),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')
    assert response.content==payload and int(response.headers['content-length'])==len(payload)
    assert response.headers['content-type']=='application/json'
    assert module.MAX_OUTPUT_BYTES==1024*1024
    monkeypatch.setattr(module,'MAX_OUTPUT_BYTES',len(payload))
    assert client.get(path).content==payload
    monkeypatch.setattr(module,'MAX_OUTPUT_BYTES',len(payload)-1)
    failure(client.get(path),500,'RESOURCE_LIMIT')


@pytest.mark.parametrize('value',[float('nan'),float('inf'),{1},'\ud800'])
def test_nonserializable_results_never_send_partial_success(value,monkeypatch):
    module=api();client=TestClient(build())
    monkeypatch.setattr(module,'candidate_series_page',lambda *a,**k: {'private':value})
    failure(client.get('/candidate/v1/runs/handwritten-if/series'),500,'INTERNAL_ERROR')


def test_real_500_response_does_not_leak_exception_or_headers(monkeypatch):
    module=api();client=TestClient(build(),raise_server_exceptions=False)
    def failed(*args,**kwargs): raise RuntimeError('private-path / traceback detail')
    monkeypatch.setattr(module,'candidate_series_page',failed)
    failure(client.get('/candidate/v1/runs/handwritten-if/series'),500,'INTERNAL_ERROR')


def test_incompatible_query_snapshot_failure_is_internal(monkeypatch):
    from traffic_anomaly.candidate_series import CandidateSeriesError
    module=api();client=TestClient(build())
    def failed(*args,**kwargs):raise CandidateSeriesError('INCOMPATIBLE_SNAPSHOT')
    monkeypatch.setattr(module,'candidate_series_page',failed)
    failure(client.get('/candidate/v1/runs/handwritten-if/series'),500,'INTERNAL_ERROR')


def test_request_phase_has_no_file_model_loader_or_worker_operations(monkeypatch):
    module=api();client=TestClient(build());base='/candidate/v1/runs/handwritten-if'
    from traffic_anomaly import candidate_artifacts, candidate_run_artifacts, candidate_ae_run_artifacts
    from traffic_anomaly import candidate_iforest, candidate_autoencoder, candidate_inputs, candidate_evaluation
    from traffic_api import worker, repository
    def forbidden(*args,**kwargs):raise AssertionError('private-forbidden operation')
    for obj,names in [(candidate_artifacts,('load_verified_candidate_artifacts',)),
        (candidate_run_artifacts,('load_verified_candidate_if_run','calibrate_candidate_scores','evaluate_candidate_predictions')),
        (candidate_ae_run_artifacts,('load_verified_candidate_ae_run','_calibrate','evaluate_candidate_predictions')),
        (candidate_iforest,('compute_synthetic_candidate_if',)),
        (candidate_autoencoder,('compute_synthetic_candidate_ae','replay_candidate_ae')),
        (candidate_inputs,('prepare_candidate_inputs',)),(candidate_inputs.CandidatePreprocessor,('fit',)),
        (candidate_evaluation,('evaluate_candidate_predictions',)),(worker.Worker,('__init__',)),
        (repository.Repository,('__init__',)),(Path,('open','read_bytes','read_text','write_bytes','write_text','mkdir'))]:
        for name in names:monkeypatch.setattr(obj,name,forbidden)
    for path in ('/candidate/v1/runs',base+'/series',base+'/detail?timestamp=2026-01-01T00:00'):
        response=client.get(path)
        assert response.status_code==200
        value=response.json();value.clear()
        assert client.get(path).json()
