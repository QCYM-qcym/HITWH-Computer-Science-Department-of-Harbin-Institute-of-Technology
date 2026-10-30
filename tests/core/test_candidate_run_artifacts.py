"""Stored synthetic run consistency, deliberately without model verification."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).parents[1] / 'fixtures' / 'g13u-records-v1.json'
JSON_NAMES = ('model-state.json', 'scores.json', 'evaluation.json', 'manifest.json')
ARTIFACTS = ('model-state.json', 'weights.bin', 'scores.json', 'evaluation.json')


def read(path):
    return json.loads(path.read_text('utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def digest(path):
    payload = path.read_bytes()
    return dict(sha256=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))


def snapshot(package):
    paths = [SOURCE, *(p for directory in package for p in directory.iterdir())]
    return {p: (p.stat().st_size, p.stat().st_mtime_ns, digest(p)['sha256']) for p in paths}


@pytest.fixture(scope='module')
def original_package(tmp_path_factory):
    # This explicit artificial setup may fit/save a toy model. The verifier
    # under test must never invoke that code or deserialize its weights.
    from traffic_anomaly.candidate_cli import _run as numeric_run
    from traffic_anomaly.candidate_record_cli import _run as records_run
    from traffic_anomaly.candidate_if_cli import run_synthetic_candidate_if
    base = tmp_path_factory.mktemp('candidate-run-original')
    records, inputs, run = (base / name for name in ('records', 'inputs', 'toy-run'))
    records_run(SOURCE, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    run_synthetic_candidate_if(records, inputs, SOURCE, 'toy-run-v1', run)
    return run, records, inputs


@pytest.fixture
def package(original_package, tmp_path):
    result = tuple(tmp_path / p.name for p in original_package)
    for source, destination in zip(original_package, result):
        shutil.copytree(source, destination)
    return result


def verify(package, *, source=SOURCE):
    from traffic_anomaly.candidate_run_artifacts import verify_candidate_if_run
    return verify_candidate_if_run(*package, source_fixture=source)


def rejects(package, *, source=SOURCE):
    from traffic_anomaly.candidate_run_artifacts import CandidateRunArtifactError
    with pytest.raises(CandidateRunArtifactError) as caught:
        verify(package, source=source)
    assert isinstance(caught.value, ValueError)
    assert str(caught.value) == caught.value.code
    assert re.fullmatch(r'[A-Z][A-Z0-9_]*', caught.value.code)
    assert all(str(path) not in str(caught.value) for path in package)
    return caught.value.code


def reseal(package):
    """Rebind every byte identity so semantic tests cannot pass via hash failure."""
    run = package[0]
    model = read(run / 'model-state.json')
    model['weights'] = digest(run / 'weights.bin')
    write(run / 'model-state.json', model)
    evaluation = read(run / 'evaluation.json')
    evaluation['scores'] = digest(run / 'scores.json')
    write(run / 'evaluation.json', evaluation)
    manifest = read(run / 'manifest.json')
    manifest['artifacts'] = {name: digest(run / name) for name in ARTIFACTS}
    write(run / 'manifest.json', manifest)


def change_document(package, name, mutate, *, seal=True):
    path = package[0] / name
    document = read(path)
    mutate(document)
    write(path, document)
    if seal:
        reseal(package)


def change_common(package, mutate):
    for name in JSON_NAMES:
        path = package[0] / name
        document = read(path)
        mutate(document)
        configuration = json.dumps(document['configuration'], sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode()
        document['configuration_sha256'] = hashlib.sha256(configuration).hexdigest()
        write(path, document)
    reseal(package)


def test_positive_is_readonly_full_evaluation_and_explicitly_not_model_replay(package):
    before = snapshot(package)
    result = verify(package)
    assert result['status'] == 'VERIFIED'
    assert result['evidence_kind'] == 'SYNTHETIC_ONLY'
    assert result['run_id'] == 'toy-run-v1'
    assert result['policy_status'] == 'AUDIT_ONLY'
    assert result['scope'] == 'STORED_ARTIFACT_CONSISTENCY_ONLY'
    assert result['checks']['model_deserialization'] == 'NOT_PERFORMED'
    assert result['checks']['model_score_replay'] == 'NOT_CHECKED'
    assert result['checks']['source_replay'] == 'VERIFIED'
    assert result['minute_count'] == 144 and result['score_valid_count'] == 24
    assert result['threshold'] == read(package[0] / 'scores.json')['threshold']
    assert result['policies'] == read(package[0] / 'evaluation.json')['evaluation']['policies']
    assert snapshot(package) == before
    encoded = json.dumps(result, allow_nan=False)
    assert all(str(path) not in encoded for path in package)


def test_optional_source_omission_preserves_unknown_source_status(package):
    result = verify(package, source=None)
    assert result['checks']['source_replay'] == 'NOT_PROVIDED'
    assert result['checks']['model_score_replay'] == 'NOT_CHECKED'


def test_whole_package_can_move_without_personal_path_bindings(package, tmp_path):
    before = verify(package)
    moved = tmp_path / 'moved'
    moved.mkdir()
    destinations = tuple(moved / p.name for p in package)
    for source, destination in zip(package, destinations):
        shutil.move(str(source), str(destination))
    assert verify(destinations) == before


def test_arbitrary_nonloadable_weights_can_be_consistent_but_never_model_verified(package):
    (package[0] / 'weights.bin').write_bytes(b'Not a pickle, not joblib, only opaque bytes.\x00\xff')
    reseal(package)
    result = verify(package)
    assert result['status'] == 'VERIFIED'
    assert result['checks']['model_deserialization'] == 'NOT_PERFORMED'
    assert result['checks']['model_score_replay'] == 'NOT_CHECKED'


def test_versions_are_cross_document_declarations_not_current_runtime_compatibility(package):
    change_common(package, lambda d: d.update(library_versions={
        'python': '0.1-declared', 'numpy': '0.2-declared',
        'scikit_learn': '0.3-declared', 'joblib': '0.4-declared'}))
    assert verify(package)['status'] == 'VERIFIED'


def test_fresh_process_verifier_imports_no_model_dependencies_and_loads_no_pickle(package):
    code = '''
import builtins, json, pickle, sys
def forbidden(*args, **kwargs):
    raise AssertionError('No model deserialization is allowed')
pickle.load = pickle.loads = forbidden
original_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('sklearn', 'joblib', 'torch'):
        raise AssertionError('No model dependency import: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded
from traffic_anomaly.candidate_run_artifacts import verify_candidate_if_run
print(json.dumps(verify_candidate_if_run(*sys.argv[1:4], source_fixture=sys.argv[4])))
'''
    completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', code,
        *(str(p) for p in package), str(SOURCE)], capture_output=True, text=True, encoding='utf-8')
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['checks']['model_deserialization'] == 'NOT_PERFORMED'


@pytest.mark.parametrize('name', ('extra.json', 'weights.pkl', 'scores.json.bak'))
def test_five_file_whitelist_rejects_extra_file(package, name):
    (package[0] / name).write_text('extra', encoding='utf-8')
    rejects(package)


@pytest.mark.parametrize('name', (*ARTIFACTS, 'manifest.json'))
def test_missing_required_file_is_safe_failure(package, name):
    (package[0] / name).unlink()
    rejects(package)


@pytest.mark.parametrize('name', ARTIFACTS)
def test_actual_bytes_must_match_manifest_without_resealing(package, name):
    with (package[0] / name).open('ab') as stream:
        stream.write(b' ')
    rejects(package)


def test_evaluation_binds_actual_score_bytes_even_if_outer_manifest_resealed(package):
    evaluation = read(package[0] / 'evaluation.json')
    evaluation['scores']['sha256'] = '0' * 64
    write(package[0] / 'evaluation.json', evaluation)
    manifest = read(package[0] / 'manifest.json')
    manifest['artifacts']['evaluation.json'] = digest(package[0] / 'evaluation.json')
    write(package[0] / 'manifest.json', manifest)
    rejects(package)


@pytest.mark.parametrize('upstream', ('record_manifest', 'input_manifest', 'source_fixture', 'minute_fixture', 'preprocess'))
def test_all_five_upstream_identities_are_bound_even_when_every_run_json_agrees(package, upstream):
    change_common(package, lambda d: d['provenance'][upstream].update(sha256='0' * 64))
    rejects(package, source=None)


@pytest.mark.parametrize('field,value', [
    ('run_id', '../unsafe'), ('run_id', 'é'), ('run_id', 'x' * 65),
    ('model_profile_id', 'production-iforest'), ('schema_version', True),
    ('evidence_kind', 'REAL_DATA'), ('policy_status', 'APPROVED'),
    ('scope', 'RESEARCH_VALIDATED'), ('time_basis', 'UTC'),
    ('value_space', 'raw'), ('selected_policy', 'P_B'),
    ('score_direction', 'LOWER_IS_MORE_ANOMALOUS'), ('qualification_windows', [15]),
])
def test_resealed_consistent_common_metadata_must_still_obey_candidate_scope(package, field, value):
    change_common(package, lambda d: d.update({field: value}))
    rejects(package)


@pytest.mark.parametrize('field,value', [
    ('input_width', 134), ('input_width', True), ('n_estimators', 17),
    ('max_samples', 32), ('quantile', .9), ('quantile_method', 'nearest'),
    ('alarm_comparison', 'GREATER_OR_EQUAL'), ('fit_scope', 'ALL_NORMAL'),
    ('parameter_status', 'RESEARCH_FROZEN'), ('n_jobs', 2),
])
def test_resealed_configuration_is_checked_semantically_not_only_by_hash(package, field, value):
    change_common(package, lambda d: d['configuration'].update({field: value}))
    rejects(package)


@pytest.mark.parametrize('name', JSON_NAMES)
def test_common_run_identity_must_match_across_all_json(package, name):
    change_document(package, name, lambda d: d.update(run_id='different-valid-run'))
    rejects(package)


def test_library_version_declarations_cannot_disagree_between_json(package):
    change_document(package, 'scores.json', lambda d: d['library_versions'].update(numpy='other-version'))
    rejects(package)


@pytest.mark.parametrize('value', [None, {}, {'python': '3.14'},
    {'python': True, 'numpy': 'x', 'scikit_learn': 'x', 'joblib': 'x'},
    {'python': '', 'numpy': 'x', 'scikit_learn': 'x', 'joblib': 'x'}])
def test_library_versions_have_complete_nonempty_string_schema(package, value):
    change_common(package, lambda d: d.update(library_versions=value))
    rejects(package)


def test_saved_preprocessing_state_is_bound_to_verified_upstream(package):
    change_common(package, lambda d: d['preprocessing_state']['scale'].__setitem__(0, 999.))
    rejects(package)


def test_feature_order_cannot_be_reversed_consistently(package):
    change_common(package, lambda d: d['feature_names'].reverse())
    rejects(package)


@pytest.mark.parametrize('mutation', [
    lambda d: d['timestamps'].pop(),
    lambda d: d['timestamps'].__setitem__(30, '2000-01-01T00:00:00.000000'),
    lambda d: d['segment_ids'].__setitem__(30, 'wrong-segment'),
    lambda d: d['partitions'].__setitem__(30, 'test'),
    lambda d: d['current_input_valid'].__setitem__(0, False),
    lambda d: d['common_valid'].__setitem__(30, False),
    lambda d: d['score_valid'].__setitem__(30, False),
    lambda d: d['score_valid'].__setitem__(30, 1),
    lambda d: d['history_invalid_reason']['15'].__setitem__(0, None),
    lambda d: d['scores'].__setitem__(0, 0.),
    lambda d: d['alarms'].__setitem__(0, False),
    lambda d: d['scores'].__setitem__(30, None),
    lambda d: d['scores'].__setitem__(30, True),
    lambda d: d['alarms'].__setitem__(30, not d['alarms'][30]),
])
def test_resealed_full_axis_masks_reasons_null_and_alarm_semantics(package, mutation):
    change_document(package, 'scores.json', mutation)
    rejects(package)


@pytest.mark.parametrize('field', ('fit_indices', 'calibration_indices'))
@pytest.mark.parametrize('kind', ('outside', 'duplicate', 'boolean', 'reverse'))
def test_exact_train_and_independent_calibration_indices_are_verified(package, field, kind):
    def mutate(document):
        values = document[field]
        if kind == 'outside': values[0] = 140
        if kind == 'duplicate': values[1] = values[0]
        if kind == 'boolean': values[0] = True
        if kind == 'reverse': values.reverse()
    change_document(package, 'model-state.json', mutate)
    rejects(package)


def test_threshold_is_recomputed_from_stored_calibration_scores_not_just_cross_json(package):
    for name in ('scores.json', 'evaluation.json'):
        path = package[0] / name
        document = read(path)
        document['threshold'] += .1
        write(path, document)
    reseal(package)
    rejects(package)


@pytest.mark.parametrize('field,value', [('sample_count', 7), ('quantile', .9),
    ('method', 'nearest'), ('comparison', 'GREATER_OR_EQUAL'),
    ('order_position_zero_based', 0.), ('strictly_above_count', 99), ('equal_count', 99)])
def test_calibration_metadata_is_recomputed_even_when_documents_agree(package, field, value):
    for name in ('scores.json', 'evaluation.json'):
        path = package[0] / name
        document = read(path)
        document['calibration'][field] = value
        write(path, document)
    reseal(package)
    rejects(package)


@pytest.mark.parametrize('policy', ('P_U', 'P_B', 'P_A'))
@pytest.mark.parametrize('section,field,value', [
    ('metrics', 'fpr', .1234567), ('confusion_counts', 'tp', 999),
    (None, 'normal_minutes', 999), (None, 'unknown_source_attack_present', 999),
    ('undefined_reasons', 'fpr', 'invented reason'),
])
def test_every_policy_evaluation_is_recomputed_in_full(package, policy, section, field, value):
    def mutate(document):
        target = document['evaluation']['policies'][policy]
        if section is not None: target = target[section]
        target[field] = value
    change_document(package, 'evaluation.json', mutate)
    rejects(package)


def test_nested_evaluation_score_origin_policy_must_match(package):
    change_document(package, 'evaluation.json', lambda d: d['evaluation'].update(score_origin_policy='P_B'))
    rejects(package)


@pytest.mark.parametrize('name', JSON_NAMES)
@pytest.mark.parametrize('kind', ('duplicate_key', 'nan'))
def test_strict_json_rejects_duplicate_keys_and_nonstandard_nan(package, name, kind):
    path = package[0] / name
    payload = path.read_text('utf-8')
    if kind == 'duplicate_key': payload = '{"schema_version":1,' + payload.lstrip()[1:]
    else: payload = '{"untrusted_number":NaN,' + payload.lstrip()[1:]
    path.write_text(payload, encoding='utf-8')
    # Seal raw bytes without parsing the deliberately malformed target.
    if name == 'scores.json':
        evaluation = read(package[0] / 'evaluation.json')
        evaluation['scores'] = digest(path)
        write(package[0] / 'evaluation.json', evaluation)
    if name != 'manifest.json':
        manifest = read(package[0] / 'manifest.json')
        manifest['artifacts'] = {n: digest(package[0] / n) for n in ARTIFACTS}
        write(package[0] / 'manifest.json', manifest)
    rejects(package)


def test_manifest_cannot_supply_arbitrary_artifact_paths(package):
    manifest = read(package[0] / 'manifest.json')
    manifest['artifacts']['../private-weights.bin'] = manifest['artifacts'].pop('weights.bin')
    write(package[0] / 'manifest.json', manifest)
    rejects(package)


@pytest.mark.parametrize('name,limit', [('weights.bin', 8*1024*1024), ('scores.json', 16*1024*1024)])
def test_individual_size_limits_are_checked_before_parsing(package, name, limit):
    with (package[0] / name).open('wb') as stream:
        stream.truncate(limit + 1)
    assert rejects(package) == 'RESOURCE_LIMIT'


def test_total_limit_counts_all_five_files_even_when_each_file_is_below_its_limit(package):
    run = package[0]
    for name in ('model-state.json', 'scores.json', 'evaluation.json'):
        path = run / name
        payload = path.read_bytes()
        path.write_bytes(payload + b' ' * (12*1024*1024 - len(payload)))
    evaluation = read(run / 'evaluation.json')
    evaluation['scores'] = digest(run / 'scores.json')
    payload = json.dumps(evaluation, sort_keys=True).encode('utf-8')
    (run / 'evaluation.json').write_bytes(payload + b' ' * (12*1024*1024 - len(payload)))
    manifest = read(run / 'manifest.json')
    manifest['artifacts'] = {name: digest(run / name) for name in ARTIFACTS}
    write(run / 'manifest.json', manifest)
    # File bytes remain valid JSON; reject the total before semantic/hash work.
    assert all(p.stat().st_size <= (8 if p.name == 'weights.bin' else 16)*1024*1024 for p in run.iterdir())
    assert sum(p.stat().st_size for p in run.iterdir()) > 32*1024*1024
    assert rejects(package) == 'RESOURCE_LIMIT'


@pytest.mark.parametrize('target', ('same-as-records', 'same-as-inputs'))
def test_directory_aliases_do_not_let_run_files_stand_in_for_upstream(package, target):
    run, records, inputs = package
    rejects((run, run if target == 'same-as-records' else records,
             run if target == 'same-as-inputs' else inputs))


@pytest.mark.parametrize('kind', ('run-directory', 'weights-file', 'ancestor-before-dotdot'))
def test_reparse_points_are_rejected_before_canonicalization(package, tmp_path, monkeypatch, kind):
    run, records, inputs = package
    alias = tmp_path / 'lexical-reparse'
    alias.mkdir()
    target = {'run-directory': run, 'weights-file': run / 'weights.bin',
              'ancestor-before-dotdot': alias}[kind]
    supplied_run = alias / '..' / run.name if kind == 'ancestor-before-dotdot' else run
    original = Path.lstat
    def flagged(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target:
            fields = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
            fields['st_file_attributes'] = getattr(info, 'st_file_attributes', 0) | 1024
            return SimpleNamespace(**fields)
        return info
    monkeypatch.setattr(Path, 'lstat', flagged)
    rejects((supplied_run, records, inputs))


def test_actual_symlink_file_is_rejected_when_supported(package, tmp_path):
    weights = package[0] / 'weights.bin'
    target = tmp_path / 'outside-weights.bin'
    weights.replace(target)
    try:
        weights.symlink_to(target)
    except OSError:
        pytest.skip('Creating actual symlinks is not permitted on this host')
    rejects(package)


def test_optional_source_still_checks_provided_artificial_bytes(package, tmp_path):
    altered = tmp_path / 'altered-source.json'
    altered.write_bytes(SOURCE.read_bytes() + b' ')
    rejects(package, source=altered)
