"""Each backend Parquet parse uses bytes bound to that load's manifest SHA."""
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from traffic_anomaly import contracts as c
from traffic_api import artifacts

from .conftest import submit, wait_terminal


PAYLOADS = {
    'channels.parquet': (artifacts.CHANNEL_SCHEMA, c.ChannelRow),
    'scores.parquet': (artifacts.SCORE_SCHEMA, c.SeriesPoint),
    'labels.parquet': (artifacts.LABEL_SCHEMA, c.LabelRow),
}


def checksum(data): return hashlib.sha256(data).hexdigest()


@pytest.fixture
def completed_payload(make_app, fixture_data, settings):
    app = make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        yield client, run_id, settings.output / run_id


def replacement_payload(workspace, name, tmp_path):
    """A valid typed replacement that leaves label presence/alarms unchanged."""
    target = workspace / name
    original = target.read_bytes()
    table = pq.read_table(target)
    timestamps = table['timestamp'].cast(pa.int64()).to_pylist()
    rows = [dict(row, timestamp=stamp) for row, stamp in zip(table.drop(['timestamp']).to_pylist(), timestamps)]
    if name == 'channels.parquet': rows[1]['current'][0] = 12345.
    elif name == 'scores.parquet': rows[1]['score'] = .75
    else: rows[1]['dos'] = 2
    schema, model = PAYLOADS[name]
    replacement = tmp_path / ('replacement-' + name)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), replacement)
    parsed = artifacts.read_rows(replacement, schema, model)
    assert len(parsed) == 4
    payload = replacement.read_bytes()
    assert checksum(payload) != checksum(original)
    return original, payload


def gated_reader_hook(monkeypatch, workspace, name, action):
    """Observe a real initial digest, then intervene just before read_rows."""
    target = workspace / name
    original_digest, original_rows, original_parser = artifacts.digest, artifacts.read_rows, pq.read_table
    expected = next(entry['sha256'] for entry in c.Manifest.model_validate_json(
        (workspace / 'manifest.json').read_bytes()).model_dump()['files'] if entry['path'] == name)
    assert original_digest(target) == expected
    state = dict(original_verified=False, entered=False, parser_called=False,
                 parser_active=False, kwargs=None, manifest_reads=0)
    original_read_bytes = Path.read_bytes
    def digest(path):
        value = original_digest(path)
        if path == target:
            assert value == expected
            state['original_verified'] = True
        return value
    def reader(path, *args, **kwargs):
        if path == target and not state['entered']:
            assert state['original_verified'], 'intervention must follow the real manifest digest'
            state['entered'] = True
            state['kwargs'] = kwargs.copy()
            action(target)
            state['parser_active'] = True
            try: return original_rows(path, *args, **kwargs)
            finally: state['parser_active'] = False
        return original_rows(path, *args, **kwargs)
    def parser(*args, **kwargs):
        if state['parser_active']: state['parser_called'] = True
        return original_parser(*args, **kwargs)
    def read_bytes(path):
        if state['entered'] and path == workspace / 'manifest.json':
            state['manifest_reads'] += 1
            raise AssertionError('do not refresh the validated manifest')
        return original_read_bytes(path)
    monkeypatch.setattr(artifacts, 'digest', digest)
    monkeypatch.setattr(artifacts, 'read_rows', reader)
    monkeypatch.setattr(pq, 'read_table', parser)
    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    return state, expected


def assert_safe_failure(response, reason):
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'EXECUTION_FAILED'
    assert response.json()['error']['details'] == [reason]
    assert 'private' not in response.text and 'Traceback' not in response.text


@pytest.mark.parametrize('name', tuple(PAYLOADS))
def test_actual_valid_file_replaced_after_verified_digest_is_rejected_before_parsing(completed_payload, tmp_path, monkeypatch, name):
    client, run_id, workspace = completed_payload
    original, changed = replacement_payload(workspace, name, tmp_path)
    def replace(path): path.write_bytes(changed)
    state, expected = gated_reader_hook(monkeypatch, workspace, name, replace)
    response = client.get(f'/api/v1/runs/{run_id}/minutes/2026-01-01T00:01:00Z')
    assert state['original_verified'] and state['entered']
    assert expected == checksum(original) and checksum((workspace / name).read_bytes()) == checksum(changed)
    assert checksum(changed) != expected and state['manifest_reads'] == 0
    if response.status_code == 200:
        value = response.json()
        if name == 'channels.parquet': assert value['current'][0] == 12345.
        elif name == 'scores.parquet': assert value['point']['score'] == .75
        else: assert value['labels']['dos'] == 2
    assert_safe_failure(response, 'ARTIFACT_INVALID')
    assert state['kwargs']['expected_sha256'] == expected
    assert state['parser_called'] is False
    assert client.get(f'/api/v1/runs/{run_id}').json()['status'] == 'succeeded'


@pytest.mark.parametrize('mode,reason', [('missing', 'RESULT_MISSING'),
                                       ('io_error', 'ARTIFACT_INVALID'), ('short', 'ARTIFACT_INVALID')])
def test_post_hash_payload_acquisition_failures_have_safe_errors(completed_payload, monkeypatch, mode, reason):
    client, run_id, workspace = completed_payload
    original = (workspace / 'channels.parquet').read_bytes()
    def action(path):
        if mode == 'missing': path.unlink()
        elif mode == 'short': path.write_bytes(original[:len(original)//2])
        else: raise OSError('private/path credential: payload acquisition failed')
    state, _ = gated_reader_hook(monkeypatch, workspace, 'channels.parquet', action)
    response = client.get(f'/api/v1/runs/{run_id}/minutes/2026-01-01T00:01:00Z')
    assert state['original_verified'] and state['entered']
    assert_safe_failure(response, reason)
    assert state['manifest_reads'] == 0
    if mode == 'short': assert state['parser_called'] is False
    assert client.get(f'/api/v1/runs/{run_id}').json()['status'] == 'succeeded'


@pytest.mark.parametrize('name', tuple(PAYLOADS))
def test_single_payload_bytes_parse_via_buffer_even_if_path_changes_after_acquisition(completed_payload, tmp_path, monkeypatch, name):
    _, _, workspace = completed_payload
    target = workspace / name
    schema, model = PAYLOADS[name]
    original, changed = replacement_payload(workspace, name, tmp_path)
    original_rows = artifacts.read_rows(target, schema, model)
    original_read, original_open, original_parser = Path.read_bytes, Path.open, pq.read_table
    state = dict(captured=False, payload_reads=0, parser_calls=0, manifest_reads=0)
    def read_bytes(path):
        if path == workspace / 'manifest.json':
            state['manifest_reads'] += 1
            raise AssertionError('the row parser must not read a manifest')
        if path == target:
            assert state['payload_reads'] == 0
            data = original_read(path)
            assert data == original
            state['payload_reads'] += 1
            path.write_bytes(changed)
            state['captured'] = True
            return data
        return original_read(path)
    def open_path(path, *args, **kwargs):
        if path == target and state['captured']:
            raise AssertionError('do not reopen or hash the path after acquiring payload bytes')
        return original_open(path, *args, **kwargs)
    def parser(source, *args, **kwargs):
        assert isinstance(source, pa.BufferReader), 'Arrow must parse the exact in-memory bytes, not a path'
        assert state['captured']
        state['parser_calls'] += 1
        return original_parser(source, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    monkeypatch.setattr(Path, 'open', open_path)
    monkeypatch.setattr(pq, 'read_table', parser)
    # Preserve the old three-positional-argument setup API; no new keyword is
    # required to collect or run these tests against the pre-fix implementation.
    actual_rows = artifacts.read_rows(target, schema, model)
    assert actual_rows == original_rows
    assert state['payload_reads'] == state['parser_calls'] == 1
    assert state['manifest_reads'] == 0
