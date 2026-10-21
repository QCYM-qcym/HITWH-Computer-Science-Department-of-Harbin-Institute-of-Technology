from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from traffic_anomaly.contracts import ErrorResponse, RunStatus

from conftest import FIXTURE, submit, wait_terminal
from traffic_api.worker import FakeExecutor


def test_submit_completes_and_persists_config(client, fixture_data):
    run_id = submit(client, fixture_data)
    state = RunStatus.model_validate(wait_terminal(client, run_id))
    assert state.status == 'succeeded'
    assert state.evidence_kind == 'SYNTHETIC_ONLY'
    assert state.config.window_minutes == 1
    assert state.created_at <= state.started_at <= state.finished_at


class BlockingExecutor(FakeExecutor):
    def __init__(self):
        super().__init__(FIXTURE)
        self.started = Event()
        self.release = Event()

    def execute(self, config, workspace):
        self.started.set()
        assert self.release.wait(8)
        return super().execute(config, workspace)


def test_submission_does_not_block_and_busy_is_rejected(make_app, fixture_data):
    executor = BlockingExecutor()
    with TestClient(make_app(executor)) as client:
        try:
            run_id = submit(client, fixture_data)
            assert executor.started.wait(2)
            assert client.get(f'/api/v1/runs/{run_id}').json()['status'] == 'running'
            response = client.post('/api/v1/runs', json=fixture_data['request'])
            assert response.status_code == 409
            assert response.json()['error']['code'] == 'RUN_BUSY'
            for endpoint in ('series', 'alarms', 'evaluation', 'minutes/2026-01-01T00:01:00Z', 'exports/config'):
                response = client.get(f'/api/v1/runs/{run_id}/{endpoint}')
                assert response.status_code == 409
                assert response.json()['error']['code'] == 'RESULT_NOT_READY'
        finally:
            executor.release.set()


def test_concurrent_submissions_reserve_one_active_slot(make_app, fixture_data):
    executor = BlockingExecutor()
    with TestClient(make_app(executor)) as client:
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                responses = list(pool.map(lambda _: client.post('/api/v1/runs', json=fixture_data['request']), range(8)))
            assert sorted(r.status_code for r in responses) == [202] + [409] * 7
        finally:
            executor.release.set()


@pytest.mark.parametrize('patch', [
    {'method': 'unknown'}, {'config_id': 'unknown'}, {'split_id': 'unknown'},
    {'dataset_id': '../private'}, {'model': {'epochs': 1}}, {'config_id': 'private/file'},
])
def test_invalid_submission_has_safe_uniform_error(client, fixture_data, patch):
    response = client.post('/api/v1/runs', json=fixture_data['request'] | patch)
    assert response.status_code == 422
    assert ErrorResponse.model_validate(response.json()).error.code == 'VALIDATION_ERROR'
    assert 'private' not in response.text


def test_unknown_dataset_and_run(client, fixture_data):
    assert client.post('/api/v1/runs', json=fixture_data['request'] | {'dataset_id': 'unknown'}).status_code == 404
    for suffix in ('', '/series', '/evaluation', '/exports/config'):
        response = client.get('/api/v1/runs/unknown' + suffix)
        assert response.status_code == 404
        assert response.json()['error']['code'] == 'NOT_FOUND'


def test_executor_failure_is_safe_persistent_and_allows_retry(make_app, fixture_data):
    class Broken:
        def execute(self, config, workspace):
            raise RuntimeError('private/file traceback secret')
    with TestClient(make_app(Broken())) as client:
        first = submit(client, fixture_data)
        state = wait_terminal(client, first)
        assert state['status'] == 'failed'
        assert state['error']['code'] == 'EXECUTION_FAILED'
        assert 'private' not in str(state) and 'traceback' not in str(state)
        assert submit(client, fixture_data) != first


def test_datasets_match_unified_fixture(client, fixture_data):
    expected = next(r['body'] for r in fixture_data['responses'] if r['schema'] == 'DatasetList')
    assert client.get('/api/v1/datasets').json() == expected


def test_framework_errors_do_not_echo_request_or_exceptions(client):
    for method, url, kwargs, status in [
        ('post', '/api/v1/runs', {'content': '{private/path'}, 422),
        ('get', '/unknown', {}, 404),
        ('delete', '/api/v1/runs/unknown', {}, 405),
    ]:
        response = client.request(method, url, **kwargs)
        assert response.status_code == status
        ErrorResponse.model_validate(response.json())
        assert 'private' not in response.text


def test_fatal_executor_exit_finishes_task_and_keeps_worker_available(make_app, fixture_data):
    class ExitsOnce(FakeExecutor):
        def __init__(self):
            super().__init__(FIXTURE)
            self.exited = False
        def execute(self, config, workspace):
            if not self.exited:
                self.exited = True
                raise SystemExit('private fatal path')
            return super().execute(config, workspace)
    with TestClient(make_app(ExitsOnce())) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'failed'
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'


@pytest.mark.parametrize('reason', ['DATASET_UNAVAILABLE', 'MODEL_NOT_FOUND'])
def test_expected_execution_failure_reasons_are_distinct(make_app, fixture_data, reason):
    # ExecutionFailure is an internal trusted reason whitelist, not str(exc).
    from traffic_api.schemas import ExecutionFailure
    class Missing:
        def execute(self, config, workspace):
            raise ExecutionFailure(reason)
    with TestClient(make_app(Missing())) as client:
        state = wait_terminal(client, submit(client, fixture_data))
        assert state['status'] == 'failed'
        assert state['error']['code'] == 'EXECUTION_FAILED'
        assert state['error']['details'] == [reason]
