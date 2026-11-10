"""Real fixed artificial CSV creation, aggregation and input preparation.

No old artificial value-object fixture is used. The expected axis and history
populations below are hand-derived from the published 48/40/40/48 recipe.
Only preprocessing is fitted; estimator imports and IF execution are forbidden.
"""
import builtins
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import importlib
import json

import pytest

from traffic_anomaly import release_iforest as forest
from traffic_anomaly import release_input_cli as input_cli
from traffic_anomaly import release_input_package as prepared_io
from traffic_anomaly import release_minute_cli as raw_cli
from traffic_anomaly import release_minute_package as raw_io
from traffic_anomaly.release_model_inputs import pair_release_model_inputs


def example_cli():
    try:
        return importlib.import_module('traffic_anomaly.release_example_cli')
    except ModuleNotFoundError as error:
        if error.name == 'traffic_anomaly.release_example_cli':
            pytest.fail('public artificial CSV create command is not implemented')
        raise


def digest(payload):
    return dict(byte_count=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def snapshot(directory):
    return {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in directory.iterdir()}


@pytest.fixture
def no_estimator(monkeypatch):
    original_import = builtins.__import__

    def forbidden(*args, **kwargs):
        raise AssertionError('artificial source integration must not execute a model')

    def guarded_import(name, *args, **kwargs):
        if name.split('.')[0] in ('sklearn', 'torch', 'joblib'):
            return forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(forest, 'fit_release_iforest', forbidden)
    monkeypatch.setattr(forest, '_compute', forbidden)
    monkeypatch.setattr(builtins, '__import__', guarded_import)


def call_json(cli, arguments, capfdbinary):
    code = cli.main(arguments)
    stdout, stderr = capfdbinary.readouterr()
    assert code == 0, (code, stderr)
    assert stderr == b''
    assert stdout.endswith(b'\n') and not stdout.endswith(b'\n\n')
    return json.loads(stdout)


def test_created_csv_spec_aggregates_and_prepares_real_packages(tmp_path, capfdbinary, no_estimator):
    """Catch a creator whose source/spec cannot feed the actual raw/input CLIs."""
    example = tmp_path / 'new artificial source'
    created = call_json(example_cli(), ['create', '--output', str(example)], capfdbinary)
    assert created['status'] == 'CREATED'
    assert set(path.name for path in example.iterdir()) == {
        'artificial.csv', 'aggregate-spec.json', 'recipe.json'}
    source = (example / 'artificial.csv').read_bytes()
    source_identity = digest(source)
    assert created['files']['artificial.csv'] == source_identity
    spec = json.loads((example / 'aggregate-spec.json').read_bytes())
    assert spec['sources'] == [dict(path=str(example / 'artificial.csv'),
                                    bytes=len(source), sha256=source_identity['sha256'])]
    before_source = snapshot(example)
    raw_directory, scratch = tmp_path / 'raw', tmp_path / 'scratch'
    aggregated = call_json(raw_cli, ['--spec', str(example / 'aggregate-spec.json'),
                                    '--scratch', str(scratch), '--output', str(raw_directory)], capfdbinary)
    assert aggregated['status'] == 'SAVED'
    assert aggregated['counts'] == dict(source_count=1, minute_count=176,
        source_valid_minutes=176, raw_records=176, eligible_records=176,
        excluded_records=0, outside_records=0, unplaced_invalid_rows=0)
    assert aggregated['source_identities'] == [dict(ordinal=0, **source_identity)]
    assert aggregated['resources']['source_content_open_count'] == 1
    assert aggregated['resources']['source_bytes_consumed'] == len(source)
    assert aggregated['resources']['logical_rows'] == 176
    assert aggregated['resources']['cleanup_status'] == 'CLEANED'
    assert not scratch.exists()
    raw = raw_io.load_release_minute_package(raw_directory)
    assert aggregated['identity'] == asdict(raw.identity)
    assert raw.minutes.source_bytes == (len(source),)
    assert raw.minutes.source_sha256 == (source_identity['sha256'],)
    starts = (datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 1),
              datetime(2026, 1, 1, 2), datetime(2026, 1, 1, 3))
    lengths = (48, 40, 40, 48)
    axis = tuple(start + timedelta(minutes=i)
                 for start, length in zip(starts, lengths) for i in range(length))
    assert raw.minutes.timestamps == axis
    assert tuple(segment.role for segment in raw.segments) == ('train', 'validation', 'calibration', 'test')
    assert tuple(segment.id for segment in raw.segments) == (
        'artificial-train', 'artificial-validation', 'artificial-calibration', 'artificial-test')
    assert tuple(segment.end for segment in raw.segments) == tuple(
        start + timedelta(minutes=length) for start, length in zip(starts, lengths))
    assert raw.minutes.source_valid == (True,) * 176
    assert raw.minutes.source_authentication == 'NOT_AUTHENTICATED'
    assert raw.minutes.time_basis == 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'
    before_raw = snapshot(raw_directory)
    prepared_directory = tmp_path / 'prepared'
    prepared_receipt = call_json(input_cli, ['prepare', '--raw-package', str(raw_directory),
        '--output', str(prepared_directory), '--epsilon', '0.000001', '--audit-fit-policy', 'P_U'], capfdbinary)
    prepared = prepared_io.load_release_input_package(prepared_directory)
    assert prepared_receipt['status'] == 'SAVED'
    assert prepared_receipt['summary']['identity'] == asdict(prepared.identity)
    assert prepared_receipt['summary']['minute_counts'] == dict(total=176, raw_valid=176,
        prepared_valid=176, common_valid=56, history_h15_valid=116, history_h30_valid=56)
    pair = pair_release_model_inputs(raw, prepared)
    assert pair.raw_identity == raw.identity and pair.prepared_identity == prepared.identity
    assert pair.population.preprocessing_fit_indices == tuple(range(30, 48))
    assert pair.population.train_indices == tuple(range(30, 48))
    assert pair.population.calibration_indices == tuple(range(118, 128))
    assert tuple(i for i, valid in enumerate(pair.prepared_minutes.common_valid) if valid) == (
        *range(30, 48), *range(78, 88), *range(118, 128), *range(158, 176))
    assert prepared.preprocessing.n_samples_seen == 18
    assert pair.configuration.audit_fit_policy == 'P_U'
    assert pair.configuration.policy_status == 'AUDIT_ONLY'
    assert pair.configuration.epsilon == 0.000001
    assert pair.configuration.windows == (15, 30)
    assert pair.configuration.fit_window == 30
    assert snapshot(example) == before_source
    assert snapshot(raw_directory) == before_raw


def test_protocol0_and_existing_label_audit_mappings_survive_pipeline(tmp_path, capfdbinary, no_estimator):
    """Catch dropping protocol0, normalizing unknown labels, or crossing gaps."""
    example = tmp_path / 'source'
    call_json(example_cli(), ['create', '--output', str(example)], capfdbinary)
    raw_directory, scratch = tmp_path / 'raw', tmp_path / 'scratch'
    call_json(raw_cli, ['--spec', str(example / 'aggregate-spec.json'), '--scratch', str(scratch),
                       '--output', str(raw_directory)], capfdbinary)
    raw = raw_io.load_release_minute_package(raw_directory)
    # 16+13+13+16 ordinary U rows, plus two test overrides from TCP/UDP.
    expected_protocols = dict(tcp=59, udp=57, known_other=0, unresolved=60, excluded_protocol=0)
    assert dict(raw.minutes.raw_protocol_counts) == expected_protocols
    # The public eligible counter has four usable channels; excluded_protocol
    # is reported only by the five-channel raw counter.
    assert dict(raw.minutes.eligible_protocol_counts) == dict(tcp=59, udp=57, known_other=0, unresolved=60)
    assert raw.minutes.excluded_records == 0
    assert sum(row[8] for row in raw.minutes.values) == 60.0
    assert raw.minutes.values[164] == (1.0, 8.0, 1.0, 80.0, 10.0, 0.0, 0.0, 0.0,
                                       1.0, 1.0, 1.0, 1.0, 0.0)
    assert raw.minutes.values[168] == (1.0, 16.0, 0.0, 160.0, 0.0, 0.0, 0.0, 0.0,
                                       1.0, 1.0, 1.0, 1.0, 1.0)
    assert raw.minutes.label_kinds[2] == ('normal', 'normal', 'normal')
    assert raw.minutes.values[2][8] == 1.0
    assert raw.minutes.label_kinds[164] == ('attack', 'attack', 'attack')
    assert raw.minutes.label_kinds[168] == ('unknown', 'normal', 'attack')
    assert raw.minutes.label_kinds[172] == ('unknown', 'unknown', 'unknown')
    assert all(raw.minutes.source_valid[index] for index in (2, 164, 168, 172))
    assert raw.minutes.label_kind_counts == ((173, 1, 2), (174, 1, 1), (173, 2, 1))
    assert raw.minutes.bucket_counts[164].definite_attack_present is True
    assert raw.minutes.bucket_counts[168].attempted_present is True
    assert raw.minutes.bucket_counts[168].definite_attack_present is False
    assert all(bucket.raw_records == bucket.eligible_records == 1 and bucket.excluded_records == 0
               for bucket in raw.minutes.bucket_counts)
    # Unregistered wall-clock gaps are absent; no fabricated zero/normal buckets.
    assert datetime(2026, 1, 1, 0, 48) not in raw.minutes.timestamps
    assert datetime(2026, 1, 1, 1, 40) not in raw.minutes.timestamps
    assert datetime(2026, 1, 1, 2, 40) not in raw.minutes.timestamps
    assert dict(raw.minutes.reason_counts)['empty_unconfirmed'] == 0
    source_before, raw_before = snapshot(example), snapshot(raw_directory)
    prepared_directory = tmp_path / 'prepared'
    call_json(input_cli, ['prepare', '--raw-package', str(raw_directory), '--output', str(prepared_directory),
                         '--epsilon', '0.000001', '--audit-fit-policy', 'P_U'], capfdbinary)
    prepared = prepared_io.load_release_input_package(prepared_directory)
    pair = pair_release_model_inputs(raw, prepared)
    assert pair.labels.saved.label_kinds == raw.minutes.label_kinds
    for mask, want in zip(prepared.labels.qualification_masks, ((15, 1, 2), (16, 1, 1), (15, 2, 1))):
        assert (sum(mask.test_current_normal), sum(mask.test_current_attack),
                sum(mask.test_current_unknown)) == want
        assert sum(mask.train_full_history_normal) == 18
        assert sum(mask.calibration_full_history_normal) == 10
        assert sum(mask.validation_current_normal) == 10
    for start in (0, 48, 88, 128):
        assert prepared.minutes.histories[0].valid[start:start + 15] == (False,) * 15
        assert prepared.minutes.histories[1].valid[start:start + 30] == (False,) * 30
        assert prepared.minutes.common_valid[start:start + 30] == (False,) * 30
    assert sum(prepared.minutes.histories[0].valid) == 116
    assert sum(prepared.minutes.histories[1].valid) == 56
    assert snapshot(example) == source_before
    assert snapshot(raw_directory) == raw_before
    assert not scratch.exists()
