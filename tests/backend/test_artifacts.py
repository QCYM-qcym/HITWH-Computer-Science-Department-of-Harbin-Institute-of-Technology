from copy import deepcopy
import json
from pathlib import Path

import jsonschema
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from fastapi.testclient import TestClient

from .conftest import FIXTURE, ROOT, submit, wait_terminal
from traffic_api.app import create_app
from traffic_api.artifacts import digest
from traffic_api.worker import FakeExecutor


def rewrite_manifest(workspace, filename):
    path = workspace / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    for entry in manifest['files']:
        if entry['path'] == filename:
            entry['sha256'] = digest(workspace / filename)
    path.write_text(json.dumps(manifest), encoding='utf-8')


@pytest.mark.parametrize('mode', ['partial', 'bad_hash', 'bad_config', 'bad_axis', 'bad_count', 'bad_identity', 'missing_model', 'wrong_type', 'nonfinite'])
def test_incomplete_or_inconsistent_output_never_succeeds(make_app, fixture_data, mode):
    class Broken(FakeExecutor):
        def execute(self, config, workspace):
            result = super().execute(config, workspace)
            if mode == 'partial':
                (workspace / 'channels.parquet').unlink()
            elif mode == 'bad_hash':
                (workspace / 'metrics.json').write_text('{}', encoding='utf-8')
            elif mode in ('bad_config', 'bad_count', 'bad_identity'):
                path = workspace / 'summary.json'
                value = json.loads(path.read_bytes())
                if mode == 'bad_config':
                    value['config']['seed'] += 1
                elif mode == 'bad_count':
                    value['row_count'] += 1
                else:
                    value['run_id'] = 'someone-else'
                path.write_text(json.dumps(value), encoding='utf-8')
                rewrite_manifest(workspace, 'summary.json')
            elif mode == 'missing_model':
                (workspace / 'model/fixture-payload.json').unlink()
            else:
                name = 'channels.parquet' if mode == 'bad_axis' else 'scores.parquet'
                table = pq.read_table(workspace / name)
                if mode == 'bad_axis':
                    table = table.take(pa.array([1, 0, 2, 3]))
                elif mode == 'wrong_type':
                    index = table.schema.get_field_index('valid')
                    table = table.set_column(index, 'valid', pa.array([0, 1, 1, 1], type=pa.int64()))
                else:
                    index = table.schema.get_field_index('score')
                    table = table.set_column(index, 'score', pa.array([None, float('nan'), 1.5, 0.25]))
                pq.write_table(table, workspace / name)
                rewrite_manifest(workspace, name)
            return result
    with TestClient(make_app(Broken(FIXTURE))) as client:
        run_id = submit(client, fixture_data)
        status = wait_terminal(client, run_id)
        assert status['status'] == 'failed'
        assert status['error']['code'] == 'EXECUTION_FAILED'
        assert client.get(f'/api/v1/runs/{run_id}/series').status_code == 409


def test_all_http_json_responses_match_frozen_schemas(client, fixture_data):
    spec = yaml.safe_load((ROOT / 'docs/design/openapi-v1.yaml').read_text(encoding='utf-8'))
    def validate(response, schema):
        instance_schema = {'$ref': f'#/components/schemas/{schema}', 'components': spec['components']}
        jsonschema.Draft202012Validator(instance_schema).validate(response.json())
    validate(client.get('/api/v1/datasets'), 'DatasetList')
    response = client.post('/api/v1/runs', json=fixture_data['request'])
    validate(response, 'RunAccepted')
    run_id = response.json()['run_id']
    assert wait_terminal(client, run_id)['status'] == 'succeeded'
    base = f'/api/v1/runs/{run_id}'
    for suffix, schema in [('', 'RunStatus'), ('/series', 'SeriesPage'), ('/alarms', 'SeriesPage'),
                           ('/evaluation', 'Evaluation'), ('/minutes/2026-01-01T00:02:00Z', 'MinuteDetail')]:
        validate(client.get(base + suffix), schema)
    validate(client.get('/api/v1/runs/unknown'), 'ErrorResponse')


def test_no_labels_empty_series_no_alarms_and_unavailable_evaluation(settings, fixture_data, tmp_path):
    fixture = deepcopy(fixture_data)
    names = ('SeriesPage', 'Evaluation')
    for name in names:
        replacement = [r for r in fixture['responses'] if r['schema'] == name][-1]['body']
        next(r for r in fixture['responses'] if r['schema'] == name)['body'] = deepcopy(replacement)
    # Empty result is a real API state; keep all saved metadata consistent.
    fixture['responses'] = [r for r in fixture['responses'] if r['schema'] != 'MinuteDetail']
    summary = next(r['body'] for r in fixture['responses'] if r['schema'] == 'RunSummary')
    summary.update(row_count=0, valid_count=0, labels_available=False)
    fixture['core_sample']['timestamps'] = []
    path = tmp_path / 'empty.json'
    path.write_text(json.dumps(fixture), encoding='utf-8')
    with TestClient(create_app(settings, fixture_path=path)) as client:
        run_id = submit(client, fixture_data)
        assert wait_terminal(client, run_id)['status'] == 'succeeded'
        for suffix in ('series', 'alarms'):
            result = client.get(f'/api/v1/runs/{run_id}/{suffix}').json()
            assert result['items'] == [] and result['total'] == 0
        result = client.get(f'/api/v1/runs/{run_id}/evaluation').json()
        assert result['available'] is False and result['metrics'] is None and result['reason']


def test_generic_framework_failure_is_sanitized(make_app):
    app = make_app()
    @app.get('/private-failure')
    def broken():
        raise RuntimeError('private/path traceback credential')
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/private-failure')
        assert response.status_code == 500
        assert response.json()['error']['code'] == 'EXECUTION_FAILED'
        assert 'private' not in response.text and 'traceback' not in response.text


def test_unavailable_dataset_differs_from_malformed_configuration(settings, fixture_data, tmp_path):
    fixture = deepcopy(fixture_data)
    dataset = next(row['body']['items'][0] for row in fixture['responses'] if row['schema'] == 'DatasetList')
    dataset.update(available=False, unavailable_reason='Synthetic unavailable case')
    path = tmp_path / 'unavailable.json'
    path.write_text(json.dumps(fixture), encoding='utf-8')
    with TestClient(create_app(settings, fixture_path=path)) as client:
        response = client.post('/api/v1/runs', json=fixture_data['request'])
        assert response.status_code == 422
        assert response.json()['error']['details'] == ['DATASET_UNAVAILABLE']


def test_frozen_http_time_parameter_patterns_match_core_minute_type():
    import re
    from traffic_anomaly.contracts import TimeRange
    spec = yaml.safe_load((ROOT / 'docs/design/openapi-v1.yaml').read_text(encoding='utf-8'))
    core_pattern = TimeRange.model_json_schema()['properties']['start']['pattern']
    parameters = [parameter for path in spec['paths'].values() for operation in path.values()
                  for parameter in operation.get('parameters', []) if parameter['name'] in ('start', 'end', 'timestamp')]
    assert len(parameters) == 5
    for parameter in parameters:
        pattern = parameter['schema']['pattern']
        assert pattern == core_pattern
        assert re.fullmatch(pattern, '2026-01-01T00:00:00Z')
        assert re.fullmatch(pattern, '2026-01-01T00:00:01Z') is None
