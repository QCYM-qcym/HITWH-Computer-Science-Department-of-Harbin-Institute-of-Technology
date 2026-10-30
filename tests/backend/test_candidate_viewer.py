"""Fixed packaged viewer resources over hand-written candidate snapshots.

These tests neither create trained packages nor use the production app fixture.
Installed-wheel resource provenance is checked separately by the root work.
"""
import importlib
import importlib.util
import io
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from . import test_candidate_app as candidate_tests


ASSETS = {
    'index.html': b'<!doctype html><title>SYNTHETIC_ONLY</title>',
    'viewer.css': b'body { color: #222; }',
    'viewer.mjs': b'export const evidence = "AUDIT_ONLY";\n',
}
ROUTES = {
    '/candidate': ('index.html', 'text/html; charset=utf-8'),
    '/candidate/viewer.css': ('viewer.css', 'text/css; charset=utf-8'),
    '/candidate/viewer.mjs': ('viewer.mjs', 'text/javascript; charset=utf-8'),
}


def viewer():
    name = 'traffic_api.candidate_viewer'
    assert importlib.util.find_spec(name) is not None, 'optional fixed-resource viewer factory is required'
    return importlib.import_module(name)


class ResourceTree:
    def __init__(self, data, events, parts=()):
        self.data, self.events, self.parts = data, events, parts

    def joinpath(self, *parts):
        return ResourceTree(self.data, self.events, self.parts + parts)

    def open(self, mode):
        assert mode == 'rb'
        assert self.parts[0] == 'candidate_static' and len(self.parts) == 2
        name = self.parts[1]
        self.events.append(('open', name))
        value = self.data[name]
        if isinstance(value, Exception):
            raise value
        events = self.events

        class Stream(io.BytesIO):
            def read(self, size=-1):
                events.append(('read', name, size))
                return super().read(size)

        return Stream(value)


def resources(monkeypatch, data=None):
    module = viewer()
    data, events = dict(ASSETS if data is None else data), []

    def files(anchor):
        assert anchor == 'traffic_api'
        events.append(('files', anchor))
        return ResourceTree(data, events)

    monkeypatch.setattr(module.resources, 'files', files)
    return module, data, events


def registrations():
    base = candidate_tests.api()
    return [base.CandidateRegistration(*candidate_tests.pair())]


@pytest.mark.parametrize('path', ROUTES)
def test_fixed_assets_have_exact_bytes_content_types_and_no_cors(path, monkeypatch):
    module, _, events = resources(monkeypatch)
    client = TestClient(module.create_candidate_viewer_app(registrations()))
    response = client.get(path)
    name, media_type = ROUTES[path]
    assert response.status_code == 200 and response.content == ASSETS[name]
    assert response.headers['content-type'] == media_type
    assert int(response.headers['content-length']) == len(ASSETS[name])
    assert 'access-control-allow-origin' not in response.headers
    assert [event for event in events if event[0] == 'open'] == [('open', name) for name in ASSETS]
    assert [event for event in events if event[0] == 'read'] == [('read', name, 1024 * 1024 + 1) for name in ASSETS]


def test_viewer_adds_exactly_three_get_routes_and_base_factory_is_unchanged(monkeypatch):
    module, _, _ = resources(monkeypatch)
    base = candidate_tests.api().create_candidate_app(registrations())
    app = module.create_candidate_viewer_app(registrations())
    before = {(route.path, frozenset(route.methods)) for route in base.routes}
    after = {(route.path, frozenset(route.methods)) for route in app.routes}
    assert after - before == {(path, frozenset({'GET'})) for path in ROUTES}
    assert len(before) == 3 and len(after) == 6
    assert not app.router.redirect_slashes and not app.debug
    assert app.openapi_url is app.docs_url is app.redoc_url is None
    candidate_tests.failure(TestClient(base).get('/candidate'), 404, 'NOT_FOUND')


@pytest.mark.parametrize('path', ROUTES)
@pytest.mark.parametrize('query', ['?path=private-secret', '?x=1&x=2', '?%70ath=private-secret', '?='])
def test_static_routes_reject_all_query_keys(path, query, monkeypatch):
    module, _, _ = resources(monkeypatch)
    response = TestClient(module.create_candidate_viewer_app(registrations())).get(path + query)
    candidate_tests.failure(response, 422, 'INVALID_QUERY')


@pytest.mark.parametrize('path', ['/candidate/', '/candidate/index.html', '/candidate/missing',
    '/candidate/candidate_viewer.py', '/candidate/%2e%2e/pyproject.toml', '/docs', '/openapi.json', '/api/v1/runs'])
def test_unknown_and_traversal_routes_remain_safe_not_found(path, monkeypatch):
    module, _, _ = resources(monkeypatch)
    client = TestClient(module.create_candidate_viewer_app(registrations()))
    candidate_tests.failure(client.get(path, follow_redirects=False), 404, 'NOT_FOUND')


@pytest.mark.parametrize('path', ROUTES)
@pytest.mark.parametrize('method', ['post', 'head', 'options'])
def test_static_routes_are_get_only(path, method, monkeypatch):
    module, _, _ = resources(monkeypatch)
    response = getattr(TestClient(module.create_candidate_viewer_app(registrations())), method)(path)
    assert response.status_code == 405 and response.headers['allow'] == 'GET'
    assert 'access-control-allow-origin' not in response.headers
    if method != 'head':
        candidate_tests.failure(response, 405, 'METHOD_NOT_ALLOWED')


def test_api_success_and_error_bytes_match_unwrapped_base(monkeypatch):
    module, _, _ = resources(monkeypatch)
    plain = TestClient(candidate_tests.api().create_candidate_app(registrations()))
    wrapped = TestClient(module.create_candidate_viewer_app(registrations()))
    for path in ('/candidate/v1/runs', '/candidate/v1/runs/handwritten-if/series',
                 '/candidate/v1/runs/handwritten-if/detail?timestamp=2026-01-01T00:00',
                 '/candidate/v1/runs/missing/series', '/candidate/v1/runs?path=private-secret'):
        original, response = plain.get(path), wrapped.get(path)
        assert (response.status_code, response.content, response.headers['content-type']) == (
            original.status_code, original.content, original.headers['content-type'])


def test_assets_are_immutable_startup_bytes_and_requests_do_not_read(monkeypatch):
    module, data, events = resources(monkeypatch)
    client = TestClient(module.create_candidate_viewer_app(registrations()))
    before = list(events)
    data.clear()

    def forbidden(*args, **kwargs):
        raise AssertionError('request attempted resource or file access')

    monkeypatch.setattr(module.resources, 'files', forbidden)
    for name in ('open', 'read_bytes', 'read_text'):
        monkeypatch.setattr(Path, name, forbidden)
    for path, (name, _) in ROUTES.items():
        assert client.get(path).content == ASSETS[name]
        assert client.get(path).content == ASSETS[name]
    assert events == before


@pytest.mark.parametrize('filename', ASSETS)
@pytest.mark.parametrize('fault', ['missing', 'oversize', 'empty', 'invalid_utf8'])
def test_resource_errors_are_safe_and_do_not_partially_add_routes(filename, fault, monkeypatch):
    data = dict(ASSETS)
    data[filename] = {'missing': FileNotFoundError('private-secret/path'),
                      'oversize': b'a' * (1024 * 1024 + 1), 'empty': b'', 'invalid_utf8': b'\xff'}[fault]
    module, _, _ = resources(monkeypatch, data)
    base = candidate_tests.api().create_candidate_app(registrations())
    monkeypatch.setattr(module, 'create_candidate_app', lambda pairs: base)
    before = tuple(base.routes)
    with pytest.raises(module.CandidateViewerError, match='^VIEWER_ASSETS_UNAVAILABLE$') as caught:
        module.create_candidate_viewer_app(registrations())
    assert caught.value.__suppress_context__
    assert tuple(base.routes) == before


def test_individual_limit_is_inclusive_and_reads_are_bounded(monkeypatch):
    data = {name: b'a' * (1024 * 1024) for name in ASSETS}
    module, _, events = resources(monkeypatch, data)
    app = module.create_candidate_viewer_app(registrations())
    assert module.MAX_ASSET_BYTES == 1024 * 1024 and module.MAX_TOTAL_ASSET_BYTES == 3 * 1024 * 1024
    assert len(app.routes) == 6
    assert [event[2] for event in events if event[0] == 'read'] == [1024 * 1024 + 1] * 3


def test_total_limit_is_checked_before_installing_any_route(monkeypatch):
    module, _, _ = resources(monkeypatch)
    monkeypatch.setattr(module, 'MAX_TOTAL_ASSET_BYTES', sum(map(len, ASSETS.values())) - 1)
    with pytest.raises(module.CandidateViewerError, match='^VIEWER_ASSETS_UNAVAILABLE$'):
        module.create_candidate_viewer_app(registrations())


def test_package_lookup_failure_has_only_safe_startup_code(monkeypatch):
    module = viewer()

    def missing(*args):
        raise ModuleNotFoundError('private-package-path')

    monkeypatch.setattr(module.resources, 'files', missing)
    with pytest.raises(module.CandidateViewerError, match='^VIEWER_ASSETS_UNAVAILABLE$') as caught:
        module.create_candidate_viewer_app(registrations())
    assert caught.value.__suppress_context__


def test_invalid_registration_is_not_disguised_as_resource_failure(monkeypatch):
    module, _, events = resources(monkeypatch)
    with pytest.raises(candidate_tests.api().CandidateRegistrationError, match='^INVALID_REGISTRATION$'):
        module.create_candidate_viewer_app([])
    assert events == []
