"""Bounded in-memory Isolation Forest consumer for saved release 13/26 inputs.

Checks internal consistency only. No source authentication, derivation replay,
preprocessing estimation, persistence or research acceptance is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

import numpy as np

from .release_minute_contract import ReleaseMinutePackageIdentity
from .release_inputs import (
    ReleaseInputContext, ReleaseInputIdentity, ReleaseInputLabels, ReleaseInputPreparationError,
    ReleasePreparedMinutes, ReleasePreprocessState, _validate_content,
)
from .release_model_inputs import (
    ReleaseModelInputPair, ReleaseModelLabelSidecar, ReleaseModelPopulation,
)

_PROFILE = 'c17-release-iforest-engineering-v1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_CODES = frozenset((
    'INVALID_IF_ARGUMENTS', 'INVALID_IF_INPUT', 'RESOURCE_LIMIT',
    'NO_TRAINING_NORMAL', 'NO_CALIBRATION_NORMAL', 'INVALID_INPUT_NUMERIC',
    'INVALID_MODEL_SCORES', 'MODEL_UNAVAILABLE', 'MODEL_ERROR', 'INVALID_IF_RESULT',
))


class ReleaseIFError(ValueError):
    """A safe bounded code, without input values or original exception details."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in _CODES else 'INVALID_IF_INPUT'
        super().__init__(self.code)


def _need(condition, code='INVALID_IF_INPUT'):
    if not condition:
        raise ReleaseIFError(code) from None


def _same(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is tuple:
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _sha(value, code):
    _need(type(value) is str and _SHA.fullmatch(value) is not None, code)


def _identity(value, kind, profile, code):
    _need(type(value) is kind, code)
    _need(type(value.profile_id) is str and value.profile_id == profile, code)
    _sha(value.context_sha256, code)
    _sha(value.manifest_sha256, code)
    _need(type(value.manifest_byte_count) is int and 1 <= value.manifest_byte_count <= 65536, code)


def _identities(value, code):
    _identity(value.raw_identity, ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1', code)
    _identity(value.prepared_identity, ReleaseInputIdentity, 'c17-release-prepared-input-package-v1', code)
    _sha(value.configuration_sha256, code)


def _indices(value, n, code='INVALID_IF_INPUT'):
    _need(type(value) is tuple and len(value) <= n, code)
    _need(all(type(i) is int and 0 <= i < n for i in value), code)
    _need(all(a < b for a, b in zip(value, value[1:])), code)


def _mask(value, n):
    _need(type(value) is tuple and len(value) == n and all(type(v) is bool for v in value))


@dataclass(frozen=True, slots=True)
class _NumericInputs:
    matrix: np.ndarray
    common_indices: tuple[int, ...]
    train_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    preprocessing_fit_indices: tuple[int, ...]


def _validated_inputs(pair, view):
    """Validate saved structure, then return numbers/indices without a label sidecar."""
    _need(type(pair) is ReleaseModelInputPair, 'INVALID_IF_ARGUMENTS')
    _need(type(view) is str and view in ('current13', 'h30_26'), 'INVALID_IF_ARGUMENTS')
    try:
        _identities(pair, 'INVALID_IF_INPUT')
        for value, expected in (
            (pair.profile_id, 'c17-release-model-input-pair-v1'),
            (pair.raw_scope, 'PACKAGE_INTERNAL_CONSISTENCY_ONLY'),
            (pair.prepared_scope, 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY'),
            (pair.source_schema_id, 'c17-release-91-v1'),
            (pair.source_authentication, 'NOT_AUTHENTICATED'),
            (pair.time_basis, 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'),
        ):
            _need(_same(value, expected))
        _need(type(pair.prepared_minutes) is ReleasePreparedMinutes)
        _need(type(pair.labels) is ReleaseModelLabelSidecar)
        _need(type(pair.population) is ReleaseModelPopulation)
        m, labels, pop = pair.prepared_minutes, pair.labels.saved, pair.population
        _need(type(m.timestamps) is tuple and len(m.timestamps) >= 1)
        n = len(m.timestamps)
        _need(n <= 10000, 'RESOURCE_LIMIT')
        _need(type(labels) is ReleaseInputLabels)
        _need(type(labels.fit_indices) is tuple and len(labels.fit_indices) <= n)
        _need(type(pair.preprocessing) is ReleasePreprocessState)
        _need(type(pair.preprocessing.n_samples_seen) is int
              and 1 <= pair.preprocessing.n_samples_seen <= n)
        _need(type(pair.segments) is tuple and len(pair.segments) >= 1)
        _need(len(pair.segments) <= 7, 'RESOURCE_LIMIT')
        context = ReleaseInputContext(pair.prepared_identity.profile_id, pair.source_schema_id,
            pair.source_authentication, pair.time_basis, pair.raw_identity, pair.configuration,
            pair.configuration_sha256, pair.segments, n)
        _validate_content(context, pair.preprocessing, m, labels)
        for values, expected in (
            (pair.segment_ids, tuple(pair.segments[j].id for j in m.segment_ordinals)),
            (pair.roles, tuple(pair.segments[j].role for j in m.segment_ordinals)),
        ):
            _need(_same(values, expected))
        _mask(pair.labels.definite_attack_present, n)
        _need(type(pair.raw_values) is tuple and len(pair.raw_values) == n)
        for row, valid in zip(pair.raw_values, m.raw_valid):
            _need(type(row) is tuple and len(row) == 13)
            _need(all(type(x) is float and math.isfinite(x) and x >= 0 for x in row)
                  if valid else all(x is None for x in row))
        for joined, history in zip((pair.joined_h15, pair.joined_h30), m.histories):
            expected = tuple(current + residual if ok else (None,) * 26
                for current, residual, ok in zip(m.current_values, history.residual, history.valid))
            _need(_same(joined, expected))
        _need(_same(pop.policy, pair.configuration.audit_fit_policy))
        selected = labels.qualification_masks[labels.policies.index(pop.policy)]
        for mask, indices, expected in (
            (pop.preprocessing_fit_mask, pop.preprocessing_fit_indices, labels.fit_mask),
            (pop.train_mask, pop.train_indices, selected.train_full_history_normal),
            (pop.calibration_mask, pop.calibration_indices, selected.calibration_full_history_normal),
        ):
            _mask(mask, n)
            _indices(indices, n)
            _need(_same(mask, expected))
            _need(indices == tuple(i for i, ok in enumerate(mask) if ok))
        _need(not set(pop.train_indices) & set(pop.calibration_indices))
        _need(set(pop.train_indices) <= set(pop.preprocessing_fit_indices))
        _need(bool(pop.train_indices), 'NO_TRAINING_NORMAL')
        _need(bool(pop.calibration_indices), 'NO_CALIBRATION_NORMAL')
        common = tuple(i for i, ok in enumerate(m.common_valid) if ok)
        rows = m.current_values if view == 'current13' else pair.joined_h30
        width = 13 if view == 'current13' else 26
        with np.errstate(over='ignore', invalid='ignore'):
            selected_values = np.asarray([rows[i] for i in common], dtype=np.float32)
        _need(np.isfinite(selected_values).all(), 'INVALID_INPUT_NUMERIC')
        matrix = np.full((n, width), np.nan, dtype=np.float32)
        matrix[list(common)] = selected_values
        matrix.flags.writeable = False
        return _NumericInputs(matrix, common, pop.train_indices, pop.calibration_indices,
                              pop.preprocessing_fit_indices)
    except ReleaseInputPreparationError as exc:
        raise ReleaseIFError('RESOURCE_LIMIT' if exc.code == 'RESOURCE_LIMIT' else 'INVALID_IF_INPUT') from None
    except ReleaseIFError:
        raise
    except (TypeError, ValueError, AttributeError, IndexError, OverflowError):
        raise ReleaseIFError('INVALID_IF_INPUT') from None


@dataclass(frozen=True, slots=True)
class ReleaseIFConfiguration:
    input_width: int
    n_estimators: int
    max_samples: int
    max_features: float
    bootstrap: bool
    contamination: str
    random_state: int
    n_jobs: int


@dataclass(frozen=True, slots=True)
class ReleaseIFResult:
    profile_id: str
    view: str
    raw_identity: ReleaseMinutePackageIdentity
    prepared_identity: ReleaseInputIdentity
    configuration_sha256: str
    scores: tuple[float | None, ...]
    predictions: tuple[bool | None, ...]
    scored_mask: tuple[bool, ...]
    threshold: float
    train_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    preprocessing_fit_indices: tuple[int, ...]
    configuration: ReleaseIFConfiguration


def _configuration(width, train_count):
    return ReleaseIFConfiguration(width, 16, min(32, train_count), 1.0,
                                  False, 'auto', 42, 1)


def _compute(values, configuration):
    """The estimator and calibration see only stripped numerical inputs."""
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        raise ReleaseIFError('MODEL_UNAVAILABLE') from None
    except Exception:
        raise ReleaseIFError('MODEL_ERROR') from None
    try:
        model = IsolationForest(n_estimators=configuration.n_estimators,
            max_samples=configuration.max_samples, max_features=configuration.max_features,
            bootstrap=configuration.bootstrap, contamination=configuration.contamination,
            random_state=configuration.random_state, n_jobs=configuration.n_jobs)
        model.fit(values.matrix[list(values.train_indices)])
        returned = model.score_samples(values.matrix[list(values.common_indices)])
    except Exception:
        raise ReleaseIFError('MODEL_ERROR') from None
    try:
        original = np.asarray(returned)
        _need(original.ndim == 1 and len(original) == len(values.common_indices)
              and original.dtype.kind in 'iuf', 'INVALID_MODEL_SCORES')
        with np.errstate(over='raise', invalid='raise'):
            scores = -original.astype(np.float64)
        _need(np.isfinite(scores).all(), 'INVALID_MODEL_SCORES')
        full = np.full(len(values.matrix), np.nan, dtype=np.float64)
        full[list(values.common_indices)] = scores
        from .evaluation.calibration import calibrate
        with np.errstate(over='raise', invalid='raise'):
            threshold = calibrate(full[list(values.calibration_indices)])
        _need(type(threshold) is float and math.isfinite(threshold), 'INVALID_MODEL_SCORES')
        return full, threshold
    except ReleaseIFError:
        raise
    except Exception:
        raise ReleaseIFError('INVALID_MODEL_SCORES') from None


def fit_release_iforest(pair: ReleaseModelInputPair, *, view: str) -> ReleaseIFResult:
    """Fit fixed engineering defaults to model train rows and score the common axis."""
    values = _validated_inputs(pair, view)
    configuration = _configuration(values.matrix.shape[1], len(values.train_indices))
    scores, threshold = _compute(values, configuration)
    selected = set(values.common_indices)
    mask = tuple(i in selected for i in range(len(values.matrix)))
    return ReleaseIFResult(_PROFILE, view, pair.raw_identity, pair.prepared_identity,
        pair.configuration_sha256,
        tuple(float(value) if ok else None for value, ok in zip(scores, mask)),
        tuple(bool(value > threshold) if ok else None for value, ok in zip(scores, mask)),
        mask, threshold, values.train_indices, values.calibration_indices,
        values.preprocessing_fit_indices, configuration)


def _validate_result(result):
    code = 'INVALID_IF_RESULT'
    _need(type(result) is ReleaseIFResult, code)
    _identities(result, code)
    _need(_same(result.profile_id, _PROFILE), code)
    _need(type(result.view) is str and result.view in ('current13', 'h30_26'), code)
    _need(type(result.scored_mask) is tuple and 1 <= len(result.scored_mask) <= 10000, code)
    n = len(result.scored_mask)
    _need(all(type(ok) is bool for ok in result.scored_mask), code)
    for vector in (result.scores, result.predictions):
        _need(type(vector) is tuple and len(vector) == n, code)
    _need(type(result.threshold) is float and math.isfinite(result.threshold), code)
    for score, prediction, ok in zip(result.scores, result.predictions, result.scored_mask):
        if ok:
            _need(type(score) is float and math.isfinite(score), code)
            _need(type(prediction) is bool and prediction == (score > result.threshold), code)
        else:
            _need(score is None and prediction is None, code)
    for indices in (result.train_indices, result.calibration_indices,
                    result.preprocessing_fit_indices):
        _indices(indices, n, code)
        _need(bool(indices), code)
    train, cal = set(result.train_indices), set(result.calibration_indices)
    _need(not train & cal, code)
    _need(all(result.scored_mask[i] for i in train | cal), code)
    _need(train <= set(result.preprocessing_fit_indices), code)
    config = result.configuration
    _need(type(config) is ReleaseIFConfiguration, code)
    width = 13 if result.view == 'current13' else 26
    expected = _configuration(width, len(result.train_indices))
    for name in ReleaseIFConfiguration.__dataclass_fields__:
        _need(_same(getattr(config, name), getattr(expected, name)), code)


def summarize_release_iforest(result: ReleaseIFResult) -> dict:
    """Return a structural engineering report; this does not authenticate execution."""
    try:
        _validate_result(result)
        def identity(value):
            return {name: getattr(value, name) for name in
                ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')}
        calibration = tuple(result.scores[i] for i in result.calibration_indices)
        return dict(version=1, profile_id=result.profile_id, status='ENGINEERING_COMPUTED',
            view=result.view,
            configuration={name: getattr(result.configuration, name)
                           for name in ReleaseIFConfiguration.__dataclass_fields__},
            raw_identity=identity(result.raw_identity), prepared_identity=identity(result.prepared_identity),
            configuration_sha256=result.configuration_sha256,
            minute_counts=dict(total=len(result.scores), scored=sum(result.scored_mask),
                training=len(result.train_indices), calibration=len(result.calibration_indices),
                preprocessing_fit=len(result.preprocessing_fit_indices)),
            threshold=result.threshold,
            calibration=dict(quantile=.99, method='linear', comparison='STRICT_GREATER',
                equal_threshold_count=sum(score == result.threshold for score in calibration),
                above_threshold_count=sum(score > result.threshold for score in calibration)),
            limitations=['ENGINEERING_DEFAULTS_ONLY', 'AUDIT_ONLY', 'NOT_AUTHENTICATED',
                'SOURCE_WALL_CLOCK_COMPLETION_PROXY', 'DERIVATION_REPLAY_NOT_PERFORMED',
                'NOT_REESTIMATED', 'EXTERNAL_ACCEPTANCE_NOT_ESTABLISHED'])
    except ReleaseIFError:
        raise
    except (TypeError, ValueError, AttributeError, IndexError, OverflowError):
        raise ReleaseIFError('INVALID_IF_RESULT') from None
