"""Synthetic channel rows follow explicit detail timestamps, never list position."""
from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest

from traffic_anomaly import contracts as c
from traffic_api.worker import FakeExecutor

from .conftest import submit, wait_terminal


CHANNELS = tuple(c.Channels.model_fields)


def sample(fixture, schema):
    return next(row['body'] for row in fixture['responses'] if row['schema'] == schema)


def explicit_details(fixture):
    return [row['body'] for row in fixture['responses'] if row['schema'] == 'MinuteDetail']


def write_private_fixture(tmp_path, fixture):
    path = tmp_path / 'private-channel-fixture.json'
    # NaN is deliberate only in the malformed-detail case; contract validation
    # must reject it, including when a different first detail was perfectly valid.
    path.write_text(json.dumps(fixture, allow_nan=True), encoding='utf-8')
    return path


def detail(client, run_id, timestamp):
    response = client.get(f'/api/v1/runs/{run_id}/minutes/{timestamp}')
    assert response.status_code == 200, response.text
    return response.json()


def assert_null_channels(value):
    assert {name: value[name] for name in CHANNELS} == {name: None for name in CHANNELS}


def test_original_fixture_missing_details_are_null_and_explicit_channels_are_exact(make_app, fixture_data, tmp_path):
    fixture = deepcopy(fixture_data)
    path = write_private_fixture(tmp_path, fixture)
    mapped = {row['point']['timestamp']: row for row in explicit_details(fixture)}
    with TestClient(make_app(FakeExecutor(path))) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        for point in sample(fixture, 'SeriesPage')['items']:
            value = detail(client, run_id, point['timestamp'])
            assert value['point'] == point
            if point['timestamp'] in mapped:
                assert {name: value[name] for name in CHANNELS} == {name: mapped[point['timestamp']][name] for name in CHANNELS}
            else:
                assert_null_channels(value)
        assert client.get(f'/api/v1/runs/{run_id}/evaluation').json() == sample(fixture, 'Evaluation') | {'run_id': run_id}
        assert client.get(f'/api/v1/runs/{run_id}/exports/config').json() == sample(fixture, 'RunSummary')['config']
        assert client.get(f'/api/v1/runs/{run_id}/minutes/2027-01-01T00:00:00Z').status_code == 404


def test_distinct_later_current_and_reversed_details_still_bind_by_timestamp(make_app, fixture_data, tmp_path):
    fixture = deepcopy(fixture_data)
    bodies = explicit_details(fixture)
    bodies[0]['current'] = [1.5] * 134
    bodies[1]['current'] = [7.5 + index for index in range(134)]
    indexes = [index for index, row in enumerate(fixture['responses']) if row['schema'] == 'MinuteDetail']
    fixture['responses'][indexes[0]], fixture['responses'][indexes[1]] = fixture['responses'][indexes[1]], fixture['responses'][indexes[0]]
    path = write_private_fixture(tmp_path, fixture)
    with TestClient(make_app(FakeExecutor(path))) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        for expected in bodies:
            actual = detail(client, run_id, expected['point']['timestamp'])
            assert actual['current'] == expected['current']
            assert actual['point'] == expected['point']


def test_explicit_warmup_current_is_retained_while_score_threshold_alarm_remain_null(make_app, fixture_data, tmp_path):
    fixture = deepcopy(fixture_data)
    warmup = deepcopy(explicit_details(fixture)[0])
    warmup['point'] = deepcopy(sample(fixture, 'SeriesPage')['items'][0])
    warmup['current'] = [42.] * 134
    c.MinuteDetail.model_validate(warmup)
    fixture['responses'].append(dict(schema='MinuteDetail', body=warmup))
    path = write_private_fixture(tmp_path, fixture)
    with TestClient(make_app(FakeExecutor(path))) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        actual = detail(client, run_id, warmup['point']['timestamp'])
        assert actual['current'] == warmup['current']
        assert actual['point'] == warmup['point']
        assert actual['point']['valid'] is False
        assert all(actual['point'][name] is None for name in ('score', 'threshold', 'alarm'))
        assert all(actual[name] is None for name in CHANNELS if name != 'current')


def test_explicit_detail_labels_never_replace_independent_core_labels(make_app, fixture_data, tmp_path):
    fixture = deepcopy(fixture_data)
    first = explicit_details(fixture)[0]
    first['labels'] = {name: 0 for name in c.LABEL_NAMES}
    c.MinuteDetail.model_validate(first)
    path = write_private_fixture(tmp_path, fixture)
    with TestClient(make_app(FakeExecutor(path))) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        value = detail(client, run_id, first['point']['timestamp'])
        assert value['labels']['dos'] == 1 and value['labels'] != first['labels']
        missing = detail(client, run_id, sample(fixture, 'SeriesPage')['items'][2]['timestamp'])
        assert missing['labels'] == {name: 0 for name in c.LABEL_NAMES}


@pytest.mark.parametrize('where', ['on_axis', 'off_axis'])
def test_duplicate_explicit_timestamps_fail_even_outside_score_axis(make_app, fixture_data, tmp_path, where):
    fixture = deepcopy(fixture_data)
    duplicate = deepcopy(explicit_details(fixture)[0])
    if where == 'off_axis':
        duplicate['point']['timestamp'] = '2026-01-02T00:01:00Z'
        fixture['responses'].append(dict(schema='MinuteDetail', body=deepcopy(duplicate)))
    fixture['responses'].append(dict(schema='MinuteDetail', body=duplicate))
    path = write_private_fixture(tmp_path, fixture)
    with TestClient(make_app(FakeExecutor(path))) as client:
        run_id = submit(client, fixture_data)
        status = wait_terminal(client, run_id)
        assert status['status'] == 'failed' and status['error']['code'] == 'EXECUTION_FAILED'
        assert client.get(f'/api/v1/runs/{run_id}/series').status_code == 409


@pytest.mark.parametrize('mode', ['nonfinite', 'wrong_width', 'off_axis_invalid', 'if_reconstruction', 'field_order'])
def test_every_explicit_detail_is_checked_not_just_first(make_app, fixture_data, tmp_path, mode):
    fixture = deepcopy(fixture_data)
    second = explicit_details(fixture)[1]
    if mode == 'nonfinite': second['current'][0] = float('nan')
    elif mode == 'wrong_width': second['current'] = [0.] * 133
    elif mode == 'off_axis_invalid':
        second['point']['timestamp'] = '2026-01-02T00:03:00Z'
        second['current'] = [0.] * 133
    elif mode == 'field_order':
        second['feature_names'][0], second['feature_names'][1] = second['feature_names'][1], second['feature_names'][0]
        second['current'] = [float(index) for index in range(134)]
        c.MinuteDetail.model_validate(second)
    else: second['reconstruction_error_current'] = [0.] * 134
    path = write_private_fixture(tmp_path, fixture)
    with TestClient(make_app(FakeExecutor(path))) as client:
        run_id = submit(client, fixture_data)
        status = wait_terminal(client, run_id)
        assert status['status'] == 'failed' and status['error']['code'] == 'EXECUTION_FAILED'
        response = client.get(f'/api/v1/runs/{run_id}/evaluation')
        assert response.status_code == 409 and response.json()['error']['code'] == 'RESULT_NOT_READY'


@pytest.mark.parametrize('mode', ['no_details', 'only_valid_off_axis'])
def test_no_matching_details_produce_null_channels_without_failing_run(make_app, fixture_data, tmp_path, mode):
    fixture = deepcopy(fixture_data)
    off_axis = deepcopy(explicit_details(fixture)[0])
    off_axis['point']['timestamp'] = '2026-01-02T00:01:00Z'
    off_axis['current'] = [19.] * 134
    c.MinuteDetail.model_validate(off_axis)
    fixture['responses'] = [row for row in fixture['responses'] if row['schema'] != 'MinuteDetail']
    if mode == 'only_valid_off_axis': fixture['responses'].append(dict(schema='MinuteDetail', body=off_axis))
    path = write_private_fixture(tmp_path, fixture)
    with TestClient(make_app(FakeExecutor(path))) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        for point in sample(fixture, 'SeriesPage')['items']:
            value = detail(client, run_id, point['timestamp'])
            assert value['point'] == point
            assert_null_channels(value)
        assert client.get(f'/api/v1/runs/{run_id}/evaluation').json() == sample(fixture, 'Evaluation') | {'run_id': run_id}
