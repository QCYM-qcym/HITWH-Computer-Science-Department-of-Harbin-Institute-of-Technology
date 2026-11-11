"""Read saved inputs and print a bounded fixed-prediction label audit.

No producer, source CSV, preprocessing replay, estimator or output file is used.
Internal binding and saved-score checks do not authenticate historical execution.
"""
from __future__ import annotations

from collections.abc import Sequence
import os
import sys

from .release_if_evaluation import (
    EVALUATION_BYTE_LIMIT, ReleaseIFEvaluationError, evaluate_release_if_result,
)
from .release_if_result_contract import ReleaseIFResultPackageError
from .release_if_result_package import load_release_if_result_package
from .release_minute_contract import ReleaseMinutePackageError
from .release_minute_package import load_release_minute_package
from .release_input_package import _lexical, load_release_input_package
from .release_inputs import ReleaseInputPreparationError
from .release_model_inputs import ReleaseModelInputPairError, pair_release_model_inputs

_HELP = (
    'usage: python -m traffic_anomaly.release_if_evaluation_cli evaluate '
    '--result-package ABS_DIR --raw-package ABS_DIR --prepared-package ABS_DIR\n'
    '\nAudit fixed saved predictions under P_U, P_B and P_A labels.\n'
    'This readonly command does not refit, recalibrate or authenticate a source.\n'
    '  -h, --help   show this fixed usage\n'
).encode('utf-8')
_OPTIONS = ('--result-package', '--raw-package', '--prepared-package')
_CLI_CODES = frozenset(('INVALID_ARGUMENTS', 'INVALID_PACKAGE_PATH', 'INVALID_RESULT',
    'RESOURCE_LIMIT', 'OUTPUT_ERROR'))
_READ_CODES = frozenset(('INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE', 'RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE', 'INVALID_PACKAGE_PATH',
    'INPUT_UNAVAILABLE', 'PACKAGE_CHANGED'))
_ERROR_CODES = {
    ReleaseIFEvaluationError: frozenset(('INVALID_EVALUATION_ARGUMENTS', 'RESOURCE_LIMIT',
        'INPUT_BINDING_MISMATCH', 'INVALID_EVALUATION_INPUT', 'EVALUATION_ERROR')),
    ReleaseMinutePackageError: _READ_CODES,
    ReleaseInputPreparationError: _READ_CODES | {'INVALID_PREPARATION_CONFIG'},
    ReleaseIFResultPackageError: _READ_CODES,
    ReleaseModelInputPairError: frozenset(('INVALID_PAIR_ARGUMENTS', 'INVALID_PAIR_STRUCTURE',
        'INCOMPATIBLE_PAIR', 'RESOURCE_LIMIT', 'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH')),
}


class _CLIError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(condition, code):
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
    _need(bool(values) and values[0] == 'evaluate', 'INVALID_ARGUMENTS')
    options = {}
    index = 1
    while index < len(values):
        option, equals, value = values[index].partition('=')
        _need(option in _OPTIONS and option not in options, 'INVALID_ARGUMENTS')
        if not equals:
            index += 1
            _need(index < len(values) and not values[index].startswith('-'), 'INVALID_ARGUMENTS')
            value = values[index]
        _need(bool(value) and not value.startswith('@'), 'INVALID_ARGUMENTS')
        options[option] = value
        index += 1
    _need(len(options) == len(_OPTIONS), 'INVALID_ARGUMENTS')
    return options


def _paths(options):
    paths = {}
    for option in _OPTIONS:
        raw = options[option]
        try:
            raw.encode('utf-8')
        except UnicodeError:
            raise _CLIError('INVALID_PACKAGE_PATH') from None
        # Give the helper the original spelling before Path normalizes anything.
        paths[option] = _lexical(raw)
    return paths


def _evaluate(paths):
    package = load_release_if_result_package(paths['--result-package'])
    raw = load_release_minute_package(paths['--raw-package'])
    prepared = load_release_input_package(paths['--prepared-package'])
    pair = pair_release_model_inputs(raw, prepared)
    payload = evaluate_release_if_result(package, pair)
    _need(type(payload) is bytes and bool(payload), 'INVALID_RESULT')
    _need(len(payload) <= EVALUATION_BYTE_LIMIT, 'RESOURCE_LIMIT')
    return payload


def _write(stream, payload):
    # Isolate only the stream operation; never wash loader/domain exceptions.
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
    if not allowed:
        return 'INTERNAL_ERROR'
    try:
        code = getattr(error, 'code', None)
        return code if type(code) is str and code in allowed else 'INTERNAL_ERROR'
    except Exception:
        return 'INTERNAL_ERROR'


def main(argv: Sequence[str] | None = None) -> int:
    try:
        options = _arguments(argv)
        payload = _HELP if options is None else _evaluate(_paths(options))
        _write(sys.stdout, payload)
    except KeyboardInterrupt:
        return _error('INTERRUPTED')
    except Exception as error:
        try:
            code = _safe_code(error)
        except KeyboardInterrupt:
            return _error('INTERRUPTED')
        return _error(code)
    return 0


def _cli_entrypoint():
    """Preserve the owned process exit when final buffered-stream flush fails."""
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
