"""Pure label sensitivity of fixed saved predictions after explicit binding.

Only scored test minutes enter confusion. Unknown and unscored populations
remain visible. Internal consistency does not authenticate labels or execution.
"""
from __future__ import annotations

import json
import math

import numpy as np

from .release_if_result_contract import (
    ReleaseIFResultPackage, ReleaseIFResultPackageError, verify_release_if_result_pair,
)
from .release_model_inputs import ReleaseModelInputPair
from .evaluation.metrics import confusion

EVALUATION_PROFILE_ID = 'c17-release-iforest-fixed-prediction-label-audit-v1'
EVALUATION_BYTE_LIMIT = 16384
_POLICIES = ('P_U', 'P_B', 'P_A')
_KINDS = ('normal', 'attack', 'unknown')
_CODES = frozenset(('INVALID_EVALUATION_ARGUMENTS', 'RESOURCE_LIMIT',
    'INPUT_BINDING_MISMATCH', 'INVALID_EVALUATION_INPUT', 'EVALUATION_ERROR'))
_VERIFY_CODES = {
    'RESOURCE_LIMIT': 'RESOURCE_LIMIT', 'INPUT_BINDING_MISMATCH': 'INPUT_BINDING_MISMATCH',
    'INVALID_PACKAGE': 'INVALID_EVALUATION_INPUT', 'INCOMPATIBLE_PACKAGE': 'INVALID_EVALUATION_INPUT',
    'INTEGRITY_MISMATCH': 'INVALID_EVALUATION_INPUT', 'INCONSISTENT_PACKAGE': 'INVALID_EVALUATION_INPUT',
}
_REASONS = dict(precision='NO_POSITIVE_LABELED_TEST_PREDICTIONS', recall='NO_SCORED_TEST_ATTACK',
    fnr='NO_SCORED_TEST_ATTACK', fpr='NO_SCORED_TEST_NORMAL',
    f1='NO_ATTACK_OR_POSITIVE_LABELED_TEST_PREDICTIONS')


class ReleaseIFEvaluationError(ValueError):
    """Finite safe codes, without paths, labels or original error messages."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in _CODES else 'EVALUATION_ERROR'
        super().__init__(self.code)


def _require(condition):
    if not condition:
        raise ValueError('invalid_evaluation_projection') from None


def _verify(package, pair):
    try:
        verify_release_if_result_pair(package, pair)
    except Exception as error:
        code = 'EVALUATION_ERROR'
        # Unknown exact types must not execute an arbitrary code getter.
        if type(error) is ReleaseIFResultPackageError:
            try:
                actual = getattr(error, 'code', None)
                if type(actual) is str:
                    code = _VERIFY_CODES.get(actual, 'EVALUATION_ERROR')
            except Exception:
                pass
        raise ReleaseIFEvaluationError(code) from None


def _count(mask):
    return int(mask.sum())


def _policy_report(normal, attack, valid, alarms, calendar, scored, unscored):
    n = len(calendar)
    for mask in (normal, attack, valid, alarms, calendar, scored, unscored):
        _require(type(mask) is np.ndarray and mask.dtype == np.bool_ and mask.shape == (n,))
    masks = (normal, attack, ~normal & ~attack)
    calendar_by_kind = dict(zip(_KINDS, (_count(mask & calendar) for mask in masks)))
    scored_by_kind = dict(zip(_KINDS, (_count(mask & valid) for mask in masks)))
    unscored_by_kind = dict(zip(_KINDS, (_count(mask & unscored) for mask in masks)))
    populations = (_count(calendar), _count(valid), _count(unscored))
    for mapping, total in zip((calendar_by_kind, scored_by_kind, unscored_by_kind), populations):
        _require(all(type(value) is int and 0 <= value <= n for value in mapping.values())
                 and sum(mapping.values()) == total)
    _require(populations[0] == populations[1] + populations[2])
    _require(all(calendar_by_kind[kind] == scored_by_kind[kind] + unscored_by_kind[kind] for kind in _KINDS))
    values = confusion(normal, attack, valid, alarms)
    counts = {name: getattr(values, name) for name in ('tp', 'fp', 'tn', 'fn')}
    _require(all(type(value) is int and 0 <= value <= n for value in counts.values()))
    tp, fp, tn, fn = (counts[name] for name in ('tp', 'fp', 'tn', 'fn'))
    _require(fp + tn == scored_by_kind['normal'] and tp + fn == scored_by_kind['attack'])
    metrics = {name: getattr(values, name) for name in ('precision', 'recall', 'f1', 'fpr')}
    metrics['fnr'] = fn / (fn + tp) if fn + tp else None
    denominators = dict(precision=tp + fp, recall=tp + fn, f1=2 * tp + fp + fn,
                        fpr=fp + tn, fnr=fn + tp)
    for name, value in metrics.items():
        if denominators[name] == 0:
            _require(value is None)
        else:
            _require(type(value) is float and math.isfinite(value) and 0. <= value <= 1.)
    return dict(calendar_test_minutes=populations[0], scored_test_minutes=populations[1],
        excluded_unscored_test_minutes=populations[2], calendar_by_kind=calendar_by_kind,
        scored_by_kind=scored_by_kind, unscored_by_kind=unscored_by_kind,
        confusion_counts=counts, metrics=metrics,
        undefined_reasons={name: _REASONS[name] for name, value in metrics.items() if value is None})


def _identity(value):
    # The one verifier has already checked these fixed four-field declarations.
    return {name: getattr(value, name) for name in
        ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')}


def evaluate_release_if_result(package: ReleaseIFResultPackage, pair: ReleaseModelInputPair) -> bytes:
    """Bind once, then audit fixed predictions under all three saved label columns."""
    if type(package) is not ReleaseIFResultPackage or type(pair) is not ReleaseModelInputPair:
        raise ReleaseIFEvaluationError('INVALID_EVALUATION_ARGUMENTS') from None
    _verify(package, pair)
    try:
        result, context = package.result, package.context
        calendar = np.asarray([role == 'test' for role in pair.roles], dtype=np.bool_)
        scored = np.asarray(result.scored_mask, dtype=np.bool_)
        valid = calendar & scored
        unscored = calendar & ~scored
        alarms = np.asarray([prediction is True for prediction in result.predictions], dtype=np.bool_)
        labels = pair.labels.saved.label_kinds
        policies = {}
        # Logical tuple columns stay P_U/P_B/P_A; JSON key sorting is separate.
        for column, policy in enumerate(_POLICIES):
            normal = np.asarray([row[column] == 'normal' for row in labels], dtype=np.bool_)
            attack = np.asarray([row[column] == 'attack' for row in labels], dtype=np.bool_)
            policies[policy] = _policy_report(normal, attack, valid, alarms, calendar, scored, unscored)
        report = dict(version=1, profile_id=EVALUATION_PROFILE_ID, status='SAVED_PREDICTION_LABEL_AUDIT',
            scope='SAVED_RESULT_LABEL_SENSITIVITY_INTERNAL_CONSISTENCY_ONLY', unit='minute',
            result_identity=_identity(package.identity), input_references=dict(raw=_identity(pair.raw_identity),
                prepared=_identity(pair.prepared_identity)), configuration_sha256=pair.configuration_sha256,
            view=result.view, audit_fit_policy=context.audit_fit_policy, policy_status='AUDIT_ONLY',
            source_authentication='NOT_AUTHENTICATED', time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',
            model_execution='NOT_AUTHENTICATED', prediction_basis='FIXED_SAVED_PREDICTIONS_NO_REFIT',
            policies=policies)
        payload = (json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True,
                              separators=(',', ':')) + '\n').encode('utf-8')
    except Exception:
        raise ReleaseIFEvaluationError('EVALUATION_ERROR') from None
    if len(payload) > EVALUATION_BYTE_LIMIT:
        raise ReleaseIFEvaluationError('RESOURCE_LIMIT') from None
    return payload
