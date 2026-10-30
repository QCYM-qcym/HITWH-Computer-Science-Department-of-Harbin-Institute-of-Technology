"""Shared examples follow the established raw-label episode definition.

Minute metrics use scored rows; a wholly unhit attack episode follows its raw
aligned label extent. These tests do not add backend interval validation.
"""
import json
from pathlib import Path

import numpy as np

from traffic_anomaly import contracts as c
from traffic_anomaly.evaluation.metrics import evaluate


FIXTURE = Path(__file__).parents[1] / 'fixtures' / 'contracts-v1.json'
AGGREGATES = ('available', 'metrics', 'normal_coverage', 'attack_coverage',
              'excluded_attack_minutes', 'background_only_minutes')


def times(minutes):
    origin = np.datetime64('2026-01-01T00:00', 'ns')
    return origin + np.array(minutes, dtype='timedelta64[m]')


def attacks_at(minutes):
    axis = times(minutes)
    labels = {name: np.zeros(len(axis), dtype=np.int64) for name in c.LABEL_NAMES}
    labels['dos'][:] = 1
    return c.LabelBatch(axis, labels)


def intervals(result):
    return [item.model_dump() for item in result.intervals]


def missed(start, end, count):
    return dict(start=f'2026-01-01T00:{start:02}:00Z', end=f'2026-01-01T00:{end:02}:00Z',
                kind='missed_attack', minute_count=count)


def test_shared_fixture_evaluation_aggregates_and_exact_interval_examples_match_pure_evaluator():
    fixture = json.loads(FIXTURE.read_text('utf-8'))
    series = next(row['body'] for row in fixture['responses'] if row['schema'] == 'SeriesPage')
    expected = c.Evaluation.model_validate(next(row['body'] for row in fixture['responses'] if row['schema'] == 'Evaluation'))
    labels = c.LabelBatch(
        np.array([stamp.removesuffix('Z') for stamp in fixture['core_sample']['timestamps']], dtype='datetime64[ns]'),
        {name: np.array(fixture['core_sample']['labels'][name], dtype=np.int64) for name in c.LABEL_NAMES})
    actual = evaluate(expected.run_id, expected.evidence_kind,
        np.array([row['timestamp'].removesuffix('Z') for row in series['items']], dtype='datetime64[ns]'),
        np.array([row['valid'] for row in series['items']], dtype=bool),
        np.array([False if row['alarm'] is None else row['alarm'] for row in series['items']], dtype=bool), labels)
    for field in AGGREGATES:
        assert getattr(actual, field) == getattr(expected, field), field
    assert intervals(actual) == intervals(expected)
    assert actual.metrics.fn == 1 and actual.excluded_attack_minutes == 1
    assert next(item for item in actual.intervals if item.kind == 'missed_attack').minute_count == 2


def test_missing_timestamp_does_not_invent_an_attack_minute_or_join_episodes():
    result = evaluate('gap', 'SYNTHETIC_ONLY', times([0, 2]), np.ones(2, bool),
                      np.zeros(2, bool), attacks_at([0, 2]))
    assert result.metrics.fn == 2 and result.attack_coverage.total == 2
    assert intervals(result) == [missed(0, 1, 1), missed(2, 3, 1)]


def test_unknown_label_between_known_attacks_splits_episode_without_becoming_normal():
    result = evaluate('unknown', 'SYNTHETIC_ONLY', times([0, 1, 2]), np.ones(3, bool),
                      np.zeros(3, bool), attacks_at([0, 2]))
    assert result.metrics.fn == 2 and result.attack_coverage.total == 2
    assert result.normal_coverage.total == 0 and result.background_only_minutes == 0
    assert intervals(result) == [missed(0, 1, 1), missed(2, 3, 1)]


def test_partial_hit_removes_completely_missed_episode_without_point_adjusting_fn():
    result = evaluate('partial', 'SYNTHETIC_ONLY', times([0, 1, 2]), np.ones(3, bool),
                      np.array([True, False, False]), attacks_at([0, 1, 2]))
    assert result.metrics.tp == 1 and result.metrics.fn == 2
    assert result.attack_coverage.eligible == 3 and result.excluded_attack_minutes == 0
    assert intervals(result) == []


def test_wholly_unscored_attack_episode_has_extent_but_no_evaluated_false_negatives():
    result = evaluate('unscored', 'SYNTHETIC_ONLY', times([0, 1]), np.zeros(2, bool),
                      np.zeros(2, bool), attacks_at([0, 1]))
    assert result.metrics.fn == 0 and result.metrics.tp == 0
    assert result.attack_coverage.eligible == 0 and result.attack_coverage.total == 2
    assert result.excluded_attack_minutes == 2 and result.metrics.recall is None
    assert intervals(result) == [missed(0, 2, 2)]
