"""Pure paging tests use hand-written value snapshots, never train models.

These tiny snapshots exercise consumer preconditions, not artifact certification.
"""
import importlib
import json
import math
from pathlib import Path

import pytest

from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun


def api():
    name = 'traffic_anomaly.candidate_series'
    assert importlib.util.find_spec(name) is not None, 'candidate range consumer is missing'
    module = importlib.import_module(name)
    return module.candidate_series_page, module.CandidateSeriesError


@pytest.fixture
def run():
    from traffic_anomaly.candidate_run_artifacts import VERIFIER_PROFILE_ID
    from traffic_anomaly.candidate_iforest import MODEL_PROFILE_ID
    shared = dict(schema_version=1, run_id='handwritten-series', model_profile_id=MODEL_PROFILE_ID,
                  evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY', selected_policy='P_U')
    report = dict(shared, verifier_profile_id=VERIFIER_PROFILE_ID, status='VERIFIED',
        scope='STORED_ARTIFACT_CONSISTENCY_ONLY', minute_count=7, score_valid_count=2, threshold=.5,
        checks={'source_replay': 'NOT_PROVIDED', 'model_score_replay': 'NOT_CHECKED'},
        artifacts={'evaluation.json': {'sha256': 'a' * 64, 'byte_count': 300}},
        policies={'P_U': {'metrics': {'precision': None}, 'undefined_reasons': {'precision': 'stored reason'}}})
    scores = dict(shared, time_basis='synthetic_source_clock', scope='ENGINEERING_TOY_ONLY',
        score_direction='HIGHER_IS_MORE_ANOMALOUS',
        timestamps=[f'2026-01-01T00:{i:02d}:00.000000' for i in (0, 1, 2, 4, 5, 6, 7)],
        segment_ids=['a', 'a', 'a', 'a', 'b', 'b', 'b'],
        partitions=['train'] * 5 + ['test'] * 2, current_input_valid=[True] * 7,
        common_valid=[False, False, True, False, False, False, True],
        score_valid=[False, False, True, False, False, False, True],
        scores=[None, None, -0.0, None, None, None, .9],
        alarms=[None, None, False, None, None, None, True], threshold=.5,
        history_invalid_reason={'15': ['warmup', None, None, 'gap', 'boundary', 'boundary', None],
                                '30': ['warmup', 'warmup', None, 'gap', 'boundary', 'boundary', None]})
    return VerifiedCandidateRun(report, scores)


def changed(run, field, value, *, report=False):
    r, s = run.report_dict(), run.scores_dict()
    (r if report else s)[field] = value
    return VerifiedCandidateRun(r, s)


def test_full_series_preserves_all_rows_and_stored_context(run):
    query, _ = api()
    result = query(run)
    assert result['total'] == result['returned'] == 7
    assert result['page'] == 1 and result['page_size'] == 100
    assert result['range'] == {'start': None, 'end': None}
    assert result['source_replay'] == 'NOT_PROVIDED'
    assert result['time_basis'] == 'synthetic_source_clock'
    assert [p['source_index'] for p in result['items']] == list(range(7))
    assert [p['score'] for p in result['items']] == [None, None, -0.0, None, None, None, .9]
    assert math.copysign(1, result['items'][2]['score']) == -1
    assert result['items'][0]['current_input_valid'] is True and result['items'][0]['valid'] is False
    assert result['items'][1]['history_invalid_reason'] == {'15': None, '30': 'warmup'}
    assert [p['break_before'] for p in result['items']] == [True, False, False, True, True, True, False]
    assert result['evaluation_reference'] == dict(scope='FULL_STORED_RUN', run_id='handwritten-series',
        artifact={'sha256': 'a' * 64, 'byte_count': 300})
    assert all(p['threshold'] == .5 for p in result['items'])
    assert 'policies' not in result and 'metrics' not in result
    json.dumps(result, allow_nan=False)


def test_half_open_range_is_filtered_before_paging(run):
    query, _ = api()
    first = query(run, start='2026-01-01T00:01', end='2026-01-01T00:06', page_size=2)
    second = query(run, start='2026-01-01T00:01:00', end='2026-01-01T00:06:00.000000', page=2, page_size=2)
    assert first['total'] == second['total'] == 4
    assert first['returned'] == second['returned'] == 2
    assert [p['source_index'] for p in first['items']] == [1, 2]
    assert [p['source_index'] for p in second['items']] == [3, 4]
    assert first['range'] == second['range'] == {
        'start': '2026-01-01T00:01:00.000000', 'end': '2026-01-01T00:06:00.000000'}
    assert first['items'][0]['break_before'] is False
    assert second['items'][0]['break_before'] is True


def test_partial_last_page_out_of_range_and_huge_page(run):
    query, _ = api()
    last = query(run, page=3, page_size=3)
    assert last['total'] == 7 and last['returned'] == 1
    assert last['items'][0]['source_index'] == 6 and last['items'][0]['break_before'] is False
    for page in (4, 10 ** 1000):
        result = query(run, page=page, page_size=3)
        assert result['total'] == 7 and result['returned'] == 0 and result['items'] == []
        assert result['evaluation_reference'] == last['evaluation_reference']


def test_gap_range_and_open_sides(run):
    query, _ = api()
    empty = query(run, start='2026-01-01T00:03', end='2026-01-01T00:04')
    assert empty['total'] == empty['returned'] == 0 and empty['items'] == []
    assert len(query(run, end='2026-01-01T00:02')['items']) == 2
    assert [p['source_index'] for p in query(run, start='2026-01-01T00:06')['items']] == [5, 6]
    assert query(run, page_size=1000)['returned'] == 7


@pytest.mark.parametrize('field', ['page', 'page_size'])
@pytest.mark.parametrize('value', [True, False, 0, -1, 1.0, '1', None])
def test_page_parameters_require_strict_positive_integers(run, field, value):
    query, error = api()
    with pytest.raises(error, match='^INVALID_QUERY$'):
        query(run, **{field: value})


def test_page_size_upper_bound(run):
    query, error = api()
    with pytest.raises(error, match='^INVALID_QUERY$'):
        query(run, page_size=1001)


@pytest.mark.parametrize('stamp', [True, 0, [], '', '2026-01-01', '2026-01-01 00:01',
    '2026-01-01T00:01Z', '2026-01-01T00:01:00+00:00', '2026-01-01T00:01:01',
    '2026-01-01T00:01:00.000001', '2026-01-01T00:01:00.0', '2026-02-30T00:01', '2026-01-01T24:00'])
def test_invalid_range_time_is_safe(run, stamp):
    query, error = api()
    for field in ('start', 'end'):
        with pytest.raises(error, match='^INVALID_QUERY$') as caught:
            query(run, **{field: stamp})
        assert caught.value.code == 'INVALID_QUERY'


@pytest.mark.parametrize('start,end', [('2026-01-01T00:01', '2026-01-01T00:01:00'),
    ('2026-01-01T00:02', '2026-01-01T00:01')])
def test_empty_or_reversed_range_is_rejected(run, start, end):
    query, error = api()
    with pytest.raises(error, match='^INVALID_QUERY$'):
        query(run, start=start, end=end)


@pytest.mark.parametrize('field,value', [('scope', 'REAL'), ('time_basis', 'UTC'),
    ('evidence_kind', 'REAL_DATA'), ('policy_status', 'APPROVED'), ('selected_policy', 'P_B'),
    ('run_id', 'different'), ('model_profile_id', 'unknown'), ('schema_version', True),
    ('score_direction', 'LOWER_IS_MORE_ANOMALOUS')])
def test_snapshot_scope_identity_mismatches_are_rejected(run, field, value):
    query, error = api()
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOT$'):
        query(changed(run, field, value))


@pytest.mark.parametrize('field', ['timestamps', 'segment_ids', 'partitions', 'current_input_valid',
    'common_valid', 'score_valid', 'scores', 'alarms'])
def test_full_axis_lengths_checked_even_outside_page(run, field):
    query, error = api()
    values = run.scores_dict()[field]; values.pop()
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOT$'):
        query(changed(run, field, values), end='2026-01-01T00:01', page_size=1)


@pytest.mark.parametrize('mutation', ['duplicate_time', 'backward_time', 'time_zone', 'noncanonical_time',
    'nonfinite_score', 'invalid_score', 'invalid_alarm', 'boolean_mask', 'common_mismatch', 'reason_length',
    'reason_unknown', 'missing_reason', 'input_invalid_scored'])
def test_malformed_stored_axis_rejected_before_selection(run, mutation):
    query, error = api()
    s = run.scores_dict()
    if mutation == 'duplicate_time': s['timestamps'][-1] = s['timestamps'][-2]
    elif mutation == 'backward_time': s['timestamps'][-1] = s['timestamps'][0]
    elif mutation == 'time_zone': s['timestamps'][-1] += 'Z'
    elif mutation == 'noncanonical_time': s['timestamps'][-1] = '2026-01-01T00:07'
    elif mutation == 'nonfinite_score': s['scores'][-1] = float('inf')
    elif mutation == 'invalid_score': s['scores'][0] = 0.0
    elif mutation == 'invalid_alarm': s['alarms'][0] = False
    elif mutation == 'boolean_mask': s['score_valid'][-1] = 1
    elif mutation == 'common_mismatch': s['common_valid'][-1] = False
    elif mutation == 'reason_length': s['history_invalid_reason']['15'].pop()
    elif mutation == 'reason_unknown': s['history_invalid_reason']['30'][0] = 'invented'
    elif mutation == 'missing_reason': s['history_invalid_reason']['30'][1] = None
    elif mutation == 'input_invalid_scored': s['current_input_valid'][-1] = False
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOT$'):
        query(VerifiedCandidateRun(run.report_dict(), s), end='2026-01-01T00:01')


@pytest.mark.parametrize('field,value', [('status', 'UNVERIFIED'), ('verifier_profile_id', 'other'),
    ('minute_count', 8), ('score_valid_count', 3), ('threshold', .6),
    ('checks', {'source_replay': 'ASSUMED'}),
    ('artifacts', {'evaluation.json': {'sha256': 'not-a-digest', 'byte_count': 1}})])
def test_report_identity_is_consistent(run, field, value):
    query, error = api()
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOT$'):
        query(changed(run, field, value, report=True))


def test_independent_outputs_full_evaluation_and_no_query_io_or_recompute(run, monkeypatch):
    from traffic_anomaly import candidate_inputs as ci, candidate_iforest as fi, candidate_autoencoder as ae
    from traffic_anomaly import candidate_evaluation as ev
    query, _ = api()
    def forbidden(*args, **kwargs):
        raise AssertionError('pure query attempted I/O or recalculation')
    monkeypatch.setattr(Path, 'open', forbidden)
    for module, name in [(ci, 'build_candidate_history'), (ci, 'prepare_candidate_inputs'),
        (fi, 'compute_synthetic_candidate_if'), (fi, 'calibrate_candidate_scores'),
        (ae, 'compute_synthetic_candidate_ae'), (ae, '_calibrate'), (ev, 'evaluate_candidate_predictions')]:
        monkeypatch.setattr(module, name, forbidden)
    r, s = run.report_dict(), run.scores_dict()
    pages = [query(run, page=p, page_size=2) for p in range(1, 5)]
    assert [v['timestamp'] for page in pages for v in page['items']] == s['timestamps']
    pages[0]['items'][0]['history_invalid_reason']['15'] = 'changed'
    pages[0]['items'][0]['score'] = 100
    pages[0]['range']['start'] = 'changed'
    pages[0]['evaluation_reference']['artifact']['sha256'] = 'changed'
    again = query(run, page_size=2)
    assert again['items'][0]['score'] is None
    assert again['items'][0]['history_invalid_reason']['15'] == 'warmup'
    assert again['range']['start'] is None
    assert again['evaluation_reference']['artifact']['sha256'] == 'a' * 64
    assert run.report_dict() == r and run.scores_dict() == s


@pytest.mark.parametrize('value', [None, {}, 0, 'fake'])
def test_verified_snapshot_type_required(value):
    query, error = api()
    with pytest.raises(error, match='^INCOMPATIBLE_SNAPSHOT$'):
        query(value)
