"""Capacity-only transport over one trusted-startup immutable bytes value.

Snapshot type/size checks are not provenance authentication. The launcher must
obtain the value from the core capacity loader before binding a loopback socket.
No classic registration, score/detail consumer or production router is used.
"""
from importlib import resources

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException

MAX_PAYLOAD_BYTES = 1048576
MAX_ASSET_BYTES = 1048576
MAX_TOTAL_ASSET_BYTES = 3 * MAX_ASSET_BYTES
_ASSETS = (
    ('/candidate/capacity', 'capacity.html', 'text/html'),
    ('/candidate/capacity.mjs', 'capacity.mjs', 'text/javascript'),
    ('/candidate/viewer.css', 'viewer.css', 'text/css'),
)
_ERRORS = {
    'NOT_FOUND': b'{"error":"NOT_FOUND"}\n',
    'METHOD_NOT_ALLOWED': b'{"error":"METHOD_NOT_ALLOWED"}\n',
    'INVALID_QUERY': b'{"error":"INVALID_QUERY"}\n',
    'INTERNAL_ERROR': b'{"error":"INTERNAL_ERROR"}\n',
}


class CandidateCapacityViewError(ValueError):
    """Fixed startup failure with no paths, resource content or exception text."""
    def __init__(self, code):
        self.code = code if type(code) is str and code in (
            'INVALID_CAPACITY_SNAPSHOT', 'VIEWER_ASSETS_UNAVAILABLE') else 'INVALID_CAPACITY_SNAPSHOT'
        super().__init__(self.code)


class _InvalidQuery(Exception):
    pass


def _read_assets():
    loaded, total = [], 0
    try:
        root = resources.files('traffic_api').joinpath('candidate_static')
        for path, name, media_type in _ASSETS:
            with root.joinpath(name).open('rb') as stream:
                value = stream.read(MAX_ASSET_BYTES + 1)
            if not value or len(value) > MAX_ASSET_BYTES:
                raise ValueError
            value.decode('utf-8')
            total += len(value)
            if total > MAX_TOTAL_ASSET_BYTES:
                raise ValueError
            loaded.append((path, value, media_type))
    except (OSError, ImportError, ValueError, TypeError, AttributeError):
        raise CandidateCapacityViewError('VIEWER_ASSETS_UNAVAILABLE') from None
    return tuple(loaded)


def _endpoint(payload, media_type):
    def serve(request: Request):
        if request.query_params:
            raise _InvalidQuery
        return Response(payload, media_type=media_type)
    return serve


def create_candidate_capacity_app(snapshot):
    """Freeze bounded resources at startup, then return the exact stored bytes.

    The core owns report validation/encoding. This factory intentionally does
    not parse, encode, verify artifacts or certify a hand-constructed snapshot.
    """
    from traffic_anomaly.candidate_capacity_snapshot import CandidateCapacitySnapshot
    if (not isinstance(snapshot, CandidateCapacitySnapshot) or type(snapshot.payload) is not bytes
            or not 0 < len(snapshot.payload) <= MAX_PAYLOAD_BYTES):
        raise CandidateCapacityViewError('INVALID_CAPACITY_SNAPSHOT')
    payload = snapshot.payload
    assets = _read_assets()  # All required assets exist before an app can be served.
    app = FastAPI(title='Synthetic capacity comparison', debug=False, openapi_url=None,
                  docs_url=None, redoc_url=None, redirect_slashes=False)

    def failure(status, code, headers=None):
        return Response(_ERRORS[code], status_code=status, media_type='application/json', headers=headers)

    @app.exception_handler(_InvalidQuery)
    async def invalid_query(request, exc):
        return failure(422, 'INVALID_QUERY')

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return failure(422, 'INVALID_QUERY')

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if exc.status_code == 405:
            return failure(405, 'METHOD_NOT_ALLOWED', {'Allow': 'GET'})
        return failure(404, 'NOT_FOUND')

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return failure(500, 'INTERNAL_ERROR')

    app.add_api_route('/candidate/v1/capacity-comparison', _endpoint(payload, 'application/json'), methods=['GET'])
    for path, value, media_type in assets:
        app.add_api_route(path, _endpoint(value, media_type), methods=['GET'])
    # Compatibility seam for locked FastAPI 0.156.6: its first request lazily
    # inspects endpoint source. Warm its existing context cache for these four
    # fixed endpoints at startup, before the launcher can bind a socket.
    from fastapi.routing import _extract_endpoint_context
    for route in app.routes:
        _extract_endpoint_context(route.endpoint)
    return app
