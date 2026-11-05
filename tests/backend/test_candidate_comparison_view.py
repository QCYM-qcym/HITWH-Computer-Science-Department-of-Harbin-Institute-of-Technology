"""Handbuilt consumer fixtures test binding, not model/source authentication."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from .test_candidate_app import pair, failure
from traffic_anomaly.candidate_artifacts import _deep_thaw
from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun
from traffic_anomaly.candidate_comparison import COMPARISON_PROFILE_ID, SLOT_ORDER
from traffic_anomaly.candidate_iforest import _configuration as if_config
from traffic_anomaly.candidate_autoencoder import _configuration as ae_config
from traffic_api.candidate_app import CandidateRegistration, CandidateRegistrationError, create_candidate_app

COUNTS = ('minute_count', 'score_valid_count', 'fit_count', 'calibration_count')
POP = ('calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes',
       'normal_minutes', 'attack_minutes', 'unknown_minutes', 'unknown_source_attack_present')
PROTOCOL = ('fit_scope', 'calibration_scope', 'quantile', 'quantile_method',
            'alarm_comparison', 'preprocessing_fit_provenance')


def fixture(slots=('if', 'current', 'h15', 'h30'), source=False):
    registrations, rows = [], []
    for slot in slots:
        run, inputs = pair(slot, source=source)
        r, s = run.report_dict(), run.scores_dict()
        config = if_config(1) if slot == 'if' else ae_config(r['method'], r['history_window'])
        r.update(fit_count=1, calibration_count=1, declared_library_versions={'python': 'test'},
            calibration=dict(sample_count=1, quantile=.99, method='linear', comparison='STRICT_GREATER',
                order_position_zero_based=0., strictly_above_count=0, equal_count=0))
        if slot != 'if': r['declared_runtime'] = {'device': 'cpu'}
        names = ('manifest.json', 'model-state.json', 'scores.json', 'evaluation.json',
                 'weights.bin' if slot == 'if' else 'weights.json')
        r['artifacts'] = {name: {'sha256': 'b'*64, 'byte_count': 300} for name in names}
        r['checks'].update(byte_integrity='VERIFIED', upstream_lineage='VERIFIED',
            stored_score_calibration='VERIFIED', strict_alarms='VERIFIED',
            model_deserialization='NOT_PERFORMED', model_score_replay='NOT_CHECKED')
        if slot != 'if': r['checks'].update(network_reconstruction='NOT_PERFORMED',
            training_execution='NOT_CHECKED', training_loss_replay='NOT_CHECKED', model_origin='NOT_AUTHENTICATED')
        s['configuration'] = config
        run = VerifiedCandidateRun(r, s)
        registrations.append(CandidateRegistration(run, inputs))
        rows.append(dict(slot=SLOT_ORDER[('if','current','h15','h30').index(slot)], run_id=r['run_id'],
            model_profile_id=r['model_profile_id'], verifier_profile_id=r['verifier_profile_id'],
            configuration=config, library_versions=r['declared_library_versions'], runtime=r.get('declared_runtime'),
            architecture=config.get('architecture'), parameter_count=config.get('parameter_count'),
            parameter_count_reason='NOT_DEFINED_FOR_OPAQUE_IF' if slot == 'if' else None,
            threshold=r['threshold'], calibration=r['calibration'], policies=r['policies'],
            actual_five_artifacts=r['artifacts'], verification_checks=r['checks'], verification_scope=r['scope']))
    rows.sort(key=lambda row: SLOT_ORDER.index(row['slot']))
    first, scores = registrations[0].run.report_dict(), registrations[0].run.scores_dict()
    shared = dict(selected_policy=first['selected_policy'], source_replay='VERIFIED' if source else 'NOT_PROVIDED',
        feature_names=scores['feature_names'], qualification_windows=scores['qualification_windows'],
        five_provenance=scores['provenance'], preprocessing_identity=scores['provenance']['preprocess'],
        preprocessing_state=scores['preprocessing_state'],
        qualification_protocol={k: scores['configuration'][k] for k in PROTOCOL},
        **{k:first[k] for k in COUNTS},
        test_denominators_by_policy={p:{k:first['policies'][p][k] for k in POP} for p in ('P_U','P_B','P_A')})
    report = dict(schema_version=1, comparison_profile_id=COMPARISON_PROFILE_ID, status='DATA_QUALIFICATION_ALIGNED',
        evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY', scope='SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY',
        included_slots=[s for s in SLOT_ORDER if any(row['slot']==s for row in rows)],
        missing_slots=[s for s in SLOT_ORDER if not any(row['slot']==s for row in rows)], shared_context=shared, runs=rows,
        limitations=dict(capacity_control='NOT_COMPARABLE', history_causal_attribution='NOT_COMPARABLE',
            cross_model_score_scale='NOT_COMPARABLE', ranking='NOT_PERFORMED', statistical_significance='NOT_PERFORMED',
            model_execution='NOT_CHECKED', model_origin='NOT_AUTHENTICATED', execution_controls='SHARED_DECLARATIONS_CONSISTENT_ONLY'))
    return report, registrations


def binder():
    name = 'traffic_api.candidate_comparison_view'
    assert importlib.util.find_spec(name) is not None, 'comparison snapshot binder is required'
    return importlib.import_module(name).freeze_candidate_comparison


@pytest.mark.parametrize('source', [False, True])
def test_bind_exact_report_and_freeze_aliases(source):
    report, regs = fixture(('h30', 'if'), source=source)
    expected = copy.deepcopy(report)
    value = binder()(report, regs)
    report['runs'][0]['threshold'] = 99
    report['shared_context']['source_replay'] = 'private'
    assert _deep_thaw(value) == expected
    with pytest.raises(TypeError): value['status'] = 'private'


@pytest.mark.parametrize('field', ['manifest.json', 'evaluation.json', 'scores.json', 'model-state.json', 'weights.bin'])
@pytest.mark.parametrize('identity', ['sha256', 'byte_count'])
def test_all_five_actual_identities_must_join(field, identity):
    report, regs = fixture()
    report['runs'][0]['actual_five_artifacts'][field][identity] = 'c'*64 if identity == 'sha256' else 301
    with pytest.raises(CandidateRegistrationError): binder()(report, regs)


@pytest.mark.parametrize('change', ['scope','profile','status','selected','source','population','counts','policies',
    'threshold','configuration','calibration','limitations','duplicate','missing','extra','checks','unknown_key','bool_schema'])
def test_inconsistent_report_is_rejected(change):
    report, regs = fixture()
    if change in ('scope','status'): report[change] = 'private'
    elif change == 'profile': report['comparison_profile_id'] = 'private'
    elif change == 'selected': report['shared_context']['selected_policy'] = 'P_A'
    elif change == 'source': report['shared_context']['source_replay'] = 'VERIFIED'
    elif change == 'population': report['shared_context']['test_denominators_by_policy']['P_U']['normal_minutes'] = 2
    elif change == 'counts': report['shared_context']['fit_count'] = 2
    elif change == 'policies': report['runs'][0]['policies']['P_U']['metrics']['precision'] = 0
    elif change in ('threshold','configuration','calibration'): report['runs'][0][change] = None
    elif change == 'limitations': report['limitations']['model_origin'] = 'VERIFIED'
    elif change == 'duplicate': report['runs'][1]['slot'] = report['runs'][0]['slot']
    elif change == 'missing': regs = regs[:-1]
    elif change == 'extra': report['runs'].pop()
    elif change == 'checks': report['runs'][0]['verification_checks']['model_score_replay'] = 'VERIFIED'
    elif change == 'unknown_key': report['private_path'] = 'secret'
    elif change == 'bool_schema': report['schema_version'] = True
    with pytest.raises(CandidateRegistrationError): binder()(report, regs)


def test_http_frozen_complete_report_and_no_request_io(monkeypatch):
    report, regs = fixture()
    expected = copy.deepcopy(report)
    app = create_candidate_app(regs, comparison=report)
    report.clear()
    def forbidden(*args, **kwargs): raise AssertionError('forbidden request work')
    import traffic_anomaly.candidate_comparison as core
    monkeypatch.setattr(core, 'compare_candidate_runs', forbidden)
    import traffic_api.candidate_comparison_view as view
    import traffic_anomaly.candidate_evaluation as evaluation
    monkeypatch.setattr(view, 'freeze_candidate_comparison', forbidden)
    monkeypatch.setattr(evaluation, 'evaluate_candidate_predictions', forbidden)
    for name in ('open', 'read_text', 'read_bytes'): monkeypatch.setattr(Path, name, forbidden)
    client = TestClient(app)
    assert client.get('/candidate/v1/runs').json()['comparison_available'] is True
    response = client.get('/candidate/v1/comparison')
    assert response.json() == expected
    assert response.content == (json.dumps(expected, ensure_ascii=False, allow_nan=False, separators=(',',':'))+'\n').encode()
    failure(client.get('/candidate/v1/comparison?page=1'), 422, 'INVALID_QUERY')
    failure(client.post('/candidate/v1/comparison'), 405, 'METHOD_NOT_ALLOWED')


def test_disabled_endpoint_and_response_limit_at_admission(monkeypatch):
    report, regs = fixture(('if','current'))
    client = TestClient(create_candidate_app(regs))
    assert client.get('/candidate/v1/runs').json()['comparison_available'] is False
    failure(client.get('/candidate/v1/comparison'), 404, 'COMPARISON_NOT_ENABLED')
    import traffic_api.candidate_app as app
    monkeypatch.setattr(app, 'MAX_OUTPUT_BYTES', 1)
    with pytest.raises(CandidateRegistrationError): create_candidate_app(regs, comparison=report)


def test_comparison_response_limit_is_exact_and_frozen_at_startup(monkeypatch):
    import traffic_api.candidate_app as app
    report, regs = fixture()
    payload = (json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(',',':'))+'\n').encode()
    monkeypatch.setattr(app, 'MAX_OUTPUT_BYTES', len(payload))
    client = TestClient(create_candidate_app(regs, comparison=report))
    monkeypatch.setattr(app, 'MAX_OUTPUT_BYTES', len(payload)-1)
    assert client.get('/candidate/v1/comparison').content == payload
    with pytest.raises(CandidateRegistrationError): create_candidate_app(regs, comparison=report)


@pytest.mark.parametrize('change', ['selected','source','counts','configuration','policy','same-slot'])
def test_snapshot_changes_are_rejected_instead_of_trusting_report(change):
    report, regs = fixture()
    index = 1
    r, s = regs[index].run.report_dict(), regs[index].run.scores_dict()
    if change == 'selected': r['selected_policy'] = s['selected_policy'] = 'P_A'
    elif change == 'source': r['checks']['source_replay'] = 'VERIFIED'
    elif change == 'counts': r['fit_count'] = 0
    elif change == 'configuration': s['configuration']['parameter_count'] = 509
    elif change == 'policy': r['policies']['P_U']['undefined_reasons']['precision'] = 'changed stored reason'
    elif change == 'same-slot': r, s = regs[0].run.report_dict(), regs[0].run.scores_dict(); r['run_id'] = s['run_id'] = 'second-if'
    regs[index] = CandidateRegistration(VerifiedCandidateRun(r,s), regs[index].inputs)
    with pytest.raises(CandidateRegistrationError): binder()(report, regs)


@pytest.mark.parametrize('change', ['nonfinite','score-threshold','calibration-shape','sample-bool','sample-count','position'])
def test_malformed_display_values_are_not_authenticated_by_matching_dictionaries(change):
    report, regs = fixture()
    r, s = regs[0].run.report_dict(), regs[0].run.scores_dict()
    row = report['runs'][0]
    if change == 'nonfinite': row['threshold'] = r['threshold'] = s['threshold'] = float('inf')
    elif change == 'score-threshold': s['threshold'] = .75
    elif change == 'calibration-shape': row['calibration'] = r['calibration'] = None
    else:
        key, value = {'sample-bool':('sample_count',True),'sample-count':('sample_count',2),
                      'position':('order_position_zero_based',5.)}[change]
        r['calibration'][key] = row['calibration'][key] = value
    regs[0] = CandidateRegistration(VerifiedCandidateRun(r,s), regs[0].inputs)
    with pytest.raises(CandidateRegistrationError): binder()(report, regs)

