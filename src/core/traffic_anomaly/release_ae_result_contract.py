"""Bounded AE result declarations; consistency does not authenticate execution.

Import is standard-library-only. Public numerical validation lazily checks the
saved scores with NumPy Q99; it never loads Torch, a model, inputs or weights.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
import hashlib
import json
import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .release_autoencoder import ReleaseAEResult
    from .release_minute_contract import ReleaseMinutePackageIdentity
    from .release_inputs import ReleaseInputIdentity
    from ._release_minutes import ReleaseSegment


PACKAGE_MEMBER_NAMES = ('result.json', 'manifest.json', 'COMPLETE.json')
PACKAGE_MEMBER_BYTE_LIMITS = tuple(zip(PACKAGE_MEMBER_NAMES, (2097152, 65536, 4096)))
PACKAGE_TOTAL_BYTE_LIMIT = 2166784
_LIMITS = dict(PACKAGE_MEMBER_BYTE_LIMITS)
_P = 'c17-release-ae-result-package-v1'
_R = 'c17-release-ae-engineering-v1'
_RAW = 'c17-release-minute-package-v1'
_PREPARED = 'c17-release-prepared-input-package-v1'
_RESULT_SCOPE = 'IN_MEMORY_ENGINEERING_NUMERICAL_RESULT_ONLY'
_CODES = frozenset((
    'INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE',
    'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE',
    'INVALID_PACKAGE_PATH', 'INPUT_UNAVAILABLE', 'OUTPUT_EXISTS',
    'PACKAGE_CHANGED', 'OUTPUT_ERROR', 'INPUT_BINDING_MISMATCH',
    'NUMERICAL_DEPENDENCY_UNAVAILABLE', 'INCOMPATIBLE_RUNTIME', 'PACKAGE_ERROR',
))
_IDENTITY = ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')
_RESULT = (
    'profile_id', 'scope', 'view', 'raw_identity', 'prepared_identity',
    'configuration_sha256', 'feature_columns', 'scores', 'predictions', 'scored_mask',
    'current_reconstruction_mse', 'history_deviation_reconstruction_mse', 'threshold',
    'train_indices', 'calibration_indices', 'preprocessing_fit_indices',
    'training_losses', 'configuration', 'calibration', 'runtime',
)
_CONFIGURATION = (
    'model_profile_id', 'parameter_status', 'method', 'input_width', 'history_window',
    'architecture', 'parameter_count', 'activation', 'device', 'training_dtype',
    'score_dtype', 'score_rule', 'epochs', 'batch_strategy', 'shuffle', 'optimizer',
    'optimizer_cpu_guard', 'optimizer_healthcheck_api', 'learning_rate', 'adam_betas',
    'adam_epsilon', 'weight_decay', 'amsgrad', 'random_state', 'fit_scope',
    'calibration_scope', 'quantile', 'quantile_method', 'alarm_comparison',
    'preprocessing_fit_provenance',
)
_CALIBRATION = ('quantile', 'method', 'comparison', 'sample_count', 'equal_count', 'strictly_above_count')
_RUNTIME = ('python_version', 'numpy_version', 'torch_version', 'device',
            'torch_num_threads', 'torch_num_interop_threads')
_CONTEXT = ('profile_id', 'result_profile_id', 'view', 'raw_identity', 'prepared_identity',
            'configuration_sha256', 'source_schema_id', 'source_authentication',
            'time_basis', 'policy_status', 'audit_fit_policy', 'segments',
            'minute_count', 'score_direction')
_VECTORS = ('scores', 'predictions', 'scored_mask', 'current_reconstruction_mse',
            'history_deviation_reconstruction_mse')
_INDICES = ('train_indices', 'calibration_indices', 'preprocessing_fit_indices')
_G13 = ('completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
    'duration_p95_s', 'no_backward_packet_source_record_count')
_ROLES = ('train', 'validation', 'calibration', 'test')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_STAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00\Z')


class ReleaseAEResultPackageError(ValueError):
    """Only a finite native code can enter the public error text."""

    def __init__(self, code):
        safe_code = code if type(code) is str and code in _CODES else 'PACKAGE_ERROR'
        self.code = safe_code
        super().__init__(safe_code)


@dataclass(frozen=True, slots=True)
class ReleaseAEResultIdentity:
    profile_id: str
    context_sha256: str
    manifest_sha256: str
    manifest_byte_count: int


@dataclass(frozen=True, slots=True)
class ReleaseAEResultDeclarations:
    raw_identity: ReleaseMinutePackageIdentity
    prepared_identity: ReleaseInputIdentity
    configuration_sha256: str
    source_schema_id: str
    source_authentication: str
    time_basis: str
    policy_status: str
    audit_fit_policy: str
    segments: tuple[ReleaseSegment, ...]
    minute_count: int


@dataclass(frozen=True, slots=True)
class ReleaseAEResultContext:
    profile_id: str
    result_profile_id: str
    view: str
    raw_identity: ReleaseMinutePackageIdentity
    prepared_identity: ReleaseInputIdentity
    configuration_sha256: str
    source_schema_id: str
    source_authentication: str
    time_basis: str
    policy_status: str
    audit_fit_policy: str
    segments: tuple[ReleaseSegment, ...]
    minute_count: int
    score_direction: str


@dataclass(frozen=True, slots=True)
class ReleaseAEResultLoadReport:
    profile_id: str
    scope: str
    byte_integrity: str
    structure: str
    saved_score_q99: str
    input_declaration_binding: str
    input_pair_binding: str
    derivation_replay: str
    source_authentication: str
    model_execution: str


@dataclass(frozen=True, slots=True)
class ReleaseAEResultPackage:
    identity: ReleaseAEResultIdentity
    context: ReleaseAEResultContext
    result: ReleaseAEResult
    load_report: ReleaseAEResultLoadReport


def _need(condition, code='INCONSISTENT_PACKAGE'):
    if not condition:
        raise ReleaseAEResultPackageError(code) from None


def _access_failure(error):
    kind = type(error)
    if issubclass(kind, (KeyboardInterrupt, SystemExit)):
        raise error from None
    code = 'RESOURCE_LIMIT' if issubclass(kind, MemoryError) else 'PACKAGE_ERROR'
    raise ReleaseAEResultPackageError(code) from None


def _raise_safe(error):
    """Classify actual types; never ask a foreign error for __class__/code."""
    kind = type(error)
    if issubclass(kind, (KeyboardInterrupt, SystemExit, MemoryError)):
        _access_failure(error)
    if kind is ReleaseAEResultPackageError:
        try:
            code = error.code
        except BaseException as failure:
            _access_failure(failure)
        code = code if type(code) is str and code in _CODES else 'PACKAGE_ERROR'
    elif kind is ModuleNotFoundError:
        try:
            name = error.name
        except BaseException as failure:
            _access_failure(failure)
        code = ('NUMERICAL_DEPENDENCY_UNAVAILABLE'
                if type(name) is str and name == 'numpy' else 'PACKAGE_ERROR')
    else:
        code = 'PACKAGE_ERROR'
    raise ReleaseAEResultPackageError(code) from None


def _exact(value, kind):
    _need(type(value) is kind, 'INVALID_PACKAGE')


def _keys(value, names):
    _exact(value, dict)
    _need(len(value) == len(names) and all(type(k) is str for k in value)
          and set(value) == set(names), 'INVALID_PACKAGE')


def _sequence(value, kind, maximum, *, length=None, positive=False):
    _exact(value, kind)
    _need(len(value) <= maximum, 'RESOURCE_LIMIT')
    if positive:
        _need(bool(value))
    if length is not None:
        _need(len(value) == length)
    return value


def _text(value, maximum=256):
    _exact(value, str)
    _need(len(value) <= maximum, 'RESOURCE_LIMIT')
    _need(not any(0xD800 <= ord(c) <= 0xDFFF for c in value), 'INVALID_PACKAGE')
    return value


def _uint(value, maximum, *, positive=False):
    _exact(value, int)
    _need(value >= int(positive), 'INVALID_PACKAGE')
    _need(value <= maximum, 'RESOURCE_LIMIT')
    return value


def _float(value):
    _exact(value, float)
    _need(math.isfinite(value) and value >= 0., 'INVALID_PACKAGE')
    return value


def _sha(value):
    _text(value)
    _need(_SHA.fullmatch(value) is not None, 'INVALID_PACKAGE')


def _fixed(value, expected, code='INCONSISTENT_PACKAGE'):
    if type(expected) is str:
        _text(value)
    else:
        _exact(value, type(expected))
    _need(value == expected, code)


def _view(value):
    _text(value)
    _need(value in ('current13', 'h30_26'), 'INCOMPATIBLE_PACKAGE')


def _reference(value, profile):
    _keys(value, _IDENTITY)
    _fixed(value['profile_id'], profile, 'INCOMPATIBLE_PACKAGE')
    _sha(value['context_sha256'])
    _sha(value['manifest_sha256'])
    _uint(value['manifest_byte_count'], 65536, positive=True)


def _holder(value, kind):
    _exact(value, kind)
    result = {}
    for field in fields(kind):
        try:
            result[field.name] = object.__getattribute__(value, field.name)
        except AttributeError:
            raise ReleaseAEResultPackageError('INVALID_PACKAGE') from None
    return result


def _data_types():
    # Frozen declarations only. No producer operation or context admission call.
    from .release_autoencoder import (
        ReleaseAEResult, ReleaseAEConfiguration, ReleaseAECalibration, ReleaseAERuntime)
    from .release_minute_contract import ReleaseMinutePackageIdentity
    from .release_inputs import ReleaseInputIdentity
    from ._release_minutes import ReleaseSegment
    return (ReleaseAEResult, ReleaseAEConfiguration, ReleaseAECalibration,
            ReleaseAERuntime, ReleaseMinutePackageIdentity, ReleaseInputIdentity, ReleaseSegment)


def _native_result(result):
    result_type, config_type, calibration_type, runtime_type, raw_type, prepared_type, _ = _data_types()
    doc = _holder(result, result_type)
    for name in (*_VECTORS, *_INDICES, 'training_losses', 'feature_columns'):
        maximum = 26 if name == 'feature_columns' else 10000
        doc[name] = list(_sequence(doc[name], tuple, maximum))
    doc['raw_identity'] = _holder(doc['raw_identity'], raw_type)
    doc['prepared_identity'] = _holder(doc['prepared_identity'], prepared_type)
    config = _holder(doc['configuration'], config_type)
    config['architecture'] = list(_sequence(config['architecture'], tuple, 5))
    config['adam_betas'] = list(_sequence(config['adam_betas'], tuple, 2))
    doc['configuration'] = config
    doc['calibration'] = _holder(doc['calibration'], calibration_type)
    doc['runtime'] = _holder(doc['runtime'], runtime_type)
    return doc


def _native_context(context):
    _, _, _, _, raw_type, prepared_type, segment_type = _data_types()
    doc = _holder(context, ReleaseAEResultContext)
    _uint(doc['minute_count'], 10000, positive=True)
    doc['raw_identity'] = _holder(doc['raw_identity'], raw_type)
    doc['prepared_identity'] = _holder(doc['prepared_identity'], prepared_type)
    segments = _sequence(doc['segments'], tuple, 7, positive=True)
    encoded = []
    for i, segment in enumerate(segments):
        values = _holder(segment, segment_type)
        for key in ('start', 'end'):
            stamp = values[key]
            _exact(stamp, datetime)
            _need(stamp.tzinfo is None and stamp.second == stamp.microsecond == 0, 'INVALID_PACKAGE')
            values[key] = stamp.isoformat(timespec='seconds')
        encoded.append(dict(ordinal=i, **values))
    doc['segments'] = encoded
    return doc


def _same_profile(actual, expected):
    if expected is None:
        _need(actual is None or type(actual) is int, 'INVALID_PACKAGE')
        _need(actual is None)
    elif type(expected) is dict:
        _keys(actual, tuple(expected))
        for name in expected:
            _same_profile(actual[name], expected[name])
    elif type(expected) is list:
        _sequence(actual, list, len(expected), length=len(expected))
        for left, right in zip(actual, expected):
            _same_profile(left, right)
    else:
        _exact(actual, type(expected))
        if type(expected) is float:
            _need(math.isfinite(actual) and actual.hex() == expected.hex())
        else:
            if type(expected) is str:
                _text(actual)
            _need(actual == expected)


def _configuration(doc, view):
    _keys(doc, _CONFIGURATION)
    from .candidate_ae_profiles import resolve_candidate_ae_configuration, MODEL_PROFILE_ID
    expected = resolve_candidate_ae_configuration('current_ae' if view == 'current13' else 'history_ae',
        None if view == 'current13' else 30, model_profile_id=MODEL_PROFILE_ID)
    _same_profile(doc, expected)


def _indices(values, n):
    _sequence(values, list, n, positive=True)
    previous = -1
    for value in values:
        _exact(value, int)
        _need(0 <= value < n and previous < value)
        previous = value


def _validate_projection(doc):
    """Only local data: no role, clock or reset certificate is fabricated."""
    _keys(doc, _RESULT)
    scores = _sequence(doc['scores'], list, 10000, positive=True)
    n = len(scores)
    for name in _VECTORS:
        _sequence(doc[name], list, 10000, length=n)
    _fixed(doc['profile_id'], _R, 'INCOMPATIBLE_PACKAGE')
    _fixed(doc['scope'], _RESULT_SCOPE)
    _view(doc['view'])
    _reference(doc['raw_identity'], _RAW)
    _reference(doc['prepared_identity'], _PREPARED)
    _sha(doc['configuration_sha256'])
    _configuration(doc['configuration'], doc['view'])
    columns = ['current:' + name for name in _G13]
    if doc['view'] == 'h30_26':
        columns += ['residual_h30:' + name for name in _G13]
    _sequence(doc['feature_columns'], list, 26, length=len(columns))
    for column, expected in zip(doc['feature_columns'], columns):
        _fixed(column, expected)
    _sequence(doc['training_losses'], list, 10000, length=5)
    for loss in doc['training_losses']:
        _float(loss)
    _float(doc['threshold'])
    for name in _INDICES:
        _indices(doc[name], n)
    train, calibration, preprocessing = (doc[k] for k in _INDICES)
    _need(set(train).isdisjoint(calibration) and set(train) <= set(preprocessing))
    mask = doc['scored_mask']
    for i in range(n):
        _exact(mask[i], bool)
        score, prediction, current, history = (doc[k][i] for k in
            ('scores', 'predictions', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse'))
        if not mask[i]:
            _need(score is prediction is current is history is None)
            continue
        _need(score is not None)
        _float(score)
        _float(current)
        _exact(prediction, bool)
        if doc['view'] == 'current13':
            _need(history is None)
            combined = current
        else:
            _float(history)
            combined = .5 * current + .5 * history
        _need(score.hex() == combined.hex())
        _need(prediction is (score > doc['threshold']))
    _need(all(mask[i] for i in (*train, *calibration)))
    declared = doc['calibration']
    _keys(declared, _CALIBRATION)
    _same_profile({k: declared[k] for k in ('quantile', 'method', 'comparison')},
                  dict(quantile=.99, method='linear', comparison='STRICT_GREATER'))
    for name in ('sample_count', 'equal_count', 'strictly_above_count'):
        _uint(declared[name], n)
    selected = [scores[i] for i in calibration]
    _need(declared['sample_count'] == len(calibration)
          and declared['equal_count'] == sum(v == doc['threshold'] for v in selected)
          and declared['strictly_above_count'] == sum(v > doc['threshold'] for v in selected))
    runtime = doc['runtime']
    _keys(runtime, _RUNTIME)
    _text(runtime['python_version'])
    _need(re.fullmatch(r'3\.14\.[0-9]+', runtime['python_version']) is not None)
    for name, value in (('numpy_version', '2.5.4'), ('torch_version', '2.14.1+cpu'), ('device', 'cpu')):
        _fixed(runtime[name], value)
    for name in ('torch_num_threads', 'torch_num_interop_threads'):
        _uint(runtime[name], 64, positive=True)
    return n


def _stamp(value):
    _text(value)
    _need(_STAMP.fullmatch(value) is not None, 'INVALID_PACKAGE')
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ReleaseAEResultPackageError('INVALID_PACKAGE') from None


def _expand_axis(segments, durations):
    """Expand roles/eligibility only after every duration/count was admitted."""
    roles, eligible = [], []
    for segment, count in zip(segments, durations):
        roles.extend([segment['role']] * count)
        eligible.extend(i >= 30 for i in range(count))
    return tuple(roles), tuple(eligible)


def _validate_context(context, result, n):
    _keys(context, _CONTEXT)
    _uint(context['minute_count'], 10000, positive=True)
    _need(context['minute_count'] == n)
    _fixed(context['profile_id'], _P, 'INCOMPATIBLE_PACKAGE')
    _fixed(context['result_profile_id'], _R, 'INCOMPATIBLE_PACKAGE')
    _view(context['view'])
    _need(context['view'] == result['view'], 'INPUT_BINDING_MISMATCH')
    _reference(context['raw_identity'], _RAW)
    _reference(context['prepared_identity'], _PREPARED)
    _sha(context['configuration_sha256'])
    for name in ('raw_identity', 'prepared_identity', 'configuration_sha256'):
        _need(context[name] == result[name], 'INPUT_BINDING_MISMATCH')
    _fixed(context['source_schema_id'], 'c17-release-91-v1', 'INCOMPATIBLE_PACKAGE')
    for name, expected in (('source_authentication', 'NOT_AUTHENTICATED'),
            ('time_basis', 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'), ('policy_status', 'AUDIT_ONLY'),
            ('score_direction', 'HIGHER_IS_MORE_ANOMALOUS')):
        _fixed(context[name], expected)
    _text(context['audit_fit_policy'])
    _need(context['audit_fit_policy'] in ('P_U', 'P_B', 'P_A'), 'INVALID_PACKAGE')
    segments = _sequence(context['segments'], list, 7, positive=True)
    durations, ids, total = [], set(), 0
    previous_end, previous_role = None, -1
    for ordinal, segment in enumerate(segments):
        _keys(segment, ('ordinal', 'id', 'role', 'start', 'end'))
        _fixed(segment['ordinal'], ordinal)
        _text(segment['id'], 128)
        _need(bool(segment['id']) and all(ord(c) >= 32 and ord(c) != 127 for c in segment['id']), 'INVALID_PACKAGE')
        _need(segment['id'] not in ids)
        ids.add(segment['id'])
        _text(segment['role'])
        _need(segment['role'] in _ROLES, 'INVALID_PACKAGE')
        role = _ROLES.index(segment['role'])
        _need(role >= previous_role)
        start, end = _stamp(segment['start']), _stamp(segment['end'])
        _need(start < end and (previous_end is None or previous_end <= start))
        delta = end - start
        count = delta.days * 1440 + delta.seconds // 60
        total += count
        _need(count <= 10000 and total <= 10000, 'RESOURCE_LIMIT')
        durations.append(count)
        previous_end, previous_role = end, role
    _need(total == n)
    _canonical(context, 16384)
    roles, eligible = _expand_axis(segments, tuple(durations))
    _need(all(not scored or eligible[i] for i, scored in enumerate(result['scored_mask'])))
    _need(all(roles[i] == 'train' for i in result['preprocessing_fit_indices']))
    _need(all(roles[i] == 'calibration' for i in result['calibration_indices']))
    # Training is a subset of preprocessing and scored; preprocessing may
    # legitimately include unscored train-role warmup indices before local30.


def _dependencies():
    import numpy as np
    version = np.__version__
    _need(type(version) is str and version == '2.5.4', 'INCOMPATIBLE_RUNTIME')
    from .evaluation.calibration import calibrate
    return np, calibrate


def _q99(result):
    _, calibrate = _dependencies()
    selected = tuple(result['scores'][i] for i in result['calibration_indices'])
    threshold = calibrate(selected, .99)
    _need(type(threshold) is float and math.isfinite(threshold) and threshold >= 0.)
    _need(threshold.hex() == result['threshold'].hex())


def _scan_json(text):
    """Bound depth and decoded strings before allocating a decoded JSON tree."""
    i, depth = 0, 0
    while i < len(text):
        c = text[i]
        if c == '"':
            i += 1
            size = 0
            while i < len(text) and text[i] != '"':
                c = text[i]
                if c == '\\':
                    i += 1
                    _need(i < len(text), 'INVALID_PACKAGE')
                    escape = text[i]
                    if escape == 'u':
                        digits = text[i + 1:i + 5]
                        _need(len(digits) == 4 and all(d in '0123456789abcdefABCDEF' for d in digits), 'INVALID_PACKAGE')
                        code = int(digits, 16)
                        i += 4
                        if 0xD800 <= code <= 0xDBFF:
                            _need(text[i + 1:i + 3] == '\\u', 'INVALID_PACKAGE')
                            digits = text[i + 3:i + 7]
                            _need(len(digits) == 4 and all(d in '0123456789abcdefABCDEF' for d in digits), 'INVALID_PACKAGE')
                            _need(0xDC00 <= int(digits, 16) <= 0xDFFF, 'INVALID_PACKAGE')
                            i += 6
                        else:
                            _need(not 0xDC00 <= code <= 0xDFFF, 'INVALID_PACKAGE')
                    else:
                        _need(escape in '"\\/bfnrt', 'INVALID_PACKAGE')
                else:
                    _need(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF, 'INVALID_PACKAGE')
                size += 1
                _need(size <= 256, 'RESOURCE_LIMIT')
                i += 1
            _need(i < len(text), 'INVALID_PACKAGE')
        elif c in '[{':
            depth += 1
            _need(depth <= 16, 'INVALID_PACKAGE')
        elif c in ']}':
            depth -= 1
            _need(depth >= 0, 'INVALID_PACKAGE')
        i += 1
    _need(depth == 0, 'INVALID_PACKAGE')


def _json_int(token):
    _need(len(token) <= 8, 'INVALID_PACKAGE')
    return int(token)


def _json_float(token):
    _need(len(token) <= 32, 'INVALID_PACKAGE')
    value = float(token)
    _need(math.isfinite(value), 'INVALID_PACKAGE')
    return value


def _json_constant(token):
    raise ReleaseAEResultPackageError('INVALID_PACKAGE') from None


def _json_pairs(pairs):
    result = {}
    for name, value in pairs:
        _need(name not in result, 'INVALID_PACKAGE')
        result[name] = value
    return result


def _canonical(value, limit):
    chunks, size = [], 0
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    for chunk in encoder.iterencode(value):
        payload = chunk.encode('utf-8')
        size += len(payload)
        _need(size + 1 <= limit, 'RESOURCE_LIMIT')
        chunks.append(payload)
    return b''.join(chunks) + b'\n'


def _json(payload, limit):
    _need(type(payload) is bytes, 'INVALID_PACKAGE_ARGUMENTS')
    _need(len(payload) <= limit, 'RESOURCE_LIMIT')
    try:
        text = payload.decode('utf-8')
        _need(not text.startswith('\ufeff'), 'INVALID_PACKAGE')
        _scan_json(text)
        document = json.loads(text, parse_int=_json_int, parse_float=_json_float,
                              parse_constant=_json_constant, object_pairs_hook=_json_pairs)
        _need(_canonical(document, limit) == payload, 'INVALID_PACKAGE')
        return document
    except (UnicodeError, ValueError) as error:
        if type(error) is ReleaseAEResultPackageError:
            raise
        raise ReleaseAEResultPackageError('INVALID_PACKAGE') from None


def _digest(payload):
    return dict(byte_count=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def _byte_reference(reference, payload, limit):
    _keys(reference, ('byte_count', 'sha256'))
    _uint(reference['byte_count'], limit, positive=True)
    _sha(reference['sha256'])
    _need(reference == _digest(payload), 'INTEGRITY_MISMATCH')


def _envelope(document, names):
    _keys(document, names)
    _fixed(document['schema_version'], 1, 'INCOMPATIBLE_PACKAGE')
    _fixed(document['profile_id'], _P, 'INCOMPATIBLE_PACKAGE')


def _content(result, context):
    context_sha = hashlib.sha256(_canonical(context, 16384)).hexdigest()
    base = dict(schema_version=1, profile_id=_P, context_sha256=context_sha)
    result_bytes = _canonical(dict(base, result=result), _LIMITS['result.json'])
    manifest = _canonical(dict(base, context=context,
        members={'result.json': _digest(result_bytes)}), _LIMITS['manifest.json'])
    complete = _canonical(dict(schema_version=1, profile_id=_P, status='COMPLETE',
        manifest=_digest(manifest)), _LIMITS['COMPLETE.json'])
    _need(len(result_bytes) + len(manifest) + len(complete) <= PACKAGE_TOTAL_BYTE_LIMIT, 'RESOURCE_LIMIT')
    identity = ReleaseAEResultIdentity(_P, context_sha, hashlib.sha256(manifest).hexdigest(), len(manifest))
    return tuple(zip(PACKAGE_MEMBER_NAMES, (result_bytes, manifest, complete))), identity


def _report():
    return ReleaseAEResultLoadReport('c17-release-ae-result-load-report-v1',
        'SAVED_AE_RESULT_INTERNAL_CONSISTENCY_ONLY', 'MATCHED', 'MATCHED', 'MATCHED',
        'MATCHED', 'NOT_PERFORMED', 'NOT_PERFORMED', 'NOT_AUTHENTICATED', 'NOT_AUTHENTICATED')


def _build_result(doc):
    result_type, config_type, calibration_type, runtime_type, raw_type, prepared_type, _ = _data_types()
    values = dict(doc)
    values['raw_identity'] = raw_type(**doc['raw_identity'])
    values['prepared_identity'] = prepared_type(**doc['prepared_identity'])
    for name in (*_VECTORS, *_INDICES, 'training_losses', 'feature_columns'):
        values[name] = tuple(doc[name])
    config = dict(doc['configuration'])
    config['architecture'], config['adam_betas'] = tuple(config['architecture']), tuple(config['adam_betas'])
    values['configuration'] = config_type(**config)
    values['calibration'], values['runtime'] = calibration_type(**doc['calibration']), runtime_type(**doc['runtime'])
    return result_type(**values)


def _build_context(doc):
    _, _, _, _, raw_type, prepared_type, segment_type = _data_types()
    values = dict(doc)
    values['raw_identity'], values['prepared_identity'] = raw_type(**doc['raw_identity']), prepared_type(**doc['prepared_identity'])
    values['segments'] = tuple(segment_type(s['id'], s['role'], _stamp(s['start']), _stamp(s['end']))
                               for s in doc['segments'])
    return ReleaseAEResultContext(**values)


def decode_release_ae_result_projection(payload: bytes) -> ReleaseAEResult:
    """Rebuild local result data; no clock/role/input-pair certification."""
    try:
        doc = _json(payload, _LIMITS['result.json'])
        _validate_projection(doc)
        _q99(doc)
        return _build_result(doc)
    except BaseException as error:
        _raise_safe(error)


def make_release_ae_result_package(
        result: ReleaseAEResult, declarations: ReleaseAEResultDeclarations,
) -> ReleaseAEResultPackage:
    """Bind declarations to primitive result data without reopening its inputs."""
    try:
        doc = _native_result(result)
        n = _validate_projection(doc)
        values = _holder(declarations, ReleaseAEResultDeclarations)
        context = ReleaseAEResultContext(profile_id=_P, result_profile_id=_R,
            view=doc['view'], score_direction='HIGHER_IS_MORE_ANOMALOUS', **values)
        context_doc = _native_context(context)
        _validate_context(context_doc, doc, n)
        _, identity = _content(doc, context_doc)
        _q99(doc)
        return ReleaseAEResultPackage(identity, _build_context(context_doc), _build_result(doc), _report())
    except BaseException as error:
        _raise_safe(error)


def encode_release_ae_result_package(package: ReleaseAEResultPackage) -> tuple[tuple[str, bytes], ...]:
    """Revalidate every holder, binding and own Q99 before returning bytes."""
    try:
        _need(type(package) is ReleaseAEResultPackage, 'INVALID_PACKAGE_ARGUMENTS')
        stored = _holder(package, ReleaseAEResultPackage)
        doc = _native_result(stored['result'])
        n = _validate_projection(doc)
        context = _native_context(stored['context'])
        _validate_context(context, doc, n)
        members, identity = _content(doc, context)
        declared = _holder(stored['identity'], ReleaseAEResultIdentity)
        _reference(declared, _P)
        _need(declared == _holder(identity, ReleaseAEResultIdentity), 'INTEGRITY_MISMATCH')
        report = _holder(stored['load_report'], ReleaseAEResultLoadReport)
        for name, expected in _holder(_report(), ReleaseAEResultLoadReport).items():
            _fixed(report[name], expected)
        _q99(doc)
        return members
    except BaseException as error:
        _raise_safe(error)


def decode_release_ae_result_package(members: dict[str, bytes]) -> ReleaseAEResultPackage:
    """Check actual canonical member bytes and context, then one saved Q99."""
    try:
        _need(type(members) is dict and len(members) == 3
              and all(type(k) is str for k in members) and set(members) == set(PACKAGE_MEMBER_NAMES),
              'INVALID_PACKAGE_ARGUMENTS')
        total = 0
        for name, limit in PACKAGE_MEMBER_BYTE_LIMITS:
            payload = members[name]
            _need(type(payload) is bytes, 'INVALID_PACKAGE_ARGUMENTS')
            _need(len(payload) <= limit, 'RESOURCE_LIMIT')
            total += len(payload)
        _need(total <= PACKAGE_TOTAL_BYTE_LIMIT, 'RESOURCE_LIMIT')
        complete = _json(members['COMPLETE.json'], _LIMITS['COMPLETE.json'])
        _envelope(complete, ('schema_version', 'profile_id', 'status', 'manifest'))
        _fixed(complete['status'], 'COMPLETE')
        _byte_reference(complete['manifest'], members['manifest.json'], _LIMITS['manifest.json'])
        manifest = _json(members['manifest.json'], _LIMITS['manifest.json'])
        _envelope(manifest, ('schema_version', 'profile_id', 'context_sha256', 'context', 'members'))
        _keys(manifest['members'], ('result.json',))
        _byte_reference(manifest['members']['result.json'], members['result.json'], _LIMITS['result.json'])
        result = _json(members['result.json'], _LIMITS['result.json'])
        _envelope(result, ('schema_version', 'profile_id', 'context_sha256', 'result'))
        context_sha = hashlib.sha256(_canonical(manifest['context'], 16384)).hexdigest()
        for document in (manifest, result):
            _sha(document['context_sha256'])
            _need(document['context_sha256'] == context_sha, 'INTEGRITY_MISMATCH')
        doc, context = result['result'], manifest['context']
        n = _validate_projection(doc)
        _validate_context(context, doc, n)
        identity = ReleaseAEResultIdentity(_P, context_sha, hashlib.sha256(members['manifest.json']).hexdigest(),
                                          len(members['manifest.json']))
        _q99(doc)
        return ReleaseAEResultPackage(identity, _build_context(context), _build_result(doc), _report())
    except BaseException as error:
        _raise_safe(error)
