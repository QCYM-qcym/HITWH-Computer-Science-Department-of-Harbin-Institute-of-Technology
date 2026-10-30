"""Hand-counted fixed-prediction evaluation of synthetic candidate minutes."""
from copy import deepcopy
import json

import numpy as np
import pytest


POLICIES = ('P_U', 'P_B', 'P_A')


def evaluate(**kwargs):
    from traffic_anomaly.candidate_evaluation import evaluate_candidate_predictions
    return evaluate_candidate_predictions(**kwargs)


def case():
    # Scored test positions 4..9. Positions 5 and 8 represent legal Attempted
    # mappings supplied by the caller, not reconstructed by the evaluator.
    return dict(
        labels={
            'P_U': ['attack'] * 4 + ['normal', 'unknown', 'attack', 'normal', 'unknown', 'attack', 'attack'],
            'P_B': ['attack'] * 4 + ['normal', 'normal', 'attack', 'normal', 'attack', 'attack', 'attack'],
            'P_A': ['attack'] * 4 + ['normal', 'attack', 'attack', 'normal', 'attack', 'attack', 'attack'],
        },
        partitions=np.array(['train', 'validation', 'calibration', 'test'] + ['test'] * 7),
        score_valid=np.array([True, True, True, False, True, True, True, True, True, True, False]),
        alarms=np.array([True, True, True, False, True, False, True, False, True, False, False]),
        source_attack_label_present=np.array([True, True, True, True, False, False, True, False, True, True, True]),
        score_origin_policy='P_U',
    )


def test_fixed_predictions_have_hand_counted_policy_denominators_and_metrics():
    result = evaluate(**case())
    assert {k: v for k, v in result.items() if k != 'policies'} == dict(
        schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        unit='minute', score_origin_policy='P_U')
    expected = {
        'P_U': (2, 2, 2, 1, dict(tp=1, fp=1, tn=1, fn=1),
                dict(precision=.5, recall=.5, f1=.5, fpr=.5, fnr=.5)),
        'P_B': (3, 3, 0, 0, dict(tp=2, fp=1, tn=2, fn=1),
                dict(precision=2/3, recall=2/3, f1=2/3, fpr=1/3, fnr=1/3)),
        'P_A': (2, 4, 0, 0, dict(tp=2, fp=1, tn=1, fn=2),
                dict(precision=2/3, recall=.5, f1=4/7, fpr=.5, fnr=.5)),
    }
    for policy, (normal, attack, unknown, excluded_attack, counts, metrics) in expected.items():
        value = result['policies'][policy]
        assert value == dict(
            calendar_test_minutes=8, scored_test_minutes=6, excluded_unscored_test_minutes=2,
            normal_minutes=normal, attack_minutes=attack, unknown_minutes=unknown,
            unknown_source_attack_present=excluded_attack, confusion_counts=counts,
            metrics=metrics, undefined_reasons={})
        assert normal + attack + unknown == value['scored_test_minutes']
        assert counts['tp'] + counts['fn'] == attack
        assert counts['fp'] + counts['tn'] == normal
    json.dumps(result, allow_nan=False)


def test_unknown_alarms_are_neither_false_positive_nor_true_positive():
    args = dict(labels={p: ['unknown', 'unknown'] for p in POLICIES},
                partitions=np.array(['test', 'test']), score_valid=np.ones(2, dtype=bool),
                alarms=np.array([True, False]), source_attack_label_present=np.array([True, False]),
                score_origin_policy='P_A')
    result = evaluate(**args)
    for value in result['policies'].values():
        assert value['unknown_minutes'] == 2 and value['unknown_source_attack_present'] == 1
        assert value['normal_minutes'] == value['attack_minutes'] == 0
        assert value['confusion_counts'] == dict(tp=0, fp=0, tn=0, fn=0)
        assert value['metrics'] == {m: None for m in ('precision', 'recall', 'f1', 'fpr', 'fnr')}
        assert set(value['undefined_reasons']) == set(value['metrics'])
        assert all(isinstance(reason, str) and len(reason) > 15 for reason in value['undefined_reasons'].values())


@pytest.mark.parametrize('kind,alarm,undefined,expected', [
    ('normal', False, {'precision', 'recall', 'f1', 'fnr'}, {'fpr': 0.}),
    ('normal', True, {'recall', 'fnr'}, {'precision': 0., 'f1': 0., 'fpr': 1.}),
    ('attack', False, {'precision', 'fpr'}, {'recall': 0., 'f1': 0., 'fnr': 1.}),
    ('attack', True, {'fpr'}, {'precision': 1., 'recall': 1., 'f1': 1., 'fnr': 0.}),
])
def test_zero_denominators_are_null_with_specific_reasons(kind, alarm, undefined, expected):
    args = dict(labels={p: [kind] for p in POLICIES}, partitions=np.array(['test']),
                score_valid=np.array([True]), alarms=np.array([alarm]),
                source_attack_label_present=np.array([kind == 'attack']), score_origin_policy='P_B')
    for value in evaluate(**args)['policies'].values():
        assert set(value['undefined_reasons']) == undefined
        assert {k for k, v in value['metrics'].items() if v is None} == undefined
        for metric, number in expected.items():
            assert value['metrics'][metric] == number
        for metric in undefined:
            reason = value['undefined_reasons'][metric].lower()
            assert 'no ' in reason and ('scored' in reason or 'prediction' in reason)


@pytest.mark.parametrize('partitions,valid,expected_calendar,excluded', [
    (['train', 'validation', 'calibration'], [True, True, True], 0, 0),
    (['test', 'test', 'test'], [False, False, False], 3, 3),
])
def test_no_scored_test_minutes_does_not_invent_zero_error_rates(partitions, valid, expected_calendar, excluded):
    args = dict(labels={p: ['attack', 'normal', 'unknown'] for p in POLICIES},
                partitions=np.array(partitions), score_valid=np.array(valid),
                alarms=np.array([False, False, False]),
                source_attack_label_present=np.array([True, False, True]), score_origin_policy='P_U')
    for value in evaluate(**args)['policies'].values():
        assert value['calendar_test_minutes'] == expected_calendar
        assert value['scored_test_minutes'] == 0
        assert value['excluded_unscored_test_minutes'] == excluded
        assert all(v is None for v in value['metrics'].values())


def test_does_not_mutate_axes_labels_or_alarms_and_does_not_use_ugr_evaluate(monkeypatch):
    from traffic_anomaly.evaluation import metrics
    def forbidden(*args, **kwargs):
        raise AssertionError('candidate must not call UGR evaluation')
    monkeypatch.setattr(metrics, 'evaluate', forbidden)
    args = case()
    before = deepcopy(args)
    evaluate(**args)
    assert args['labels'] == before['labels']
    for key in ('partitions', 'score_valid', 'alarms', 'source_attack_label_present'):
        assert np.array_equal(args[key], before[key])


@pytest.mark.parametrize('mask', ['score_valid', 'alarms', 'source_attack_label_present'])
@pytest.mark.parametrize('bad', ['list', 'integer', 'object', '2d', 'short'])
def test_masks_are_strict_aligned_boolean_numpy_arrays(mask, bad):
    args = case()
    value = args[mask]
    args[mask] = {'list': value.tolist(), 'integer': value.astype(int),
                  'object': value.astype(object), '2d': value[:, None], 'short': value[:-1]}[bad]
    with pytest.raises(ValueError):
        evaluate(**args)


@pytest.mark.parametrize('bad', [[], ['test'], np.array([], dtype=str), np.array([['test']]),
                                  np.array(['train'] * 10), np.array(['invalid'] * 11),
                                  np.array([1] * 11), np.array([True] * 11)])
def test_partitions_require_nonempty_bounded_aligned_numpy_enumerations(bad):
    args = case()
    args['partitions'] = bad
    with pytest.raises(ValueError):
        evaluate(**args)


@pytest.mark.parametrize('bad', [None, [], {}, {'P_U': ['normal'] * 11},
    {**{p: ['normal'] * 11 for p in POLICIES}, 'P_X': ['normal'] * 11},
    {p: 'normal' for p in POLICIES}, {p: ['normal'] * 10 for p in POLICIES},
    {p: ['invalid'] * 11 for p in POLICIES}, {p: [None] * 11 for p in POLICIES},
    {p: np.array([['normal']] * 11) for p in POLICIES}])
def test_all_three_label_axes_are_required_and_strict_tristate(bad):
    args = case()
    args['labels'] = bad
    with pytest.raises(ValueError):
        evaluate(**args)


@pytest.mark.parametrize('policy', ['P_X', '', None, 1])
def test_score_origin_policy_is_explicit_audit_policy(policy):
    args = case()
    args['score_origin_policy'] = policy
    with pytest.raises(ValueError):
        evaluate(**args)


def test_invalid_score_alarm_placeholder_is_false():
    args = case()
    args['alarms'][3] = True
    with pytest.raises(ValueError):
        evaluate(**args)


def test_maximum_axis_is_bounded():
    n = 10001
    args = dict(labels={p: ['normal'] * n for p in POLICIES}, partitions=np.array(['test'] * n),
                score_valid=np.ones(n, dtype=bool), alarms=np.zeros(n, dtype=bool),
                source_attack_label_present=np.zeros(n, dtype=bool), score_origin_policy='P_U')
    with pytest.raises(ValueError):
        evaluate(**args)


def test_accepts_tuple_and_numpy_label_sequences_at_boundary():
    args = case()
    args['labels']['P_U'] = tuple(args['labels']['P_U'])
    args['labels']['P_A'] = np.array(args['labels']['P_A'])
    result = evaluate(**args)
    assert result['policies']['P_U']['unknown_minutes'] == 2
    assert result['policies']['P_A']['attack_minutes'] == 4
