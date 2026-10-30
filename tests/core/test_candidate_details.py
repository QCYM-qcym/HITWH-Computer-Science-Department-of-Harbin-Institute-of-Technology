"""Candidate-only minute consumers preserve stored values and join identities."""
from dataclasses import replace
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

SOURCE = Path(__file__).parents[1] / 'fixtures/g13u-records-v1.json'
SLOTS = ('if', 'current', 'history15', 'history30')


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    # Only this fixture setup creates new SYNTHETIC_ONLY toy model outputs.
    from traffic_anomaly.candidate_record_cli import _run as records_run
    from traffic_anomaly.candidate_cli import _run as numeric_run
    from traffic_anomaly.candidate_if_cli import run_synthetic_candidate_if
    from traffic_anomaly.candidate_ae_cli import run_synthetic_candidate_ae
    base = tmp_path_factory.mktemp('candidate-details')
    records, inputs = base / 'records', base / 'inputs'
    records_run(SOURCE, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    result = {}
    for slot in SLOTS:
        run = base / slot
        if slot == 'if':
            run_synthetic_candidate_if(records, inputs, SOURCE, 'detail-if', run)
        else:
            window = None if slot == 'current' else int(slot.removeprefix('history'))
            run_synthetic_candidate_ae(records, inputs, SOURCE, 'detail-' + slot, run,
                method='current_ae' if window is None else 'history_ae', history_window=window)
        result[slot] = (run, records, inputs)
    return result


def api():
    name = 'traffic_anomaly.candidate_details'
    assert importlib.util.find_spec(name) is not None, 'candidate minute consumer is missing'
    module = importlib.import_module(name)
    return module.candidate_minute_detail, module.CandidateDetailError


@pytest.fixture(scope='module')
def snapshots(originals):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
    from traffic_anomaly.candidate_run_artifacts import load_verified_candidate_if_run
    from traffic_anomaly.candidate_ae_run_artifacts import load_verified_candidate_ae_run
    result = {}
    for slot, package in originals.items():
        loader = load_verified_candidate_if_run if slot == 'if' else load_verified_candidate_ae_run
        result[slot] = (loader(*package, source_fixture=SOURCE),
            load_verified_candidate_artifacts(*package[1:], source_fixture=SOURCE))
    return result


def changed_run(run, field, value, *, report=False):
    from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun
    r, s = run.report_dict(), run.scores_dict()
    (r if report else s)[field] = value
    return VerifiedCandidateRun(r, s)


def array_input(inputs, **changes):
    from traffic_anomaly.candidate_artifacts import _array_mapping
    arrays = {key: value for key, value in inputs._arrays.items()}
    arrays.update(changes)
    return replace(inputs, _arrays=_array_mapping(arrays))


@pytest.mark.parametrize('slot', SLOTS)
@pytest.mark.parametrize('index', [0, 15, 30])
def test_manual_warmup_partial_history_and_valid_minute(snapshots, slot, index):
    detail, _ = api()
    run, inputs = snapshots[slot]
    value = detail(run, inputs, f'2026-01-01T00:{index:02d}')
    assert value['point']['timestamp'] == f'2026-01-01T00:{index:02d}:00.000000'
    assert value['point']['valid'] is (index == 30)
    assert value['point']['segment_id'] == 'synthetic-source'
    assert value['point']['partition'] == 'train'
    assert value['point']['score'] == run.scores_document['scores'][index]
    assert value['point']['alarm'] == (False if index == 30 else None)
    assert value['point']['threshold'] == run.scores_document['threshold']
    assert value['inputs']['raw']['valid'] is True
    assert value['inputs']['raw']['values'][0] == 4.0
    assert len(value['feature_names']) == len(value['inputs']['raw']['values']) == 13
    assert value['inputs']['prepared']['valid'] is True
    assert value['inputs']['prepared']['values'][0] == 0.0
    assert value['inputs']['prepared']['values'] == inputs.current_values[index].tolist()
    for h in (15, 30):
        row = value['histories'][str(h)]
        assert row['valid'] is (index >= h)
        assert row['invalid_reason'] == (None if index >= h else 'warmup')
        assert row['residual'] == (inputs.histories[h].residual[index].tolist() if index >= h else [None] * 13)
    assert value['labels'] == {'policies': {'P_U': 'normal', 'P_B': 'normal', 'P_A': 'normal'},
                               'source_attack_label_present': False}
    r = value['reconstruction']
    assert r['per_feature'] == {'status': 'NOT_STORED', 'values': None}
    assert r['current']['status'] == ('NOT_APPLICABLE' if slot == 'if' else 'APPLICABLE')
    assert r['history_deviation']['status'] == ('APPLICABLE' if slot.startswith('history') else 'NOT_APPLICABLE')
    if slot != 'if':
        assert r['current']['value'] == run.scores_document['current_reconstruction_mse'][index]
        assert r['history_deviation']['value'] == run.scores_document['history_deviation_reconstruction_mse'][index]
    json.dumps(value, allow_nan=False)


@pytest.mark.parametrize('stamp', ['2026-01-01T00:30', '2026-01-01T00:30:00', '2026-01-01T00:30:00.000000'])
def test_query_forms_canonicalize_without_time_zone(snapshots, stamp):
    detail, _ = api()
    assert detail(*snapshots['if'], stamp)['point']['timestamp'] == '2026-01-01T00:30:00.000000'


@pytest.mark.parametrize('stamp', [None, True, 0, [], '2026-01-01 00:30', '2026-01-01T00:30Z',
    '2026-01-01T00:30:00+08:00', '2026-01-01T00:30:01', '2026-01-01T00:30:00.000001',
    '2026-01-01T00:30:00.0', '2026-02-30T00:30', '2026-01-01T24:00', ''])
def test_bad_queries_have_safe_distinct_error(snapshots, stamp):
    detail, error = api()
    with pytest.raises(error, match='^INVALID_QUERY$') as caught:
        detail(*snapshots['if'], stamp)
    assert caught.value.code == 'INVALID_QUERY'


def test_absent_minute_is_not_invented(snapshots):
    detail, error = api()
    with pytest.raises(error, match='^MINUTE_NOT_FOUND$'):
        detail(*snapshots['if'], '2025-12-31T23:59')


@pytest.mark.parametrize('key', ['record_manifest', 'input_manifest', 'source_fixture', 'minute_fixture', 'preprocess'])
def test_each_complete_provenance_identity_is_required(snapshots, key):
    detail, error = api()
    run, inputs = snapshots['if']
    provenance = run.scores_dict()['provenance']
    provenance[key]['byte_count'] += 1
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOTS$'):
        detail(changed_run(run, 'provenance', provenance), inputs, '2026-01-01T00:30')


@pytest.mark.parametrize('field', ['timestamps', 'segment_ids', 'partitions', 'current_input_valid', 'common_valid', 'score_valid'])
def test_entire_axis_is_checked_before_requested_row(snapshots, field):
    detail, error = api()
    run, inputs = snapshots['if']
    values = run.scores_dict()[field]
    values[-1] = (not values[-1]) if type(values[-1]) is bool else 'unrelated-mismatched-last-row'
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOTS$'):
        detail(changed_run(run, field, values), inputs, '2026-01-01T00:30')


@pytest.mark.parametrize('field,value', [('selected_policy', 'P_B'), ('feature_names', ['wrong'] * 13),
    ('preprocessing_state', {}), ('qualification_windows', [30]), ('evidence_kind', 'REAL_DATA'),
    ('scope', 'FORMAL'), ('model_profile_id', 'unknown'), ('time_basis', 'UTC')])
def test_context_mismatches_cannot_join(snapshots, field, value):
    detail, error = api()
    run, inputs = snapshots['if']
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOTS$'):
        detail(changed_run(run, field, value), inputs, '2026-01-01T00:30')


@pytest.mark.parametrize('run_proof,input_proof', [('VERIFIED', 'VERIFIED'), ('VERIFIED', 'NOT_PROVIDED'),
    ('NOT_PROVIDED', 'VERIFIED'), ('NOT_PROVIDED', 'NOT_PROVIDED')])
def test_source_proof_is_never_upgraded(snapshots, run_proof, input_proof):
    from traffic_anomaly.candidate_artifacts import _deep_freeze
    detail, _ = api()
    run, inputs = snapshots['if']
    checks = run.report_dict()['checks']; checks['source_replay'] = run_proof
    r = inputs.report_dict(); r['checks']['source_replay'] = input_proof
    out = detail(changed_run(run, 'checks', checks, report=True), replace(inputs, report=_deep_freeze(r)), '2026-01-01T00:30')
    assert out['source_replay'] == {'run': run_proof, 'inputs': input_proof,
        'combined': 'VERIFIED' if run_proof == input_proof == 'VERIFIED' else 'NOT_PROVIDED'}


def test_output_is_independent_and_query_does_not_recompute_or_open_files(snapshots, monkeypatch):
    from traffic_anomaly import candidate_inputs as ci, candidate_iforest as fi, candidate_autoencoder as ae
    from traffic_anomaly import candidate_evaluation as ev
    detail, _ = api()
    def forbidden(*args, **kwargs):
        raise AssertionError('pure query attempted I/O or recomputation')
    monkeypatch.setattr(Path, 'open', forbidden)
    for module, name in [(ci, 'build_candidate_history'), (ci, 'prepare_candidate_inputs'),
        (fi, 'compute_synthetic_candidate_if'), (fi, 'calibrate_candidate_scores'),
        (ae, 'compute_synthetic_candidate_ae'), (ae, '_calibrate'), (ev, 'evaluate_candidate_predictions')]:
        monkeypatch.setattr(module, name, forbidden)
    run, inputs = snapshots['history15']
    before = run.report_dict()
    out = detail(run, inputs, '2026-01-01T00:30')
    out['inputs']['raw']['values'][0] = -123
    out['histories']['15']['residual'][0] = 999
    out['labels']['policies']['P_U'] = 'attack'
    assert detail(run, inputs, '2026-01-01T00:30')['inputs']['raw']['values'][0] == 4
    assert run.report_dict() == before


@pytest.mark.parametrize('field', ['raw_values', 'current_values'])
def test_nonfinite_valid_features_are_rejected(snapshots, field):
    detail, error = api()
    run, inputs = snapshots['if']
    values = getattr(inputs, field).copy(); values[30, 0] = np.nan
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOTS$'):
        detail(run, array_input(inputs, **{field: values}), '2026-01-01T00:30')


def test_invalid_raw_mask_does_not_hide_prepared_features(snapshots):
    detail, _ = api()
    run, inputs = snapshots['if']
    raw = inputs.raw_values.copy(); raw[30] = np.nan
    valid = inputs.raw_valid.copy(); valid[30] = False
    value = detail(run, array_input(inputs, raw_values=raw, raw_valid=valid), '2026-01-01T00:30')
    assert value['inputs']['raw'] == {'valid': False, 'values': [None] * 13}
    assert value['inputs']['prepared']['valid'] is True
    json.dumps(value, allow_nan=False)


def test_nonfinite_valid_history_is_rejected(snapshots):
    from traffic_anomaly.candidate_artifacts import _array_mapping
    detail, error = api()
    run, inputs = snapshots['if']
    histories = dict(inputs.histories)
    history = histories[15]
    arrays = dict(history._arrays.items())
    residual = history.residual.copy(); residual[30, 0] = np.inf
    arrays['residual'] = residual
    histories[15] = replace(history, _arrays=_array_mapping(arrays))
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOTS$'):
        detail(run, replace(inputs, histories=histories), '2026-01-01T00:30')


def test_snapshot_types_are_required(snapshots):
    detail, error = api()
    run, inputs = snapshots['if']
    for pair in (({}, inputs), (run, {})):
        with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOTS$'):
            detail(*pair, '2026-01-01T00:30')
