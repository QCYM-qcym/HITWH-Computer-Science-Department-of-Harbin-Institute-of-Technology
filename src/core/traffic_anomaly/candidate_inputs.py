"""Isolated G13U numeric inputs for bounded SYNTHETIC_ONLY development.

Consumes already aggregated candidate minutes. This is not the production
134/268 contract, a CSV adapter, or authorization for real preprocessing.
Timestamps are explicit source-clock coordinates, never machine local time.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

import numpy as np

PROFILE_ID = 'c17-i1-g13u-candidate-v1'
G13U_FEATURE_NAMES = (
    'completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
    'duration_p95_s', 'no_backward_packet_source_record_count',
)
PARTITIONS = ('train', 'validation', 'calibration', 'test')
MAX_MINUTES = 10000


def _freeze(values, dtype=None):
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _bool_mask(values, n):
    result = np.asarray(values)
    if result.dtype != np.dtype(bool) or result.shape != (n,):
        raise ValueError('aligned_boolean_mask_required')
    return result


def _window(window):
    if type(window) is not int or not 1 <= window <= 120:
        raise ValueError('window_out_of_bounds')


@dataclass(frozen=True)
class CandidateMinuteBatch:
    timestamps: np.ndarray
    values: np.ndarray
    row_valid: np.ndarray
    segment_ids: np.ndarray
    partitions: np.ndarray
    feature_names: tuple[str, ...] = G13U_FEATURE_NAMES
    value_space: str = 'raw'
    evidence_kind: str = 'SYNTHETIC_ONLY'

    def __post_init__(self):
        t = np.asarray(self.timestamps)
        if t.ndim != 1 or not 1 <= len(t) <= MAX_MINUTES or t.dtype.kind != 'M':
            raise ValueError('bounded_datetime_array_required')
        stamps = t.astype('datetime64[us]')
        if (np.isnat(stamps).any() or not np.array_equal(t, stamps.astype(t.dtype))
                or (stamps.view('i8') % 60000000 != 0).any()
                or (np.diff(stamps) <= np.timedelta64(0, 'us')).any()):
            raise ValueError('strictly_increasing_whole_source_minutes_required')
        n = len(t)
        x = np.asarray(self.values)
        valid = _bool_mask(self.row_valid, n)
        if x.shape != (n, 13) or x.dtype.kind not in 'fiu':
            raise ValueError('numeric_13_columns_required')
        if tuple(self.feature_names) != G13U_FEATURE_NAMES:
            raise ValueError('candidate_feature_order_mismatch')
        if self.evidence_kind != 'SYNTHETIC_ONLY' or self.value_space not in ('raw', 'prepared'):
            raise ValueError('candidate_scope_or_value_space')
        x = np.array(x, dtype=np.float64, copy=True)
        if not np.isfinite(x[valid]).all() or (self.value_space == 'raw' and (x[valid] < 0).any()):
            raise ValueError('invalid_candidate_values')
        x[~valid] = np.nan
        strings = []
        for values in (self.segment_ids, self.partitions):
            a = np.asarray(values)
            if a.shape != (n,) or any(not isinstance(s, (str, np.str_)) or not 1 <= len(s) <= 128 for s in a):
                raise ValueError('aligned_nonempty_string_ids_required')
            strings.append(np.array(a, dtype=str))
        segments, partitions = strings
        if any(p not in PARTITIONS for p in partitions):
            raise ValueError('candidate_partition')
        ranks = np.array([PARTITIONS.index(p) for p in partitions])
        if (np.diff(ranks) < 0).any():
            raise ValueError('chronological_partition_order_required')
        for key, value in (('timestamps', stamps), ('values', x), ('row_valid', valid),
                           ('segment_ids', segments), ('partitions', partitions)):
            object.__setattr__(self, key, _freeze(value))
        object.__setattr__(self, 'feature_names', G13U_FEATURE_NAMES)


def _reset(batch, i):
    if i == 0:
        return None
    if (batch.partitions[i] != batch.partitions[i-1]
            or batch.segment_ids[i] != batch.segment_ids[i-1]):
        return 'boundary'
    if batch.timestamps[i] - batch.timestamps[i-1] != np.timedelta64(1, 'm'):
        return 'gap'
    return None


def _eligible(batch, window, normal=None):
    """Current plus previous window qualification, with original axis intact."""
    _window(window)
    n = len(batch.timestamps)
    if normal is not None:
        normal = _bool_mask(normal, n)
    result, start = np.zeros(n, bool), 0
    for i in range(n):
        if _reset(batch, i):
            start = i
        if not batch.row_valid[i]:
            start = i + 1
        elif i-start >= window:
            result[i] = normal is None or normal[i-window:i+1].all()
    return result


@dataclass(frozen=True)
class CandidateHistoryBatch:
    current: np.ndarray
    residual: np.ndarray
    joined: np.ndarray
    valid: np.ndarray
    invalid_reason: tuple[str | None, ...]


def build_candidate_history(batch, *, window, epsilon):
    _window(window)
    if (isinstance(epsilon, (bool, np.bool_)) or not isinstance(epsilon, (int, float))
            or not math.isfinite(epsilon) or epsilon <= 0):
        raise ValueError('positive_finite_epsilon_required')
    if batch.value_space != 'prepared':
        raise ValueError('prepared_candidate_values_required')
    n = len(batch.timestamps)
    residual, valid = np.full((n, 13), np.nan), np.zeros(n, bool)
    reasons, start, pending = [], 0, 'warmup'
    for i in range(n):
        reset = _reset(batch, i)
        if reset:
            start, pending = i, reset
        if not batch.row_valid[i]:
            reasons.append('invalid_input')
            start, pending = i+1, 'invalid_input'
        elif i-start < window:
            reasons.append(pending)
        else:
            past = batch.values[i-window:i]
            with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
                median = np.median(past, axis=0)
                mad = np.median(np.abs(past-median), axis=0)
                numerator, denominator = batch.values[i]-median, mad+epsilon
                values = numerator/denominator
            if all(np.isfinite(v).all() for v in (median, mad, numerator, denominator, values)):
                residual[i], valid[i] = values, True
                reasons.append(None)
            else:
                reasons.append('nonfinite_history')
                start, pending = i+1, 'nonfinite_history'
    joined = np.concatenate((batch.values, residual), axis=1)
    joined[~valid] = np.nan
    return CandidateHistoryBatch(batch.values, _freeze(residual), _freeze(joined),
                                 _freeze(valid), tuple(reasons))


class CandidatePreprocessor:
    """Training-only log1p and population-standard-deviation scaling."""

    def __init__(self):
        self.mean = self.scale = None
        self.n_samples_seen = 0
        self.fit_window = None

    def fit(self, batch, normal_candidates, window=30):
        if batch.value_space != 'raw':
            raise ValueError('raw_candidate_values_required')
        eligible = _eligible(batch, window, normal_candidates) & (batch.partitions == 'train')
        if not eligible.any():
            raise ValueError('no_eligible_training_normal_minutes')
        z = np.log1p(batch.values[eligible])
        mean, scale = z.mean(axis=0), z.std(axis=0, ddof=0)
        # Reductions can leave a tiny nonzero std even for bitwise constant
        # columns. Preserve the specified exact constant-column semantics.
        constant = (z == z[0]).all(axis=0)
        mean[constant], scale[constant] = z[0, constant], 1
        scale[scale == 0] = 1
        self.mean, self.scale = _freeze(mean), _freeze(scale)
        self.n_samples_seen, self.fit_window = int(eligible.sum()), window
        return self

    def _require_fitted(self):
        if self.mean is None or self.scale is None:
            raise ValueError('candidate_preprocessor_not_fitted')

    def transform(self, batch):
        self._require_fitted()
        if batch.value_space != 'raw':
            raise ValueError('raw_candidate_values_required')
        x = np.full(batch.values.shape, np.nan)
        valid = batch.row_valid.copy()
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            x[valid] = (np.log1p(batch.values[valid])-self.mean)/self.scale
        valid &= np.isfinite(x).all(axis=1)
        return CandidateMinuteBatch(batch.timestamps, x, valid, batch.segment_ids,
                                    batch.partitions, value_space='prepared')

    def save(self, path):
        self._require_fitted()
        state = dict(schema_version=1, profile_id=PROFILE_ID, evidence_kind='SYNTHETIC_ONLY',
                     transform='log1p_standard_ddof0', feature_names=list(G13U_FEATURE_NAMES),
                     mean=self.mean.tolist(), scale=self.scale.tolist(),
                     n_samples_seen=self.n_samples_seen, fit_window=self.fit_window)
        with Path(path).open('x', encoding='utf-8') as f:
            json.dump(state, f, allow_nan=False, indent=2)
            f.write('\n')

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > 16384:
            raise ValueError('candidate_state_size')
        data = json.loads(path.read_text('utf-8'))
        expected = {'schema_version','profile_id','evidence_kind','transform','feature_names',
                    'mean','scale','n_samples_seen','fit_window'}
        if (not isinstance(data, dict) or set(data) != expected
                or type(data['schema_version']) is not int or data['schema_version'] != 1
                or data['profile_id'] != PROFILE_ID or data['evidence_kind'] != 'SYNTHETIC_ONLY'
                or data['transform'] != 'log1p_standard_ddof0'
                or data['feature_names'] != list(G13U_FEATURE_NAMES)
                or type(data['n_samples_seen']) is not int or not 1 <= data['n_samples_seen'] <= MAX_MINUTES):
            raise ValueError('incompatible_candidate_state')
        _window(data['fit_window'])
        try:
            mean, scale = np.asarray(data['mean']), np.asarray(data['scale'])
            if (mean.dtype.kind not in 'fiu' or scale.dtype.kind not in 'fiu'
                    or mean.shape != (13,) or scale.shape != (13,)
                    or not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale <= 0).any()):
                raise ValueError('invalid_candidate_state_values')
        except (TypeError, OverflowError) as exc:
            raise ValueError('invalid_candidate_state_values') from exc
        result = cls()
        result.mean, result.scale = _freeze(mean, float), _freeze(scale, float)
        result.n_samples_seen, result.fit_window = data['n_samples_seen'], data['fit_window']
        return result


@dataclass(frozen=True)
class CandidateInputs:
    preprocessor: CandidatePreprocessor
    prepared: CandidateMinuteBatch
    histories: dict[int, CandidateHistoryBatch]
    common_valid: np.ndarray
    training_normal: np.ndarray
    calibration_normal: np.ndarray
    test_normal: np.ndarray


def prepare_candidate_inputs(batch, normal_candidates, *, epsilon=1e-6):
    """Fixed H15/H30 development chain; consumes no model or test labels in history."""
    normal = _bool_mask(normal_candidates, len(batch.timestamps))
    preprocessor = CandidatePreprocessor().fit(batch, normal, window=30)
    prepared = preprocessor.transform(batch)
    histories = {w: build_candidate_history(prepared, window=w, epsilon=epsilon) for w in (15,30)}
    common = histories[15].valid & histories[30].valid
    all_normal = _eligible(prepared, 30, normal) & common
    return CandidateInputs(preprocessor, prepared, histories, _freeze(common),
        _freeze(all_normal & (batch.partitions == 'train')),
        _freeze(all_normal & (batch.partitions == 'calibration')),
        _freeze(common & normal & (batch.partitions == 'test')))
