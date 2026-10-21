"""Failure injection is synthetic plumbing evidence, never model evidence."""
import json
from pathlib import Path
from threading import Event
from time import monotonic, sleep

from fastapi.testclient import TestClient
from traffic_anomaly.contracts import RunConfig
from traffic_anomaly.synthetic import create_demo_workspace
from traffic_api.app import create_app
from traffic_api.core_executor import CoreRegistration
from traffic_api.schemas import Settings

ROOT = Path(__file__).resolve().parents[2]


def terminal(client, run_id):
    deadline = monotonic() + 20
    while monotonic() < deadline:
        status = client.get('/api/v1/runs/' + run_id).json()
        if status['status'] in ('succeeded', 'failed'):
            return status
        sleep(.02)
    raise AssertionError('synthetic task did not finish')


def test_busy_failure_sanitization_and_core_retry(tmp_path):
    source = tmp_path / 'input'
    create_demo_workspace(source)
    config = RunConfig.model_validate_json((ROOT / 'configs/core/smoke.example.json').read_bytes())
    entered, release = Event(), Event()

    class FailOnce(CoreRegistration):
        first = True

        def execute(self, config, workspace):
            if self.first:
                self.first = False
                entered.set()
                assert release.wait(5)
                raise RuntimeError('PRIVATE_PATH_SENTINEL secret diagnostics')
            return super().execute(config, workspace)

    registration = FailOnce(source, config, config_id='smoke-v1')
    settings = Settings(database=tmp_path / 'tasks.sqlite3', output=tmp_path / 'output')
    app = create_app(settings, fixture_path=ROOT / 'tests/fixtures/contracts-v1.json', registration=registration)
    request = registration.request.model_dump()
    with TestClient(app) as client:
        first = client.post('/api/v1/runs', json=request).json()['run_id']
        assert entered.wait(5)
        try:
            assert client.post('/api/v1/runs', json=request).status_code == 409
            assert client.get(f'/api/v1/runs/{first}/series').status_code == 409
        finally:
            release.set()
        status = terminal(client, first)
        assert status['status'] == 'failed'
        assert 'PRIVATE_PATH_SENTINEL' not in json.dumps(status)
        assert status['error']['code'] == 'EXECUTION_FAILED'
        assert client.post('/api/v1/runs', json={}).status_code == 422
        assert client.get('/api/v1/runs/missing').status_code == 404
        second = client.post('/api/v1/runs', json=request).json()['run_id']
        assert second != first
        assert terminal(client, second)['status'] == 'succeeded'
