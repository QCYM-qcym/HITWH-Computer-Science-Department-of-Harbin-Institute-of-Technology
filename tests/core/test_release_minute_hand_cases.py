"""Independent invented full91 answers, not source/aggregation authentication.

The JSON table was hand-authored before execution. Never replace its answers
with the result under test or derive them via either package codec.
"""
from dataclasses import fields, is_dataclass, replace
from datetime import datetime
import hashlib
import importlib
import json
import math
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tests/fixtures/release-minute-hand-cases-v1.json').read_text(encoding='utf-8'))
CASES = FIXTURE['cases']
COUNTER_FIELDS = {'reason_counts', 'raw_protocol_counts', 'eligible_protocol_counts', 'label_anomaly_counts'}
SOURCE_FIELDS = {'source_bytes', 'source_sha256'}
MEMBERS = ('minutes.json', 'labels.json', 'diagnostics.json', 'manifest.json', 'COMPLETE.json')


def modules():
    # Keep missing production interfaces as behavior failures, not collection errors.
    contract = importlib.import_module('traffic_anomaly.release_minute_contract')
    storage = importlib.import_module('traffic_anomaly.release_minute_package')
    helper = importlib.import_module('.release_minute_package_cases', __package__)
    minute = importlib.import_module('traffic_anomaly._release_minutes')
    return contract, storage, helper, minute


def inputs(case, helper, minute):
    segments = tuple(minute.ReleaseSegment(
        item['id'], item['role'], datetime.fromisoformat(item['start']), datetime.fromisoformat(item['end'])
    ) for item in case['segments'])
    sources = tuple(tuple(dict(row) for row in source) for source in case['sources'])
    return helper.make_result(sources, segments), segments


def plain(value):
    """Independent dataclass field projection, not package encoding/decoding."""
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {field.name: plain(dict(getattr(value, field.name)) if field.name in COUNTER_FIELDS
                                 else getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: plain(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [plain(child) for child in value]
    return value


def assert_hand_result(result, expected):
    assert {field.name for field in fields(result)} - set(expected) == SOURCE_FIELDS
    actual = plain(result)
    for key, answer in expected.items():
        assert actual[key] == answer, key
    assert type(result.source_bytes) is tuple and all(type(value) is int and value > 0 for value in result.source_bytes)
    assert type(result.source_sha256) is tuple and len(result.source_bytes) == len(result.source_sha256)
    assert all(len(value) == 64 and set(value) <= set('0123456789abcdef') for value in result.source_sha256)
    for valid, values in zip(result.source_valid, result.values):
        assert len(values) == 13
        if valid:
            assert all(type(value) is float and math.isfinite(value) and value >= 0 for value in values)
        else:
            assert values == (None,) * 13


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def test_hand_table_is_independent_artificial_full91_cases():
    assert set(FIXTURE) == {'fixture_version', 'evidence_kind', 'cases'}
    assert FIXTURE['fixture_version'] == 1 and FIXTURE['evidence_kind'] == 'SYNTHETIC_ONLY'
    assert [case['name'] for case in CASES] == ['A-variable-labels', 'B-global-unplaced', 'C-duplicate-protocol', 'D-segment-gap']
    csv = importlib.import_module('traffic_anomaly._release_csv')
    assert len(csv.EXPECTED_HEADER) == 91
    attempted = CASES[0]['sources'][0][4]
    assert attempted['Label'] == 'FTP-Patator - Attempted' and attempted['Label'] in csv._ATTEMPTED_LABELS
    assert attempted['Attempted Category'] == '0' and attempted['Attempted Category'] in csv._ATTEMPTED_CATEGORIES
    assert CASES[0]['sources'][0][3]['Label'] == 'Portscan' and 'Portscan' in csv._ATTACK_LABELS
    assert CASES[0]['expected']['values'][0] == [4.0,10.0,3.0,100.0,15.0,1.0,1.0,1.0,1.0,4.0,2.5,3.85,2.0]
    for case in CASES:
        assert set(case) == {'name', 'sources', 'segments', 'expected'}
        for source in case['sources']:
            for row in source:
                assert {'id', 'Timestamp'} <= row.keys() <= set(csv.EXPECTED_HEADER)
                assert all(type(value) is str for value in row.values())
        assert all(math.isfinite(value) for value in walk(case['expected']) if type(value) is float)
    assert CASES[2]['sources'][0][0] == CASES[2]['sources'][1][0]


@pytest.mark.parametrize('case', CASES, ids=[case['name'] for case in CASES])
def test_hand_cases_match_existing_full91_aggregation(case):
    helper = importlib.import_module('.release_minute_package_cases', __package__)
    minute = importlib.import_module('traffic_anomaly._release_minutes')
    result, _segments = inputs(case, helper, minute)
    assert_hand_result(result, case['expected'])


@pytest.mark.parametrize('case', CASES, ids=[case['name'] for case in CASES])
def test_independent_hand_cases_survive_package_roundtrip(case, tmp_path):
    contract, storage, helper, minute = modules()
    result, segments = inputs(case, helper, minute)
    assert_hand_result(result, case['expected'])
    directory = tmp_path / case['name']
    identity = storage.save_release_minute_package(result, segments, directory)
    snapshot = storage.load_release_minute_package(directory)
    assert snapshot.identity == identity
    assert snapshot.segments == segments
    assert snapshot.scope == 'PACKAGE_INTERNAL_CONSISTENCY_ONLY'
    assert_hand_result(snapshot.minutes, case['expected'])
    assert snapshot.minutes == result
    encoded = dict(contract.encode_release_minute_package(result, segments))
    assert set(encoded) == set(MEMBERS)
    assert all((directory / name).read_bytes() == encoded[name] for name in MEMBERS)
    manifest = (directory / 'manifest.json').read_bytes()
    assert identity.manifest_byte_count == len(manifest)
    assert identity.manifest_sha256 == hashlib.sha256(manifest).hexdigest()
    numeric_doc = json.loads(encoded['minutes.json'])
    assert set(numeric_doc) == {'schema_version','profile_id','context_sha256','timestamps','segment_ordinals','source_valid','values'}
    assert numeric_doc['values'] == case['expected']['values']
    assert numeric_doc['source_valid'] == case['expected']['source_valid']
    for raw in encoded.values():
        assert all('evidence_kind' not in node for node in walk(json.loads(raw)) if isinstance(node, dict))
    # Reopening returns values, not a lazy path-dependent reader.
    (directory / 'minutes.json').unlink()
    assert_hand_result(snapshot.minutes, case['expected'])


def test_current_package_identity_cannot_be_old_candidate_identity(tmp_path):
    contract, _storage, helper, minute = modules()
    result, segments = inputs(CASES[0], helper, minute)
    encoded = dict(contract.encode_release_minute_package(result, segments))
    assert result.schema_id == 'c17-release-91-v1' and not hasattr(result, 'evidence_kind')
    # Both old readers below are numeric/record validators, with no model imports.
    records = importlib.import_module('traffic_anomaly.candidate_record_cli')
    old_inputs = importlib.import_module('traffic_anomaly.candidate_cli')
    for name, raw in encoded.items():
        doc = json.loads(raw)
        assert doc['profile_id'] == 'c17-release-minute-package-v1'
        assert 'evidence_kind' not in doc and 'model_profile_id' not in doc
        path = tmp_path / name
        path.write_bytes(raw)
        with pytest.raises(records._SafeError, match='^INVALID_FIXTURE$'):
            records._read_fixture(path, 'P_U')
        with pytest.raises(old_inputs._SafeError, match='^INVALID_FIXTURE$'):
            old_inputs._read_fixture(path)
    # The shared old artifact gate runs before either IF/AE execution path.
    artifacts = importlib.import_module('traffic_anomaly.candidate_artifacts')
    directory = tmp_path / 'new-package'
    directory.mkdir()
    for name, raw in encoded.items():
        (directory / name).write_bytes(raw)
    with pytest.raises(artifacts.CandidateArtifactError, match='^INVALID_PACKAGE$'):
        artifacts.load_verified_candidate_artifacts(directory, directory)
    # Old IF/AE model entry points are deliberately NOT imported or executed.


def test_self_consistent_new_source_declaration_changes_identity_not_authentication():
    contract, _storage, helper, minute = modules()
    result, segments = inputs(CASES[0], helper, minute)
    original = contract.decode_release_minute_package(dict(contract.encode_release_minute_package(result, segments)))
    invented = replace(result, source_sha256=('e' * 64,), source_bytes=(result.source_bytes[0] + 1,))
    changed = contract.decode_release_minute_package(dict(contract.encode_release_minute_package(invented, segments)))
    assert original.identity.profile_id == changed.identity.profile_id == 'c17-release-minute-package-v1'
    assert changed.identity.context_sha256 != original.identity.context_sha256
    assert changed.identity.manifest_sha256 != original.identity.manifest_sha256
    assert changed.minutes.source_sha256 == ('e' * 64,)
    assert changed.minutes.source_bytes == (result.source_bytes[0] + 1,)
    assert changed.scope == 'PACKAGE_INTERNAL_CONSISTENCY_ONLY'
    assert_hand_result(changed.minutes, CASES[0]['expected'])
    assert changed.minutes.source_authentication == original.minutes.source_authentication == 'NOT_AUTHENTICATED'
    assert changed.minutes.bucket_counts[0].definite_attack_present is True
    assert changed.minutes.bucket_counts[1].attempted_present is True
    assert changed.minutes.label_kinds[1] == ('unknown', 'normal', 'attack')
