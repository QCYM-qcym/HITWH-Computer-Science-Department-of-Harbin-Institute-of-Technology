"""Exact saved producer interval consistency, separately from aggregate checks."""
from copy import deepcopy

from fastapi.testclient import TestClient
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from traffic_anomaly import contracts as c
from traffic_api.artifacts import CHANNEL_SCHEMA, LABEL_SCHEMA, SCORE_SCHEMA
from traffic_api.worker import FakeExecutor

from .conftest import FIXTURE, submit, wait_terminal
from .test_artifacts import rewrite_manifest
from .test_saved_evaluation import (
    AGGREGATES, read_json, write_json, recompute_aggregates_for_legitimate_saved_case,
)


def episode(kind, start, end, count):
    return dict(kind=kind, start=f'2026-01-01T00:{start:02}:00Z',
                end=f'2026-01-01T00:{end:02}:00Z', minute_count=count)


def corrupted_intervals(original, mode):
    result = deepcopy(original)
    missed = next(value for value in result['intervals'] if value['kind'] == 'missed_attack')
    if mode == 'extent': missed.update(start='2026-01-01T00:01:00Z', minute_count=1)
    elif mode == 'count': missed['minute_count'] = 1
    elif mode == 'deleted': result['intervals'].remove(missed)
    elif mode == 'duplicate': result['intervals'].append(deepcopy(missed))
    elif mode == 'extra': result['intervals'].append(episode('false_positive', 3, 4, 1))
    elif mode == 'reordered': result['intervals'].reverse()
    else: raise AssertionError(mode)
    c.Evaluation.model_validate(result)
    assert {field: result[field] for field in AGGREGATES} == {field: original[field] for field in AGGREGATES}
    return result


def replace_metrics(workspace, mode):
    write_json(workspace / 'metrics.json', corrupted_intervals(read_json(workspace / 'metrics.json'), mode))
    rewrite_manifest(workspace, 'metrics.json')


@pytest.mark.parametrize('mode', ['extent', 'count', 'deleted', 'duplicate', 'extra', 'reordered'])
def test_schema_valid_resealed_interval_only_mismatch_cannot_complete(make_app, fixture_data, mode):
    original = next(row['body'] for row in fixture_data['responses'] if row['schema'] == 'Evaluation')
    corrupted_intervals(original, mode)
    class BrokenIntervals(FakeExecutor):
        def execute(self, config, workspace):
            result = super().execute(config, workspace)
            replace_metrics(workspace, mode)
            return result
    with TestClient(make_app(BrokenIntervals(FIXTURE))) as client:
        run_id = submit(client, fixture_data)
        status = wait_terminal(client, run_id)
        assert status['status'] == 'failed' and status['error']['code'] == 'EXECUTION_FAILED'
        for suffix in ('series', 'evaluation', 'exports/metrics'):
            assert client.get(f'/api/v1/runs/{run_id}/{suffix}').status_code == 409


@pytest.mark.parametrize('mode', ['extent', 'reordered'])
def test_post_success_interval_corruption_is_not_returned_or_exported(client, fixture_data, settings, mode):
    run_id = submit(client, fixture_data)
    assert wait_terminal(client, run_id)['status'] == 'succeeded'
    workspace = settings.output / run_id
    replace_metrics(workspace, mode)
    for suffix in ('evaluation', 'series', 'exports/metrics'):
        response = client.get(f'/api/v1/runs/{run_id}/{suffix}')
        assert response.status_code == 500
        assert response.json()['error']['code'] == 'EXECUTION_FAILED'
        assert response.json()['error']['details'] == ['ARTIFACT_INVALID']
        assert str(workspace) not in response.text and 'Traceback' not in response.text


def parquet_rows(workspace, name):
    table = pq.read_table(workspace / name)
    stamps = table['timestamp'].cast(pa.int64()).to_pylist()
    return [dict(row, timestamp=stamp) for row, stamp in zip(table.drop(['timestamp']).to_pylist(), stamps)]


def write_rows(workspace, name, rows, schema):
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), workspace / name)
    rewrite_manifest(workspace, name)


def coherent_case(workspace, mode):
    points = parquet_rows(workspace, 'scores.parquet')
    channels = parquet_rows(workspace, 'channels.parquet')
    labels = parquet_rows(workspace, 'labels.parquet')
    summary = read_json(workspace / 'summary.json')
    if mode == 'all_unscored':
        for row in points:
            row.update(score=None, threshold=None, alarm=None, valid=False,
                       invalid_reason='warmup', flow_count=None)
    elif mode == 'partial_hit': labels[2]['dos'] = 1
    elif mode == 'gap':
        points, channels, labels = ([rows[index] for index in (1, 3)] for rows in (points, channels, labels))
        labels[1]['dos'] = 1
    elif mode == 'unknown_label':
        points[0].update(score=.25, threshold=1., alarm=False, valid=True, invalid_reason=None)
        points[2].update(score=1., threshold=1., alarm=False)
        labels[2]['dos'] = 1
        labels.pop(1)
    elif mode == 'no_labels':
        (workspace / 'labels.parquet').unlink()
        manifest = read_json(workspace / 'manifest.json')
        manifest['files'] = [entry for entry in manifest['files'] if entry['path'] != 'labels.parquet']
        write_json(workspace / 'manifest.json', manifest)
        summary['labels_available'] = False
    elif mode == 'empty_axis': points, channels, labels = [], [], []
    elif mode != 'invalid_prefix': raise AssertionError(mode)
    write_rows(workspace, 'scores.parquet', points, SCORE_SCHEMA)
    write_rows(workspace, 'channels.parquet', channels, CHANNEL_SCHEMA)
    if mode != 'no_labels': write_rows(workspace, 'labels.parquet', labels, LABEL_SCHEMA)
    summary.update(row_count=len(points), valid_count=sum(row['valid'] for row in points))
    write_json(workspace / 'summary.json', summary)
    rewrite_manifest(workspace, 'summary.json')
    return recompute_aggregates_for_legitimate_saved_case(workspace)


@pytest.mark.parametrize('mode', ['invalid_prefix', 'all_unscored', 'partial_hit', 'gap', 'unknown_label', 'no_labels', 'empty_axis'])
def test_valid_raw_episode_extents_and_pointwise_denominators_are_preserved(make_app, fixture_data, mode):
    captured = {}
    class Legitimate(FakeExecutor):
        def execute(self, config, workspace):
            result = super().execute(config, workspace)
            captured['evaluation'] = coherent_case(workspace, mode)
            return result
    with TestClient(make_app(Legitimate(FIXTURE))) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        response = client.get(f'/api/v1/runs/{run_id}/evaluation')
        assert response.status_code == 200 and response.json() == captured['evaluation']
        value = response.json()
        if mode == 'invalid_prefix':
            expected = [episode('false_positive', 2, 3, 1), episode('missed_attack', 0, 2, 2)]
            assert value['metrics']['fn'] == 1 and value['excluded_attack_minutes'] == 1
        elif mode == 'all_unscored':
            expected = [episode('missed_attack', 0, 2, 2)]
            assert value['metrics']['fn'] == 0 and value['excluded_attack_minutes'] == 2
            assert value['metrics']['recall'] is None
        elif mode == 'partial_hit':
            expected = []
            assert value['metrics']['tp'] == 1 and value['metrics']['fn'] == 1
        elif mode == 'gap':
            expected = [episode('missed_attack', 1, 2, 1), episode('missed_attack', 3, 4, 1)]
            assert value['metrics']['fn'] == 2
        elif mode == 'unknown_label':
            expected = [episode('missed_attack', 0, 1, 1), episode('missed_attack', 2, 3, 1)]
            assert value['metrics']['fn'] == 2 and value['normal_coverage']['total'] == 1
        else:
            expected = []
            assert value['available'] is False and value['metrics'] is None
            assert value['reason'] == 'Saved explanation must be preserved'
        assert value['intervals'] == expected
        assert value['high_load_unavailable_reason'] == 'Protocol counts have not been verified'


@pytest.mark.parametrize('mode', ['no_labels', 'empty_axis'])
def test_unavailable_empty_evaluation_cannot_claim_fabricated_intervals(make_app, fixture_data, mode):
    class Fabricated(FakeExecutor):
        def execute(self, config, workspace):
            result = super().execute(config, workspace)
            saved = coherent_case(workspace, mode)
            saved['intervals'] = [episode('missed_attack', 0, 1, 1)]
            c.Evaluation.model_validate(saved)
            write_json(workspace / 'metrics.json', saved)
            rewrite_manifest(workspace, 'metrics.json')
            return result
    with TestClient(make_app(Fabricated(FIXTURE))) as client:
        run_id = submit(client, fixture_data)
        status = wait_terminal(client, run_id)
        assert status['status'] == 'failed' and status['error']['code'] == 'EXECUTION_FAILED'


def test_each_saved_load_evaluates_once_and_keeps_response_and_export_bytes(client, fixture_data, settings, monkeypatch):
    from traffic_api import artifacts
    run_id = submit(client, fixture_data)
    assert wait_terminal(client, run_id)['status'] == 'succeeded'
    path = settings.output / run_id / 'metrics.json'
    before = path.read_bytes(), path.stat().st_mtime_ns
    actual = artifacts.evaluate
    calls = []
    def counted(*args, **kwargs):
        calls.append(True)
        return actual(*args, **kwargs)
    monkeypatch.setattr(artifacts, 'evaluate', counted)
    response = client.get(f'/api/v1/runs/{run_id}/evaluation')
    assert response.status_code == 200 and response.json() == read_json(path)
    assert len(calls) == 1
    export = client.get(f'/api/v1/runs/{run_id}/exports/metrics')
    assert export.status_code == 200 and export.content == before[0]
    assert len(calls) == 2
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
