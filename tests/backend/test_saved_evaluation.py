"""Saved aggregate evaluation must match stored predictions and aligned labels.

The frozen interval examples have a separately known semantic difference. This
batch neither changes them nor claims to verify interval-only inconsistencies.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from traffic_anomaly import contracts as c
from traffic_api.artifacts import LABEL_SCHEMA, SCORE_SCHEMA, read_rows
from traffic_api.worker import FakeExecutor

from .conftest import FIXTURE, submit, wait_terminal
from .test_artifacts import rewrite_manifest


AGGREGATES = ('available', 'metrics', 'normal_coverage', 'attack_coverage',
              'excluded_attack_minutes', 'background_only_minutes')


def read_json(path): return json.loads(path.read_text('utf-8'))
def write_json(path, value): path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')


def changed_aggregate(evaluation, mode):
    value = deepcopy(evaluation)
    if mode == 'available':
        value.update(available=False, metrics=None, reason='False unavailable saved claim')
    elif mode == 'metrics':
        value['metrics'] = dict(tp=1, fp=0, tn=2, fn=0,
            precision=1., recall=1., f1=1., fpr=0., undefined_reasons=[])
    elif mode == 'normal_coverage':
        value['normal_coverage']['total'] = 3
    elif mode == 'attack_coverage':
        value['attack_coverage']['total'] = 3
        value['excluded_attack_minutes'] = 2
    elif mode == 'excluded_attack_minutes':
        value['attack_coverage']['total'] = 1
        value['excluded_attack_minutes'] = 0
    elif mode == 'background_only_minutes':
        value['background_only_minutes'] = 1
    else:
        raise AssertionError(mode)
    # Each contradiction passes the contract's own arithmetic/coverage checks.
    c.Evaluation.model_validate(value)
    return value


def replace_labels(workspace, mode):
    path = workspace / 'labels.parquet'
    table = pq.read_table(path)
    stamps = table['timestamp'].cast(pa.int64()).to_pylist()
    rows = [dict(row, timestamp=stamp) for row, stamp in zip(table.drop(['timestamp']).to_pylist(), stamps)]
    day_ns = 86400 * 1_000_000_000
    if mode == 'unmatched_timestamps':
        for row in rows: row['timestamp'] += day_ns
    elif mode == 'missing_attack_minute': rows.pop(1)
    elif mode == 'empty_labels': rows = []
    elif mode == 'background_change': rows[2]['blacklist'] = 1
    elif mode in ('no_attacks', 'no_normals', 'all_background'):
        for row in rows:
            for name in c.LABEL_NAMES: row[name] = 0
            if mode == 'no_normals': row['dos'] = 1
            if mode == 'all_background': row['blacklist'] = 1
    elif mode == 'extra_unmatched_row':
        extra = dict(rows[-1], timestamp=rows[-1]['timestamp'] + day_ns, dos=1)
        rows.append(extra)
    else: raise AssertionError(mode)
    pq.write_table(pa.Table.from_pylist(rows, schema=LABEL_SCHEMA), path)
    rewrite_manifest(workspace, 'labels.parquet')


def recompute_aggregates_for_legitimate_saved_case(workspace):
    """Build temporary positive cases; preserve all unrelated saved prose/intervals."""
    from traffic_anomaly.evaluation.metrics import evaluate
    series = read_rows(workspace / 'scores.parquet', SCORE_SCHEMA, c.SeriesPoint)
    rows = read_rows(workspace / 'labels.parquet', LABEL_SCHEMA, c.LabelRow) if (workspace / 'labels.parquet').exists() else []
    labels = None if not rows else c.LabelBatch(
        np.array([r.timestamp.removesuffix('Z') for r in rows], dtype='datetime64[ns]'),
        {name: np.array([getattr(r, name) for r in rows], dtype=np.int64) for name in c.LABEL_NAMES})
    saved = read_json(workspace / 'metrics.json')
    measured = evaluate(saved['run_id'], saved['evidence_kind'],
        np.array([r.timestamp.removesuffix('Z') for r in series], dtype='datetime64[ns]'),
        np.array([r.valid for r in series], dtype=bool),
        np.array([False if r.alarm is None else r.alarm for r in series], dtype=bool), labels)
    calculated = measured.model_dump(mode='json')
    saved.update({field: calculated[field] for field in AGGREGATES})
    saved['reason'] = None if saved['available'] else 'Saved explanation must be preserved'
    c.Evaluation.model_validate(saved)
    write_json(workspace / 'metrics.json', saved)
    rewrite_manifest(workspace, 'metrics.json')
    return saved


@pytest.mark.parametrize('mode', AGGREGATES)
def test_schema_valid_but_false_saved_aggregates_fail_worker_and_all_result_queries(make_app, fixture_data, mode):
    original = next(r['body'] for r in fixture_data['responses'] if r['schema'] == 'Evaluation')
    changed_aggregate(original, mode)
    class Broken(FakeExecutor):
        def execute(self, config, workspace):
            result = super().execute(config, workspace)
            write_json(workspace / 'metrics.json', changed_aggregate(read_json(workspace / 'metrics.json'), mode))
            rewrite_manifest(workspace, 'metrics.json')
            return result
    with TestClient(make_app(Broken(FIXTURE))) as client:
        run_id = submit(client, fixture_data)
        status = wait_terminal(client, run_id)
        assert status['status'] == 'failed'
        assert status['error']['code'] == 'EXECUTION_FAILED'
        for suffix in ('series', 'alarms', 'evaluation', 'exports/metrics'):
            response = client.get(f'/api/v1/runs/{run_id}/{suffix}')
            assert response.status_code == 409
            assert response.json()['error']['code'] == 'RESULT_NOT_READY'


@pytest.mark.parametrize('mode', ['unmatched_timestamps', 'missing_attack_minute', 'empty_labels', 'background_change'])
def test_resealed_labels_must_align_with_scores_for_saved_aggregate_claims(make_app, fixture_data, mode):
    class BrokenLabels(FakeExecutor):
        changed = False
        def execute(self, config, workspace):
            result = super().execute(config, workspace)
            replace_labels(workspace, mode)
            self.changed = True
            return result
    executor = BrokenLabels(FIXTURE)
    with TestClient(make_app(executor)) as client:
        run_id = submit(client, fixture_data)
        status = wait_terminal(client, run_id)
        assert executor.changed, 'the synthetic label mutation must finish before validation'
        assert status['status'] == 'failed' and status['error']['code'] == 'EXECUTION_FAILED'
        assert client.get(f'/api/v1/runs/{run_id}/evaluation').status_code == 409


@pytest.mark.parametrize('mode', ['metrics', 'normal_coverage'])
def test_resealed_post_success_corruption_is_rejected_when_serving_results(client, fixture_data, settings, mode):
    run_id = submit(client, fixture_data)
    assert wait_terminal(client, run_id)['status'] == 'succeeded'
    workspace = settings.output / run_id
    write_json(workspace / 'metrics.json', changed_aggregate(read_json(workspace / 'metrics.json'), mode))
    rewrite_manifest(workspace, 'metrics.json')
    for suffix in ('evaluation', 'series', 'exports/metrics'):
        response = client.get(f'/api/v1/runs/{run_id}/{suffix}')
        assert response.status_code == 500
        assert response.json()['error']['code'] == 'EXECUTION_FAILED'
        assert response.json()['error']['details'] == ['ARTIFACT_INVALID']
        assert 'Traceback' not in response.text and str(workspace) not in response.text


def test_original_fixture_is_returned_with_original_intervals_and_unavailable_reason(client, fixture_data):
    run_id = submit(client, fixture_data)
    assert wait_terminal(client, run_id)['status'] == 'succeeded'
    expected = deepcopy(next(r['body'] for r in fixture_data['responses'] if r['schema'] == 'Evaluation'))
    expected['run_id'] = run_id
    response = client.get(f'/api/v1/runs/{run_id}/evaluation')
    assert response.status_code == 200 and response.json() == expected
    assert [interval['kind'] for interval in response.json()['intervals']] == ['missed_attack', 'false_positive']
    assert response.json()['high_load_unavailable_reason'] == 'Protocol counts have not been verified'


@pytest.mark.parametrize('mode', ['no_labels', 'no_attacks', 'no_normals', 'all_background', 'extra_unmatched_row'])
def test_legitimate_zero_denominators_and_label_absence_preserve_saved_values(make_app, fixture_data, mode):
    captured = {}
    class Legitimate(FakeExecutor):
        def execute(self, config, workspace):
            result = super().execute(config, workspace)
            if mode == 'no_labels':
                (workspace / 'labels.parquet').unlink()
                manifest = read_json(workspace / 'manifest.json')
                manifest['files'] = [entry for entry in manifest['files'] if entry['path'] != 'labels.parquet']
                write_json(workspace / 'manifest.json', manifest)
                summary = read_json(workspace / 'summary.json'); summary['labels_available'] = False
                write_json(workspace / 'summary.json', summary)
                rewrite_manifest(workspace, 'summary.json')
            else: replace_labels(workspace, mode)
            captured['evaluation'] = recompute_aggregates_for_legitimate_saved_case(workspace)
            return result
    with TestClient(make_app(Legitimate(FIXTURE))) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        response = client.get(f'/api/v1/runs/{run_id}/evaluation')
        assert response.status_code == 200 and response.json() == captured['evaluation']
        value = response.json()
        if mode in ('no_labels', 'all_background'):
            assert value['available'] is False and value['metrics'] is None
            assert value['reason'] == 'Saved explanation must be preserved'
        elif mode == 'no_attacks':
            assert value['metrics']['recall'] is None and 'recall' in value['metrics']['undefined_reasons']
            assert value['normal_coverage'] == dict(eligible=3, total=4)
        elif mode == 'no_normals':
            assert value['metrics']['fpr'] is None and 'fpr' in value['metrics']['undefined_reasons']
            assert value['attack_coverage'] == dict(eligible=3, total=4)
        else:
            assert value['attack_coverage'] == dict(eligible=1, total=2)
        if mode == 'all_background': assert value['background_only_minutes'] == 4


def test_fresh_fake_worker_validation_and_serving_import_no_models_or_spawn_processes(tmp_path):
    code = '''
import builtins, json, pathlib, subprocess, sys, time
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('torch','sklearn','joblib'):
        raise AssertionError('saved aggregate validation imported a model runtime')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from fastapi.testclient import TestClient
from traffic_api.app import create_app
from traffic_api.schemas import Settings
def forbidden_process(*args, **kwargs):
    raise AssertionError('aggregate checking must not launch another process')
subprocess.Popen.__init__ = forbidden_process
fixture = pathlib.Path(sys.argv[1]); base = pathlib.Path(sys.argv[2])
data = json.loads(fixture.read_text('utf-8'))
with TestClient(create_app(Settings(database=base/'tasks.sqlite3',output=base/'runs'),fixture_path=fixture)) as client:
    submitted = client.post('/api/v1/runs',json=data['request'])
    assert submitted.status_code == 202
    run_id = submitted.json()['run_id']; deadline = time.monotonic()+8
    while True:
        status = client.get('/api/v1/runs/'+run_id).json()
        if status['status'] in ('succeeded','failed'): break
        assert time.monotonic() < deadline
        time.sleep(.01)
    assert status['status'] == 'succeeded'
    evaluation = client.get('/api/v1/runs/'+run_id+'/evaluation')
    assert evaluation.status_code == 200 and evaluation.json()['metrics']['fp'] == 1
assert not any(name in sys.modules for name in ('torch','sklearn','joblib'))
'''
    completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', code, str(FIXTURE), str(tmp_path)],
        capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert completed.returncode == 0, completed.stderr
