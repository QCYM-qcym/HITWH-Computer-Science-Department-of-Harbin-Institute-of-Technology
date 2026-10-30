"""Manifest-backed backend JSON is parsed from the bytes checked for that load."""
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from traffic_anomaly import contracts as c
from traffic_api import artifacts

from .conftest import submit, wait_terminal


MODELS = {
    'metrics.json': c.Evaluation,
    'summary.json': c.RunSummary,
    'config.json': c.RunConfig,
    'model/metadata.json': c.ModelMetadata,
    'model/preprocess.json': c.PreprocessState,
}
MARKER = 'POST_HASH_UNVERIFIED_REASON'


def checksum(data): return hashlib.sha256(data).hexdigest()
def snapshot(workspace):
    return {path.relative_to(workspace).as_posix():
            (checksum(path.read_bytes()), path.stat().st_mtime_ns)
            for path in workspace.rglob('*') if path.is_file()}


@pytest.fixture
def completed_json(make_app, fixture_data, settings):
    app = make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        yield client, run_id, settings.output / run_id


def legal_replacement(original, name):
    model = MODELS[name]
    if name == 'metrics.json':
        changed = json.loads(original)
        changed['reason'] = MARKER
        payload = json.dumps(changed, allow_nan=False).encode('utf-8')
        assert model.model_validate_json(payload).model_dump(exclude={'reason'}) == model.model_validate_json(original).model_dump(exclude={'reason'})
    else:
        payload = b' \n' + original + b'\n '
        assert model.model_validate_json(payload) == model.model_validate_json(original)
    assert checksum(payload) != checksum(original)
    return payload


def gate_json(monkeypatch, workspace, name, *, replacement=None, failure=None):
    target, model = workspace / name, MODELS[name]
    expected = next(entry.sha256 for entry in c.Manifest.model_validate_json(
        (workspace / 'manifest.json').read_bytes()).files if entry.path == name)
    original = target.read_bytes()
    assert checksum(original) == expected
    original_digest, original_json, original_bytes = artifacts.digest, artifacts.read_json, Path.read_bytes
    original_parser = model.model_validate_json
    state = dict(original_verified=False, entered=False, inside_json=False, completed=False,
                 payload_reads=0, model_parses=0, kwargs=None, manifest_kwargs=[], manifest_refreshes=0)
    def digest(path):
        actual = original_digest(path)
        if path == target:
            assert actual == expected
            state['original_verified'] = True
        return actual
    def read_json(path, *args, **kwargs):
        if path == workspace / 'manifest.json': state['manifest_kwargs'].append(kwargs.copy())
        if path == target and not state['entered']:
            assert state['original_verified'], 'replace only after original manifest digest actually passed'
            state['entered'], state['kwargs'] = True, kwargs.copy()
            if replacement is not None: path.write_bytes(replacement)
            elif failure == 'missing': path.unlink()
            elif failure == 'short': path.write_bytes(original[:-1])
            state['inside_json'] = True
            try: return original_json(path, *args, **kwargs)
            finally: state['inside_json'] = False
        return original_json(path, *args, **kwargs)
    def read_bytes(path):
        if state['entered'] and not state['completed'] and path == workspace / 'manifest.json':
            state['manifest_refreshes'] += 1
            raise AssertionError('do not replace the accepted manifest reference')
        if state['inside_json'] and path == target:
            state['payload_reads'] += 1
            if failure in ('permission', 'io_error'):
                error = PermissionError if failure == 'permission' else OSError
                raise error('private/path credential: JSON acquisition failed')
        return original_bytes(path)
    def parser(data, *args, **kwargs):
        if state['inside_json']: state['model_parses'] += 1
        return original_parser(data, *args, **kwargs)
    monkeypatch.setattr(artifacts, 'digest', digest)
    monkeypatch.setattr(artifacts, 'read_json', read_json)
    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    monkeypatch.setattr(model, 'model_validate_json', staticmethod(parser))
    return state, expected, original


def assert_safe_failure(response, reason):
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'EXECUTION_FAILED'
    assert response.json()['error']['details'] == [reason]
    assert MARKER not in response.text and 'private' not in response.text and 'Traceback' not in response.text


@pytest.mark.parametrize('name', tuple(MODELS))
def test_each_formal_json_rejects_a_valid_physical_replacement_before_model_parse(completed_json, monkeypatch, name):
    client, run_id, workspace = completed_json
    before = snapshot(workspace)
    changed = legal_replacement((workspace / name).read_bytes(), name)
    state, expected, original = gate_json(monkeypatch, workspace, name, replacement=changed)
    response = client.get(f'/api/v1/runs/{run_id}/evaluation')
    state['completed'] = True
    assert state['original_verified'] and state['entered'] and state['payload_reads'] == 1
    assert checksum(original) == expected and checksum(changed) != expected
    after = snapshot(workspace)
    assert after[name][0] == checksum(changed)
    assert {key: value for key, value in after.items() if key != name} == {key: value for key, value in before.items() if key != name}
    assert state['manifest_kwargs'] == [{}] and state['manifest_refreshes'] == 0
    if name == 'metrics.json' and response.status_code == 200:
        assert response.json()['reason'] == MARKER
    assert_safe_failure(response, 'ARTIFACT_INVALID')
    assert state['kwargs']['expected_sha256'] == expected
    assert state['model_parses'] == 0
    assert client.get(f'/api/v1/runs/{run_id}').json()['status'] == 'succeeded'


@pytest.mark.parametrize('failure,reason', [('missing', 'RESULT_MISSING'), ('permission', 'ARTIFACT_INVALID'),
                                          ('io_error', 'ARTIFACT_INVALID'), ('short', 'ARTIFACT_INVALID')])
def test_post_hash_json_acquisition_errors_are_safe(completed_json, monkeypatch, failure, reason):
    client, run_id, workspace = completed_json
    state, _, _ = gate_json(monkeypatch, workspace, 'metrics.json', failure=failure)
    response = client.get(f'/api/v1/runs/{run_id}/evaluation')
    state['completed'] = True
    assert state['original_verified'] and state['entered'] and state['payload_reads'] == 1
    assert_safe_failure(response, reason)
    assert state['model_parses'] == 0 and state['manifest_refreshes'] == 0
    assert client.get(f'/api/v1/runs/{run_id}').json()['status'] == 'succeeded'


@pytest.mark.parametrize('name,model', [('metrics.json', c.Evaluation), ('manifest.json', c.Manifest)])
def test_two_argument_parse_uses_one_original_bytes_object_after_path_changes(completed_json, monkeypatch, name, model):
    # The legacy two-argument mode is type parsing, not a parent-SHA claim. The
    # root manifest has no parent digest in the frozen package format.
    _, _, workspace = completed_json
    target = workspace / name
    data = target.read_bytes()
    original_parser = model.model_validate_json
    expected = original_parser(data)
    original_bytes, original_open = Path.read_bytes, Path.open
    state = dict(captured=False, reads=0, parses=0, captured_bytes=None)
    def read_bytes(path):
        if path == target:
            assert state['reads'] == 0
            original = original_bytes(path)
            state['reads'] += 1
            state['captured_bytes'] = original
            path.write_bytes(b' \n' + original + b'\n ')
            state['captured'] = True
            return original
        raise AssertionError('standalone JSON parser must not read another file or parent manifest')
    def open_path(path, *args, **kwargs):
        if state['captured'] and path == target:
            raise AssertionError('do not reopen a path after acquiring the JSON payload')
        return original_open(path, *args, **kwargs)
    def parse(payload, *args, **kwargs):
        assert payload is state['captured_bytes'] and isinstance(payload, bytes)
        state['parses'] += 1
        return original_parser(payload, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    monkeypatch.setattr(Path, 'open', open_path)
    monkeypatch.setattr(model, 'model_validate_json', staticmethod(parse))
    assert artifacts.read_json(target, model) == expected
    assert state['reads'] == state['parses'] == 1
