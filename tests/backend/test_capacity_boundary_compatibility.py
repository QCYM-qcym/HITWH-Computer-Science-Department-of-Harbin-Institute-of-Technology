"""Classic transport boundaries after Task13; no files, training or calibration.

Hand-built two-row snapshots exercise consumer admission only. Their VERIFIED
declarations do not certify a source, saved package, training or model origin.
"""
import json
from unittest.mock import Mock

from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
import pytest

from traffic_anomaly import contracts
from traffic_anomaly.candidate_ae_profiles import (
    CAPACITY492_MODEL_PROFILE_ID, resolve_candidate_ae_configuration,
)
from traffic_anomaly.candidate_ae_run_artifacts import CAPACITY_VERIFIER_PROFILE_ID
from traffic_anomaly.candidate_details import CandidateDetailError, candidate_minute_detail
from traffic_anomaly.candidate_evaluation_view import (
    CandidateEvaluationViewError, candidate_evaluation_view,
)
from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun
from traffic_anomaly.candidate_series import CandidateSeriesError, candidate_series_page
from traffic_api import candidate_serve_cli
from traffic_api.candidate_app import (
    CandidateRegistration, CandidateRegistrationError, create_candidate_app,
)
from traffic_api.candidate_viewer import create_candidate_viewer_app

from .test_candidate_app import pair
from .test_candidate_comparison_view import fixture as classic_comparison_fixture


def capacity_pair():
    run, inputs = pair('current', run_id='hand-capacity492')
    report, scores = run.report_dict(), run.scores_dict()
    report['model_profile_id'] = scores['model_profile_id'] = CAPACITY492_MODEL_PROFILE_ID
    report['verifier_profile_id'] = CAPACITY_VERIFIER_PROFILE_ID
    scores['configuration'] = resolve_candidate_ae_configuration(
        'current_ae', None, model_profile_id=CAPACITY492_MODEL_PROFILE_ID,
    )
    return VerifiedCandidateRun(report, scores), inputs


@pytest.mark.parametrize('slot', ['if', 'current', 'h15', 'h30'])
def test_classic_consumers_still_accept_original_four_slots(slot):
    run, inputs = pair(slot)
    assert candidate_series_page(run)['run_id'] == run.report['run_id']
    assert candidate_evaluation_view(run)['run_id'] == run.report['run_id']
    assert candidate_minute_detail(run, inputs, '2026-01-01T00:30')['run_id'] == run.report['run_id']


@pytest.mark.parametrize('consumer,error', [
    ('series', CandidateSeriesError), ('evaluation', CandidateEvaluationViewError),
    ('detail', CandidateDetailError),
])
def test_new492_remains_outside_classic_read_consumers(consumer, error):
    run, inputs = capacity_pair()
    with pytest.raises(error) as caught:
        if consumer == 'series':
            candidate_series_page(run)
        elif consumer == 'evaluation':
            candidate_evaluation_view(run)
        else:
            candidate_minute_detail(run, inputs, '2026-01-01T00:30')
    assert caught.value.code in ('INCOMPATIBLE_SNAPSHOT', 'INCOMPATIBLE_SNAPSHOTS')


@pytest.mark.parametrize('factory', [create_candidate_app, create_candidate_viewer_app])
def test_new492_cannot_be_registered_to_classic_http_or_viewer(factory):
    with pytest.raises(CandidateRegistrationError, match='^INVALID_REGISTRATION$'):
        factory([CandidateRegistration(*capacity_pair())])


def test_classic_comparison_binder_does_not_accept_new_capacity_slot():
    from traffic_api.candidate_comparison_view import freeze_candidate_comparison
    report, registrations = classic_comparison_fixture(('current', 'h15'))
    freeze_candidate_comparison(report, registrations)
    registrations[0] = CandidateRegistration(*capacity_pair())
    with pytest.raises(CandidateRegistrationError, match='^INVALID_COMPARISON$'):
        freeze_candidate_comparison(report, registrations)


@pytest.mark.parametrize('path', [
    '/candidate/v1/capacity-comparison', '/candidate/capacity',
    '/candidate/capacity.mjs', '/api/v1/runs',
    '/candidate/v1/runs/handwritten-current/exports/scores',
    '/candidate/v1/release-audit',
])
def test_classic_http_has_no_capacity_production_export_or_release_audit_routes(path):
    app = create_candidate_app([CandidateRegistration(*pair('current'))])
    response = TestClient(app).get(path, follow_redirects=False)
    assert response.status_code == 404
    assert response.json() == {'error': 'NOT_FOUND'}


@pytest.mark.parametrize('option', ['--capacity-comparison', '--model-profile'])
def test_unstarted_capacity_launcher_options_reject_before_load_or_bind(option, monkeypatch, capsys):
    module = candidate_serve_cli
    loaders = []
    for name in ('load_verified_candidate_artifacts', 'load_verified_candidate_if_run',
                 'load_verified_candidate_ae_run', 'compare_candidate_runs'):
        call = Mock(side_effect=AssertionError('unexpected admission'))
        loaders.append(call)
        monkeypatch.setattr(module, name, call)
    listener = Mock(side_effect=AssertionError('unexpected socket'))
    monkeypatch.setattr(module.socket, 'socket', listener)
    args = ['--records', 'unused-records', '--inputs', 'unused-inputs', '--ae-run', 'unused-run', option]
    assert module.main(args) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': 'INVALID_ARGUMENTS'}
    assert all(call.call_count == 0 for call in [*loaders, listener])


def test_classic_launcher_rejects_admitted_new492_snapshot_before_socket(monkeypatch, capsys):
    run, inputs = capacity_pair()
    module = candidate_serve_cli
    monkeypatch.setattr(module, 'load_verified_candidate_artifacts', Mock(return_value=inputs))
    monkeypatch.setattr(module, 'load_verified_candidate_ae_run', Mock(return_value=run))
    listener = Mock(side_effect=AssertionError('new492 must not reach socket'))
    monkeypatch.setattr(module.socket, 'socket', listener)
    args = ['--records', 'unused-records', '--inputs', 'unused-inputs', '--ae-run', 'unused-run']
    assert module.main(args) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': 'INVALID_REGISTRATION'}
    listener.assert_not_called()


@pytest.mark.parametrize('extra', [
    {'model_profile_id': CAPACITY492_MODEL_PROFILE_ID}, {'capacity_comparison': True},
    {'architecture': [13, 14, 3, 14, 13]},
])
def test_production_task_request_has_no_implicit_capacity_parameters(extra):
    request = dict(dataset_id='synthetic-v1', split_id='split-v1', method='current_ae', config_id='smoke-v1')
    with pytest.raises(ValidationError):
        contracts.RunRequest.model_validate(request | extra)


@pytest.mark.parametrize('width,accepted', [(13, False), (26, False), (134, True)])
def test_production_detail_channel_width_remains_134(width, accepted):
    if accepted:
        assert len(TypeAdapter(contracts.Vector).validate_python([0.] * width)) == 134
    else:
        with pytest.raises(ValidationError):
            TypeAdapter(contracts.Vector).validate_python([0.] * width)


@pytest.mark.parametrize('method,width,accepted', [
    ('current_ae', 13, False), ('history_ae', 26, False),
    ('current_ae', 134, True), ('history_ae', 268, True),
])
def test_production_model_metadata_retains_134_268(method, width, accepted):
    value = dict(method=method, input_width=width, feature_names=[f'f{i}' for i in range(134)],
                 preprocess_version='log1p-standard-v1', threshold=0., parameter_count=0,
                 payload={'path': 'model/synthetic.json', 'sha256': 'a' * 64})
    if accepted:
        assert contracts.ModelMetadata.model_validate(value).input_width == width
    else:
        with pytest.raises(ValidationError):
            contracts.ModelMetadata.model_validate(value)
