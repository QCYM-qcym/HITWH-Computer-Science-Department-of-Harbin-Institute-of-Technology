"""Read-only pairing of saved release inputs; never prepares or executes models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re

from ._release_minutes import ReleaseBucketCounts, ReleaseMinuteResult, ReleaseSegment
from .candidate_inputs import G13U_FEATURE_NAMES
from .release_minute_contract import ReleaseMinutePackage, ReleaseMinutePackageIdentity
from .release_inputs import (
    ReleaseInputContext, ReleaseInputIdentity, ReleaseInputLabels, ReleaseInputLoadReport,
    ReleasePolicyQualification, ReleasePreparationConfig, ReleasePreparedHistory,
    ReleasePreparedInputs, ReleasePreparedMinutes, ReleasePreprocessState,
)

Rows = tuple[tuple[float | None, ...], ...]

_CODES = frozenset((
    'INVALID_PAIR_ARGUMENTS', 'INVALID_PAIR_STRUCTURE', 'INCOMPATIBLE_PAIR',
    'RESOURCE_LIMIT', 'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH',
))
_POLICIES = ('P_U', 'P_B', 'P_A')
_ROLES = ('train', 'validation', 'calibration', 'test')
_QUALIFICATIONS = ('train_full_history_normal', 'calibration_full_history_normal',
    'validation_current_normal', 'validation_current_attack', 'validation_current_unknown',
    'test_current_normal', 'test_current_attack', 'test_current_unknown')
_SHA = re.compile(r'[0-9a-f]{64}\Z')


class ReleaseModelInputPairError(ValueError):
    """A bounded safe error code, without input details."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in _CODES else 'INVALID_PAIR_STRUCTURE'
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ReleaseModelLabelSidecar:
    saved: ReleaseInputLabels
    definite_attack_present: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class ReleaseModelPopulation:
    policy: str
    preprocessing_fit_mask: tuple[bool, ...]
    preprocessing_fit_indices: tuple[int, ...]
    train_mask: tuple[bool, ...]
    train_indices: tuple[int, ...]
    calibration_mask: tuple[bool, ...]
    calibration_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ReleaseModelInputPair:
    profile_id: str
    raw_identity: ReleaseMinutePackageIdentity
    prepared_identity: ReleaseInputIdentity
    configuration: ReleasePreparationConfig
    configuration_sha256: str
    preprocessing: ReleasePreprocessState
    segments: tuple[ReleaseSegment, ...]
    segment_ids: tuple[str, ...]
    roles: tuple[str, ...]
    raw_values: Rows
    prepared_minutes: ReleasePreparedMinutes
    joined_h15: Rows
    joined_h30: Rows
    labels: ReleaseModelLabelSidecar
    population: ReleaseModelPopulation
    raw_scope: str
    prepared_scope: str
    source_schema_id: str
    source_authentication: str
    time_basis: str


def _need(condition, code='INVALID_PAIR_STRUCTURE'):
    if not condition:
        raise ReleaseModelInputPairError(code)


def _exact(value, kind):
    _need(type(value) is kind)


def _tuple(value, count, code='INVALID_PAIR_STRUCTURE'):
    _exact(value, tuple)
    _need(len(value) == count, code)


def _fixed(value, expected):
    _exact(value, type(expected))
    _need(value == expected, 'INCOMPATIBLE_PAIR')


def _sha(value):
    _exact(value, str)
    _need(_SHA.fullmatch(value) is not None)


def _identity(value, kind, profile):
    _exact(value, kind)
    _fixed(value.profile_id, profile)
    _sha(value.context_sha256)
    _sha(value.manifest_sha256)
    _exact(value.manifest_byte_count, int)
    _need(value.manifest_byte_count >= 1)
    _need(value.manifest_byte_count <= 65536, 'RESOURCE_LIMIT')


def _stamp(value):
    _exact(value, datetime)
    _need(value.tzinfo is None and value.second == value.microsecond == 0)


def _segments(value):
    _exact(value, tuple)
    _need(len(value) >= 1)
    _need(len(value) <= 7, 'RESOURCE_LIMIT')
    seen = set()
    last_end = None
    last_role = -1
    for segment in value:
        _exact(segment, ReleaseSegment)
        _exact(segment.id, str)
        _need(1 <= len(segment.id) <= 128 and all(
            ord(c) >= 32 and ord(c) != 127 and not 0xd800 <= ord(c) <= 0xdfff for c in segment.id))
        _need(segment.id not in seen)
        seen.add(segment.id)
        _exact(segment.role, str)
        _need(segment.role in _ROLES)
        _stamp(segment.start)
        _stamp(segment.end)
        _need(segment.start < segment.end and (last_end is None or last_end <= segment.start))
        rank = _ROLES.index(segment.role)
        _need(rank >= last_role)
        last_end, last_role = segment.end, rank


def _mask(value, n):
    _tuple(value, n)
    _need(all(type(item) is bool for item in value))


def _vector(value, *, positive=False):
    _tuple(value, 13)
    _need(all(type(item) is float and math.isfinite(item)
              and (not positive or item > 0) for item in value))


def _rows(value, valid, n, *, raw=False):
    _tuple(value, n)
    for row, ok in zip(value, valid):
        _tuple(row, 13)
        if ok:
            _vector(row)
            if raw:
                _need(all(item >= 0 for item in row))
        else:
            _need(all(item is None for item in row))


def _reasons(value, valid, n, allowed):
    _tuple(value, n)
    for reason, ok in zip(value, valid):
        if ok:
            _need(reason is None)
        else:
            _need(type(reason) is str and reason in allowed)


def _validate_pair(raw, saved):
    _need(type(raw) is ReleaseMinutePackage and type(saved) is ReleasePreparedInputs,
          'INVALID_PAIR_ARGUMENTS')
    for value, kind in ((raw.minutes, ReleaseMinuteResult), (saved.context, ReleaseInputContext),
        (saved.preprocessing, ReleasePreprocessState), (saved.minutes, ReleasePreparedMinutes),
        (saved.labels, ReleaseInputLabels), (saved.load_report, ReleaseInputLoadReport)):
        _exact(value, kind)
    r, context, state, minutes, labels = raw.minutes, saved.context, saved.preprocessing, saved.minutes, saved.labels
    n = context.minute_count
    _exact(n, int)
    _need(n >= 1)
    _need(n <= 10000, 'RESOURCE_LIMIT')
    _segments(raw.segments)
    _segments(context.segments)
    _identity(raw.identity, ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
    _identity(context.upstream, ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
    _identity(saved.identity, ReleaseInputIdentity, 'c17-release-prepared-input-package-v1')
    _identity(saved.load_report.identity, ReleaseInputIdentity, 'c17-release-prepared-input-package-v1')
    _need(raw.identity == context.upstream, 'UPSTREAM_IDENTITY_MISMATCH')
    _need(saved.identity == saved.load_report.identity, 'PAIR_ALIGNMENT_MISMATCH')
    _fixed(raw.scope, 'PACKAGE_INTERNAL_CONSISTENCY_ONLY')
    _fixed(saved.load_report.scope, 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY')
    _fixed(context.profile_id, 'c17-release-prepared-input-package-v1')
    for value in (r.schema_id, context.source_schema_id):
        _fixed(value, 'c17-release-91-v1')
    for value in (r.source_authentication, context.source_authentication):
        _fixed(value, 'NOT_AUTHENTICATED')
    for value in (r.time_basis, context.time_basis):
        _fixed(value, 'SOURCE_WALL_CLOCK_COMPLETION_PROXY')
    config = context.configuration
    _exact(config, ReleasePreparationConfig)
    _fixed(config.schema_version, 1)
    _fixed(config.numeric_rules_id, 'c17-release-log1p-mad-input-rules-v1')
    for names in (r.feature_names, config.feature_names):
        _tuple(names, 13)
        _need(all(type(name) is str for name in names))
        _need(names == G13U_FEATURE_NAMES, 'INCOMPATIBLE_PAIR')
    _tuple(config.windows, 2)
    _need(all(type(window) is int for window in config.windows))
    _need(config.windows == (15, 30), 'INCOMPATIBLE_PAIR')
    _fixed(config.fit_window, 30)
    _exact(config.epsilon, float)
    _need(math.isfinite(config.epsilon) and config.epsilon > 0, 'INCOMPATIBLE_PAIR')
    _exact(config.audit_fit_policy, str)
    _need(config.audit_fit_policy in _POLICIES, 'INCOMPATIBLE_PAIR')
    _fixed(config.policy_status, 'AUDIT_ONLY')
    _sha(context.configuration_sha256)
    _vector(state.mean)
    _vector(state.scale, positive=True)
    _fixed(state.fit_window, 30)
    _exact(state.audit_fit_policy, str)
    _need(state.audit_fit_policy == config.audit_fit_policy)
    _sha(state.fit_mask_sha256)
    _sha(state.fit_rows_sha256)
    _need(raw.segments == context.segments, 'PAIR_ALIGNMENT_MISMATCH')
    for axis in (r.timestamps, r.segment_ids, r.roles, minutes.timestamps, minutes.segment_ordinals):
        _tuple(axis, n, 'PAIR_ALIGNMENT_MISMATCH')
    for stamps in (r.timestamps, minutes.timestamps):
        for stamp in stamps:
            _stamp(stamp)
    _need(r.timestamps == minutes.timestamps, 'PAIR_ALIGNMENT_MISMATCH')
    for i, (stamp, ordinal, segment_id, role) in enumerate(zip(
            minutes.timestamps, minutes.segment_ordinals, r.segment_ids, r.roles)):
        _exact(ordinal, int)
        _need(0 <= ordinal < len(raw.segments))
        _exact(segment_id, str)
        _exact(role, str)
        segment = raw.segments[ordinal]
        _need(segment_id == segment.id and role == segment.role
              and segment.start <= stamp < segment.end, 'PAIR_ALIGNMENT_MISMATCH')
        _need(not i or minutes.timestamps[i - 1] < stamp, 'PAIR_ALIGNMENT_MISMATCH')
    for mask in (r.source_valid, minutes.raw_valid, minutes.prepared_valid, minutes.common_valid):
        _mask(mask, n)
    _need(r.source_valid == minutes.raw_valid, 'PAIR_ALIGNMENT_MISMATCH')
    _rows(r.values, r.source_valid, n, raw=True)
    _rows(minutes.current_values, minutes.prepared_valid, n)
    _reasons(minutes.prepared_reason, minutes.prepared_valid, n, ('source_invalid', 'nonfinite_transform'))
    _need(all(not valid or raw_valid for valid, raw_valid in zip(minutes.prepared_valid, minutes.raw_valid)))
    _tuple(minutes.histories, 2)
    for history, window in zip(minutes.histories, (15, 30)):
        _exact(history, ReleasePreparedHistory)
        _fixed(history.window, window)
        _mask(history.valid, n)
        _rows(history.residual, history.valid, n)
        _reasons(history.invalid_reason, history.valid, n,
                 ('warmup', 'boundary', 'gap', 'invalid_input', 'nonfinite_history'))
        _need(all(not valid or prepared for valid, prepared in zip(history.valid, minutes.prepared_valid)))
    _need(all(common == (prepared and h15 and h30) for common, prepared, h15, h30 in zip(
        minutes.common_valid, minutes.prepared_valid, minutes.histories[0].valid, minutes.histories[1].valid)))
    _tuple(labels.policies, 3)
    _need(all(type(policy) is str for policy in labels.policies))
    _need(labels.policies == _POLICIES, 'INCOMPATIBLE_PAIR')
    for kinds in (r.label_kinds, labels.label_kinds):
        _tuple(kinds, n, 'PAIR_ALIGNMENT_MISMATCH')
        for row in kinds:
            _tuple(row, 3)
            _need(all(type(kind) is str and kind in ('normal', 'attack', 'unknown') for kind in row))
    _need(r.label_kinds == labels.label_kinds, 'PAIR_ALIGNMENT_MISMATCH')
    _tuple(r.bucket_counts, n)
    for bucket in r.bucket_counts:
        _exact(bucket, ReleaseBucketCounts)
        _exact(bucket.definite_attack_present, bool)
    _mask(labels.fit_mask, n)
    _exact(labels.fit_indices, tuple)
    _need(len(labels.fit_indices) <= n)
    _need(all(type(index) is int and 0 <= index < n for index in labels.fit_indices))
    _need(labels.fit_indices == tuple(i for i, ok in enumerate(labels.fit_mask) if ok))
    _exact(state.n_samples_seen, int)
    _need(state.n_samples_seen == len(labels.fit_indices) and state.n_samples_seen >= 1)
    selected = _POLICIES.index(config.audit_fit_policy)
    for i in labels.fit_indices:
        _need(minutes.raw_valid[i] and r.roles[i] == 'train' and labels.label_kinds[i][selected] == 'normal')
    _tuple(labels.qualification_masks, 3)
    for qualification, policy in zip(labels.qualification_masks, _POLICIES):
        _exact(qualification, ReleasePolicyQualification)
        _fixed(qualification.policy, policy)
        for name in _QUALIFICATIONS:
            _mask(getattr(qualification, name), n)
    qualification = labels.qualification_masks[selected]
    for mask, role in ((qualification.train_full_history_normal, 'train'),
                       (qualification.calibration_full_history_normal, 'calibration')):
        for i, ok in enumerate(mask):
            if ok:
                _need(minutes.common_valid[i] and r.roles[i] == role and labels.label_kinds[i][selected] == 'normal')


def pair_release_model_inputs(
    raw: ReleaseMinutePackage, saved: ReleasePreparedInputs,
) -> ReleaseModelInputPair:
    _validate_pair(raw, saved)
    r = raw.minutes
    minutes = saved.minutes
    qualification = saved.labels.qualification_masks[
        saved.labels.policies.index(saved.context.configuration.audit_fit_policy)]
    population = ReleaseModelPopulation(
        saved.context.configuration.audit_fit_policy, saved.labels.fit_mask,
        saved.labels.fit_indices, qualification.train_full_history_normal,
        tuple(i for i, ok in enumerate(qualification.train_full_history_normal) if ok),
        qualification.calibration_full_history_normal,
        tuple(i for i, ok in enumerate(qualification.calibration_full_history_normal) if ok),
    )
    joined = tuple(tuple(current + residual if valid else (None,) * 26
                         for current, residual, valid in zip(
                             minutes.current_values, history.residual, history.valid))
                   for history in minutes.histories)
    return ReleaseModelInputPair(
        'c17-release-model-input-pair-v1', raw.identity, saved.identity,
        saved.context.configuration, saved.context.configuration_sha256,
        saved.preprocessing, raw.segments, r.segment_ids, r.roles, r.values,
        minutes, joined[0], joined[1],
        ReleaseModelLabelSidecar(saved.labels, tuple(b.definite_attack_present for b in r.bucket_counts)),
        population, raw.scope, saved.load_report.scope, r.schema_id,
        r.source_authentication, r.time_basis,
    )


def summarize_release_model_inputs(pair: ReleaseModelInputPair) -> dict:
    _need(type(pair) is ReleaseModelInputPair, 'INVALID_PAIR_ARGUMENTS')
    config, minutes, state = pair.configuration, pair.prepared_minutes, pair.preprocessing
    def identity(value):
        return {name: getattr(value, name) for name in (
            'profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')}
    columns = list(config.feature_names)
    return dict(
        version=1, profile_id=pair.profile_id, status='INPUTS_PAIRED',
        raw_identity=identity(pair.raw_identity), prepared_identity=identity(pair.prepared_identity),
        configuration=dict(schema_version=config.schema_version, numeric_rules_id=config.numeric_rules_id,
            windows=list(config.windows), fit_window=config.fit_window, epsilon=config.epsilon,
            audit_fit_policy=config.audit_fit_policy, policy_status=config.policy_status),
        configuration_sha256=pair.configuration_sha256,
        source=dict(schema_id=pair.source_schema_id, authentication=pair.source_authentication, time_basis=pair.time_basis),
        scopes=dict(pair='READ_ONLY_MODEL_INPUT_PAIR', raw=pair.raw_scope, prepared=pair.prepared_scope),
        checks=dict(derivation_replay='DERIVATION_REPLAY_NOT_PERFORMED', fit_parameters='NOT_REESTIMATED',
            model='MODEL_NOT_LOADED', execution='EXECUTION_NOT_GRANTED', external_case_evidence='NOT_ESTABLISHED'),
        feature_columns=dict(raw13=columns, current13=list(columns),
            h15_26=['current:' + name for name in columns] + ['residual_h15:' + name for name in columns],
            h30_26=['current:' + name for name in columns] + ['residual_h30:' + name for name in columns]),
        minute_counts=dict(total=len(minutes.timestamps), raw_valid=sum(minutes.raw_valid),
            prepared_valid=sum(minutes.prepared_valid), history_h15_valid=sum(minutes.histories[0].valid),
            history_h30_valid=sum(minutes.histories[1].valid), common_valid=sum(minutes.common_valid),
            definite_attack_present=sum(pair.labels.definite_attack_present)),
        preprocessing_fit=dict(count=len(pair.population.preprocessing_fit_indices),
            mask_sha256=state.fit_mask_sha256, rows_sha256=state.fit_rows_sha256),
        model_population=dict(policy=pair.population.policy, train_count=len(pair.population.train_indices),
            calibration_count=len(pair.population.calibration_indices)),
        qualification_counts={q.policy: {name: sum(getattr(q, name)) for name in _QUALIFICATIONS}
                              for q in pair.labels.saved.qualification_masks},
    )
