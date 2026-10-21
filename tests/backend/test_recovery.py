import json

import pytest
from fastapi.testclient import TestClient
from filelock import Timeout
from traffic_anomaly.contracts import RunConfig, can_transition

from conftest import submit, wait_terminal
from traffic_api.repository import Repository


def test_running_is_failed_and_queued_is_resumed(make_app, settings, fixture_data):
    repo = Repository(settings.database)
    config = RunConfig(**{k: fixture_data['request'][k] for k in ('dataset_id', 'split_id', 'method')}, window_minutes=1)
    repo.create('interrupted', config, 'SYNTHETIC_ONLY')
    repo.transition('interrupted', 'running')
    with TestClient(make_app()) as client:
        status = client.get('/api/v1/runs/interrupted').json()
        assert status['status'] == 'failed'
        assert status['error']['code'] == 'WORKER_INTERRUPTED'
        fresh = submit(client, fixture_data)
        assert wait_terminal(client, fresh)['status'] == 'succeeded'
    repo.create('queued-run', config, 'SYNTHETIC_ONLY')
    with TestClient(make_app()) as client:
        assert wait_terminal(client, 'queued-run')['status'] == 'succeeded'


def test_completed_results_survive_service_restart(make_app, fixture_data):
    with TestClient(make_app()) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        before = client.get(f'/api/v1/runs/{run_id}/series').json()
    with TestClient(make_app()) as client:
        assert client.get(f'/api/v1/runs/{run_id}/series').json() == before


def test_only_one_service_can_own_database(make_app):
    with TestClient(make_app()):
        with pytest.raises(Timeout):
            with TestClient(make_app()):
                pytest.fail('second worker acquired same database')


def test_terminal_state_cannot_regress(settings, fixture_data):
    repo = Repository(settings.database)
    config = RunConfig(**{k: fixture_data['request'][k] for k in ('dataset_id', 'split_id', 'method')})
    repo.create('terminal', config, 'SYNTHETIC_ONLY')
    repo.transition('terminal', 'running')
    repo.transition('terminal', 'succeeded')
    with pytest.raises(ValueError):
        repo.transition('terminal', 'running')
    assert repo.get('terminal')['status'] == 'succeeded'


def test_worker_recovers_from_transient_queue_and_failure_write_errors(make_app, fixture_data, monkeypatch):
    import sqlite3
    from traffic_api.worker import FakeExecutor
    from conftest import FIXTURE
    class Broken:
        def execute(self, config, workspace):
            raise RuntimeError('synthetic execution failed')
    app = make_app(Broken())
    repo = app.state.service.repository
    original_queue, original_transition = repo.queued, repo.transition
    failures = {'queue': 1, 'write': 1}
    def queued():
        if failures['queue']:
            failures['queue'] -= 1
            raise sqlite3.OperationalError('transient queue read')
        return original_queue()
    def transition(run_id, following, **kwargs):
        if following == 'failed' and failures['write']:
            failures['write'] -= 1
            raise sqlite3.OperationalError('transient failure write')
        return original_transition(run_id, following, **kwargs)
    monkeypatch.setattr(repo, 'queued', queued)
    monkeypatch.setattr(repo, 'transition', transition)
    with TestClient(app) as client:
        # The transient queue failure is retried; the same queued task stays durable.
        from time import monotonic, sleep
        deadline = monotonic() + 3
        while not app.state.service.worker.available.is_set() and monotonic() < deadline:
            sleep(0.01)
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'failed'


def test_dead_worker_does_not_accept_new_tasks(make_app, fixture_data):
    app = make_app()
    with TestClient(app) as client:
        app.state.service.worker.close()
        response = client.post('/api/v1/runs', json=fixture_data['request'])
        assert response.status_code == 500
        assert response.json()['error']['code'] == 'EXECUTION_FAILED'
