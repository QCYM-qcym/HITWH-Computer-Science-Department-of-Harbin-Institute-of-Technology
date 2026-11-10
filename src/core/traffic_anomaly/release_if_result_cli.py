"""Single-view IF result generation, saved inspection and declaration binding.

Inspection and verification never fit, score or replay preprocessing. Success
reports internal consistency; it does not authenticate a source or execution.
"""
from __future__ import annotations

from collections.abc import Sequence
import json
import math
import os
from pathlib import Path
import re
import sys

from .release_input_package import load_release_input_package, _lexical, _signature, _directory
from .release_inputs import ReleaseInputIdentity, ReleaseInputPreparationError
from .release_minute_contract import ReleaseMinutePackageIdentity, ReleaseMinutePackageError
from .release_minute_package import load_release_minute_package
from .release_model_inputs import ReleaseModelInputPairError, pair_release_model_inputs
from .release_iforest import ReleaseIFError, ReleaseIFResult, fit_release_iforest
from .release_if_result_contract import (
    ReleaseIFResultIdentity, ReleaseIFResultPackage, ReleaseIFResultContext,
    ReleaseIFResultLoadReport, ReleaseIFResultPackageError,
    make_release_if_result_package, verify_release_if_result_pair,
)
from .release_if_result_package import load_release_if_result_package, save_release_if_result_package

_HELP = (
    'usage: python -m traffic_anomaly.release_if_result_cli COMMAND OPTIONS\n'
    '\ncommands:\n'
    '  run --raw-package ABS --prepared-package ABS --view {current13,h30_26} --output NEW_ABS\n'
    '  inspect --result-package ABS\n'
    '  verify --result-package ABS --raw-package ABS --prepared-package ABS\n'
    '\nRun fits and scores one view; inspect and verify only check saved results and declarations.\n'
    '  -h, --help   show this fixed usage\n'
).encode('utf-8')
_OUTPUT_LIMIT = 65536
_P = 'c17-release-iforest-result-package-v1'
_R = 'c17-release-iforest-engineering-v1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_IDENTITY_FIELDS = ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')
_OPTIONS = {
    'run': ('--raw-package', '--prepared-package', '--view', '--output'),
    'inspect': ('--result-package',),
    'verify': ('--result-package', '--raw-package', '--prepared-package'),
}
_PACKAGE_CODES = frozenset(('INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE',
    'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE', 'INVALID_PACKAGE_PATH',
    'INPUT_UNAVAILABLE', 'OUTPUT_EXISTS', 'PACKAGE_CHANGED', 'OUTPUT_ERROR'))
_ERROR_CODES = {
    ReleaseMinutePackageError: _PACKAGE_CODES,
    ReleaseInputPreparationError: _PACKAGE_CODES | frozenset(('INVALID_PREPARATION_CONFIG',
        'UPSTREAM_IDENTITY_MISMATCH', 'NO_TRAINING_NORMAL_MINUTES', 'NONFINITE_FIT_STATE', 'DERIVATION_MISMATCH')),
    ReleaseIFResultPackageError: _PACKAGE_CODES | {'INPUT_BINDING_MISMATCH'},
    ReleaseModelInputPairError: frozenset(('INVALID_PAIR_ARGUMENTS', 'INVALID_PAIR_STRUCTURE',
        'INCOMPATIBLE_PAIR', 'RESOURCE_LIMIT', 'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH')),
    ReleaseIFError: frozenset(('INVALID_IF_ARGUMENTS', 'INVALID_IF_INPUT', 'RESOURCE_LIMIT',
        'NO_TRAINING_NORMAL', 'NO_CALIBRATION_NORMAL', 'INVALID_INPUT_NUMERIC',
        'INVALID_MODEL_SCORES', 'MODEL_UNAVAILABLE', 'MODEL_ERROR', 'INVALID_IF_RESULT')),
}
_CLI_CODES = _PACKAGE_CODES | frozenset(('INVALID_ARGUMENTS', 'INVALID_PATH_LAYOUT',
    'INVALID_RESULT', 'INTERRUPTED', 'INTERNAL_ERROR'))


class _CLIError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(condition, code='INVALID_RESULT'):
    if not condition:
        raise _CLIError(code) from None


def _arguments(argv):
    if argv is None:
        argv = sys.argv[1:]
    _need(not isinstance(argv, (str, bytes)) and isinstance(argv, Sequence), 'INVALID_ARGUMENTS')
    values = list(argv)
    _need(all(type(value) is str and not value.startswith('@') for value in values), 'INVALID_ARGUMENTS')
    if values in (['-h'], ['--help']):
        return None
    _need(bool(values) and values[0] in _OPTIONS, 'INVALID_ARGUMENTS')
    command = values[0]
    options = {}
    index = 1
    while index < len(values):
        option, equals, value = values[index].partition('=')
        _need(option in _OPTIONS[command] and option not in options, 'INVALID_ARGUMENTS')
        if not equals:
            index += 1
            _need(index < len(values) and not values[index].startswith('-'), 'INVALID_ARGUMENTS')
            value = values[index]
        _need(bool(value) and not value.startswith('@'), 'INVALID_ARGUMENTS')
        options[option] = value
        index += 1
    _need(len(options) == len(_OPTIONS[command]), 'INVALID_ARGUMENTS')
    if command == 'run':
        _need(options['--view'] in ('current13', 'h30_26'), 'INVALID_ARGUMENTS')
    return command, options


def _paths(command, options):
    # Preserve the original spelling for lexical validation (before Path can
    # normalize components). This also fixes the specified first-error order.
    names = tuple(name for name in _OPTIONS[command] if name != '--view')
    return {name: _lexical(options[name]) for name in names}


def _output_preflight(paths):
    output = paths['--output']
    for name in ('--raw-package', '--prepared-package'):
        source = paths[name]
        _need(output != source and output not in source.parents and source not in output.parents,
              'INVALID_PATH_LAYOUT')
    try:
        for parent in reversed(output.parents):
            _signature(parent.lstat(), directory=True)
        try:
            output.lstat()
        except FileNotFoundError:
            return
        _need(False, 'OUTPUT_EXISTS')
    except OSError:
        raise _CLIError('OUTPUT_ERROR') from None


def _input_alias_preflight(paths):
    roots = []
    for name in ('--raw-package', '--prepared-package'):
        try:
            roots.append(_directory(paths[name])[:2])
        except OSError:
            raise _CLIError('INPUT_UNAVAILABLE') from None
    try:
        for parent in paths['--output'].parents:
            identity = _signature(parent.lstat(), directory=True)[:2]
            _need(identity not in roots, 'INVALID_PATH_LAYOUT')
    except OSError:
        raise _CLIError('OUTPUT_ERROR') from None


def _identity(value, kind, profile):
    _need(type(value) is kind and type(value.profile_id) is str and value.profile_id == profile)
    for name in ('context_sha256', 'manifest_sha256'):
        actual = getattr(value, name)
        _need(type(actual) is str and _SHA.fullmatch(actual) is not None)
    _need(type(value.manifest_byte_count) is int and 1 <= value.manifest_byte_count <= 65536)
    return {name: getattr(value, name) for name in _IDENTITY_FIELDS}


def _receipt(package, command):
    """Project bounded admitted fields only, never arbitrary upstream objects."""
    try:
        _need(type(package) is ReleaseIFResultPackage)
        context, result, report = package.context, package.result, package.load_report
        _need(type(context) is ReleaseIFResultContext and type(result) is ReleaseIFResult
              and type(report) is ReleaseIFResultLoadReport)
        _need(type(context.profile_id) is str and context.profile_id == _P
              and type(result.profile_id) is str and result.profile_id == _R)
        _need(type(context.view) is str and context.view in ('current13', 'h30_26')
              and type(result.view) is str and result.view == context.view)
        identity = _identity(package.identity, ReleaseIFResultIdentity, _P)
        raw = _identity(context.raw_identity, ReleaseMinutePackageIdentity, 'c17-release-minute-package-v1')
        prepared = _identity(context.prepared_identity, ReleaseInputIdentity, 'c17-release-prepared-input-package-v1')
        _need(type(result.raw_identity) is ReleaseMinutePackageIdentity and result.raw_identity == context.raw_identity
              and type(result.prepared_identity) is ReleaseInputIdentity and result.prepared_identity == context.prepared_identity)
        _need(type(context.configuration_sha256) is str and _SHA.fullmatch(context.configuration_sha256) is not None
              and type(result.configuration_sha256) is str and result.configuration_sha256 == context.configuration_sha256)
        for name, expected in (('profile_id', _P), ('scope', 'SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY'),
                ('structure', 'MATCHED'), ('byte_integrity', 'MATCHED'), ('saved_score_q99', 'MATCHED'),
                ('source_authentication', 'NOT_AUTHENTICATED'), ('model_execution', 'NOT_AUTHENTICATED')):
            actual = getattr(report, name)
            _need(type(actual) is str and actual == expected)
        n = context.minute_count
        _need(type(n) is int and 1 <= n <= 10000)
        for vector in (result.scores, result.predictions, result.scored_mask):
            _need(type(vector) is tuple and len(vector) == n)
        _need(all(type(value) is bool for value in result.scored_mask))
        _need(type(result.threshold) is float and math.isfinite(result.threshold))
        for indices in (result.train_indices, result.calibration_indices, result.preprocessing_fit_indices):
            _need(type(indices) is tuple and 1 <= len(indices) <= n)
            _need(all(type(i) is int and 0 <= i < n for i in indices)
                  and all(a < b for a, b in zip(indices, indices[1:])))
        return dict(version=1, command=command, status={'run': 'SAVED',
            'inspect': 'INTERNAL_CONSISTENCY_CHECKED', 'verify': 'INPUT_BINDING_MATCHED'}[command],
            result_identity=identity, view=context.view, threshold=result.threshold,
            configuration_sha256=context.configuration_sha256, input_references=dict(raw=raw, prepared=prepared),
            counts=dict(total=n, scored=sum(result.scored_mask), training=len(result.train_indices),
                calibration=len(result.calibration_indices), preprocessing_fit=len(result.preprocessing_fit_indices)),
            checks=dict(internal_consistency='MATCHED', saved_score_q99='MATCHED',
                input_pair_binding='NOT_PERFORMED' if command == 'inspect' else 'MATCHED',
                source_authentication='NOT_AUTHENTICATED', model_execution='NOT_AUTHENTICATED'),
            operations=dict(model_fit_score='PERFORMED' if command == 'run' else 'NOT_PERFORMED'))
    except _CLIError:
        raise
    except Exception:
        raise _CLIError('INVALID_RESULT') from None


def _encode(receipt):
    try:
        payload = (json.dumps(receipt, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    except Exception:
        raise _CLIError('INVALID_RESULT') from None
    _need(len(payload) <= _OUTPUT_LIMIT, 'RESOURCE_LIMIT')
    return payload


def _run_view(value, kind, view):
    try:
        _need(type(value) is kind)
        selected = value.context if kind is ReleaseIFResultPackage else value
        if kind is ReleaseIFResultPackage:
            _need(type(selected) is ReleaseIFResultContext)
        _need(type(selected.view) is str and selected.view == view)
    except _CLIError:
        raise
    except Exception:
        raise _CLIError('INVALID_RESULT') from None


def _execute(command, paths, options):
    if command == 'run':
        _output_preflight(paths)
        raw = load_release_minute_package(paths['--raw-package'])
        prepared = load_release_input_package(paths['--prepared-package'])
        pair = pair_release_model_inputs(raw, prepared)
        _input_alias_preflight(paths)
        result = fit_release_iforest(pair, view=options['--view'])
        _run_view(result, ReleaseIFResult, options['--view'])
        package = make_release_if_result_package(pair, result)
        _run_view(package, ReleaseIFResultPackage, options['--view'])
        saved = save_release_if_result_package(package, paths['--output'])
        try:
            _identity(saved, ReleaseIFResultIdentity, _P)
            _identity(package.identity, ReleaseIFResultIdentity, _P)
            _need(saved == package.identity)
        except _CLIError:
            raise
        except Exception:
            raise _CLIError('INVALID_RESULT') from None
    else:
        package = load_release_if_result_package(paths['--result-package'])
        if command == 'verify':
            raw = load_release_minute_package(paths['--raw-package'])
            prepared = load_release_input_package(paths['--prepared-package'])
            pair = pair_release_model_inputs(raw, prepared)
            verify_release_if_result_pair(package, pair)
    return _encode(_receipt(package, command))


def _write(stream, payload):
    try:
        binary = stream.buffer
        count = binary.write(payload)
        _need(type(count) is int and count == len(payload), 'OUTPUT_ERROR')
        binary.flush()
    except KeyboardInterrupt:
        raise
    except Exception:
        raise _CLIError('OUTPUT_ERROR') from None


def _error(code):
    try:
        _write(sys.stderr, ('{"error":"' + code + '"}\n').encode('utf-8'))
    except (Exception, KeyboardInterrupt):
        pass
    return 2


def _safe_code(error):
    allowed = _CLI_CODES if type(error) is _CLIError else _ERROR_CODES.get(type(error), ())
    try:
        code = getattr(error, 'code', None)
        return code if type(code) is str and code in allowed else 'INTERNAL_ERROR'
    except Exception:
        return 'INTERNAL_ERROR'


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _arguments(argv)
        if arguments is None:
            payload = _HELP
        else:
            command, options = arguments
            paths = _paths(command, options)
            payload = _execute(command, paths, options)
        _write(sys.stdout, payload)
    except KeyboardInterrupt:
        return _error('INTERRUPTED')
    except Exception as error:
        return _error(_safe_code(error))
    return 0


def _cli_entrypoint():
    """Protect the owned process exit from failed buffered-stream final flush."""
    status = main()
    if status != 0:
        for stream in (sys.stdout, sys.stderr):
            try:
                target = stream.fileno()
                null_fd = os.open(os.devnull, os.O_WRONLY)
                try:
                    os.dup2(null_fd, target)
                finally:
                    if null_fd != target:
                        os.close(null_fd)
            except (Exception, KeyboardInterrupt):
                pass
    return status


if __name__ == '__main__':
    raise SystemExit(_cli_entrypoint())
