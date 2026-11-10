"""Read-only release package pairing command."""
from __future__ import annotations

from collections.abc import Sequence
import json
import os
from pathlib import Path
import sys

from .release_input_package import load_release_input_package
from .release_inputs import ReleaseInputPreparationError
from .release_minute_contract import ReleaseMinutePackageError
from .release_minute_package import load_release_minute_package
from .release_model_inputs import (
    ReleaseModelInputPairError, pair_release_model_inputs, summarize_release_model_inputs,
)

_HELP = (
    'usage: python -m traffic_anomaly.release_model_input_cli '
    '--raw-package ABS_DIR --prepared-package ABS_DIR\n'
    '\nRead-only pairing of saved release inputs; model execution is not granted.\n'
    '  -h, --help   show this fixed usage\n'
).encode('utf-8')
_SAFE_CODES = frozenset((
    'INVALID_PAIR_ARGUMENTS', 'INVALID_PAIR_STRUCTURE', 'INCOMPATIBLE_PAIR',
    'RESOURCE_LIMIT', 'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH',
    'INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE',
    'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE', 'INVALID_PACKAGE_PATH',
    'INPUT_UNAVAILABLE', 'PACKAGE_CHANGED', 'INVALID_PREPARATION_CONFIG',
    'INVALID_ARGUMENTS', 'INVALID_RESULT', 'OUTPUT_ERROR', 'INTERRUPTED', 'INTERNAL_ERROR',
))


class _CLIError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _arguments(argv):
    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise _CLIError('INVALID_ARGUMENTS')
    values = list(argv)
    if any(type(value) is not str or value.startswith('@') for value in values):
        raise _CLIError('INVALID_ARGUMENTS')
    if values in (['-h'], ['--help']):
        return None
    options = {}
    index = 0
    while index < len(values):
        token = values[index]
        option, equal, value = token.partition('=')
        if option not in ('--raw-package', '--prepared-package') or option in options:
            raise _CLIError('INVALID_ARGUMENTS')
        if not equal:
            index += 1
            if index >= len(values):
                raise _CLIError('INVALID_ARGUMENTS')
            value = values[index]
            if value.startswith('-'):
                raise _CLIError('INVALID_ARGUMENTS')
        if not value or value.startswith('@'):
            raise _CLIError('INVALID_ARGUMENTS')
        options[option] = value
        index += 1
    if len(options) != 2:
        raise _CLIError('INVALID_ARGUMENTS')
    return options['--raw-package'], options['--prepared-package']


def _error(code):
    try:
        _write(sys.stderr, ('{"error":"' + code + '"}\n').encode('utf-8'))
    except (Exception, KeyboardInterrupt):
        pass
    return 2


def _write(stream, payload):
    try:
        binary = stream.buffer
        written = binary.write(payload)
        if type(written) is not int or written != len(payload):
            raise _CLIError('OUTPUT_ERROR')
        binary.flush()
    except KeyboardInterrupt:
        raise
    except Exception:
        raise _CLIError('OUTPUT_ERROR') from None


def _safe_code(error):
    try:
        code = getattr(error, 'code', None)
        if type(code) is str and code in _SAFE_CODES:
            return code
    except (Exception, KeyboardInterrupt):
        pass
    return 'INTERNAL_ERROR'


def _encode(summary):
    try:
        if type(summary) is not dict or summary.get('status') != 'INPUTS_PAIRED':
            raise _CLIError('INVALID_RESULT')
        payload = (json.dumps(summary, ensure_ascii=False, allow_nan=False,
                              sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    except Exception:
        raise _CLIError('INVALID_RESULT') from None
    if len(payload) > 65536:
        raise _CLIError('RESOURCE_LIMIT')
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _arguments(argv)
        if args is None:
            payload = _HELP
        else:
            raw = load_release_minute_package(Path(args[0]))
            saved = load_release_input_package(Path(args[1]))
            paired = pair_release_model_inputs(raw, saved)
            payload = _encode(summarize_release_model_inputs(paired))
    except _CLIError as error:
        return _error(_safe_code(error))
    except (ReleaseModelInputPairError, ReleaseInputPreparationError, ReleaseMinutePackageError) as error:
        return _error(_safe_code(error))
    except KeyboardInterrupt:
        return _error('INTERRUPTED')
    except Exception:
        return _error('INTERNAL_ERROR')
    try:
        _write(sys.stdout, payload)
    except KeyboardInterrupt:
        return _error('INTERRUPTED')
    except _CLIError:
        return _error('OUTPUT_ERROR')
    return 0


def _cli_entrypoint():
    """Own failed process descriptors so final reflush cannot replace exit 2.

    Callable main leaves its host streams untouched. Here a failed buffered
    write may retain bytes, so redirect before Python's shutdown flush.
    """
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
                # Keep the safe status even when this descriptor is unusable.
                pass
    return status


if __name__ == '__main__':
    raise SystemExit(_cli_entrypoint())
