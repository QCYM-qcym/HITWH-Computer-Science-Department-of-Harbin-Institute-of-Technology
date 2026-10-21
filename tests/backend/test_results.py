from io import BytesIO
import json

import pyarrow.parquet as pq
import pytest
from traffic_anomaly import contracts as c

from conftest import submit, wait_terminal


@pytest.fixture
def completed(client, fixture_data):
    run_id = submit(client, fixture_data)
    assert wait_terminal(client, run_id)['status'] == 'succeeded'
    return run_id


def test_series_pagination_range_and_alarms(client, completed, fixture_data):
    base = f'/api/v1/runs/{completed}'
    rows = next(r['body']['items'] for r in fixture_data['responses'] if r['schema'] == 'SeriesPage')
    response = client.get(base + '/series', params={'page': 2, 'page_size': 2})
    page = c.SeriesPage.model_validate(response.json())
    assert page.total == 4 and [p.model_dump() for p in page.items] == rows[2:]
    page = client.get(base + '/series', params={'start': rows[1]['timestamp'], 'end': rows[3]['timestamp']}).json()
    assert page['total'] == 2 and page['items'] == rows[1:3]
    alarms = client.get(base + '/alarms', params={'page_size': 1}).json()
    assert alarms['total'] == 1 and alarms['items'] == [rows[2]]
    assert client.get(base + '/alarms', params={'page': 2, 'page_size': 1}).json()['items'] == []
    assert client.get(base + '/series', params={'start': '2027-01-01T00:00:00Z'}).json()['total'] == 0


@pytest.mark.parametrize('params', [
    {'page': 0}, {'page_size': 1001}, {'page': 'bad'}, {'start': '2026-02-30T00:00:00Z'},
    {'start': '2026-01-01T00:00:01Z'}, {'end': 'private'},
    {'start': '2026-01-02T00:00:00Z', 'end': '2026-01-01T00:00:00Z'},
])
def test_invalid_queries(client, completed, params):
    response = client.get(f'/api/v1/runs/{completed}/series', params=params)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'
    assert 'private' not in response.text


def test_evaluation_and_minute_are_saved_fixture_values(client, completed, fixture_data):
    base = f'/api/v1/runs/{completed}'
    expected = next(r['body'] for r in fixture_data['responses'] if r['schema'] == 'Evaluation') | {'run_id': completed}
    assert client.get(base + '/evaluation').json() == expected
    expected = next(r['body'] for r in fixture_data['responses'] if r['schema'] == 'MinuteDetail') | {'run_id': completed}
    assert client.get(base + '/minutes/' + expected['point']['timestamp']).json() == expected
    assert client.get(base + '/minutes/2027-01-01T00:00:00Z').status_code == 404


def test_exports_are_complete_and_whitelisted(client, completed, fixture_data):
    base = f'/api/v1/runs/{completed}/exports/'
    response = client.get(base + 'scores', params={'page_size': 1})
    assert response.headers['content-type'] == 'application/vnd.apache.parquet'
    table = pq.read_table(BytesIO(response.content))
    assert table.num_rows == 4 and table['score'][0].as_py() is None
    assert client.get(base + 'metrics').json() == client.get(f'/api/v1/runs/{completed}/evaluation').json()
    assert client.get(base + 'config').json() == client.get(f'/api/v1/runs/{completed}').json()['config']
    for kind in ('manifest', 'model', 'private'):
        assert client.get(base + kind).status_code == 422


def test_corrupted_artifact_is_not_served(client, completed, settings):
    (settings.output / completed / 'metrics.json').write_text('private/path', encoding='utf-8')
    response = client.get(f'/api/v1/runs/{completed}/evaluation')
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'EXECUTION_FAILED'
    assert 'private' not in response.text


@pytest.mark.parametrize('name,reason', [('model/fixture-payload.json', 'MODEL_NOT_FOUND'), ('scores.parquet', 'RESULT_MISSING')])
def test_missing_saved_resources_have_fixed_public_reason(client, completed, settings, name, reason):
    (settings.output / completed / name).unlink()
    response = client.get(f'/api/v1/runs/{completed}/evaluation')
    assert response.status_code == 500
    assert response.json()['error']['details'] == [reason]
