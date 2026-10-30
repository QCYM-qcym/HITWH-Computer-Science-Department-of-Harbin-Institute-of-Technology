"""Outgoing export bytes stay bound to the manifest accepted by that load."""
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from .conftest import submit, wait_terminal


KINDS = {
    'scores': ('scores.parquet', 'application/vnd.apache.parquet'),
    'metrics': ('metrics.json', 'application/json'),
    'config': ('config.json', 'application/json'),
}


def snapshot(workspace):
    return {path.relative_to(workspace).as_posix():
            (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in workspace.rglob('*') if path.is_file()}


@pytest.fixture
def completed_export(make_app, fixture_data, settings):
    app = make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        yield app, client, run_id, settings.output / run_id


def inject_after_real_validation(app, monkeypatch, workspace, kind, outcome, *, later_manifest=None):
    """Arm only after the real SavedArtifacts constructor has finished.

    Original files are never changed. A deterministic final-read substitute
    avoids nondeterministic races and must not be mistaken for prevalidation.
    """
    target = workspace / KINDS[kind][0]
    original_read = Path.read_bytes
    original_saved = app.state.service.saved
    state = dict(armed=False, target_reads=[], manifest_reads=[], saved_returns=0)
    def guarded(path):
        if state['armed'] and path == workspace / 'manifest.json':
            state['manifest_reads'].append(True)
            if later_manifest is not None: return later_manifest
            raise AssertionError('export must not refresh its accepted manifest')
        if state['armed'] and path == target:
            state['target_reads'].append(True)
            if isinstance(outcome, BaseException): raise outcome
            return outcome
        return original_read(path)
    def saved(run_id):
        checked = original_saved(run_id)
        state['saved_returns'] += 1
        state['armed'] = True
        return checked
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    monkeypatch.setattr(app.state.service, 'saved', saved)
    return state


def assert_finished_read(state):
    state['armed'] = False
    assert state['saved_returns'] == 1
    assert len(state['target_reads']) == 1
    assert state['manifest_reads'] == []


def assert_safe_export_failure(response, reason):
    assert response.status_code == 500
    assert response.headers['content-type'] == 'application/json'
    assert 'content-disposition' not in response.headers
    assert response.json()['error']['code'] == 'EXECUTION_FAILED'
    assert response.json()['error']['details'] == [reason]
    assert 'unverified_export' not in response.text and 'private' not in response.text
    assert 'Traceback' not in response.text


@pytest.mark.parametrize('kind', tuple(KINDS))
@pytest.mark.parametrize('change', ['replacement', 'truncated'])
def test_final_substituted_or_truncated_bytes_are_not_exported(completed_export, monkeypatch, kind, change):
    app, client, run_id, workspace = completed_export
    before = snapshot(workspace)
    original = (workspace / KINDS[kind][0]).read_bytes()
    changed = b'{"unverified_export":true}' if change == 'replacement' else original[:-1]
    state = inject_after_real_validation(app, monkeypatch, workspace, kind, changed)
    response = client.get(f'/api/v1/runs/{run_id}/exports/{kind}')
    assert_finished_read(state)
    assert_safe_export_failure(response, 'ARTIFACT_INVALID')
    assert snapshot(workspace) == before
    assert client.get(f'/api/v1/runs/{run_id}').json()['status'] == 'succeeded'


@pytest.mark.parametrize('error_type,reason', [
    (FileNotFoundError, 'RESULT_MISSING'), (PermissionError, 'ARTIFACT_INVALID'),
    (OSError, 'ARTIFACT_INVALID'),
])
def test_final_read_errors_use_saved_artifact_safe_reasons(completed_export, monkeypatch, error_type, reason):
    app, client, run_id, workspace = completed_export
    before = snapshot(workspace)
    error = error_type('private/path credential: final export read failed')
    state = inject_after_real_validation(app, monkeypatch, workspace, 'metrics', error)
    response = client.get(f'/api/v1/runs/{run_id}/exports/metrics')
    assert_finished_read(state)
    assert_safe_export_failure(response, reason)
    assert snapshot(workspace) == before
    assert client.get(f'/api/v1/runs/{run_id}').json()['status'] == 'succeeded'


@pytest.mark.parametrize('kind', tuple(KINDS))
def test_original_full_bytes_headers_and_length_survive_ignored_pagination(completed_export, monkeypatch, kind):
    app, client, run_id, workspace = completed_export
    filename, media_type = KINDS[kind]
    original = (workspace / filename).read_bytes()
    before = snapshot(workspace)
    state = inject_after_real_validation(app, monkeypatch, workspace, kind, original)
    response = client.get(f'/api/v1/runs/{run_id}/exports/{kind}', params={'page_size': 1, 'page': 2})
    assert_finished_read(state)
    assert response.status_code == 200 and response.content == original
    assert response.headers['content-type'] == media_type
    assert response.headers['content-disposition'] == f'attachment; filename="{run_id}-{filename}"'
    assert response.headers['content-length'] == str(len(original))
    assert snapshot(workspace) == before


def test_later_manifest_with_new_digest_is_not_authority_for_current_export(completed_export, monkeypatch):
    app, client, run_id, workspace = completed_export
    before = snapshot(workspace)
    substitute = b'{"unverified_export":true,"fresh_manifest":true}'
    forged_manifest = json.loads((workspace / 'manifest.json').read_bytes())
    entry = next(value for value in forged_manifest['files'] if value['path'] == 'metrics.json')
    entry['sha256'] = hashlib.sha256(substitute).hexdigest()
    state = inject_after_real_validation(app, monkeypatch, workspace, 'metrics', substitute,
        later_manifest=json.dumps(forged_manifest).encode('utf-8'))
    response = client.get(f'/api/v1/runs/{run_id}/exports/metrics')
    assert_finished_read(state)
    assert_safe_export_failure(response, 'ARTIFACT_INVALID')
    assert snapshot(workspace) == before


def test_unknown_run_and_nonexportable_kind_keep_existing_early_errors(completed_export, monkeypatch):
    app, client, run_id, workspace = completed_export
    original = Path.read_bytes
    reads = []
    def counted(path):
        if path.is_relative_to(workspace): reads.append(path)
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', counted)
    missing = client.get('/api/v1/runs/unknown-run/exports/metrics')
    assert missing.status_code == 404 and missing.json()['error']['code'] == 'NOT_FOUND'
    invalid = client.get(f'/api/v1/runs/{run_id}/exports/manifest')
    assert invalid.status_code == 422 and invalid.json()['error']['code'] == 'VALIDATION_ERROR'
    assert reads == []
