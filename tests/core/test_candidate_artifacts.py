"""Read-only evidence checks of existing synthetic candidate artifacts."""
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from traffic_anomaly.candidate_cli import _run as numeric_run
from traffic_anomaly.candidate_record_cli import _run as records_run


SOURCE = Path(__file__).parents[1] / 'fixtures' / 'g13u-records-v1.json'


@pytest.fixture
def package(tmp_path):
    records, inputs = tmp_path / 'records', tmp_path / 'inputs'
    records_run(SOURCE, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    return records, inputs


def read(path):
    return json.loads(path.read_text('utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')


def reseal(directory, name):
    manifest = read(directory / 'manifest.json')
    payload = (directory / name).read_bytes()
    manifest['artifacts'][name] = dict(sha256=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))
    write(directory / 'manifest.json', manifest)


def verify(package, **kwargs):
    from traffic_anomaly.candidate_artifacts import verify_candidate_artifacts
    return verify_candidate_artifacts(*package, **kwargs)


def rejects(package, *, code=None, **kwargs):
    from traffic_anomaly.candidate_artifacts import CandidateArtifactError
    with pytest.raises(CandidateArtifactError) as caught:
        verify(package, **kwargs)
    assert str(caught.value) == caught.value.code
    assert all(str(directory) not in str(caught.value) for directory in package)
    if code is not None:
        assert caught.value.code == code


def test_source_replay_is_readonly_and_never_refits(package, monkeypatch):
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor
    before = {p: p.read_bytes() for d in package for p in d.iterdir()}
    def forbidden(*args, **kwargs):
        raise AssertionError('verifier must not fit')
    monkeypatch.setattr(CandidatePreprocessor, 'fit', forbidden)
    report = verify(package, source_fixture=SOURCE)
    assert report['status'] == 'VERIFIED'
    assert report['evidence_kind'] == 'SYNTHETIC_ONLY'
    assert report['selected_policy'] == 'P_U' and report['policy_status'] == 'AUDIT_ONLY'
    assert report['checks']['source_replay'] == 'VERIFIED'
    assert report['checks']['fit_parameters'] == 'NOT_REESTIMATED'
    assert report['minute_count'] == 144
    assert report['partition_summary']['test']['common_valid_count'] == 6
    assert {p: p.read_bytes() for d in package for p in d.iterdir()} == before
    assert str(SOURCE) not in json.dumps(report)


def test_without_source_does_not_claim_source_was_verified(package):
    report = verify(package)
    assert report['checks']['source_replay'] == 'NOT_PROVIDED'
    assert report['checks']['saved_transform_replay'] == 'VERIFIED'


@pytest.mark.parametrize('include_source', [False, True])
def test_legal_minute_precision_source_matches_second_precision_export(tmp_path, include_source):
    source = tmp_path / 'minute-precision.json'
    value = read(SOURCE)
    for row in value['minutes']:
        row['timestamp'] = row['timestamp'][:16]
    write(source, value)
    records, inputs = tmp_path / 'records', tmp_path / 'inputs'
    records_run(source, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    report = verify((records, inputs), source_fixture=source if include_source else None)
    assert report['status'] == 'VERIFIED'


def test_packages_can_move_without_the_original_source_directory(package, tmp_path):
    moved = tuple(tmp_path / name for name in ('moved-records', 'moved-inputs'))
    for old, new in zip(package, moved):
        shutil.copytree(old, new)
        shutil.rmtree(old)
    assert verify(moved)['minute_count'] == 144


@pytest.mark.parametrize('name', ['minute-fixture.json', 'label-audit.json'])
def test_adapter_bytes_cannot_change_unnoticed(package, name):
    path = package[0] / name
    path.write_bytes(path.read_bytes() + b' ')
    rejects(package, code='INTEGRITY_MISMATCH')


@pytest.mark.parametrize('name', ['candidate-inputs.json', 'preprocess.json'])
def test_numeric_bytes_cannot_change_unnoticed(package, name):
    path = package[1] / name
    path.write_bytes(path.read_bytes() + b' ')
    rejects(package, code='INTEGRITY_MISMATCH')


def test_cross_policy_numeric_results_cannot_be_attached(package, tmp_path):
    other_records, other_inputs = tmp_path / 'pb-records', tmp_path / 'pb-inputs'
    records_run(SOURCE, 'P_B', other_records)
    numeric_run(other_records / 'minute-fixture.json', other_inputs)
    rejects((package[0], other_inputs), code='INTEGRITY_MISMATCH')


@pytest.mark.parametrize('field', ['schema_version', 'profile_id', 'evidence_kind', 'configuration_sha256'])
def test_manifest_schema_profile_and_configuration_are_explicit(package, field):
    path = package[1] / 'manifest.json'
    data = read(path)
    data[field] = True if field == 'schema_version' else 'incompatible'
    write(path, data)
    rejects(package)


def test_manifest_does_not_allow_arbitrary_artifact_paths(package):
    path = package[0] / 'manifest.json'
    data = read(path)
    data['artifacts']['../private.json'] = data['artifacts']['label-audit.json']
    write(path, data)
    rejects(package)


@pytest.mark.parametrize('where,name', [(0, 'manifest.json'), (1, 'manifest.json'), (1, 'preprocess.json')])
def test_incomplete_packages_are_rejected(package, where, name):
    (package[where] / name).unlink()
    rejects(package)


def test_unknown_sidecar_is_not_part_of_a_complete_package(package):
    (package[1] / 'scores.json').write_text('{}', encoding='utf-8')
    rejects(package)


def test_duplicate_json_keys_are_rejected(package):
    path = package[1] / 'manifest.json'
    path.write_text(path.read_text('utf-8').replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'), encoding='utf-8')
    rejects(package)


@pytest.mark.parametrize('change', ['value', 'feature_order', 'common_mask', 'history_reason', 'summary', 'axis', 'joined'])
def test_resealing_cannot_hide_numerical_or_structural_inconsistency(package, change):
    path = package[1] / 'candidate-inputs.json'
    data = read(path)
    if change == 'value': data['current_values'][33][0] += 1
    elif change == 'feature_order': data['feature_names'].reverse()
    elif change == 'common_mask': data['common_valid'][0] = True
    elif change == 'history_reason': data['histories']['30']['invalid_reason'][0] = None
    elif change == 'summary': data['partition_summary']['train']['common_valid_count'] = 7
    elif change == 'axis': data['timestamps'].pop()
    elif change == 'joined': data['histories']['30']['joined'][33][0] += 1
    write(path, data)
    reseal(package[1], path.name)
    rejects(package, code='REPLAY_MISMATCH')


@pytest.mark.parametrize('change', ['count', 'scale', 'fit_window', 'extra_label'])
def test_state_compatibility_and_declared_training_count_are_checked(package, change):
    path = package[1] / 'preprocess.json'
    data = read(path)
    if change == 'count': data['n_samples_seen'] += 1
    elif change == 'scale': data['scale'][0] = 0
    elif change == 'fit_window': data['fit_window'] = 15
    elif change == 'extra_label': data['attack_label'] = 'Portscan'
    write(path, data)
    reseal(package[1], path.name)
    rejects(package)


def test_selected_normal_mask_must_match_the_separate_policy_audit(package):
    path = package[0] / 'label-audit.json'
    data = read(path)
    data['normal_candidates']['P_U'][0] = False
    write(path, data)
    reseal(package[0], path.name)
    rejects(package)


@pytest.mark.parametrize('change', ['missing', 'confirmed_empty', 'attack_flag'])
def test_audit_cannot_contradict_its_own_counts_without_source(package, change):
    path = package[0] / 'label-audit.json'
    data = read(path)
    if change == 'attack_flag':
        data['audit']['minute_reports'][0]['source_attack_label_present'] = True
    else:
        data['audit']['minute_reports'][0]['coverage'] = change
    write(path, data)
    reseal(package[0], path.name)
    rejects(package)


@pytest.mark.parametrize('which', [0, 1])
def test_configuration_epsilon_does_not_use_numeric_replay_tolerance(package, which):
    path = package[which] / 'manifest.json'
    data = read(path)
    data['configuration']['epsilon'] += 1e-13
    data['configuration_sha256'] = hashlib.sha256(json.dumps(data['configuration'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    write(path, data)
    rejects(package, code='INCOMPATIBLE_PACKAGE')


@pytest.mark.parametrize('change', ['channel_sum', 'fractional_count', 'duration_order', 'source_sum_bound'])
def test_record_aggregation_invariants_hold_even_without_original_records(package, tmp_path, change):
    path = package[0] / 'minute-fixture.json'
    data = read(path)
    if change == 'channel_sum': data['minutes'][0]['features'][5] += 1
    elif change == 'fractional_count': data['minutes'][0]['features'][1] += 0.5
    elif change == 'source_sum_bound': data['minutes'][0]['features'][1] = 4000000001
    else: data['minutes'][0]['features'][10] = 5
    write(path, data)
    reseal(package[0], path.name)
    new_inputs = tmp_path / 'coherently-recomputed-inputs'
    numeric_run(path, new_inputs)
    rejects((package[0], new_inputs))


def test_optional_source_identity_is_actually_checked(package, tmp_path):
    source = tmp_path / 'other-source.json'
    source.write_bytes(SOURCE.read_bytes() + b' ')
    rejects(package, source_fixture=source, code='INTEGRITY_MISMATCH')


def test_source_replay_detects_false_audit_even_after_resealing(package):
    path = package[0] / 'label-audit.json'
    data = read(path)
    data['audit']['source_label_counts']['BENIGN'] -= 1
    write(path, data)
    reseal(package[0], path.name)
    rejects(package, source_fixture=SOURCE)


def test_nonstandard_nonfinite_json_is_not_accepted(package):
    path = package[1] / 'candidate-inputs.json'
    data = read(path)
    data['current_values'][0][0] = float('nan')
    path.write_text(json.dumps(data), encoding='utf-8')
    reseal(package[1], path.name)
    rejects(package)


def test_size_bound_is_applied_before_json_parsing(package, monkeypatch):
    import traffic_anomaly.candidate_artifacts as module
    monkeypatch.setattr(module, 'MAX_MANIFEST_BYTES', 8)
    rejects(package, code='RESOURCE_LIMIT')


def test_file_symlinks_cannot_escape_the_package(package, tmp_path):
    target = tmp_path / 'external.json'
    source = package[1] / 'candidate-inputs.json'
    target.write_bytes(source.read_bytes())
    source.unlink()
    try:
        source.symlink_to(target)
    except OSError:
        pytest.skip('host does not permit unprivileged symbolic links')
    rejects(package)


@pytest.mark.parametrize('where', ['directory', 'file', 'ancestor'])
def test_windows_reparse_points_are_rejected_without_link_privileges(package, monkeypatch, where):
    target = {'directory': package[0], 'file': package[1] / 'candidate-inputs.json',
              'ancestor': package[0].parent}[where]
    original = Path.lstat
    def marked(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=1024)
        return info
    monkeypatch.setattr(Path, 'lstat', marked)
    rejects(package, code='INVALID_PACKAGE')


@pytest.mark.parametrize('limit', ['MAX_AUDIT_BYTES', 'MAX_INPUT_BYTES', 'MAX_STATE_BYTES'])
def test_each_artifact_limit_precedes_parsing(package, monkeypatch, limit):
    import traffic_anomaly.candidate_artifacts as module
    monkeypatch.setattr(module, limit, 8)
    rejects(package, code='RESOURCE_LIMIT')


def test_a_boolean_cannot_impersonate_a_numeric_value_even_after_resealing(package):
    path = package[1] / 'candidate-inputs.json'
    data = read(path)
    data['current_values'][0][0] = True
    write(path, data)
    reseal(package[1], path.name)
    rejects(package, code='REPLAY_MISMATCH')


def test_invalid_minutes_remain_null_and_history_warms_up_again(tmp_path):
    value = read(SOURCE)
    value['records'][40 * 4]['protocol'] = 200
    source = tmp_path / 'invalid-record.json'
    write(source, value)
    records, inputs = tmp_path / 'records', tmp_path / 'inputs'
    records_run(source, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    report = verify((records, inputs), source_fixture=source)
    assert report['partition_summary']['validation']['input_valid_count'] == 35
    path = inputs / 'candidate-inputs.json'
    data = read(path)
    assert data['current_values'][40] == [None] * 13
    assert data['histories']['30']['current'][39] != [None] * 13
    assert not any(data['common_valid'][40:71])
    data['current_values'][40] = [0] * 13
    write(path, data)
    reseal(inputs, path.name)
    rejects((records, inputs), code='REPLAY_MISMATCH')


def test_raw_fit_eligibility_is_distinct_from_finite_history_eligibility(tmp_path):
    value = read(SOURCE)
    value['epsilon'] = 1e-320
    for record in value['records']:
        record['fwd_packets'] = 1
    value['records'][33 * 4]['fwd_packets'] = 2
    source = tmp_path / 'nonfinite-history.json'
    write(source, value)
    records, inputs = tmp_path / 'records', tmp_path / 'inputs'
    records_run(source, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    report = verify((records, inputs), source_fixture=source)
    assert read(inputs / 'preprocess.json')['n_samples_seen'] == 6
    assert report['partition_summary']['train']['training_normal_count'] == 3
    data = read(inputs / 'candidate-inputs.json')
    assert data['histories']['30']['invalid_reason'][33] == 'nonfinite_history'
    assert data['histories']['30']['joined'][33] == [None] * 26
