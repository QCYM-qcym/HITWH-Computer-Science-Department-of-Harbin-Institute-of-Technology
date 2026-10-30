"""Isolated, read-only HTTP views over already checked synthetic snapshots.

Trusted local startup loads artifacts before registration. This module creates
no worker, database or model; it does not decide the server's bind address.
"""
from dataclasses import dataclass
import json
import re
from types import MappingProxyType

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from traffic_anomaly.candidate_artifacts import VerifiedCandidateArtifacts, _deep_freeze, _deep_thaw
from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun
from traffic_anomaly.candidate_details import CandidateDetailError, candidate_minute_detail
from traffic_anomaly.candidate_series import CandidateSeriesError, candidate_series_page
from traffic_anomaly.candidate_iforest import MODEL_PROFILE_ID as IF_PROFILE

MAX_OUTPUT_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class CandidateRegistration:
    run: VerifiedCandidateRun
    inputs: VerifiedCandidateArtifacts


class CandidateRegistrationError(ValueError):
    """The trusted startup collection is invalid; no partial app is served."""


class _RequestError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def _failure(status, code, *, headers=None):
    return Response((json.dumps({'error': code}, separators=(',', ':')) + '\n').encode('utf-8'),
                    status_code=status, media_type='application/json', headers=headers)


def _success(value):
    try:
        payload = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        return _failure(500, 'INTERNAL_ERROR')
    if len(payload) > MAX_OUTPUT_BYTES:
        return _failure(500, 'RESOURCE_LIMIT')
    return Response(payload, media_type='application/json')


def _query(request, allowed):
    values = {}
    for key, value in request.query_params.multi_items():
        if key not in allowed or key in values:
            raise _RequestError(422, 'INVALID_QUERY')
        values[key] = value
    return values


def _integer(value):
    if not re.fullmatch('[0-9]+', value, flags=re.ASCII):
        raise _RequestError(422, 'INVALID_QUERY')
    try:
        return int(value)
    except ValueError:
        raise _RequestError(422, 'INVALID_QUERY') from None


def create_candidate_app(registrations):
    """Admit 1–4 loader-produced pairs, then serve a fixed synthetic catalog.

    Shape checks do not authenticate directly constructed snapshots. Callers
    must use existing safe loaders and bind the resulting app to loopback only.
    """
    if type(registrations) not in (list, tuple) or not 1 <= len(registrations) <= 4:
        raise CandidateRegistrationError('INVALID_REGISTRATION')
    accepted, items = {}, []
    try:
        for registration in registrations:
            if (not isinstance(registration, CandidateRegistration)
                    or not isinstance(registration.run, VerifiedCandidateRun)
                    or not isinstance(registration.inputs, VerifiedCandidateArtifacts)):
                raise ValueError
            run, inputs = registration.run, registration.inputs
            candidate_series_page(run, page=1, page_size=1)
            detail = candidate_minute_detail(run, inputs, run.scores_document['timestamps'][0])
            report = run.report
            run_id = report['run_id']
            if run_id in accepted:
                raise ValueError
            accepted[run_id] = registration
            is_if = report['model_profile_id'] == IF_PROFILE
            method = 'iforest' if is_if else report['method']
            window = None if is_if else report['history_window']
            if not is_if and (method not in ('current_ae', 'history_ae')
                    or (method == 'current_ae' and window is not None)
                    or (method == 'history_ae' and (type(window) is not int or window not in (15, 30)))):
                raise ValueError
            items.append(dict(run_id=run_id, model_profile_id=report['model_profile_id'],
                method=method, history_window=window,
                selected_policy=report['selected_policy'], minute_count=report['minute_count'],
                score_valid_count=report['score_valid_count'], source_replay=detail['source_replay']))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError):
        raise CandidateRegistrationError('INVALID_REGISTRATION') from None
    registry = MappingProxyType(accepted)
    catalog = _deep_freeze(dict(schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        scope='SYNTHETIC_SAVED_RUN_INSPECTION_ONLY', items=items))
    app = FastAPI(title='Synthetic candidate saved-run inspection', debug=False,
                  openapi_url=None, docs_url=None, redoc_url=None, redirect_slashes=False)

    @app.exception_handler(_RequestError)
    async def request_error(request, exc):
        return _failure(exc.status, exc.code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return _failure(422, 'INVALID_QUERY')

    async def query_error(request, exc):
        if exc.code == 'INVALID_QUERY':
            return _failure(422, 'INVALID_QUERY')
        if exc.code == 'MINUTE_NOT_FOUND':
            return _failure(404, 'MINUTE_NOT_FOUND')
        return _failure(500, 'INTERNAL_ERROR')

    app.add_exception_handler(CandidateDetailError, query_error)
    app.add_exception_handler(CandidateSeriesError, query_error)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if exc.status_code == 404:
            return _failure(404, 'NOT_FOUND')
        if exc.status_code == 405:
            return _failure(405, 'METHOD_NOT_ALLOWED', headers={'Allow': 'GET'})
        return _failure(500, 'INTERNAL_ERROR')

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return _failure(500, 'INTERNAL_ERROR')

    def registered(run_id):
        if run_id not in registry:
            raise _RequestError(404, 'RUN_NOT_FOUND')
        return registry[run_id]

    @app.get('/candidate/v1/runs')
    def runs(request: Request):
        _query(request, set())
        return _success(_deep_thaw(catalog))

    @app.get('/candidate/v1/runs/{run_id}/series')
    def series(run_id: str, request: Request):
        registration = registered(run_id)
        query = _query(request, {'start', 'end', 'page', 'page_size'})
        return _success(candidate_series_page(registration.run, start=query.get('start'), end=query.get('end'),
            page=_integer(query.get('page', '1')), page_size=_integer(query.get('page_size', '100'))))

    @app.get('/candidate/v1/runs/{run_id}/detail')
    def detail(run_id: str, request: Request):
        registration = registered(run_id)
        query = _query(request, {'timestamp'})
        if 'timestamp' not in query:
            raise _RequestError(422, 'INVALID_QUERY')
        return _success(candidate_minute_detail(registration.run, registration.inputs, query['timestamp']))

    return app
