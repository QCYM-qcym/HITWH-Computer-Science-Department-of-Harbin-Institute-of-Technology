"""Bounded saved IF results: internal consistency and explicit input declarations.

The codec neither authenticates sources nor proves model execution. It checks
the saved calibration scores without fitting, scoring or replaying inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
import hashlib
import json
import math
import re

import numpy as np

from ._release_minutes import ReleaseSegment
from .release_minute_contract import ReleaseMinutePackageIdentity
from .release_inputs import ReleaseInputIdentity
from .release_model_inputs import ReleaseModelInputPair
from .release_iforest import (
    ReleaseIFConfiguration, ReleaseIFResult, ReleaseIFError, _validated_inputs,
)
from .evaluation.calibration import calibrate

PACKAGE_MEMBER_NAMES = ('result.json', 'manifest.json', 'COMPLETE.json')
PACKAGE_MEMBER_BYTE_LIMITS = tuple(zip(PACKAGE_MEMBER_NAMES, (1048576, 65536, 4096)))
PACKAGE_TOTAL_BYTE_LIMIT = 1118208
_LIMITS = dict(PACKAGE_MEMBER_BYTE_LIMITS)
_P = 'c17-release-iforest-result-package-v1'
_R = 'c17-release-iforest-engineering-v1'
_SOURCE = 'c17-release-91-v1'
_AUTH = 'NOT_AUTHENTICATED'
_TIME = 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'
_SCOPE = 'SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY'
_ROLES = ('train', 'validation', 'calibration', 'test')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_STAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00\Z')
_CODES = frozenset(('INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE',
    'INCOMPATIBLE_PACKAGE', 'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH',
    'INCONSISTENT_PACKAGE', 'INVALID_PACKAGE_PATH', 'INPUT_UNAVAILABLE',
    'OUTPUT_EXISTS', 'PACKAGE_CHANGED', 'OUTPUT_ERROR', 'INPUT_BINDING_MISMATCH'))
_RESULT_FIELDS = ('scores', 'predictions', 'scored_mask', 'threshold',
    'train_indices', 'calibration_indices', 'preprocessing_fit_indices')
_IDENTITY_FIELDS = ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')


class ReleaseIFResultPackageError(ValueError):
    """A safe finite error code, without paths, values or original exceptions."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in _CODES else 'INVALID_PACKAGE'
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ReleaseIFResultIdentity:
    profile_id: str
    context_sha256: str
    manifest_sha256: str
    manifest_byte_count: int


@dataclass(frozen=True, slots=True)
class ReleaseIFCalibration:
    quantile: float
    method: str
    comparison: str


@dataclass(frozen=True, slots=True)
class ReleaseIFResultContext:
    profile_id: str
    result_profile_id: str
    view: str
    source_schema_id: str
    source_authentication: str
    time_basis: str
    policy_status: str
    audit_fit_policy: str
    raw_identity: ReleaseMinutePackageIdentity
    prepared_identity: ReleaseInputIdentity
    configuration_sha256: str
    model_configuration: ReleaseIFConfiguration
    segments: tuple[ReleaseSegment, ...]
    minute_count: int
    score_direction: str
    calibration: ReleaseIFCalibration


@dataclass(frozen=True, slots=True)
class ReleaseIFResultLoadReport:
    profile_id: str
    scope: str
    byte_integrity: str
    structure: str
    saved_score_q99: str
    source_authentication: str
    model_execution: str


@dataclass(frozen=True, slots=True)
class ReleaseIFResultPackage:
    identity: ReleaseIFResultIdentity
    context: ReleaseIFResultContext
    result: ReleaseIFResult
    load_report: ReleaseIFResultLoadReport


def _need(condition, code='INCONSISTENT_PACKAGE'):
    if not condition:
        raise ReleaseIFResultPackageError(code) from None


def _exact(value, kind):
    _need(type(value) is kind, 'INVALID_PACKAGE')
    if hasattr(kind, '__dataclass_fields__'):
        _need(all(hasattr(value, field.name) for field in fields(kind)), 'INVALID_PACKAGE')


def _fixed(value, expected, code='INCONSISTENT_PACKAGE'):
    _exact(value, type(expected))
    _need(value == expected, code)


def _uint(value, maximum, *, positive=False):
    _exact(value, int)
    _need(value >= int(positive), 'INVALID_PACKAGE')
    _need(value <= maximum, 'RESOURCE_LIMIT')
    return value


def _sha(value):
    _exact(value, str)
    _need(_SHA.fullmatch(value) is not None, 'INVALID_PACKAGE')


def _keys(value, names):
    _exact(value, dict)
    _need(len(value) == len(names) and all(type(k) is str for k in value)
          and set(value) == set(names), 'INVALID_PACKAGE')


def _sequence(value, kind, maximum, *, length=None, positive=False):
    _exact(value, kind)
    _need(len(value) <= maximum, 'RESOURCE_LIMIT')
    _need(not positive or bool(value), 'INCONSISTENT_PACKAGE')
    if length is not None:
        _need(len(value) == length)
    return value


def _identity(value, kind, profile):
    _exact(value, kind)
    _fixed(value.profile_id, profile, 'INCOMPATIBLE_PACKAGE')
    _sha(value.context_sha256)
    _sha(value.manifest_sha256)
    _uint(value.manifest_byte_count, 65536, positive=True)


def _values(value):
    return {field.name: getattr(value, field.name) for field in fields(value)}


def _report():
    return ReleaseIFResultLoadReport(_P, _SCOPE, 'MATCHED', 'MATCHED', 'MATCHED', _AUTH, _AUTH)


def _canonical(document, limit):
    output = bytearray()
    try:
        for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                sort_keys=True, separators=(',', ':')).iterencode(document):
            encoded = chunk.encode('utf-8')
            _need(len(output) + len(encoded) + 1 <= limit, 'RESOURCE_LIMIT')
            output.extend(encoded)
    except ReleaseIFResultPackageError:
        raise
    except (UnicodeError, TypeError, ValueError, OverflowError, RecursionError):
        raise ReleaseIFResultPackageError('INVALID_PACKAGE') from None
    return bytes(output) + b'\n'


def _digest(payload):
    return dict(byte_count=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def _json_integer(token):
    _need(len(token) <= 8, 'INVALID_PACKAGE')
    return int(token)


def _json_float(token):
    _need(len(token) <= 32, 'INVALID_PACKAGE')
    value = float(token)
    _need(math.isfinite(value), 'INVALID_PACKAGE')
    return value


def _json_object(pairs):
    document = {}
    for key, value in pairs:
        _need(key not in document, 'INVALID_PACKAGE')
        document[key] = value
    return document


def _bad_constant(_):
    raise ReleaseIFResultPackageError('INVALID_PACKAGE') from None


def _parse(payload, limit):
    try:
        document = json.loads(payload.decode('utf-8'), object_pairs_hook=_json_object,
            parse_int=_json_integer, parse_float=_json_float, parse_constant=_bad_constant)
        _need(_canonical(document, limit) == payload, 'INVALID_PACKAGE')
        return document
    except ReleaseIFResultPackageError:
        raise
    except (UnicodeError, TypeError, ValueError, OverflowError, RecursionError):
        raise ReleaseIFResultPackageError('INVALID_PACKAGE') from None


def _header(document, names, *, bound=True):
    _keys(document, names)
    _fixed(document['schema_version'], 1, 'INCOMPATIBLE_PACKAGE')
    _fixed(document['profile_id'], _P, 'INCOMPATIBLE_PACKAGE')
    if bound:
        _sha(document['context_sha256'])


def _binding(reference, payload):
    _keys(reference, ('byte_count', 'sha256'))
    _uint(reference['byte_count'], PACKAGE_TOTAL_BYTE_LIMIT, positive=True)
    _sha(reference['sha256'])
    _need(reference == _digest(payload), 'INTEGRITY_MISMATCH')


def _segments_axis(segments):
    _sequence(segments, tuple, 7, positive=True)
    roles, eligible = [], []
    previous_end, previous_role = None, -1
    seen = set()
    for segment in segments:
        _exact(segment, ReleaseSegment)
        _exact(segment.id, str)
        _need(len(segment.id) <= 128, 'RESOURCE_LIMIT')
        _need(bool(segment.id) and all(ord(c) >= 32 and ord(c) != 127
            and not 0xD800 <= ord(c) <= 0xDFFF for c in segment.id), 'INVALID_PACKAGE')
        _exact(segment.role, str)
        _need(segment.role in _ROLES, 'INVALID_PACKAGE')
        _need(segment.id not in seen)
        seen.add(segment.id)
        role = _ROLES.index(segment.role)
        _need(role >= previous_role)
        for stamp in (segment.start, segment.end):
            _exact(stamp, datetime)
            _need(stamp.tzinfo is None and stamp.second == stamp.microsecond == 0, 'INVALID_PACKAGE')
        _need(segment.start < segment.end
              and (previous_end is None or previous_end <= segment.start))
        count = (segment.end - segment.start) // timedelta(minutes=1)
        _need(len(roles) + count <= 10000, 'RESOURCE_LIMIT')
        roles.extend([segment.role] * count)
        eligible.extend(i >= 30 for i in range(count))
        previous_end, previous_role = segment.end, role
    return tuple(roles), tuple(eligible)


def _configuration(config, view, train_count=None):
    _exact(config, ReleaseIFConfiguration)
    _uint(config.max_samples, 32, positive=True)
    expected = ReleaseIFConfiguration(13 if view == 'current13' else 26,
        16, min(32, train_count) if train_count is not None else config.max_samples,
        1., False, 'auto', 42, 1)
    for field in fields(expected):
        _fixed(getattr(config, field.name), getattr(expected, field.name))


def _validate_context(context):
    _exact(context, ReleaseIFResultContext)
    for name, expected in (('profile_id', _P), ('result_profile_id', _R),
                            ('source_schema_id', _SOURCE)):
        _fixed(getattr(context, name), expected, 'INCOMPATIBLE_PACKAGE')
    _exact(context.view, str)
    _need(context.view in ('current13', 'h30_26'), 'INCOMPATIBLE_PACKAGE')
    for name, expected in (('source_authentication', _AUTH), ('time_basis', _TIME),
        ('policy_status', 'AUDIT_ONLY'), ('score_direction', 'NEGATIVE_SCORE_SAMPLES')):
        _fixed(getattr(context, name), expected)
    _exact(context.audit_fit_policy, str)
    _need(context.audit_fit_policy in ('P_U', 'P_B', 'P_A'), 'INVALID_PACKAGE')
    _identity(context.raw_identity, ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
    _identity(context.prepared_identity, ReleaseInputIdentity, 'c17-release-prepared-input-package-v1')
    _sha(context.configuration_sha256)
    _configuration(context.model_configuration, context.view)
    _uint(context.minute_count, 10000, positive=True)
    roles, eligible = _segments_axis(context.segments)
    _need(len(roles) == context.minute_count)
    _exact(context.calibration, ReleaseIFCalibration)
    for name, expected in (('quantile', .99), ('method', 'linear'), ('comparison', 'STRICT_GREATER')):
        _fixed(getattr(context.calibration, name), expected)
    return roles, eligible


def _indices(indices, n):
    _sequence(indices, tuple, n, positive=True)
    _need(all(type(i) is int for i in indices), 'INVALID_PACKAGE')
    _need(all(0 <= i < n for i in indices))
    _need(all(a < b for a, b in zip(indices, indices[1:])))


def _validate_result_storage(result):
    """Validate the saved result before any optional pair-number allocation."""
    _exact(result, ReleaseIFResult)
    _fixed(result.profile_id, _R, 'INCOMPATIBLE_PACKAGE')
    _exact(result.view, str)
    _need(result.view in ('current13', 'h30_26'), 'INCOMPATIBLE_PACKAGE')
    _identity(result.raw_identity, ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
    _identity(result.prepared_identity, ReleaseInputIdentity, 'c17-release-prepared-input-package-v1')
    _sha(result.configuration_sha256)
    # Bound every container before inspecting any of its entries.
    _sequence(result.scored_mask, tuple, 10000, positive=True)
    n = len(result.scored_mask)
    for vector in (result.scores, result.predictions, result.scored_mask):
        _sequence(vector, tuple, 10000, length=n)
    for indices in (result.train_indices, result.calibration_indices, result.preprocessing_fit_indices):
        _sequence(indices, tuple, n, positive=True)
    _exact(result.threshold, float)
    _need(math.isfinite(result.threshold), 'INVALID_PACKAGE')
    for score, prediction, scored in zip(result.scores, result.predictions, result.scored_mask):
        _exact(scored, bool)
        if score is not None:
            _exact(score, float)
            _need(math.isfinite(score), 'INVALID_PACKAGE')
        if prediction is not None:
            _exact(prediction, bool)
        if scored:
            _need(score is not None and prediction is not None)
            _need(prediction == (score > result.threshold))
        else:
            _need(score is None and prediction is None)
    for indices in (result.train_indices, result.calibration_indices, result.preprocessing_fit_indices):
        _indices(indices, n)
    train, calibration, fit = (set(indices) for indices in (result.train_indices,
        result.calibration_indices, result.preprocessing_fit_indices))
    _need(not train & calibration and train <= fit)
    _need(all(result.scored_mask[i] for i in train | calibration))
    _configuration(result.configuration, result.view, len(train))
    try:
        with np.errstate(over='raise', invalid='raise'):
            threshold = calibrate([result.scores[i] for i in result.calibration_indices])
        _need(type(threshold) is float and math.isfinite(threshold) and threshold == result.threshold)
    except (ValueError, FloatingPointError, OverflowError):
        raise ReleaseIFResultPackageError('INCONSISTENT_PACKAGE') from None


def _validate_result(result, context, roles, eligible):
    _validate_result_storage(result)
    for name in ('view', 'raw_identity', 'prepared_identity', 'configuration_sha256'):
        _need(getattr(result, name) == getattr(context, name))
    _need(len(result.scored_mask) == context.minute_count)
    _need(result.configuration == context.model_configuration)
    _need(all(not scored or allowed for scored, allowed in zip(result.scored_mask, eligible)))
    _need(all(roles[i] == 'train' and eligible[i] for i in result.preprocessing_fit_indices))
    _need(all(roles[i] == 'calibration' for i in result.calibration_indices))


def _context_document(context):
    document = _values(context)
    for name in ('raw_identity', 'prepared_identity', 'model_configuration', 'calibration'):
        document[name] = _values(getattr(context, name))
    document['segments'] = [dict(ordinal=i, id=s.id, role=s.role,
        start=s.start.isoformat(), end=s.end.isoformat()) for i, s in enumerate(context.segments)]
    return document


def _encode_content(context, result):
    roles, eligible = _validate_context(context)
    _validate_result(result, context, roles, eligible)
    document = _context_document(context)
    context_sha = hashlib.sha256(_canonical(document, 16384)).hexdigest()
    base = dict(schema_version=1, profile_id=_P, context_sha256=context_sha)
    encoded = []
    total = 0
    def append(name, value):
        nonlocal total
        payload = _canonical(value, min(_LIMITS[name], PACKAGE_TOTAL_BYTE_LIMIT - total))
        total += len(payload)
        encoded.append((name, payload))
        return payload
    payload = append('result.json', dict(base, **{name: getattr(result, name) for name in _RESULT_FIELDS}))
    manifest = append('manifest.json', dict(base, context=document, members={'result.json': _digest(payload)}))
    append('COMPLETE.json', dict(schema_version=1, profile_id=_P, status='COMPLETE', manifest=_digest(manifest)))
    identity = ReleaseIFResultIdentity(_P, context_sha, hashlib.sha256(manifest).hexdigest(), len(manifest))
    return tuple(encoded), identity


def encode_release_if_result_package(package: ReleaseIFResultPackage) -> tuple[tuple[str, bytes], ...]:
    """Revalidate objects and declarations before producing canonical bounded bytes."""
    _need(type(package) is ReleaseIFResultPackage, 'INVALID_PACKAGE_ARGUMENTS')
    _exact(package, ReleaseIFResultPackage)
    members, identity = _encode_content(package.context, package.result)
    _identity(package.identity, ReleaseIFResultIdentity, _P)
    _need(package.identity == identity, 'INTEGRITY_MISMATCH')
    _exact(package.load_report, ReleaseIFResultLoadReport)
    for field in fields(package.load_report):
        _fixed(getattr(package.load_report, field.name), getattr(_report(), field.name))
    return members


def _identity_from_document(document, kind, profile):
    _keys(document, _IDENTITY_FIELDS)
    # Check before constructing the upstream raw identity, whose constructor validates.
    _fixed(document['profile_id'], profile, 'INCOMPATIBLE_PACKAGE')
    _sha(document['context_sha256'])
    _sha(document['manifest_sha256'])
    _uint(document['manifest_byte_count'], 65536, positive=True)
    return kind(**document)


def _stamp(value):
    _exact(value, str)
    _need(_STAMP.fullmatch(value) is not None, 'INVALID_PACKAGE')
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ReleaseIFResultPackageError('INVALID_PACKAGE') from None


def _context_from_document(document):
    _keys(document, tuple(field.name for field in fields(ReleaseIFResultContext)))
    value = document.copy()
    value['raw_identity'] = _identity_from_document(value['raw_identity'],
        ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
    value['prepared_identity'] = _identity_from_document(value['prepared_identity'],
        ReleaseInputIdentity, 'c17-release-prepared-input-package-v1')
    _keys(value['model_configuration'], tuple(field.name for field in fields(ReleaseIFConfiguration)))
    value['model_configuration'] = ReleaseIFConfiguration(**value['model_configuration'])
    _keys(value['calibration'], ('quantile', 'method', 'comparison'))
    value['calibration'] = ReleaseIFCalibration(**value['calibration'])
    raw_segments = _sequence(value['segments'], list, 7, positive=True)
    segments = []
    for i, segment in enumerate(raw_segments):
        _keys(segment, ('ordinal', 'id', 'role', 'start', 'end'))
        _fixed(segment['ordinal'], i)
        segments.append(ReleaseSegment(segment['id'], segment['role'],
            _stamp(segment['start']), _stamp(segment['end'])))
    value['segments'] = tuple(segments)
    return ReleaseIFResultContext(**value)


def decode_release_if_result_package(members: dict[str, bytes]) -> ReleaseIFResultPackage:
    """Read three supplied payloads only; saved-score Q99 is checked, never fitted."""
    _need(type(members) is dict and len(members) == 3
        and all(type(k) is str for k in members) and set(members) == set(PACKAGE_MEMBER_NAMES)
        and all(type(v) is bytes for v in members.values()), 'INVALID_PACKAGE_ARGUMENTS')
    _need(all(len(members[name]) <= limit for name, limit in PACKAGE_MEMBER_BYTE_LIMITS)
        and sum(map(len, members.values())) <= PACKAGE_TOTAL_BYTE_LIMIT, 'RESOURCE_LIMIT')
    complete = _parse(members['COMPLETE.json'], _LIMITS['COMPLETE.json'])
    _header(complete, ('schema_version', 'profile_id', 'status', 'manifest'), bound=False)
    _fixed(complete['status'], 'COMPLETE', 'INVALID_PACKAGE')
    _binding(complete['manifest'], members['manifest.json'])
    manifest = _parse(members['manifest.json'], _LIMITS['manifest.json'])
    _header(manifest, ('schema_version', 'profile_id', 'context_sha256', 'context', 'members'))
    _keys(manifest['members'], ('result.json',))
    _binding(manifest['members']['result.json'], members['result.json'])
    context_sha = hashlib.sha256(_canonical(manifest['context'], 16384)).hexdigest()
    _need(context_sha == manifest['context_sha256'], 'INTEGRITY_MISMATCH')
    context = _context_from_document(manifest['context'])
    roles, eligible = _validate_context(context)
    document = _parse(members['result.json'], _LIMITS['result.json'])
    _header(document, ('schema_version', 'profile_id', 'context_sha256', *_RESULT_FIELDS))
    _need(document['context_sha256'] == context_sha, 'INTEGRITY_MISMATCH')
    n = context.minute_count
    for name in ('scores', 'predictions', 'scored_mask'):
        _sequence(document[name], list, 10000, length=n)
    for name in ('train_indices', 'calibration_indices', 'preprocessing_fit_indices'):
        _sequence(document[name], list, n, positive=True)
    result = ReleaseIFResult(_R, context.view, context.raw_identity, context.prepared_identity,
        context.configuration_sha256, tuple(document['scores']), tuple(document['predictions']),
        tuple(document['scored_mask']), document['threshold'], tuple(document['train_indices']),
        tuple(document['calibration_indices']), tuple(document['preprocessing_fit_indices']),
        context.model_configuration)
    _validate_result(result, context, roles, eligible)
    identity = ReleaseIFResultIdentity(_P, context_sha,
        hashlib.sha256(members['manifest.json']).hexdigest(), len(members['manifest.json']))
    return ReleaseIFResultPackage(identity, context, result, _report())


def _pair_inputs(pair, view):
    try:
        return _validated_inputs(pair, view)
    except ReleaseIFError as exc:
        raise ReleaseIFResultPackageError('RESOURCE_LIMIT' if exc.code == 'RESOURCE_LIMIT'
                                         else 'INVALID_PACKAGE') from None


def _bind(context, result, pair, inputs):
    expected = dict(raw_identity=pair.raw_identity, prepared_identity=pair.prepared_identity,
        configuration_sha256=pair.configuration_sha256, source_schema_id=pair.source_schema_id,
        source_authentication=pair.source_authentication, time_basis=pair.time_basis,
        policy_status=pair.configuration.policy_status, audit_fit_policy=pair.configuration.audit_fit_policy,
        segments=pair.segments, minute_count=len(pair.prepared_minutes.timestamps))
    for name, value in expected.items():
        _need(getattr(context, name) == value, 'INPUT_BINDING_MISMATCH')
    for actual, expected_value in ((result.scored_mask, pair.prepared_minutes.common_valid),
            (result.train_indices, inputs.train_indices),
            (result.calibration_indices, inputs.calibration_indices),
            (result.preprocessing_fit_indices, inputs.preprocessing_fit_indices)):
        _need(actual == expected_value, 'INPUT_BINDING_MISMATCH')


def make_release_if_result_package(pair: ReleaseModelInputPair, result: ReleaseIFResult) -> ReleaseIFResultPackage:
    """Bind a saved result to explicit validated input declarations, without I/O."""
    _validate_result_storage(result)
    inputs = _pair_inputs(pair, result.view)
    context = ReleaseIFResultContext(_P, _R, result.view, pair.source_schema_id,
        pair.source_authentication, pair.time_basis, pair.configuration.policy_status,
        pair.configuration.audit_fit_policy, result.raw_identity, result.prepared_identity,
        result.configuration_sha256, result.configuration, pair.segments,
        len(pair.prepared_minutes.timestamps), 'NEGATIVE_SCORE_SAMPLES',
        ReleaseIFCalibration(.99, 'linear', 'STRICT_GREATER'))
    _bind(context, result, pair, inputs)
    _, identity = _encode_content(context, result)
    return ReleaseIFResultPackage(identity, context, result, _report())


def verify_release_if_result_pair(package: ReleaseIFResultPackage, pair: ReleaseModelInputPair) -> None:
    """Check codec consistency then explicit input declarations; no source authentication."""
    encode_release_if_result_package(package)
    inputs = _pair_inputs(pair, package.context.view)
    _bind(package.context, package.result, pair, inputs)
