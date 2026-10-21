import json
from pathlib import Path
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient

from traffic_api.app import create_app
from traffic_api.schemas import Settings
from traffic_api.worker import FakeExecutor

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/contracts-v1.json'


@pytest.fixture
def fixture_data():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


@pytest.fixture
def settings(tmp_path):
    return Settings(database=tmp_path / 'tasks.sqlite3', output=tmp_path / 'runs')


@pytest.fixture
def make_app(settings):
    def build(executor=None):
        return create_app(settings, fixture_path=FIXTURE, executor=executor)
    return build


@pytest.fixture
def client(make_app):
    with TestClient(make_app()) as client:
        yield client


def wait_terminal(client, run_id):
    deadline = monotonic() + 8
    while monotonic() < deadline:
        response = client.get(f'/api/v1/runs/{run_id}')
        assert response.status_code == 200, response.text
        status = response.json()
        if status['status'] in ('succeeded', 'failed'):
            return status
        sleep(0.01)
    pytest.fail('worker did not reach a terminal state')


def submit(client, fixture_data):
    response = client.post('/api/v1/runs', json=fixture_data['request'])
    assert response.status_code == 202, response.text
    return response.json()['run_id']
