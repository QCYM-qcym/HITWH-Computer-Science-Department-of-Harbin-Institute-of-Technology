"""Inspect a saved AE result declaration without model or upstream execution.

Import, help and argument admission use only the standard library. A valid
inspect lazily loads its package once; formatting adds no calibration or codec.
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime
import json
import math
import os
import re
import sys


_HELP = (b'usage: python -m traffic_anomaly.release_ae_result_cli '
         b'inspect --result-package ABS\n'
         b'Inspect saved internal consistency; no model, input pairing or replay.\n')
_LIBRARY_CODES = frozenset((
    'INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE',
    'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE',
    'INVALID_PACKAGE_PATH', 'INPUT_UNAVAILABLE', 'OUTPUT_EXISTS',
    'PACKAGE_CHANGED', 'OUTPUT_ERROR', 'INPUT_BINDING_MISMATCH',
    'NUMERICAL_DEPENDENCY_UNAVAILABLE', 'INCOMPATIBLE_RUNTIME', 'PACKAGE_ERROR',
))
_CLI_CODES = _LIBRARY_CODES | {'INVALID_ARGUMENTS', 'INTERRUPTED', 'OUTPUT_ERROR', 'CLI_ERROR'}
_CHECKS = dict(byte_integrity='MATCHED', structure='MATCHED', saved_score_q99='MATCHED',
    input_declaration_binding='MATCHED', input_pair_binding='NOT_PERFORMED',
    derivation_replay='NOT_PERFORMED', source_authentication='NOT_AUTHENTICATED',
    model_execution='NOT_AUTHENTICATED')
_PACKAGE_PROFILE = 'c17-release-ae-result-package-v1'
_RESULT_PROFILE = 'c17-release-ae-engineering-v1'
_IDENTITY_FIELDS = ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_OUTPUT_LIMIT = 65536


class _CLIError(ValueError):
    def __init__(self, code):
        safe = code if type(code) is str and code in _CLI_CODES else 'CLI_ERROR'
        self.code = safe
        super().__init__(safe)


def _need(condition, code='CLI_ERROR'):
    if not condition:
        raise _CLIError(code) from None


def _arguments(argv):
    if argv is None:
        host = sys.argv
        _need(type(host) in (list, tuple), 'INVALID_ARGUMENTS')
        _need(all(type(value) is str for value in host), 'INVALID_ARGUMENTS')
        argv = host[1:]
    _need(type(argv) in (list, tuple), 'INVALID_ARGUMENTS')
    _need(all(type(value) is str for value in argv), 'INVALID_ARGUMENTS')
    if len(argv) == 1 and argv[0] in ('-h', '--help'):
        return None
    _need(len(argv) in (2, 3) and argv[0] == 'inspect', 'INVALID_ARGUMENTS')
    if len(argv) == 3:
        _need(argv[1] == '--result-package', 'INVALID_ARGUMENTS')
        path = argv[2]
    else:
        _need(argv[1].startswith('--result-package='), 'INVALID_ARGUMENTS')
        path = argv[1][len('--result-package='):]
    _need(bool(path) and not path.startswith(('-', '@')), 'INVALID_ARGUMENTS')
    return path


def _holder(value, kind):
    _need(type(value) is kind)
    result = {}
    for field in fields(kind):
        try:
            result[field.name] = object.__getattribute__(value, field.name)
        except AttributeError:
            raise _CLIError('CLI_ERROR') from None
    return result


def _text(value, maximum=256):
    _need(type(value) is str and len(value) <= maximum)
    _need(not any(0xD800 <= ord(c) <= 0xDFFF for c in value))
    return value


def _uint(value, maximum, *, positive=False):
    _need(type(value) is int and int(positive) <= value <= maximum)
    return value


def _float(value):
    _need(type(value) is float and math.isfinite(value) and value >= 0.)
    return value


def _primitive(value, depth=0):
    """Copy only bounded native data for a fresh structural projection."""
    _need(depth <= 16)
    kind = type(value)
    if value is None or kind is bool:
        return value
    if kind is str:
        return _text(value)
    if kind is int:
        _need(value.bit_length() <= 64)
        return value
    if kind is float:
        _need(math.isfinite(value))
        return value
    if kind is tuple:
        _need(len(value) <= 10000)
        return [_primitive(item, depth + 1) for item in value]
    raise _CLIError('CLI_ERROR') from None


def _declared_holder(value, kind, count):
    data = _holder(value, kind)
    _need(len(data) == count)
    return {name: _primitive(item) for name, item in data.items()}


def _identity(value, kind, profile):
    data = _holder(value, kind)
    _need(set(data) == set(_IDENTITY_FIELDS))
    _need(_text(data['profile_id']) == profile)
    for name in ('context_sha256', 'manifest_sha256'):
        _need(_SHA.fullmatch(_text(data[name])) is not None)
    _uint(data['manifest_byte_count'], 65536, positive=True)
    return dict(data)


def _segments(values, kind):
    _need(type(values) is tuple and 1 <= len(values) <= 7)
    result = []
    for ordinal, value in enumerate(values):
        data = _holder(value, kind)
        _need(set(data) == {'id', 'role', 'start', 'end'})
        identifier = _text(data['id'], 128)
        _need(bool(identifier) and all(ord(c) >= 32 and ord(c) != 127 for c in identifier))
        role = _text(data['role'])
        _need(role in ('train', 'validation', 'calibration', 'test'))
        for name in ('start', 'end'):
            stamp = data[name]
            _need(type(stamp) is datetime)
            _need(stamp.tzinfo is None and stamp.second == stamp.microsecond == 0)
        _need(data['start'] < data['end'])
        result.append(dict(ordinal=ordinal, id=identifier, role=role,
            start=data['start'].isoformat(timespec='seconds'), end=data['end'].isoformat(timespec='seconds')))
    return result


def _ranges(result, view, n):
    names = ('scores', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse')
    ranges = {name: dict(count=0, min=None, max=None) for name in names}
    for name in (*names, 'scored_mask', 'predictions'):
        _need(type(result[name]) is tuple and len(result[name]) == n)
    scored = 0
    for i in range(n):
        mask = result['scored_mask'][i]
        _need(type(mask) is bool)
        if not mask:
            _need(result['predictions'][i] is None and all(result[name][i] is None for name in names))
            continue
        scored += 1
        _need(type(result['predictions'][i]) is bool)
        for name in names:
            value = result[name][i]
            if name == 'history_deviation_reconstruction_mse' and view == 'current13':
                _need(value is None)
                continue
            _float(value)
            row = ranges[name]
            if row['count'] == 0:
                row['min'] = row['max'] = value
            else:
                if value < row['min']:
                    row['min'] = value
                if value > row['max']:
                    row['max'] = value
            row['count'] += 1
    return ranges, scored


def _summary(package, contract):
    """Project only the just-loaded holder, with no codec/Q99 revalidation."""
    from .release_autoencoder import (
        ReleaseAEResult, ReleaseAEConfiguration, ReleaseAECalibration, ReleaseAERuntime)
    from .release_minute_contract import ReleaseMinutePackageIdentity
    from .release_inputs import ReleaseInputIdentity
    from ._release_minutes import ReleaseSegment

    stored = _holder(package, contract.ReleaseAEResultPackage)
    result = _holder(stored['result'], ReleaseAEResult)
    context = _holder(stored['context'], contract.ReleaseAEResultContext)
    _need(len(result) == 20 and len(context) == 14)
    view = _text(result['view'])
    _need(view in ('current13', 'h30_26') and _text(context['view']) == view)
    _need(_text(result['profile_id']) == _RESULT_PROFILE
          and _text(result['scope']) == 'IN_MEMORY_ENGINEERING_NUMERICAL_RESULT_ONLY'
          and _text(context['profile_id']) == _PACKAGE_PROFILE
          and _text(context['result_profile_id']) == _RESULT_PROFILE)
    identity = _identity(stored['identity'], contract.ReleaseAEResultIdentity, _PACKAGE_PROFILE)
    raw = _identity(result['raw_identity'], ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
    prepared = _identity(result['prepared_identity'], ReleaseInputIdentity, 'c17-release-prepared-input-package-v1')
    _need(raw == _identity(context['raw_identity'], ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
          and prepared == _identity(context['prepared_identity'], ReleaseInputIdentity, 'c17-release-prepared-input-package-v1'))
    configuration_sha = _text(result['configuration_sha256'])
    _need(_SHA.fullmatch(configuration_sha) is not None and _text(context['configuration_sha256']) == configuration_sha)
    _need(type(result['scores']) is tuple)
    n = _uint(len(result['scores']), 10000, positive=True)
    _need(_uint(context['minute_count'], 10000, positive=True) == n)
    ranges, scored = _ranges(result, view, n)
    counts = dict(total=n, scored=scored)
    for source, target in (('train_indices', 'training'), ('calibration_indices', 'calibration'),
                           ('preprocessing_fit_indices', 'preprocessing_fit')):
        values = result[source]
        _need(type(values) is tuple and 1 <= len(values) <= n)
        for value in values:
            _uint(value, n - 1)
        counts[target] = len(values)
    columns = result['feature_columns']
    _need(type(columns) is tuple and len(columns) == (13 if view == 'current13' else 26))
    columns = [_text(name) for name in columns]
    losses = result['training_losses']
    _need(type(losses) is tuple and len(losses) == 5)
    losses = [_float(value) for value in losses]
    report = _holder(stored['load_report'], contract.ReleaseAEResultLoadReport)
    _need(len(report) == 10
          and _text(report['profile_id']) == 'c17-release-ae-result-load-report-v1'
          and _text(report['scope']) == 'SAVED_AE_RESULT_INTERNAL_CONSISTENCY_ONLY')
    for name, expected in _CHECKS.items():
        _need(_text(report[name]) == expected)
    return dict(schema_version=1, profile_id='c17-release-ae-result-cli-v1', command='inspect',
        status='INTERNAL_CONSISTENCY_CHECKED', result_identity=identity, view=view,
        input_references=dict(raw=raw, prepared=prepared), configuration_sha256=configuration_sha,
        segments=_segments(context['segments'], ReleaseSegment), counts=counts,
        feature_columns=columns, model_configuration=_declared_holder(result['configuration'], ReleaseAEConfiguration, 30),
        runtime_declarations=_declared_holder(result['runtime'], ReleaseAERuntime, 6),
        threshold=_float(result['threshold']), training_losses=losses,
        calibration=_declared_holder(result['calibration'], ReleaseAECalibration, 6),
        score_ranges=ranges, checks=dict(_CHECKS),
        operations=dict(model_fit_calls=0, model_forward_calls=0, saved_score_q99_checks=1, upstream_package_loads=0))


def _inspect(path):
    from . import release_ae_result_contract as contract
    from .release_ae_result_package import load_release_ae_result_package
    package = load_release_ae_result_package(path)
    return _summary(package, contract)


def _encode(value):
    output = bytearray()
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    for chunk in encoder.iterencode(value):
        raw = chunk.encode('utf-8')
        _need(len(output) + len(raw) + 1 <= _OUTPUT_LIMIT, 'RESOURCE_LIMIT')
        output.extend(raw)
    output.extend(b'\n')
    return bytes(output)


def _write(stream, payload):
    try:
        binary = stream.buffer
        written = binary.write(payload)
        _need(type(written) is int and written == len(payload), 'OUTPUT_ERROR')
        binary.flush()
    except BaseException as error:
        kind = type(error)
        if issubclass(kind, (MemoryError, KeyboardInterrupt, SystemExit)) or kind is _CLIError:
            raise error from None
        raise _CLIError('OUTPUT_ERROR') from None


def _classification_failure(error):
    kind = type(error)
    if issubclass(kind, SystemExit):
        raise error from None
    if issubclass(kind, KeyboardInterrupt):
        return 'INTERRUPTED'
    if issubclass(kind, MemoryError):
        return 'RESOURCE_LIMIT'
    return 'CLI_ERROR'


def _safe_code(error, owner):
    kind = type(error)
    if issubclass(kind, (SystemExit, KeyboardInterrupt, MemoryError)):
        return _classification_failure(error)
    allowed = _CLI_CODES if kind is _CLIError else _LIBRARY_CODES if kind is owner else ()
    if not allowed:
        return 'CLI_ERROR'
    try:
        code = error.code
    except BaseException as failure:
        return _classification_failure(failure)
    return code if type(code) is str and code in allowed else 'CLI_ERROR'


def _error(code):
    # A chosen finite primary survives every later diagnostic failure. Never
    # write a second line, retry, use text fallback or rethrow its secondary.
    try:
        payload = ('{"code":"' + code + '","status":"ERROR"}\n').encode('ascii')
        _need(len(payload) <= 1024)
        _write(sys.stderr, payload)
    except BaseException:
        pass
    return 2


def main(argv=None) -> int:
    owner = None
    try:
        path = _arguments(argv)
        if path is None:
            payload = _HELP
        else:
            from . import release_ae_result_contract as contract
            owner = contract.ReleaseAEResultPackageError
            payload = _encode(_inspect(path))
        _write(sys.stdout, payload)
    except BaseException as error:
        return _error(_safe_code(error, owner))
    return 0


def _cli_entrypoint() -> int:
    status = main()
    if status != 0:
        # The accepted narrow shutdown mitigation prevents a pending buffered
        # broken-pipe flush from replacing the selected nonzero physical exit.
        for stream in (sys.stdout, sys.stderr):
            try:
                target = stream.fileno()
                null_fd = os.open(os.devnull, os.O_WRONLY)
                try:
                    os.dup2(null_fd, target)
                finally:
                    if null_fd != target:
                        os.close(null_fd)
            except BaseException:
                pass
    return status


if __name__ == '__main__':
    raise SystemExit(_cli_entrypoint())
