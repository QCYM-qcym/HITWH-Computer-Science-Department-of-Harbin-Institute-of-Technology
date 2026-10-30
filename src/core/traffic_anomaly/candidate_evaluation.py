"""Fixed-prediction, minute-level evaluation for synthetic candidate artifacts.

Labels are supplied as three audited mappings. This module neither infers
source-label policies nor trains models, calibrates scores or uses UGR labels.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from .candidate_inputs import MAX_MINUTES, PARTITIONS
from .candidate_records import POLICIES
from .evaluation.metrics import confusion


_LABELS = ('normal', 'attack', 'unknown')
_UNDEFINED_REASONS = {
    'precision': 'No positive predictions on scored normal or attack test minutes.',
    'recall': 'No scored attack test minutes.',
    'f1': 'No scored attack test minutes or positive predictions on scored labeled test minutes.',
    'fpr': 'No scored normal test minutes.',
    'fnr': 'No scored attack test minutes.',
}


def _boolean_axis(value, n):
    if not isinstance(value, np.ndarray) or value.dtype != np.dtype(bool) or value.shape != (n,):
        raise ValueError('aligned_boolean_numpy_axis_required')


def evaluate_candidate_predictions(*, labels: Mapping, partitions: np.ndarray,
                                   score_valid: np.ndarray, alarms: np.ndarray,
                                   source_attack_label_present: np.ndarray,
                                   score_origin_policy: str) -> dict:
    """Evaluate one fixed prediction vector under all three audit policies.

    Unscored rows retain a False internal alarm placeholder and are excluded,
    rather than counted as negative predictions. Unknown labels never enter
    normal/attack confusion counts, even when their alarm or attack flag is True.
    """
    if (not isinstance(partitions, np.ndarray) or partitions.ndim != 1
            or not 1 <= len(partitions) <= MAX_MINUTES
            or any(not isinstance(value, (str, np.str_)) or value not in PARTITIONS
                   for value in partitions)):
        raise ValueError('bounded_partition_numpy_axis_required')
    n = len(partitions)
    for value in (score_valid, alarms, source_attack_label_present):
        _boolean_axis(value, n)
    if np.any(alarms & ~score_valid):
        raise ValueError('unscored_alarm_placeholder_must_be_false')
    if not isinstance(score_origin_policy, str) or score_origin_policy not in POLICIES:
        raise ValueError('explicit_score_origin_policy_required')
    if not isinstance(labels, Mapping) or set(labels) != set(POLICIES):
        raise ValueError('all_three_candidate_label_policies_required')
    label_axes = {}
    for policy in POLICIES:
        values = labels[policy]
        if (isinstance(values, (str, bytes))
                or not isinstance(values, (Sequence, np.ndarray))
                or isinstance(values, np.ndarray) and values.ndim != 1
                or len(values) != n
                or any(not isinstance(value, (str, np.str_)) or value not in _LABELS for value in values)):
            raise ValueError('aligned_tristate_candidate_labels_required')
        label_axes[policy] = np.asarray(values)

    test = partitions == 'test'
    valid = test & score_valid
    calendar_count, scored_count = int(test.sum()), int(valid.sum())
    policies = {}
    for policy in POLICIES:
        axis = label_axes[policy]
        normal, attack, unknown = (axis == kind for kind in _LABELS)
        measured = confusion(normal, attack, valid, alarms)
        counts = {key: int(getattr(measured, key)) for key in ('tp', 'fp', 'tn', 'fn')}
        metrics = {key: getattr(measured, key) for key in ('precision', 'recall', 'f1', 'fpr')}
        attack_count = counts['tp'] + counts['fn']
        metrics['fnr'] = counts['fn'] / attack_count if attack_count else None
        policies[policy] = {
            'calendar_test_minutes': calendar_count,
            'scored_test_minutes': scored_count,
            'excluded_unscored_test_minutes': calendar_count - scored_count,
            'normal_minutes': int((normal & valid).sum()),
            'attack_minutes': int((attack & valid).sum()),
            'unknown_minutes': int((unknown & valid).sum()),
            'unknown_source_attack_present': int((unknown & valid & source_attack_label_present).sum()),
            'confusion_counts': counts,
            'metrics': metrics,
            'undefined_reasons': {key: _UNDEFINED_REASONS[key]
                                  for key, value in metrics.items() if value is None},
        }
    return {
        'schema_version': 1,
        'evidence_kind': 'SYNTHETIC_ONLY',
        'policy_status': 'AUDIT_ONLY',
        'unit': 'minute',
        'score_origin_policy': score_origin_policy,
        'policies': policies,
    }
