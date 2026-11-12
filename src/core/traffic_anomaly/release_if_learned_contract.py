"""Bounded learned declarations and P1 composition; no numerical dependencies.

These bytes establish internal consistency, not source or model authentication.
Topology and numeric-state syntax remain the accepted P1 codec's responsibility.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from functools import wraps
import hashlib
import json
import math
import re

from .iforest_numeric_state import (
    IForestNumericState, IForestNumericStateError,
    encode_iforest_numeric_state, decode_iforest_numeric_state,
)

LEARNED_PACKAGE_PROFILE_ID = 'c17-release-iforest-learned-package-v1'
LEARNED_FIT_RUNTIME_ID = 'python314-numpy254-sklearn191-joblib160-serial-wm1024-v1'
PACKAGE_MEMBER_NAMES = ('numeric-state.json', 'manifest.json', 'COMPLETE.json')
PACKAGE_MEMBER_BYTE_LIMITS = tuple(zip(PACKAGE_MEMBER_NAMES, (262144, 8192, 4096)))
PACKAGE_TOTAL_BYTE_LIMIT = 274432
_LIMITS = dict(PACKAGE_MEMBER_BYTE_LIMITS)
_INPUT_RULES = 'c17-release-log1p-mad-input-rules-v1'
_REFERENCE_PROFILES = ('c17-release-minute-package-v1',
    'c17-release-prepared-input-package-v1', 'c17-release-iforest-result-package-v1')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_FEATURE_NAMES = ('completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
    'duration_p95_s', 'no_backward_packet_source_record_count')
_CODES = frozenset(('INVALID_LEARNED_ARGUMENTS', 'INVALID_LEARNED_PACKAGE',
    'INCOMPATIBLE_LEARNED_PACKAGE', 'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH',
    'INPUT_BINDING_MISMATCH', 'NO_TRAINING_NORMAL', 'NO_CALIBRATION_NORMAL',
    'INVALID_INPUT_NUMERIC', 'MODEL_UNAVAILABLE', 'MODEL_ERROR', 'INVALID_MODEL_STATE',
    'INVALID_MODEL_SCORES', 'SCORE_MISMATCH', 'CALIBRATION_MISMATCH',
    'PREDICTION_MISMATCH', 'INCOMPATIBLE_RUNTIME', 'INVALID_PACKAGE_PATH',
    'INPUT_UNAVAILABLE', 'OUTPUT_EXISTS', 'PACKAGE_CHANGED', 'OUTPUT_ERROR', 'LEARNED_ERROR'))


class ReleaseIFLearnedError(ValueError):
    """A finite code only; never foreign exception details or declarations."""

    def __init__(self, code: str):
        self.code = code if type(code) is str and code in _CODES else 'LEARNED_ERROR'
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class ReleaseIFLearnedReference:
    profile_id: str
    context_sha256: str
    manifest_sha256: str
    manifest_byte_count: int


@dataclass(frozen=True, slots=True)
class ReleaseIFLearnedConfiguration:
    input_width: int
    n_estimators: int
    max_samples: int
    max_features: float
    bootstrap: bool
    contamination: str
    random_state: int
    n_jobs: int


@dataclass(frozen=True, slots=True)
class ReleaseIFLearnedContext:
    profile_id: str
    view: str
    raw_identity: ReleaseIFLearnedReference
    prepared_identity: ReleaseIFLearnedReference
    result_identity: ReleaseIFLearnedReference
    configuration_sha256: str
    minute_count: int
    train_count: int
    calibration_count: int
    preprocessing_fit_count: int
    population_sha256: str
    input_rules_id: str
    feature_columns: tuple[str, ...]
    model_configuration: ReleaseIFLearnedConfiguration
    fit_runtime_id: str


@dataclass(frozen=True, slots=True)
class ReleaseIFLearnedLoadReport:
    profile_id: str
    scope: str
    byte_integrity: str
    structure: str
    numerical_replay: str
    source_authentication: str
    model_origin: str


@dataclass(frozen=True, slots=True)
class ReleaseIFLearnedPackage:
    identity: ReleaseIFLearnedReference
    context: ReleaseIFLearnedContext
    state: IForestNumericState
    load_report: ReleaseIFLearnedLoadReport


def _fail(code):
    raise ReleaseIFLearnedError(code) from None


def _need(condition, code='INVALID_LEARNED_PACKAGE'):
    if not condition:
        _fail(code)


def _safe(function):
    @wraps(function)
    def boundary(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MemoryError:
            raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
        except Exception as error:
            if type(error) is ReleaseIFLearnedError:
                raise
            if type(error) is IForestNumericStateError:
                code = {'RESOURCE_LIMIT': 'RESOURCE_LIMIT',
                    'INCOMPATIBLE_STATE': 'INCOMPATIBLE_LEARNED_PACKAGE',
                    'INVALID_STATE_ARGUMENTS': 'INVALID_LEARNED_PACKAGE',
                    'INVALID_STATE': 'INVALID_LEARNED_PACKAGE'}.get(error.code, 'LEARNED_ERROR')
                raise ReleaseIFLearnedError(code) from None
            raise ReleaseIFLearnedError('LEARNED_ERROR') from None
    return boundary


def _exact(value, kind):
    _need(type(value) is kind)
    if hasattr(kind, '__dataclass_fields__'):
        try:
            for field in fields(kind):
                object.__getattribute__(value, field.name)
        except AttributeError:
            _fail('INVALID_LEARNED_PACKAGE')


def _keys(value, names):
    _exact(value, dict)
    _need(len(value) == len(names) and all(type(key) is str for key in value)
        and value.keys() == set(names))


def _sha(value):
    _exact(value, str)
    _need(_SHA.fullmatch(value) is not None)


def _reference_shape(reference):
    _exact(reference, ReleaseIFLearnedReference)
    for name in ('profile_id', 'context_sha256', 'manifest_sha256'):
        _exact(getattr(reference, name), str)
    _exact(reference.manifest_byte_count, int)


def _reference_values(reference, cap):
    _need(reference.manifest_byte_count <= cap, 'RESOURCE_LIMIT')
    _need(reference.manifest_byte_count > 0)
    _sha(reference.context_sha256)
    _sha(reference.manifest_sha256)


@_safe
def _feature_columns(view: str) -> tuple[str, ...]:
    _exact(view, str)
    _need(view in ('current13', 'h30_26'), 'INCOMPATIBLE_LEARNED_PACKAGE')
    current = tuple('current:' + name for name in _FEATURE_NAMES)
    return current if view == 'current13' else current + tuple(
        'residual_h30:' + name for name in _FEATURE_NAMES)


def _validate_context(context, *, feature_kind=tuple):
    _exact(context, ReleaseIFLearnedContext)
    for name in ('profile_id', 'view', 'configuration_sha256', 'population_sha256',
            'input_rules_id', 'fit_runtime_id'):
        _exact(getattr(context, name), str)
    counts = (context.minute_count, context.train_count, context.calibration_count,
        context.preprocessing_fit_count)
    for value in counts:
        _exact(value, int)
    _exact(context.feature_columns, feature_kind)
    references = (context.raw_identity, context.prepared_identity, context.result_identity)
    for reference in references:
        _reference_shape(reference)
    config = context.model_configuration
    _exact(config, ReleaseIFLearnedConfiguration)
    for name, kind in (('input_width', int), ('n_estimators', int), ('max_samples', int),
            ('max_features', float), ('bootstrap', bool), ('contamination', str),
            ('random_state', int), ('n_jobs', int)):
        _exact(getattr(config, name), kind)
    # All sibling caps precede feature-element traversal and fixed declarations.
    _need(all(value <= 10000 for value in counts) and len(context.feature_columns) <= 26
        and config.max_samples <= 32
        and all(reference.manifest_byte_count <= 65536 for reference in references), 'RESOURCE_LIMIT')
    _need(all(value > 0 for value in counts) and config.max_samples > 0
        and math.isfinite(config.max_features))
    for reference in references:
        _reference_values(reference, 65536)
    _sha(context.configuration_sha256)
    _sha(context.population_sha256)
    for column in context.feature_columns:
        _exact(column, str)
    _need(context.profile_id == LEARNED_PACKAGE_PROFILE_ID
        and context.view in ('current13', 'h30_26')
        and context.input_rules_id == _INPUT_RULES
        and context.fit_runtime_id == LEARNED_FIT_RUNTIME_ID, 'INCOMPATIBLE_LEARNED_PACKAGE')
    for reference, profile in zip(references, _REFERENCE_PROFILES):
        _need(reference.profile_id == profile, 'INCOMPATIBLE_LEARNED_PACKAGE')
    width = 13 if context.view == 'current13' else 26
    _need(tuple(context.feature_columns) == _feature_columns(context.view), 'INCOMPATIBLE_LEARNED_PACKAGE')
    _need((config.input_width, config.n_estimators, config.max_features, config.bootstrap,
        config.contamination, config.random_state, config.n_jobs)
        == (width, 16, 1., False, 'auto', 42, 1), 'INCOMPATIBLE_LEARNED_PACKAGE')
    _need(context.train_count <= context.preprocessing_fit_count <= context.minute_count
        and context.calibration_count <= context.minute_count
        and context.train_count + context.calibration_count <= context.minute_count
        and config.max_samples == min(32, context.train_count), 'INPUT_BINDING_MISMATCH')


def _projection(value):
    # Called only after the exact dataclass and every required slot are validated.
    return {field.name: getattr(value, field.name) for field in fields(type(value))}


def _context_projection(context):
    value = _projection(context)
    for name in ('raw_identity', 'prepared_identity', 'result_identity', 'model_configuration'):
        value[name] = _projection(value[name])
    value['feature_columns'] = list(context.feature_columns)
    return value


def _canonical(value, limit, *, limit_error='RESOURCE_LIMIT'):
    output = bytearray()
    for chunk in json.JSONEncoder(ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False).iterencode(value):
        encoded = chunk.encode('utf-8')
        _need(len(output) + len(encoded) + 1 <= limit, limit_error)
        output.extend(encoded)
    return bytes(output) + b'\n'


def _digest(payload):
    return {'byte_count': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


def _report():
    return ReleaseIFLearnedLoadReport(LEARNED_PACKAGE_PROFILE_ID,
        'SAVED_LEARNED_INTERNAL_CONSISTENCY_ONLY', 'MATCHED', 'MATCHED', 'NOT_RUN',
        'NOT_AUTHENTICATED', 'NOT_AUTHENTICATED')


def _state_binding(context, state):
    # Both exact state and its numeric invariants have already passed P1.
    _need(state.input_width == context.model_configuration.input_width
        and state.max_samples == context.model_configuration.max_samples, 'INPUT_BINDING_MISMATCH')


def _encode_content(context, state):
    _validate_context(context)
    state_bytes = encode_iforest_numeric_state(state)
    _state_binding(context, state)
    context_document = _context_projection(context)
    context_bytes = _canonical(context_document, 4096)
    context_sha = hashlib.sha256(context_bytes).hexdigest()
    manifest_bytes = _canonical({'schema_version': 1, 'profile_id': LEARNED_PACKAGE_PROFILE_ID,
        'context_sha256': context_sha, 'context': context_document,
        'members': {'numeric-state.json': _digest(state_bytes)}}, 8192)
    complete_bytes = _canonical({'schema_version': 1, 'profile_id': LEARNED_PACKAGE_PROFILE_ID,
        'status': 'COMPLETE', 'manifest': _digest(manifest_bytes)}, 4096)
    members = tuple(zip(PACKAGE_MEMBER_NAMES, (state_bytes, manifest_bytes, complete_bytes)))
    _need(sum(len(payload) for _, payload in members) <= PACKAGE_TOTAL_BYTE_LIMIT, 'RESOURCE_LIMIT')
    identity = ReleaseIFLearnedReference(LEARNED_PACKAGE_PROFILE_ID, context_sha,
        hashlib.sha256(manifest_bytes).hexdigest(), len(manifest_bytes))
    return members, identity


@_safe
def _make_release_if_learned_package(
    context: ReleaseIFLearnedContext, state: IForestNumericState,
) -> ReleaseIFLearnedPackage:
    _, identity = _encode_content(context, state)
    return ReleaseIFLearnedPackage(identity, context, state, _report())


@_safe
def encode_release_if_learned_package(
    package: ReleaseIFLearnedPackage,
) -> tuple[tuple[str, bytes], ...]:
    _need(type(package) is ReleaseIFLearnedPackage, 'INVALID_LEARNED_ARGUMENTS')
    _exact(package, ReleaseIFLearnedPackage)
    members, identity = _encode_content(package.context, package.state)
    _reference_shape(package.identity)
    _reference_values(package.identity, 8192)
    _exact(package.load_report, ReleaseIFLearnedLoadReport)
    for field in fields(ReleaseIFLearnedLoadReport):
        _exact(getattr(package.load_report, field.name), str)
    _need(package.identity == identity and package.load_report == _report(), 'INTEGRITY_MISMATCH')
    return members


def _object(pairs):
    value = {}
    for key, item in pairs:
        _need(key not in value)
        value[key] = item
    return value


def _integer(token):
    _need(len(token) <= 8)
    return int(token)


def _floating(token):
    _need(len(token) <= 32)
    value = float(token)
    _need(math.isfinite(value))
    return value


def _constant(_token):
    _fail('INVALID_LEARNED_PACKAGE')


def _parse(payload, limit):
    try:
        value = json.loads(payload.decode('utf-8'), object_pairs_hook=_object,
            parse_int=_integer, parse_float=_floating, parse_constant=_constant)
        _need(_canonical(value, limit, limit_error='INVALID_LEARNED_PACKAGE') == payload)
        return value
    except Exception as error:
        if type(error) in (json.JSONDecodeError, UnicodeDecodeError, UnicodeEncodeError,
                RecursionError, OverflowError):
            _fail('INVALID_LEARNED_PACKAGE')
        raise


def _header(value, names):
    _keys(value, names)
    _exact(value['schema_version'], int)
    _exact(value['profile_id'], str)
    _need(value['schema_version'] == 1 and value['profile_id'] == LEARNED_PACKAGE_PROFILE_ID,
        'INCOMPATIBLE_LEARNED_PACKAGE')


def _binding(reference, payload, limit):
    _keys(reference, ('byte_count', 'sha256'))
    _exact(reference['byte_count'], int)
    _need(reference['byte_count'] <= limit, 'RESOURCE_LIMIT')
    _need(reference['byte_count'] > 0)
    _sha(reference['sha256'])
    _need(reference == _digest(payload), 'INTEGRITY_MISMATCH')


def _context_from_document(value):
    _keys(value, tuple(field.name for field in fields(ReleaseIFLearnedContext)))
    for name in ('raw_identity', 'prepared_identity', 'result_identity'):
        _keys(value[name], tuple(field.name for field in fields(ReleaseIFLearnedReference)))
    _keys(value['model_configuration'], tuple(field.name for field in fields(ReleaseIFLearnedConfiguration)))
    projected = value.copy()
    for name in ('raw_identity', 'prepared_identity', 'result_identity'):
        projected[name] = ReleaseIFLearnedReference(**value[name])
    projected['model_configuration'] = ReleaseIFLearnedConfiguration(**value['model_configuration'])
    context = ReleaseIFLearnedContext(**projected)
    # JSON's list representation follows the same shape/cap/primitive/fixed order
    # as typed context, before allocating its bounded immutable projection.
    _validate_context(context, feature_kind=list)
    projected['feature_columns'] = tuple(context.feature_columns)
    return ReleaseIFLearnedContext(**projected)


@_safe
def decode_release_if_learned_package(
    members: dict[str, bytes],
) -> ReleaseIFLearnedPackage:
    _need(type(members) is dict and len(members) == 3
        and all(type(key) is str for key in members) and members.keys() == set(PACKAGE_MEMBER_NAMES)
        and all(type(value) is bytes for value in members.values()), 'INVALID_LEARNED_ARGUMENTS')
    _need(all(len(members[name]) <= limit for name, limit in PACKAGE_MEMBER_BYTE_LIMITS)
        and sum(len(value) for value in members.values()) <= PACKAGE_TOTAL_BYTE_LIMIT, 'RESOURCE_LIMIT')
    complete = _parse(members['COMPLETE.json'], 4096)
    _header(complete, ('schema_version', 'profile_id', 'status', 'manifest'))
    _exact(complete['status'], str)
    _need(complete['status'] == 'COMPLETE')
    _binding(complete['manifest'], members['manifest.json'], 8192)
    manifest = _parse(members['manifest.json'], 8192)
    _header(manifest, ('schema_version', 'profile_id', 'context_sha256', 'context', 'members'))
    _sha(manifest['context_sha256'])
    _keys(manifest['members'], ('numeric-state.json',))
    _binding(manifest['members']['numeric-state.json'], members['numeric-state.json'], 262144)
    context_bytes = _canonical(manifest['context'], 4096)
    _need(hashlib.sha256(context_bytes).hexdigest() == manifest['context_sha256'], 'INTEGRITY_MISMATCH')
    context = _context_from_document(manifest['context'])
    state = decode_iforest_numeric_state(members['numeric-state.json'])
    _state_binding(context, state)
    identity = ReleaseIFLearnedReference(LEARNED_PACKAGE_PROFILE_ID, manifest['context_sha256'],
        hashlib.sha256(members['manifest.json']).hexdigest(), len(members['manifest.json']))
    return ReleaseIFLearnedPackage(identity, context, state, _report())


@_safe
def _population_sha256(*, minute_count: int, scored_mask: tuple[bool, ...],
    train_indices: tuple[int, ...], calibration_indices: tuple[int, ...],
    preprocessing_fit_indices: tuple[int, ...]) -> str:
    _exact(minute_count, int)
    sequences = (scored_mask, train_indices, calibration_indices, preprocessing_fit_indices)
    for sequence in sequences:
        _exact(sequence, tuple)
    _need(minute_count <= 10000, 'RESOURCE_LIMIT')
    _need(minute_count > 0)
    _need(all(len(sequence) <= minute_count for sequence in sequences), 'RESOURCE_LIMIT')
    _need(len(scored_mask) == minute_count and all(type(value) is bool for value in scored_mask))
    populations = sequences[1:]
    for indices in populations:
        _need(bool(indices))
        previous = -1
        for index in indices:
            _exact(index, int)
            _need(previous < index < minute_count)
            previous = index
    train, calibration, preprocessing = (set(indices) for indices in populations)
    _need(not train.intersection(calibration) and train.issubset(preprocessing)
        and all(scored_mask[index] for index in train_indices + calibration_indices),
        'INPUT_BINDING_MISMATCH')
    document = {'schema_version': 1, 'minute_count': minute_count,
        'scored_mask': list(scored_mask), 'train_indices': list(train_indices),
        'calibration_indices': list(calibration_indices),
        'preprocessing_fit_indices': list(preprocessing_fit_indices)}
    return hashlib.sha256(_canonical(document, 262144)).hexdigest()
