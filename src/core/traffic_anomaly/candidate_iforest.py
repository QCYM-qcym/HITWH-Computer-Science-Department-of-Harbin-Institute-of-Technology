"""Current13 IF engineering on verified SYNTHETIC_ONLY candidate snapshots."""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .candidate_artifacts import VerifiedCandidateArtifacts
from .candidate_evaluation import evaluate_candidate_predictions
from .candidate_inputs import (
    CandidateMinuteBatch, G13U_FEATURE_NAMES, MAX_MINUTES, PARTITIONS, _eligible,
)
from .candidate_records import POLICIES
from .evaluation.calibration import calibrate

MODEL_PROFILE_ID = 'c17-i1-g13u-iforest-synthetic-v1'
_MODEL_KEYS = ('n_estimators', 'max_samples', 'max_features', 'bootstrap',
               'contamination', 'random_state', 'n_jobs')


class CandidateIFError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code='INVALID_INPUT_SCOPE'):
    if not condition:
        raise CandidateIFError(code)


def _mask(value, n):
    array = np.asarray(value)
    _require(array.shape == (n,) and array.dtype == np.dtype(bool))
    return array


def _readonly(value):
    array = np.asarray(value)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


def _configuration(n_train):
    return dict(model_profile_id=MODEL_PROFILE_ID, parameter_status='ENGINEERING_TOY_ONLY',
        input_width=13, n_estimators=16, max_samples=min(32, n_train), max_features=1.0,
        bootstrap=False, contamination='auto', random_state=42, n_jobs=1,
        score_direction='HIGHER_IS_MORE_ANOMALOUS', fit_scope='TRAIN_NORMAL_COMMON',
        calibration_scope='CALIBRATION_NORMAL_COMMON', quantile=.99, quantile_method='linear',
        alarm_comparison='STRICT_GREATER', preprocessing_fit_provenance='NOT_REESTIMATED')


def _inputs(snapshot):
    _require(isinstance(snapshot, VerifiedCandidateArtifacts))
    report = snapshot.report
    _require(report.get('status') == 'VERIFIED' and report.get('evidence_kind') == 'SYNTHETIC_ONLY'
             and report.get('time_basis') == 'synthetic_source_clock'
             and report.get('policy_status') == 'AUDIT_ONLY'
             and report.get('selected_policy') in POLICIES
             and report.get('checks', {}).get('source_replay') == 'VERIFIED'
             and report.get('checks', {}).get('fit_parameters') == 'NOT_REESTIMATED'
             and snapshot.feature_names == G13U_FEATURE_NAMES and snapshot.value_space == 'prepared')
    n = len(snapshot.timestamps)
    _require(1 <= n <= MAX_MINUTES)
    row_valid = _mask(snapshot.row_valid, n)
    common = _mask(snapshot.common_valid, n)
    train, calibration = _mask(snapshot.training_normal, n), _mask(snapshot.calibration_normal, n)
    _mask(snapshot.source_attack_label_present, n)
    for policy in POLICIES:
        labels = snapshot.labels[policy]
        _require(len(labels) == n and all(kind in ('normal', 'attack', 'unknown') for kind in labels))
        normal = _mask(snapshot.normal_candidates[policy], n)
        _require(np.array_equal(normal, [kind == 'normal' for kind in labels]))
    h15 = _mask(snapshot.histories[15].valid, n)
    h30 = _mask(snapshot.histories[30].valid, n)
    _require(np.array_equal(common, h15 & h30) and not (common & ~row_valid).any())
    batch = CandidateMinuteBatch(snapshot.timestamps, snapshot.current_values, row_valid,
        snapshot.segment_ids, snapshot.partitions, value_space='prepared')
    selected_normal = snapshot.normal_candidates[report['selected_policy']]
    all_normal = _eligible(batch, 30, selected_normal) & common
    _require(np.array_equal(train, all_normal & (batch.partitions == 'train'))
             and np.array_equal(calibration, all_normal & (batch.partitions == 'calibration')))
    _require(train.any(), 'NO_TRAINING_NORMAL')
    _require(calibration.any(), 'NO_CALIBRATION_NORMAL')
    with np.errstate(over='ignore', invalid='ignore'):
        selected = batch.values[common].astype(np.float32)
    _require(np.isfinite(selected).all(), 'INVALID_INPUT_NUMERIC')
    return batch, common, train, calibration


def calibrate_candidate_scores(scores, score_valid, calibration_mask):
    """Independent fixed Q99 plus strict alarms; invalid axis positions are NaN."""
    try:
        scores = np.asarray(scores)
        _require(scores.ndim == 1 and 1 <= len(scores) <= MAX_MINUTES
                 and scores.dtype.kind in 'fiu', 'INVALID_MODEL_SCORES')
        scores = scores.astype(np.float64)
        valid, calibration = _mask(score_valid, len(scores)), _mask(calibration_mask, len(scores))
        _require(not (calibration & ~valid).any() and calibration.any(), 'NO_CALIBRATION_NORMAL')
        _require(np.isfinite(scores[valid]).all() and np.isnan(scores[~valid]).all(), 'INVALID_MODEL_SCORES')
        selected = scores[calibration]
        threshold = calibrate(selected)
        _require(math.isfinite(threshold), 'INVALID_MODEL_SCORES')
        alarms = np.zeros(len(scores), bool)
        alarms[valid] = scores[valid] > threshold
        metadata = dict(sample_count=len(selected), quantile=.99, method='linear', comparison='STRICT_GREATER',
            order_position_zero_based=(len(selected)-1)*.99,
            strictly_above_count=int((selected > threshold).sum()), equal_count=int((selected == threshold).sum()))
        return threshold, _readonly(alarms), metadata
    except CandidateIFError:
        raise
    except (ValueError, TypeError, OverflowError) as exc:
        raise CandidateIFError('INVALID_MODEL_SCORES') from exc


@dataclass(frozen=True, slots=True)
class CandidateIFResult:
    model: object
    scores: np.ndarray
    score_valid: np.ndarray
    alarms: np.ndarray
    threshold: float
    calibration: dict
    evaluation: dict
    configuration: dict
    fit_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]


def compute_synthetic_candidate_if(snapshot):
    """Fit a fixed toy IF; consumes no paths, CSV or preprocessing fit."""
    try:
        batch, common, train, calibration = _inputs(snapshot)
        configuration = _configuration(int(train.sum()))
        # CPU model dependency is imported only when explicitly executing.
        from sklearn.ensemble import IsolationForest
        model = IsolationForest(**{key: configuration[key] for key in _MODEL_KEYS})
        with np.errstate(over='ignore', invalid='ignore'):
            x_train = batch.values[train].astype(np.float32)
            x_score = batch.values[common].astype(np.float32)
        _require(np.isfinite(x_train).all() and np.isfinite(x_score).all(), 'INVALID_INPUT_NUMERIC')
        model.fit(x_train)
        scored = np.asarray(-model.score_samples(x_score), dtype=np.float64)
        _require(scored.shape == (int(common.sum()),) and np.isfinite(scored).all(), 'INVALID_MODEL_SCORES')
        scores = np.full(len(batch.timestamps), np.nan)
        scores[common] = scored
        threshold, alarms, calibration_metadata = calibrate_candidate_scores(scores, common, calibration)
        evaluation = evaluate_candidate_predictions(labels=snapshot.labels, partitions=batch.partitions,
            score_valid=common, alarms=alarms, source_attack_label_present=snapshot.source_attack_label_present,
            score_origin_policy=snapshot.report['selected_policy'])
        return CandidateIFResult(model, _readonly(scores), _readonly(common), alarms, threshold,
            calibration_metadata, evaluation, configuration, tuple(np.flatnonzero(train).tolist()),
            tuple(np.flatnonzero(calibration).tolist()))
    except CandidateIFError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError, RuntimeError) as exc:
        raise CandidateIFError('MODEL_ERROR') from exc


def replay_saved_candidate_if(snapshot, result, reloaded_model):
    """Check the caller's own just-created model; never opens a model file."""
    try:
        from sklearn.ensemble import IsolationForest
        batch, common, train, calibration = _inputs(snapshot)
        expected_configuration = _configuration(int(train.sum()))
        _require(isinstance(reloaded_model, IsolationForest) and isinstance(result, CandidateIFResult)
                 and result.configuration == expected_configuration, 'MODEL_RELOAD_MISMATCH')
        params = reloaded_model.get_params(deep=False)
        _require(all(params[key] == expected_configuration[key] for key in _MODEL_KEYS)
                 and reloaded_model.n_features_in_ == 13 and len(reloaded_model.estimators_) == 16
                 and reloaded_model.max_samples_ == min(32, int(train.sum())), 'MODEL_RELOAD_MISMATCH')
        with np.errstate(over='ignore', invalid='ignore'):
            matrix = batch.values[common].astype(np.float32)
        _require(np.isfinite(matrix).all(), 'MODEL_RELOAD_MISMATCH')
        scored = -reloaded_model.score_samples(matrix)
        _require(np.array_equal(result.score_valid, common)
                 and np.array_equal(result.scores[common], scored), 'MODEL_RELOAD_MISMATCH')
        threshold, alarms, meta = calibrate_candidate_scores(result.scores, common, calibration)
        _require(result.threshold == threshold and np.array_equal(result.alarms, alarms)
                 and result.calibration == meta and result.fit_indices == tuple(np.flatnonzero(train).tolist())
                 and result.calibration_indices == tuple(np.flatnonzero(calibration).tolist()), 'MODEL_RELOAD_MISMATCH')
        evaluation = evaluate_candidate_predictions(labels=snapshot.labels, partitions=batch.partitions,
            score_valid=common, alarms=alarms, source_attack_label_present=snapshot.source_attack_label_present,
            score_origin_policy=snapshot.report['selected_policy'])
        _require(result.evaluation == evaluation, 'MODEL_RELOAD_MISMATCH')
    except CandidateIFError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RuntimeError) as exc:
        raise CandidateIFError('MODEL_RELOAD_MISMATCH') from exc
