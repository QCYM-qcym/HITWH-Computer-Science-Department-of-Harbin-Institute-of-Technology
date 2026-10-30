"""Cross-run byte/qualification alignment, without model or causal proof."""
from collections import Counter
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest


SOURCE = Path(__file__).parents[1] / 'fixtures' / 'g13u-records-v1.json'
SLOTS = ('iforest_current13', 'current_ae13', 'history_ae26_h15', 'history_ae26_h30')
POPULATION = ('calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes',
              'normal_minutes', 'attack_minutes', 'unknown_minutes', 'unknown_source_attack_present')


def read(path): return json.loads(path.read_text('utf-8'))
def write(path, value): path.write_text(json.dumps(value, allow_nan=False, sort_keys=True) + '\n', encoding='utf-8')
def digest(path):
    payload = path.read_bytes()
    return dict(sha256=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    # Only setup executes four engineering-toy models; comparison must not.
    from traffic_anomaly.candidate_record_cli import _run as record_run
    from traffic_anomaly.candidate_cli import _run as input_run
    from traffic_anomaly.candidate_if_cli import run_synthetic_candidate_if
    from traffic_anomaly.candidate_ae_cli import run_synthetic_candidate_ae
    base = tmp_path_factory.mktemp('candidate-comparison')
    records, inputs = base / 'records', base / 'inputs'
    record_run(SOURCE, 'P_U', records)
    input_run(records / 'minute-fixture.json', inputs)
    runs = {slot: base / slot for slot in SLOTS}
    run_synthetic_candidate_if(records, inputs, SOURCE, 'comparison-if', runs[SLOTS[0]])
    for slot, method, window in ((SLOTS[1], 'current_ae', None), (SLOTS[2], 'history_ae', 15),
                                 (SLOTS[3], 'history_ae', 30)):
        run_synthetic_candidate_ae(records, inputs, SOURCE, slot.replace('_', '-'), runs[slot],
                                   method=method, history_window=window)
    return runs, records, inputs


@pytest.fixture
def package(originals, tmp_path):
    runs, records, inputs = originals
    copied = {slot: tmp_path / path.name for slot, path in runs.items()}
    for slot, path in runs.items(): shutil.copytree(path, copied[slot])
    destination_records, destination_inputs = tmp_path / 'records', tmp_path / 'inputs'
    shutil.copytree(records, destination_records)
    shutil.copytree(inputs, destination_inputs)
    return copied, destination_records, destination_inputs


def specs(package, chosen=SLOTS):
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun
    return [CandidateComparisonRun('iforest' if slot == SLOTS[0] else 'autoencoder', package[0][slot])
            for slot in chosen]


def compare(package, chosen=SLOTS, *, source=SOURCE):
    from traffic_anomaly.candidate_comparison import compare_candidate_runs
    return compare_candidate_runs(specs(package, chosen), package[1], package[2], source_fixture=source)


def reject(callback, *, code=None):
    from traffic_anomaly.candidate_comparison import CandidateComparisonError
    with pytest.raises(CandidateComparisonError) as caught: callback()
    assert caught.value.code == str(caught.value)
    assert re.fullmatch(r'[A-Z][A-Z0-9_]*', caught.value.code)
    if code is not None: assert caught.value.code == code
    return caught.value.code


def file_snapshot(package):
    directories = [*package[0].values(), package[1], package[2]]
    paths = [SOURCE, *(path for directory in directories for path in directory.iterdir())]
    return {path: (digest(path), path.stat().st_mtime_ns) for path in paths}


def reseal(run):
    weights_name = 'weights.bin' if (run / 'weights.bin').exists() else 'weights.json'
    state = read(run / 'model-state.json'); state['weights'] = digest(run / weights_name)
    write(run / 'model-state.json', state)
    evaluation = read(run / 'evaluation.json'); evaluation['scores'] = digest(run / 'scores.json')
    write(run / 'evaluation.json', evaluation)
    manifest = read(run / 'manifest.json')
    manifest['artifacts'] = {name: digest(run / name) for name in
        ('model-state.json', weights_name, 'scores.json', 'evaluation.json')}
    write(run / 'manifest.json', manifest)


def change_common(run, mutate):
    names = ['manifest.json', 'model-state.json', 'scores.json', 'evaluation.json']
    if (run / 'weights.json').exists(): names.append('weights.json')
    for name in names:
        path = run / name; data = read(path)
        mutate(data['binding'] if name == 'weights.json' else data)
        write(path, data)
    reseal(run)


def verifier(slot):
    if slot == SLOTS[0]:
        from traffic_anomaly.candidate_run_artifacts import verify_candidate_if_run
        return verify_candidate_if_run
    from traffic_anomaly.candidate_ae_run_artifacts import verify_candidate_ae_run
    return verify_candidate_ae_run


def patch_ae_verifier(monkeypatch, callback):
    from traffic_anomaly import candidate_comparison
    monkeypatch.setattr(candidate_comparison, 'verify_candidate_ae_run', callback)


def test_four_slots_report_original_results_and_no_extra_proof(package):
    before = file_snapshot(package)
    result = compare(package, tuple(reversed(SLOTS)))
    assert result['schema_version'] == 1 and result['comparison_profile_id'] == 'c17-i1-g13u-comparison-context-v1'
    assert result['status'] == 'DATA_QUALIFICATION_ALIGNED'
    assert result['scope'] == 'SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY'
    assert result['evidence_kind'] == 'SYNTHETIC_ONLY' and result['policy_status'] == 'AUDIT_ONLY'
    assert result['included_slots'] == list(SLOTS) and result['missing_slots'] == []
    assert [row['slot'] for row in result['runs']] == list(SLOTS)
    context = result['shared_context']; manifest = read(package[0][SLOTS[0]] / 'manifest.json')
    assert context['five_provenance'] == manifest['provenance']
    assert context['preprocessing_identity'] == manifest['provenance']['preprocess']
    assert context['preprocessing_state'] == manifest['preprocessing_state']
    assert context['selected_policy'] == 'P_U' and context['source_replay'] == 'VERIFIED'
    assert context['qualification_windows'] == [15, 30]
    assert (context['minute_count'], context['score_valid_count'], context['fit_count'], context['calibration_count']) == (144, 24, 6, 6)
    for row in result['runs']:
        original = verifier(row['slot'])(package[0][row['slot']], package[1], package[2], source_fixture=SOURCE)
        stored = read(package[0][row['slot']] / 'manifest.json')
        assert row['run_id'] == stored['run_id'] and row['configuration'] == stored['configuration']
        assert row['threshold'] == original['threshold'] and row['calibration'] == original['calibration']
        assert row['policies'] == original['policies']
        assert row['actual_five_artifacts'] == original['artifacts']
        assert row['verification_checks'] == original['checks']
        assert row['library_versions'] == stored['library_versions']
        assert row['parameter_count'] == (None if row['slot'] == SLOTS[0] else 288 if row['slot'] == SLOTS[1] else 509)
        if row['slot'] == SLOTS[0]: assert row['parameter_count_reason'] == 'NOT_DEFINED_FOR_OPAQUE_IF'
        for policy, counts in row['policies'].items():
            assert context['test_denominators_by_policy'][policy] == {k: counts[k] for k in POPULATION}
    for key in ('capacity_control', 'history_causal_attribution', 'cross_model_score_scale'):
        assert result['limitations'][key] == 'NOT_COMPARABLE'
    assert result['limitations']['ranking'] == result['limitations']['statistical_significance'] == 'NOT_PERFORMED'
    assert file_snapshot(package) == before
    encoded = json.dumps(result, allow_nan=False)
    assert all(str(path) not in encoded for path in package[0].values())
    assert not any(key in result for key in ('winner', 'rank', 'best_window', 'p_value'))


@pytest.mark.parametrize('chosen', [(SLOTS[0], SLOTS[1]), (SLOTS[2], SLOTS[3]), SLOTS[:3]])
def test_supported_partial_sets_keep_fixed_order_and_explicit_missing_slots(package, chosen):
    result = compare(package, tuple(reversed(chosen)), source=None)
    assert result['included_slots'] == [slot for slot in SLOTS if slot in chosen]
    assert result['missing_slots'] == [slot for slot in SLOTS if slot not in chosen]
    assert result['shared_context']['source_replay'] == 'NOT_PROVIDED'


@pytest.mark.parametrize('kind', ['empty', 'one', 'five', 'generator', 'unknown_family', 'not_a_run'])
def test_invalid_run_container_or_family_fails_before_file_reads(package, monkeypatch, kind):
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun, compare_candidate_runs
    values = specs(package)
    candidate = {'empty': [], 'one': values[:1], 'five': values + values[:1],
                 'generator': iter(values), 'unknown_family': [CandidateComparisonRun('arbitrary.module', 'missing'), values[0]],
                 'not_a_run': [object(), values[0]]}[kind]
    def forbidden(*args, **kwargs): raise AssertionError('invalid container must fail before opening files')
    monkeypatch.setattr(Path, 'open', forbidden)
    reject(lambda: compare_candidate_runs(candidate, package[1], package[2]))


def test_run_specification_is_frozen_and_does_not_accept_runtime_model_classes(package):
    value = specs(package)[0]
    with pytest.raises((FrozenInstanceError, AttributeError)): value.family = 'autoencoder'


def test_canonical_directory_alias_cannot_be_listed_twice(package):
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun, compare_candidate_runs
    same = package[0][SLOTS[0]]
    runs = [CandidateComparisonRun('iforest', same), CandidateComparisonRun('iforest', same / '..' / same.name)]
    reject(lambda: compare_candidate_runs(runs, package[1], package[2], source_fixture=SOURCE))


def test_distinct_slots_with_duplicate_valid_run_id_are_rejected(package):
    run_id = read(package[0][SLOTS[0]] / 'manifest.json')['run_id']
    change_common(package[0][SLOTS[1]], lambda d: d.update(run_id=run_id))
    reject(lambda: compare(package, SLOTS[:2]), code='DUPLICATE_RUN_ID')


def test_duplicate_slot_with_distinct_directory_and_run_id_is_rejected(package, tmp_path):
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun, compare_candidate_runs
    copied = tmp_path / 'second-current-ae'; shutil.copytree(package[0][SLOTS[1]], copied)
    change_common(copied, lambda d: d.update(run_id='another-current-ae'))
    runs = [CandidateComparisonRun('autoencoder', package[0][SLOTS[1]]), CandidateComparisonRun('autoencoder', copied)]
    reject(lambda: compare_candidate_runs(runs, package[1], package[2], source_fixture=SOURCE), code='DUPLICATE_RUN_SLOT')


def test_manifest_pre_read_bytes_are_bound_to_verifier_actual_digest(package, monkeypatch):
    actual = verifier(SLOTS[1]); changed = []
    def switch(run, records, inputs, *, source_fixture=None):
        if Path(run) == package[0][SLOTS[1]] and not changed:
            change_common(Path(run), lambda d: d.update(run_id='new-valid-id-during-verification'))
            changed.append(True)
        return actual(run, records, inputs, source_fixture=source_fixture)
    patch_ae_verifier(monkeypatch, switch)
    reject(lambda: compare(package, SLOTS[:2]), code='CHANGED_DURING_COMPARISON')
    assert changed


@pytest.mark.parametrize('change', ['manifest_digest', 'score_count', 'fit_count', 'policy_population',
    'source_scope', 'scope_upgrade', 'proof_upgrade'])
def test_comparison_checks_verifier_report_contradictions(package, monkeypatch, change):
    actual = verifier(SLOTS[1])
    def changed(run, records, inputs, *, source_fixture=None):
        result = deepcopy(actual(run, records, inputs, source_fixture=source_fixture))
        if change == 'manifest_digest': result['artifacts']['manifest.json']['sha256'] = '0' * 64
        elif change == 'score_count': result['score_valid_count'] += 1
        elif change == 'fit_count': result['fit_count'] += 1
        elif change == 'policy_population': result['policies']['P_U']['unknown_minutes'] += 1
        elif change == 'source_scope': result['checks']['source_replay'] = 'NOT_PROVIDED'
        elif change == 'scope_upgrade': result['scope'] = 'MODEL_EXECUTION_VALIDATED'
        else: result['checks']['model_score_replay'] = 'VERIFIED'
        return result
    patch_ae_verifier(monkeypatch, changed)
    reject(lambda: compare(package, SLOTS[:2]))


@pytest.mark.parametrize('change', ['provenance_bytes', 'preprocessing_state', 'selected_policy',
    'field_order', 'qualification_window', 'fit_scope'])
def test_equal_counts_do_not_hide_inconsistent_bound_manifest_context(package, monkeypatch, change):
    # Isolate comparison's own cross-run checks: a stub supplies a previously
    # VERIFIED report, with its manifest identity rebound to the probe bytes.
    actual = verifier(SLOTS[1]); target = package[0][SLOTS[1]]
    target_report = actual(target, package[1], package[2], source_fixture=SOURCE)
    manifest = read(target / 'manifest.json')
    if change == 'provenance_bytes': manifest['provenance']['preprocess']['sha256'] = '0' * 64
    elif change == 'preprocessing_state': manifest['preprocessing_state']['scale'][0] += 1.
    elif change == 'selected_policy': manifest['selected_policy'] = 'P_B'
    elif change == 'field_order': manifest['feature_names'].reverse()
    elif change == 'qualification_window': manifest['qualification_windows'] = [15]
    else: manifest['configuration']['fit_scope'] = 'ALL_NORMAL'
    write(target / 'manifest.json', manifest)
    target_report['artifacts']['manifest.json'] = digest(target / 'manifest.json')
    def bound_report(run, records, inputs, *, source_fixture=None):
        return deepcopy(target_report) if Path(run) == target else actual(run, records, inputs, source_fixture=source_fixture)
    patch_ae_verifier(monkeypatch, bound_report)
    reject(lambda: compare(package, SLOTS[:2]))


def rewrite_predictions(run, records, inputs, *, all_zero):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
    from traffic_anomaly.candidate_autoencoder import _calibrate
    from traffic_anomaly.candidate_evaluation import evaluate_candidate_predictions
    snapshot = load_verified_candidate_artifacts(records, inputs, source_fixture=SOURCE)
    common = snapshot.common_valid
    scores = np.full(len(common), np.nan); scores[common] = 0. if all_zero else 7.
    if not all_zero: scores[snapshot.calibration_normal] = np.arange(1., 7.)
    threshold, alarms, calibration = _calibrate(scores, common, snapshot.calibration_normal)
    document = read(run / 'scores.json')
    document.update(scores=[float(v) if keep else None for v, keep in zip(scores, common)],
                    alarms=[bool(v) if keep else None for v, keep in zip(alarms, common)],
                    threshold=threshold, calibration=calibration)
    if (run / 'weights.json').exists():
        document['current_reconstruction_mse'] = list(document['scores'])
        if document['configuration']['method'] == 'history_ae':
            document['history_deviation_reconstruction_mse'] = list(document['scores'])
    write(run / 'scores.json', document)
    evaluation = read(run / 'evaluation.json')
    evaluation.update(threshold=threshold, calibration=calibration,
        evaluation=evaluate_candidate_predictions(labels=snapshot.labels, partitions=snapshot.partitions,
            score_valid=common, alarms=alarms, source_attack_label_present=snapshot.source_attack_label_present,
            score_origin_policy=snapshot.report['selected_policy']))
    write(run / 'evaluation.json', evaluation); reseal(run)


def test_different_coherent_predictions_null_metrics_and_tail_counts_are_preserved_not_ranked(package):
    rewrite_predictions(package[0][SLOTS[0]], package[1], package[2], all_zero=False)
    rewrite_predictions(package[0][SLOTS[1]], package[1], package[2], all_zero=True)
    result = compare(package, SLOTS[:2]); forest, current = result['runs']
    assert forest['threshold'] == 5.95 and current['threshold'] == 0.
    assert forest['calibration']['equal_count'] == 0 and current['calibration']['equal_count'] == 6
    assert forest['policies']['P_U']['confusion_counts'] != current['policies']['P_U']['confusion_counts']
    assert current['policies']['P_U']['metrics']['precision'] is None
    assert 'precision' in current['policies']['P_U']['undefined_reasons']
    assert result['limitations']['cross_model_score_scale'] == 'NOT_COMPARABLE'
    assert all(row['verification_checks']['model_score_replay'] == 'NOT_CHECKED' for row in result['runs'])


def test_legal_distinct_execution_declarations_are_reported_as_uncontrolled(package):
    change_common(package[0][SLOTS[1]], lambda d: d.update(
        library_versions=dict(python='0.1-declared', numpy='0.2-declared', torch='0.3-declared'),
        runtime=dict(device='cpu', torch_num_threads=2, torch_num_interop_threads=3)))
    result = compare(package, SLOTS[:2])
    assert result['limitations']['execution_controls'] == 'DECLARED_EXECUTION_CONTROLS_DIFFER'
    assert result['runs'][1]['library_versions']['torch'] == '0.3-declared'
    assert result['runs'][1]['runtime']['torch_num_threads'] == 2


def test_manifest_has_one_extra_read_but_other_run_files_are_not_reopened(package, monkeypatch):
    reads = Counter(); actual = Path.open
    run_paths = set(package[0].values())
    def counted(path, *args, **kwargs):
        if path.parent in run_paths: reads[(path.parent, path.name)] += 1
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', counted)
    compare(package, SLOTS[:2])
    for slot in SLOTS[:2]:
        run = package[0][slot]
        assert reads[(run, 'manifest.json')] == 2
        for name in ('scores.json', 'evaluation.json', 'model-state.json'):
            assert reads[(run, name)] == 1


@pytest.mark.parametrize('kind', ['duplicate_keys', 'nonfinite', 'bad_utf8', 'oversized'])
def test_additional_manifest_read_is_bounded_and_strict(package, kind):
    path = package[0][SLOTS[0]] / 'manifest.json'
    if kind == 'oversized':
        with path.open('wb') as stream: stream.truncate(16*1024*1024 + 1)
    elif kind == 'bad_utf8': path.write_bytes(b'\xff')
    else:
        body = path.read_text('utf-8')
        path.write_text(('{"schema_version":1,' if kind == 'duplicate_keys' else '{"number":1e999,') + body.lstrip()[1:], 'utf-8')
    reject(lambda: compare(package, SLOTS[:2]), code='RESOURCE_LIMIT' if kind == 'oversized' else None)


def test_lexical_reparse_ancestor_is_not_hidden_by_dotdot_canonicalization(package, tmp_path, monkeypatch):
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun, compare_candidate_runs
    alias = tmp_path / 'lexical-link'; alias.mkdir(); actual = Path.lstat
    def marked(path, *args, **kwargs):
        info = actual(path, *args, **kwargs)
        if path == alias:
            fields = {key: getattr(info, key) for key in dir(info) if key.startswith('st_')}
            fields['st_file_attributes'] = getattr(info, 'st_file_attributes', 0) | 1024
            return SimpleNamespace(**fields)
        return info
    monkeypatch.setattr(Path, 'lstat', marked)
    runs = [CandidateComparisonRun('iforest', alias / '..' / package[0][SLOTS[0]].name), specs(package)[1]]
    reject(lambda: compare_candidate_runs(runs, package[1], package[2], source_fixture=SOURCE))


def test_fresh_comparison_import_and_execution_use_no_model_dependencies(package):
    code = '''
import builtins, json, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('torch', 'sklearn', 'joblib'):
        raise AssertionError('comparison imported a training runtime: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from traffic_anomaly.candidate_comparison import CandidateComparisonRun, compare_candidate_runs
runs=[CandidateComparisonRun('iforest',sys.argv[1]),CandidateComparisonRun('autoencoder',sys.argv[2])]
result=compare_candidate_runs(runs,sys.argv[3],sys.argv[4],source_fixture=sys.argv[5])
assert not any(x in sys.modules for x in ('torch','sklearn','joblib'))
print(json.dumps(result))
'''
    completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', code,
        str(package[0][SLOTS[0]]), str(package[0][SLOTS[1]]), str(package[1]), str(package[2]), str(SOURCE)],
        capture_output=True, text=True, encoding='utf-8')
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['status'] == 'DATA_QUALIFICATION_ALIGNED'
