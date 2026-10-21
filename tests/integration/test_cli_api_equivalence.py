"""SYNTHETIC_ONLY: CLI, persisted worker and HTTP share complete artifacts."""
import io
import json
from pathlib import Path
import subprocess
import sys
import time

import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from traffic_anomaly.contracts import RunConfig
from traffic_anomaly.synthetic import create_demo_workspace
from traffic_api.app import create_app
from traffic_api.schemas import Settings

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/contracts-v1.json'


@pytest.mark.parametrize('method', ['iforest', 'current_ae', 'history_ae'])
def test_cli_http_full_artifact_equivalence(tmp_path, method):
    from traffic_api.core_executor import CoreRegistration
    source = tmp_path / 'source'
    create_demo_workspace(source)
    raw = json.loads((ROOT / 'configs/core/smoke.example.json').read_text())
    raw['method'] = method
    config = RunConfig.model_validate(raw)
    path = tmp_path / 'config.json'
    path.write_text(config.model_dump_json())
    settings = Settings(database=tmp_path / 'tasks.sqlite3', output=tmp_path / 'output')
    registration = CoreRegistration(source, config, config_id='smoke-v1')
    app = create_app(settings, fixture_path=FIXTURE, registration=registration)
    with TestClient(app) as client:
        datasets = client.get('/api/v1/datasets').json()['items']
        assert datasets[0]['dataset_id'] == config.dataset_id
        request = dict(dataset_id=config.dataset_id, split_id=config.split_id,
                       method=method, config_id='smoke-v1')
        response = client.post('/api/v1/runs', json=request)
        assert response.status_code == 202, response.text
        run_id = response.json()['run_id']
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = client.get(f'/api/v1/runs/{run_id}').json()
            if status['status'] in ('succeeded', 'failed'):
                break
            time.sleep(.02)
        assert status['status'] == 'succeeded', status
        # A separate CLI workspace uses the exact accepted API execution ID.
        cli = subprocess.run([sys.executable, '-m', 'traffic_anomaly.cli', 'run',
            '--workspace', str(source), '--config', str(path), '--run-id', run_id],
            capture_output=True, text=True, check=True)
        result = json.loads(cli.stdout)
        assert result['run_id'] == run_id
        expected_root = (source / result['manifest_path']).parent
        base = f'/api/v1/runs/{run_id}'
        series = client.get(base + '/series?page_size=1000').json()
        assert series['run_id'] == run_id
        assert series['total'] == 40
        exported = client.get(base + '/exports/scores')
        table = pq.read_table(io.BytesIO(exported.content))
        expected = pq.read_table(expected_root / 'scores.parquet')
        assert table.equals(expected)
        # Keep Arrow's UTC nanoseconds; Windows has no bundled IANA tzdata.
        rows = table.drop(['timestamp']).to_pylist()
        assert [r['score'] for r in series['items']] == [r['score'] for r in rows]
        assert [r['alarm'] for r in series['items']] == [r['alarm'] for r in rows]
        assert [r['valid'] for r in series['items']] == [r['valid'] for r in rows]
        assert sum(r['valid'] for r in rows) == 37
        assert all(r['score'] is None and r['alarm'] is None for r in rows[:3])
        alarm_rows = client.get(base + '/alarms?page_size=1000').json()
        assert alarm_rows['items'] == [r for r in series['items'] if r['valid'] and r['alarm']]
        evaluation = client.get(base + '/evaluation').json()
        metrics = client.get(base + '/exports/metrics').json()
        expected_metrics = json.loads((expected_root / 'metrics.json').read_text())
        assert evaluation == metrics
        assert metrics['run_id'] == run_id
        assert metrics == expected_metrics
        assert client.get(base + '/series?page_size=2').json()['total'] == 40
        assert client.get(base + '/evaluation').json() == evaluation
        assert client.get(base + '/exports/config').json() == config.model_dump(mode='json')
        detail = client.get(base + '/minutes/' + series['items'][5]['timestamp']).json()
        assert detail['run_id'] == run_id
        assert len(detail['current']) == len(detail['history_residual']) == 134
        assert (detail['reconstruction_error_current'] is None) == (method == 'iforest')
        assert (detail['reconstruction_error_history'] is not None) == (method == 'history_ae')
        assert client.get(base + '/exports/weights').status_code == 422
        assert client.get(base + '/series', params={'start': '2026-01-01T02:10:00Z', 'end': '2026-01-01T02:00:00Z'}).status_code == 422
        assert client.get(base + '/series', params={'start': '2027-01-01T00:00:00Z'}).json()['total'] == 0
    # Saved outputs remain readable after worker/service restart.
    with TestClient(create_app(settings, fixture_path=FIXTURE, registration=registration)) as client:
        assert client.get(base).json()['status'] == 'succeeded'
        assert client.get(base + '/exports/scores').content == exported.content


def test_explicit_id_rejects_traversal_and_collision_before_execution(tmp_path):
    from traffic_anomaly.pipeline import execute_run
    source = tmp_path / 'source'
    create_demo_workspace(source)
    config = RunConfig.model_validate_json((ROOT / 'configs/core/smoke.example.json').read_bytes())
    with pytest.raises(ValueError):
        execute_run(config, source, run_id='../escape')
    (source / 'runs/occupied').mkdir(parents=True)
    with pytest.raises(FileExistsError):
        execute_run(config, source, run_id='occupied')


def test_core_registration_cannot_enable_real_data(tmp_path):
    from traffic_api.core_executor import CoreRegistration
    create_demo_workspace(tmp_path)
    path = tmp_path / 'registry.json'
    registry = json.loads(path.read_text())
    registry['datasets']['synthetic-w1']['evidence_kind'] = 'REAL_DATA'
    path.write_text(json.dumps(registry))
    config = RunConfig.model_validate_json((ROOT / 'configs/core/smoke.example.json').read_bytes())
    with pytest.raises(ValueError, match='synthetic'):
        CoreRegistration(tmp_path, config, config_id='smoke-v1')
