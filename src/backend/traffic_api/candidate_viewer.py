"""Optional same-origin viewer for retained synthetic candidate snapshots."""
from importlib import resources

from fastapi import Request
from fastapi.responses import Response

from .candidate_app import create_candidate_app, _query

MAX_ASSET_BYTES = 1024 * 1024
MAX_TOTAL_ASSET_BYTES = 3 * MAX_ASSET_BYTES
_ASSETS = (
    ('/candidate', 'index.html', 'text/html'),
    ('/candidate/viewer.css', 'viewer.css', 'text/css'),
    ('/candidate/viewer.mjs', 'viewer.mjs', 'text/javascript'),
)


class CandidateViewerError(ValueError):
    """Required packaged resources could not be admitted at trusted startup."""


def _read_assets():
    loaded, total = [], 0
    try:
        root = resources.files('traffic_api').joinpath('candidate_static')
        for route, name, media_type in _ASSETS:
            with root.joinpath(name).open('rb') as stream:
                payload = stream.read(MAX_ASSET_BYTES + 1)
            if not payload or len(payload) > MAX_ASSET_BYTES:
                raise ValueError
            payload.decode('utf-8')
            total += len(payload)
            if total > MAX_TOTAL_ASSET_BYTES:
                raise ValueError
            loaded.append((route, payload, media_type))
    except (OSError, ImportError, ValueError, TypeError, AttributeError):
        raise CandidateViewerError('VIEWER_ASSETS_UNAVAILABLE') from None
    return tuple(loaded)


def _asset_endpoint(payload, media_type):
    def asset(request: Request):
        _query(request, set())
        return Response(payload, media_type=media_type)
    return asset


def create_candidate_viewer_app(registrations):
    """Add three fixed resources; preserve the base app and startup admission.

    Callers safely load registrations first and bind the resulting app only to
    loopback. Resource bytes are bounded and frozen before any viewer route is
    installed. Requests never read a resource or accept a filesystem path.
    """
    app = create_candidate_app(registrations)
    loaded = _read_assets()
    for route, payload, media_type in loaded:
        app.add_api_route(route, _asset_endpoint(payload, media_type), methods=['GET'])
    return app
