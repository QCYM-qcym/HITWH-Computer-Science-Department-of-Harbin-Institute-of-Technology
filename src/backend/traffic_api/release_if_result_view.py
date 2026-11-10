"""Freeze two internally checked saved IF results before any listener binds."""
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
from importlib import resources
import json
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from traffic_anomaly import release_if_result_contract as contract


_PROFILE = 'c17-release-iforest-view-v1'
_SCOPE = 'SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY'
_SUMMARY_LIMIT = 16384
_SERIES_LIMIT = 131072
_ASSET_LIMIT = 65536
_TOTAL_LIMIT = 16777216
_ASSETS = (('/release/results', 'results.html', 'text/html'),
           ('/release/results/results.mjs', 'results.mjs', 'text/javascript'),
           ('/release/results/results.css', 'results.css', 'text/css'))
_HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
_CSP = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
_ERRORS = {code: ('{"error":"'+code+'"}\n').encode('ascii') for code in
           ('NOT_FOUND', 'METHOD_NOT_ALLOWED', 'INVALID_QUERY', 'VIEW_UNAVAILABLE')}


class ReleaseIFResultViewError(ValueError):
    """Only fixed safe codes cross the startup boundary."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in (
            'INVALID_VIEW_ARGUMENTS', 'INCOMPATIBLE_RESULT_PAIR', 'RESOURCE_LIMIT', 'VIEW_UNAVAILABLE') else 'VIEW_UNAVAILABLE'
        super().__init__(self.code)


class _InvalidQuery(Exception):
    pass


def _json_bytes(value, limit):
    result = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
    for chunk in encoder.iterencode(value):
        encoded = chunk.encode('utf-8')
        if len(result) + len(encoded) + 1 > limit:
            raise ReleaseIFResultViewError('RESOURCE_LIMIT')
        result.extend(encoded)
    result.extend(b'\n')
    return bytes(result)


def _read_assets():
    values = []
    try:
        root = resources.files('traffic_api').joinpath('release_if_static')
        for path, name, media_type in _ASSETS:
            with root.joinpath(name).open('rb') as stream:
                payload = stream.read(_ASSET_LIMIT + 1)
            if type(payload) is not bytes or not payload:
                raise ReleaseIFResultViewError('VIEW_UNAVAILABLE')
            if len(payload) > _ASSET_LIMIT:
                raise ReleaseIFResultViewError('RESOURCE_LIMIT')
            payload.decode('utf-8')
            values.append((path, payload, media_type))
    except ReleaseIFResultViewError:
        raise
    except Exception:
        raise ReleaseIFResultViewError('VIEW_UNAVAILABLE') from None
    return tuple(values)


def _axis(context):
    rows = []
    for segment in context.segments:
        current = segment.start
        while current < segment.end:
            rows.append((current, current.isoformat(timespec='seconds'), segment.id, segment.role))
            current += timedelta(minutes=1)
    return tuple(rows)


def _admit(current, h30):
    for package in (current, h30):
        try:
            contract.encode_release_if_result_package(package)
        except contract.ReleaseIFResultPackageError as exc:
            code = 'RESOURCE_LIMIT' if exc.code == 'RESOURCE_LIMIT' else 'INCOMPATIBLE_RESULT_PAIR'
            raise ReleaseIFResultViewError(code) from None
    a, b = current.context, h30.context
    if a.view != 'current13' or b.view != 'h30_26':
        raise ReleaseIFResultViewError('INCOMPATIBLE_RESULT_PAIR')
    fields = ('raw_identity', 'prepared_identity', 'configuration_sha256', 'source_schema_id',
              'source_authentication', 'time_basis', 'policy_status', 'audit_fit_policy', 'minute_count', 'segments')
    if any(getattr(a, field) != getattr(b, field) for field in fields):
        raise ReleaseIFResultViewError('INCOMPATIBLE_RESULT_PAIR')
    for field in ('scored_mask', 'train_indices', 'calibration_indices', 'preprocessing_fit_indices'):
        if getattr(current.result, field) != getattr(h30.result, field):
            raise ReleaseIFResultViewError('INCOMPATIBLE_RESULT_PAIR')
    axis = _axis(a)
    if axis != _axis(b):
        raise ReleaseIFResultViewError('INCOMPATIBLE_RESULT_PAIR')
    return axis


def _freeze(current, h30):
    axis = _admit(current, h30)
    c, r = current.context, current.result
    n = c.minute_count
    references = dict(current13=asdict(current.identity), h30_26=asdict(h30.identity))
    snapshot = sha256(_json_bytes(dict(profile_id=_PROFILE, **references), _SUMMARY_LIMIT)).hexdigest()
    envelope = dict(version=1, profile_id=_PROFILE, scope=_SCOPE, snapshot_sha256=snapshot)
    segments = []
    offset = 0
    for ordinal, segment in enumerate(c.segments):
        count = (segment.end - segment.start) // timedelta(minutes=1)
        segments.append(dict(ordinal=ordinal, id=segment.id, role=segment.role,
                             start=segment.start.isoformat(timespec='seconds'),
                             end=segment.end.isoformat(timespec='seconds'), minute_count=count,
                             scored_count=sum(r.scored_mask[offset:offset+count])))
        offset += count
    views = {}
    for name, package in (('current13', current), ('h30_26', h30)):
        result = package.result
        views[name] = dict(configuration=asdict(result.configuration), threshold=result.threshold,
            training_count=len(result.train_indices), calibration_count=len(result.calibration_indices),
            preprocessing_fit_count=len(result.preprocessing_fit_indices),
            equal_threshold_count=sum(result.scores[i] == result.threshold for i in result.calibration_indices),
            above_threshold_count=sum(result.scores[i] > result.threshold for i in result.calibration_indices))
    summary = dict(**envelope,
        source=dict(schema_id=c.source_schema_id, authentication=c.source_authentication,
            time_basis=c.time_basis, policy_status=c.policy_status, audit_fit_policy=c.audit_fit_policy),
        input_references=dict(raw=asdict(c.raw_identity), prepared=asdict(c.prepared_identity),
            configuration_sha256=c.configuration_sha256), result_references=references,
        axis=dict(minute_count=n, scored_count=sum(r.scored_mask), unscored_count=n-sum(r.scored_mask),
            page_size=100, page_count=(n+99)//100, segments=segments), views=views,
        checks=dict(internal_consistency='MATCHED', saved_score_q99='MATCHED', cross_view_binding='MATCHED',
            input_pair_binding='NOT_PERFORMED', source_authentication='NOT_AUTHENTICATED', model_execution='NOT_AUTHENTICATED'))
    summary_bytes = _json_bytes(summary, _SUMMARY_LIMIT)
    pages = []
    total = len(summary_bytes) + sum(map(len, _ERRORS.values()))
    for start in range(0, n, 100):
        items = []
        for i in range(start, min(start+100, n)):
            stamp, text, segment_id, role = axis[i]
            scored = r.scored_mask[i]
            broken = (i == 0 or segment_id != axis[i-1][2] or
                      stamp-axis[i-1][0] != timedelta(minutes=1) or not scored or not r.scored_mask[i-1])
            items.append(dict(index=i, timestamp=text, segment_id=segment_id, role=role,
                break_before=broken, scored=scored,
                current13=dict(score=r.scores[i], prediction=r.predictions[i]),
                h30_26=dict(score=h30.result.scores[i], prediction=h30.result.predictions[i]),
                reason=None if scored else 'NOT_SCORED_CAUSE_NOT_SAVED'))
        payload = _json_bytes(dict(**envelope, page=start//100, page_size=100,
            total=n, returned=len(items), items=items), _SERIES_LIMIT)
        total += len(payload)
        if total > _TOTAL_LIMIT:
            raise ReleaseIFResultViewError('RESOURCE_LIMIT')
        pages.append(payload)
    assets = _read_assets()
    if total + sum(len(payload) for _, payload, _ in assets) > _TOTAL_LIMIT:
        raise ReleaseIFResultViewError('RESOURCE_LIMIT')
    return summary_bytes, tuple(pages), assets


def _endpoint(payload, media_type, *, html=False):
    headers = {**_HEADERS, **({'Content-Security-Policy': _CSP} if html else {})}
    async def serve(request: Request):
        if request.scope.get('query_string', b''):
            raise _InvalidQuery()
        return Response(payload, media_type=media_type, headers=headers)
    return serve


def _series_endpoint(pages):
    async def serve(request: Request):
        query = request.scope.get('query_string', b'')
        if query:
            parameters = request.query_params.multi_items()
            if len(parameters) != 1 or parameters[0][0] != 'page':
                raise _InvalidQuery()
            value = parameters[0][1]
            if re.fullmatch(r'0|[1-9][0-9]?', value) is None:
                raise _InvalidQuery()
            page = int(value)
        else:
            page = 0
        if page >= len(pages):
            raise _InvalidQuery()
        return Response(pages[page], media_type='application/json', headers=_HEADERS)
    return serve


def create_release_if_result_view_app(current13: contract.ReleaseIFResultPackage,
                                     h30_26: contract.ReleaseIFResultPackage) -> FastAPI:
    """Recheck declared packages, pair their full axes, then freeze all responses.

    Internal checks and saved-score Q99 verification do not authenticate original
    source bytes or model execution. No model fitting or scoring occurs here.
    """
    if type(current13) is not contract.ReleaseIFResultPackage or type(h30_26) is not contract.ReleaseIFResultPackage:
        raise ReleaseIFResultViewError('INVALID_VIEW_ARGUMENTS')
    try:
        summary, pages, assets = _freeze(current13, h30_26)
        app = FastAPI(title='Saved release IF results', debug=False, openapi_url=None,
                      docs_url=None, redoc_url=None, redirect_slashes=False)

        def failure(request, status, code):
            headers = {**_HEADERS, **({'Allow': 'GET'} if status == 405 else {})}
            return Response(b'' if request.method == 'HEAD' else _ERRORS[code],
                            status_code=status, media_type='application/json', headers=headers)

        @app.exception_handler(_InvalidQuery)
        async def invalid_query(request, exc):
            return failure(request, 422, 'INVALID_QUERY')

        @app.exception_handler(RequestValidationError)
        async def invalid_request(request, exc):
            return failure(request, 422, 'INVALID_QUERY')

        @app.exception_handler(HTTPException)
        async def http_error(request, exc):
            if exc.status_code == 405:
                return failure(request, 405, 'METHOD_NOT_ALLOWED')
            if exc.status_code == 404:
                return failure(request, 404, 'NOT_FOUND')
            return failure(request, 500, 'VIEW_UNAVAILABLE')

        @app.exception_handler(Exception)
        async def internal_error(request, exc):
            return failure(request, 500, 'VIEW_UNAVAILABLE')

        app.add_api_route('/release-if/v1/summary', _endpoint(summary, 'application/json'), methods=['GET'])
        app.add_api_route('/release-if/v1/series', _series_endpoint(pages), methods=['GET'])
        for path, payload, media_type in assets:
            app.add_api_route(path, _endpoint(payload, media_type, html=media_type == 'text/html'), methods=['GET'])
        # The locked FastAPI version lazily inspects endpoint source. Resolve
        # these five contexts now so the first GET also needs no file access.
        from fastapi.routing import _extract_endpoint_context
        for route in app.routes:
            _extract_endpoint_context(route.endpoint)
        return app
    except ReleaseIFResultViewError:
        raise
    except Exception:
        raise ReleaseIFResultViewError('VIEW_UNAVAILABLE') from None
