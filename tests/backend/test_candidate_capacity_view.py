"""Capacity transport tests use immutable bytes, not model/package execution."""
import importlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest


ASSETS = {'capacity.html': b'<!doctype html><title>capacity</title>',
          'capacity.mjs': b'export const capacity = true;', 'viewer.css': b'body{color:black}'}
ROUTES = {'/candidate/capacity': ('capacity.html', 'text/html; charset=utf-8'),
          '/candidate/capacity.mjs': ('capacity.mjs', 'text/javascript; charset=utf-8'),
          '/candidate/viewer.css': ('viewer.css', 'text/css; charset=utf-8')}
DATA_ROUTE = '/candidate/v1/capacity-comparison'
PAYLOAD = b'{"evidence_kind":"SYNTHETIC_ONLY","value":0}\n'


def api():
    name = 'traffic_api.candidate_capacity_view'
    assert importlib.util.find_spec(name) is not None, 'capacity-only HTTP app is required'
    return importlib.import_module(name)


@pytest.fixture
def snapshot_type(monkeypatch):
    """Final transport checks require the actual N1 immutable value type."""
    return importlib.import_module('traffic_anomaly.candidate_capacity_snapshot').CandidateCapacitySnapshot


class ResourceTree:
    def __init__(self, values, events, name=None):
        self.values, self.events, self.name = values, events, name
    def joinpath(self, name):
        return ResourceTree(self.values, self.events, name)
    def open(self, mode):
        assert mode == 'rb'
        value = self.values[self.name]
        if isinstance(value, Exception):
            raise value
        events, name = self.events, self.name
        class Stream(BytesIO):
            def read(self, size=-1):
                events.append((name, size))
                return super().read(size)
        return Stream(value)


def resources(monkeypatch, values=None):
    module = api()
    values, events = dict(ASSETS if values is None else values), []
    monkeypatch.setattr(module.resources, 'files', lambda name: ResourceTree(values, events))
    return module, values, events


def build(monkeypatch, snapshot_type, payload=PAYLOAD):
    module, values, events = resources(monkeypatch)
    snapshot = snapshot_type(payload=payload, run_ids=('current492', 'history15'))
    return module.create_candidate_capacity_app(snapshot), module, values, events


def test_capacity_returns_exact_startup_bytes_and_four_get_routes(monkeypatch, snapshot_type):
    app, module, values, events = build(monkeypatch, snapshot_type)
    assert {(route.path, tuple(sorted(route.methods))) for route in app.routes} == {
        (path, ('GET',)) for path in [DATA_ROUTE, *ROUTES]}
    client = TestClient(app)
    for _ in range(2):
        response = client.get(DATA_ROUTE)
        assert response.status_code == 200 and response.content == PAYLOAD
        assert response.headers['content-type'] == 'application/json'
        assert int(response.headers['content-length']) == len(PAYLOAD)
        assert 'access-control-allow-origin' not in response.headers
    assert sorted(events) == [(name, 1048577) for name in sorted(ASSETS)]


@pytest.mark.parametrize('path', list(ROUTES))
def test_fixed_resource_bytes_types_and_mutation_isolation(monkeypatch, snapshot_type, path):
    app, _, values, _ = build(monkeypatch, snapshot_type)
    name, media_type = ROUTES[path]
    values[name] = b'changed after startup'
    response = TestClient(app).get(path)
    assert response.status_code == 200 and response.content == ASSETS[name]
    assert response.headers['content-type'] == media_type


@pytest.mark.parametrize('path', [DATA_ROUTE, *ROUTES])
@pytest.mark.parametrize('query', ['?page=1', '?path=private-file', '?x=1&x=2', '?%70age=1'])
def test_every_query_key_is_rejected(path, query, monkeypatch, snapshot_type):
    app, *_ = build(monkeypatch, snapshot_type)
    response = TestClient(app).get(path + query)
    assert response.status_code == 422 and response.json() == {'error': 'INVALID_QUERY'}
    assert 'private' not in response.text


@pytest.mark.parametrize('path', [DATA_ROUTE, *ROUTES])
@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
def test_only_get_is_available(path, method, monkeypatch, snapshot_type):
    app, *_ = build(monkeypatch, snapshot_type)
    response = TestClient(app).request(method, path)
    assert response.status_code == 405 and response.headers['allow'] == 'GET'
    if method != 'HEAD':
        assert response.json() == {'error': 'METHOD_NOT_ALLOWED'}


@pytest.mark.parametrize('path', ['/candidate', '/candidate/viewer.mjs', '/candidate/v1/runs',
    '/candidate/v1/comparison', '/api/v1/runs', '/docs', '/openapi.json',
    '/candidate/v1/capacity-comparison/', '/candidate/unknown', '/candidate/../private'])
def test_classic_production_and_unknown_routes_remain_absent(path, monkeypatch, snapshot_type):
    app, *_ = build(monkeypatch, snapshot_type)
    response = TestClient(app).get(path, follow_redirects=False)
    assert response.status_code == 404 and response.json() == {'error': 'NOT_FOUND'}


@pytest.mark.parametrize('value', [None, b'bytes', SimpleNamespace(payload=PAYLOAD),
                                 {'payload': PAYLOAD, 'run_ids': ('a', 'b')}])
def test_invalid_snapshot_wrapper_rejects_before_asset_reads(value, monkeypatch, snapshot_type):
    module, _, events = resources(monkeypatch)
    with pytest.raises(module.CandidateCapacityViewError, match='^INVALID_CAPACITY_SNAPSHOT$'):
        module.create_candidate_capacity_app(value)
    assert not events


@pytest.mark.parametrize('payload', [b'', bytearray(PAYLOAD), 'text', b'x' * (1048576 + 1)],
                         ids=['empty', 'mutable', 'text', 'oversize'])
def test_snapshot_payload_type_and_limit_rechecked_without_parsing(payload, monkeypatch, snapshot_type):
    module, _, events = resources(monkeypatch)
    # Bypass any N1 constructor checks to exercise the consuming boundary.
    snapshot = object.__new__(snapshot_type)
    object.__setattr__(snapshot, 'payload', payload)
    object.__setattr__(snapshot, 'run_ids', ('a', 'b'))
    with pytest.raises(module.CandidateCapacityViewError, match='^INVALID_CAPACITY_SNAPSHOT$'):
        module.create_candidate_capacity_app(snapshot)
    assert not events


def test_exact_payload_limit_is_inclusive_and_not_reparsed(monkeypatch, snapshot_type):
    module, _, _ = resources(monkeypatch)
    snapshot = object.__new__(snapshot_type)
    object.__setattr__(snapshot, 'payload', b'x' * 1048576)
    object.__setattr__(snapshot, 'run_ids', ('a', 'b'))
    app = module.create_candidate_capacity_app(snapshot)
    assert TestClient(app).get(DATA_ROUTE).content == b'x' * 1048576


@pytest.mark.parametrize('name', list(ASSETS))
@pytest.mark.parametrize('value', [b'', b'\xff', OSError('private asset path'), b'x' * 1048577],
                         ids=['empty', 'invalid-utf8', 'oserror', 'oversize'])
def test_missing_empty_invalid_or_oversized_assets_fail_before_serving(name, value, monkeypatch, snapshot_type):
    module, _, _ = resources(monkeypatch, ASSETS | {name: value})
    with pytest.raises(module.CandidateCapacityViewError, match='^VIEWER_ASSETS_UNAVAILABLE$'):
        module.create_candidate_capacity_app(snapshot_type(payload=PAYLOAD, run_ids=('a', 'b')))


def test_request_phase_does_not_read_parse_encode_or_execute(monkeypatch, snapshot_type):
    app, module, _, events = build(monkeypatch, snapshot_type)
    client = TestClient(app)
    before = list(events)
    def forbidden(*args, **kwargs):
        raise AssertionError('request performed a forbidden operation')
    from traffic_anomaly import candidate_capacity_comparison, candidate_artifacts, candidate_ae_run_artifacts
    from traffic_anomaly import candidate_capacity_snapshot
    from traffic_anomaly import candidate_autoencoder, candidate_iforest, candidate_evaluation
    for owner, names in [(module.resources, ('files',)),
        (Path, ('open', 'read_bytes', 'read_text', 'write_bytes', 'write_text')),
        (candidate_capacity_comparison, ('compare_candidate_ae_capacity_runs',)),
        (candidate_capacity_snapshot, ('encode_capacity_report', 'load_verified_candidate_capacity_comparison')),
        (candidate_artifacts, ('load_verified_candidate_artifacts',)),
        (candidate_ae_run_artifacts, ('load_verified_candidate_ae_run',)),
        (candidate_autoencoder, ('compute_synthetic_candidate_ae', 'replay_candidate_ae')),
        (candidate_iforest, ('compute_synthetic_candidate_if',)),
        (candidate_evaluation, ('evaluate_candidate_predictions',))]:
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    # JSON is patched only on the capacity module if it imports it. Framework
    # internals may use JSON; response bytes must not pass through a serializer.
    if hasattr(module, 'json'):
        monkeypatch.setattr(module, 'json', SimpleNamespace(loads=forbidden, dumps=forbidden))
    for path in [DATA_ROUTE, *ROUTES]:
        assert client.get(path).status_code == 200
    assert events == before


def test_resource_exact_limit_and_total_limit_are_startup_guards(monkeypatch, snapshot_type):
    module, _, events = resources(monkeypatch, ASSETS | {'capacity.html': b'x' * 1048576})
    app = module.create_candidate_capacity_app(snapshot_type(PAYLOAD, ('a', 'b')))
    assert len(TestClient(app).get('/candidate/capacity').content) == 1048576
    assert all(size == 1048577 for _, size in events)
    monkeypatch.setattr(module, 'MAX_TOTAL_ASSET_BYTES', 1)
    with pytest.raises(module.CandidateCapacityViewError, match='VIEWER_ASSETS_UNAVAILABLE'):
        module.create_candidate_capacity_app(snapshot_type(PAYLOAD, ('a', 'b')))


def test_factory_never_parses_and_captures_payload_value(monkeypatch, snapshot_type):
    from traffic_anomaly import candidate_capacity_snapshot as core
    module, _, _ = resources(monkeypatch)
    def forbidden(*args, **kwargs):
        raise AssertionError('transport attempted report verification or encoding')
    monkeypatch.setattr(core, 'encode_capacity_report', forbidden)
    monkeypatch.setattr(core, 'validate_capacity_report', forbidden)
    value = snapshot_type(PAYLOAD, ('a', 'b'))
    app = module.create_candidate_capacity_app(value)
    object.__setattr__(value, 'payload', b'changed after factory')
    assert TestClient(app).get(DATA_ROUTE).content == PAYLOAD


def test_actual_500_uses_only_fixed_error_bytes(monkeypatch, snapshot_type):
    app, *_ = build(monkeypatch, snapshot_type)
    def broken(request):
        raise RuntimeError('private path and traceback')
    route = next(route for route in app.routes if route.path == DATA_ROUTE)
    monkeypatch.setattr(route.dependant, 'call', broken)
    response = TestClient(app, raise_server_exceptions=False).get(DATA_ROUTE)
    assert response.status_code == 500 and response.content == b'{"error":"INTERNAL_ERROR"}\n'
