"""Saved candidate minute payloads for replay consumers, without model loading."""
from collections import Counter
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields
import hashlib
import importlib
import json
import math
from pathlib import Path
import shutil
from types import MappingProxyType

import pytest

SOURCE = Path(__file__).parents[1] / 'fixtures/g13u-records-v1.json'
SLOTS = ('if', 'current', 'history15', 'history30')


def read(path):
    return json.loads(path.read_text('utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False) + '\n', 'utf-8')


def digest(path):
    data = path.read_bytes()
    return dict(sha256=hashlib.sha256(data).hexdigest(), byte_count=len(data))


def api(slot):
    suffix = 'if' if slot == 'if' else 'ae'
    module = importlib.import_module('traffic_anomaly.candidate_' + ('run_artifacts' if suffix == 'if' else 'ae_run_artifacts'))
    load = getattr(module, f'load_verified_candidate_{suffix}_run', None)
    assert callable(load), 'verified saved-run payload loader is missing'
    return load, getattr(module, f'verify_candidate_{suffix}_run')


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    # Explicit SYNTHETIC_ONLY fixture generation may train toy models. Loading
    # snapshots below must not fit, score, deserialize or rebuild those models.
    from traffic_anomaly.candidate_record_cli import _run as records_run
    from traffic_anomaly.candidate_cli import _run as numeric_run
    from traffic_anomaly.candidate_if_cli import run_synthetic_candidate_if
    from traffic_anomaly.candidate_ae_cli import run_synthetic_candidate_ae
    base = tmp_path_factory.mktemp('saved-run-snapshots')
    records, inputs = base / 'records', base / 'inputs'
    records_run(SOURCE, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    runs = {}
    for slot in SLOTS:
        run = base / slot
        if slot == 'if':
            run_synthetic_candidate_if(records, inputs, SOURCE, 'snapshot-if', run)
        else:
            window = None if slot == 'current' else int(slot.removeprefix('history'))
            run_synthetic_candidate_ae(records, inputs, SOURCE, 'snapshot-' + slot, run,
                method='current_ae' if window is None else 'history_ae', history_window=window)
        runs[slot] = (run, records, inputs)
    return runs


def copied(originals, slot, directory):
    package = tuple(directory / p.name for p in originals[slot])
    for original, target in zip(originals[slot], package):
        shutil.copytree(original, target)
    return package


def reseal(run):
    evaluation = read(run / 'evaluation.json')
    evaluation['scores'] = digest(run / 'scores.json')
    write(run / 'evaluation.json', evaluation)
    manifest = read(run / 'manifest.json')
    manifest['artifacts'] = {name: digest(run / name) for name in manifest['artifacts']}
    write(run / 'manifest.json', manifest)


def assert_immutable(value):
    if isinstance(value, Mapping):
        if value:
            key = next(iter(value))
            with pytest.raises(TypeError):
                value[key] = value[key]
        for item in value.values():
            assert_immutable(item)
    elif isinstance(value, tuple):
        if value:
            with pytest.raises(TypeError):
                value[0] = value[0]
        for item in value:
            assert_immutable(item)
    else:
        assert value is None or type(value) in (str, bool, int, float)


@pytest.mark.parametrize('slot', SLOTS)
@pytest.mark.parametrize('include_source', [False, True])
def test_exact_saved_document_and_old_report_for_four_slots(originals, slot, include_source):
    load, verify = api(slot)
    package = originals[slot]
    source = SOURCE if include_source else None
    expected = read(package[0] / 'scores.json')
    payload = load(*package, source_fixture=source)
    assert payload.report_dict() == verify(*package, source_fixture=source)
    assert payload.scores_dict() == expected
    assert payload.report['checks']['source_replay'] == ('VERIFIED' if include_source else 'NOT_PROVIDED')
    assert len(payload.scores_document['timestamps']) == 144
    assert sum(v is None for v in payload.scores_document['scores']) == 120
    assert sum(v is None for v in payload.scores_document['alarms']) == 120
    assert set(payload.scores_document['history_invalid_reason']) == {'15', '30'}
    assert payload.report['artifacts']['scores.json'] == digest(package[0] / 'scores.json')
    if slot == 'if':
        assert 'current_reconstruction_mse' not in payload.scores_document
    else:
        historical = payload.scores_document['history_deviation_reconstruction_mse']
        assert sum(v is None for v in historical) == (144 if slot == 'current' else 120)
    assert payload.report['checks']['model_deserialization'] == 'NOT_PERFORMED'
    assert payload.report['checks']['model_score_replay'] == 'NOT_CHECKED'


@pytest.mark.parametrize('slot', SLOTS)
def test_deeply_frozen_payload_and_independent_json_copies(originals, slot):
    load, _ = api(slot)
    payload = load(*originals[slot], source_fixture=SOURCE)
    assert {field.name for field in fields(payload)} == {'report', 'scores_document'}
    assert not hasattr(payload, '__dict__')
    with pytest.raises(FrozenInstanceError):
        payload.report = {}
    assert_immutable(payload.report)
    assert_immutable(payload.scores_document)
    report, scores = payload.report_dict(), payload.scores_dict()
    report['artifacts']['scores.json']['sha256'] = 'changed'
    scores['scores'][30] = 999
    scores['history_invalid_reason']['15'][0] = 'changed'
    assert payload.report_dict()['artifacts']['scores.json']['sha256'] != 'changed'
    assert payload.scores_dict() == read(originals[slot][0] / 'scores.json')


@pytest.mark.parametrize('slot', SLOTS)
def test_loading_reads_each_payload_once_and_never_runs_models(originals, slot, monkeypatch):
    from traffic_anomaly import candidate_autoencoder as ae, candidate_ae_weights as weights, candidate_iforest as forest
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor
    load, _ = api(slot)
    def forbidden(*args, **kwargs):
        raise AssertionError('model execution forbidden while loading')
    for module, names in [(ae, ('compute_synthetic_candidate_ae', 'replay_candidate_ae')),
                          (weights, ('build_candidate_ae_network', 'rebuild_candidate_ae_from_json')),
                          (forest, ('compute_synthetic_candidate_if', 'replay_saved_candidate_if'))]:
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(CandidatePreprocessor, 'fit', forbidden)
    package = originals[slot]
    expected = {SOURCE.resolve(), *(p.resolve() for directory in package for p in directory.iterdir())}
    counts, original_open = Counter(), Path.open
    def track(path, *args, **kwargs):
        if path.resolve() in expected:
            counts[path.resolve()] += 1
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', track)
    payload = load(*package, source_fixture=SOURCE)
    assert len(payload.scores_document['scores']) == 144
    assert set(counts) == expected and all(count == 1 for count in counts.values())


@pytest.mark.parametrize('slot', SLOTS)
def test_loaded_payload_survives_original_file_changes(originals, slot, tmp_path):
    load, _ = api(slot)
    package = copied(originals, slot, tmp_path)
    payload = load(*package, source_fixture=SOURCE)
    report, scores = payload.report_dict(), payload.scores_dict()
    (package[0] / 'scores.json').write_bytes(b'not json')
    assert payload.report_dict() == report and payload.scores_dict() == scores
    with pytest.raises(ValueError):
        load(*package, source_fixture=SOURCE)


@pytest.mark.parametrize('slot', ['if', 'current'])
@pytest.mark.parametrize('fault', ['missing', 'nonfinite', 'resealed_alarm'])
def test_original_failure_codes_are_preserved(originals, slot, fault, tmp_path):
    load, verify = api(slot)
    package = copied(originals, slot, tmp_path)
    target = package[0] / 'scores.json'
    if fault == 'missing':
        target.unlink()
    elif fault == 'nonfinite':
        target.write_text('{"scores":[NaN]}', 'utf-8')
    else:
        value = read(target)
        value['alarms'][30] = not value['alarms'][30]
        write(target, value)
        reseal(package[0])
    with pytest.raises(ValueError) as old:
        verify(*package, source_fixture=SOURCE)
    with pytest.raises(type(old.value)) as new:
        load(*package, source_fixture=SOURCE)
    assert new.value.code == old.value.code
    assert str(new.value) == new.value.code


@pytest.mark.parametrize('slot', ['if', 'current'])
def test_stored_negative_zero_is_not_replaced_by_recomputed_document(originals, slot, tmp_path):
    load, _ = api(slot)
    package = copied(originals, slot, tmp_path)
    target = package[0] / 'scores.json'
    doc = read(target)
    index = next(i for i, part in enumerate(doc['partitions']) if part == 'test' and doc['score_valid'][i])
    doc['scores'][index] = -0.0
    if slot == 'current':
        # Current AE arithmetic compares equal, but rebuilding from +0.0 would
        # lose the stored score's sign. This is exact equality, not tolerance.
        doc['current_reconstruction_mse'][index] = 0.0
    assert doc['alarms'][index] is False
    write(target, doc)
    reseal(package[0])
    payload = load(*package, source_fixture=SOURCE)
    assert payload.scores_dict() == doc
    assert math.copysign(1, payload.scores_document['scores'][index]) == -1


def test_snapshot_detaches_constructor_inputs():
    module_name = 'traffic_anomaly.candidate_run_snapshot'
    assert importlib.util.find_spec(module_name) is not None, 'saved-run snapshot type is missing'
    cls = importlib.import_module(module_name).VerifiedCandidateRun
    report, scores = {'nested': {'items': [1]}}, {'scores': [None, .5]}
    payload = cls(report, scores)
    report['nested']['items'][0] = 3
    scores['scores'][1] = 4
    assert payload.report_dict() == {'nested': {'items': [1]}}
    assert payload.scores_dict() == {'scores': [None, .5]}


def test_constructor_requires_plain_json_dictionaries():
    from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun
    mapping = MappingProxyType({'nested': {'items': [1]}})
    for report, scores in [(mapping, {}), ({}, mapping)]:
        with pytest.raises(TypeError, match='JSON dictionaries'):
            VerifiedCandidateRun(report, scores)
