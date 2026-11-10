"""Create the fixed artificial CSV example without running a data pipeline.

Exclusive creation and observable identities protect existing files. This is
not an atomic snapshot or durability protocol; any failed output is retained.
"""
from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import sys

from .release_example import (
    EXAMPLE_PROFILE_ID, EXAMPLE_MEMBER_NAMES, EXAMPLE_MEMBER_BYTE_LIMITS,
    EXAMPLE_TOTAL_BYTE_LIMIT, ReleaseExample, ReleaseExampleError,
    build_release_example,
)
from .release_input_package import _lexical, _signature, _directory
from .release_inputs import ReleaseInputPreparationError

_HELP = (
    'usage: python -m traffic_anomaly.release_example_cli create --output ABS_NEW_DIRECTORY\n'
    '\nCreate artificial.csv, aggregate-spec.json and recipe.json in a new directory.\n'
    'No aggregation, preprocessing, model execution or server is started.\n'
    '  -h, --help   show this fixed usage\n'
).encode('utf-8')
_OUTPUT_LIMIT = 65536
_CLI_CODES = frozenset(('INVALID_ARGUMENTS', 'INVALID_PACKAGE_PATH', 'OUTPUT_EXISTS',
    'OUTPUT_ERROR', 'INVALID_RESULT', 'RESOURCE_LIMIT', 'PACKAGE_CHANGED'))
_ERROR_CODES = {
    ReleaseExampleError: frozenset(('INVALID_EXAMPLE_ARGUMENTS', 'RESOURCE_LIMIT', 'EXAMPLE_ERROR')),
    ReleaseInputPreparationError: frozenset(('INVALID_PACKAGE_PATH', 'PACKAGE_CHANGED')),
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
    _need(bool(values) and values[0] == 'create', 'INVALID_ARGUMENTS')
    output = None
    index = 1
    while index < len(values):
        option, equals, value = values[index].partition('=')
        _need(option == '--output' and output is None, 'INVALID_ARGUMENTS')
        if not equals:
            index += 1
            _need(index < len(values) and not values[index].startswith('-'), 'INVALID_ARGUMENTS')
            value = values[index]
        _need(bool(value) and not value.startswith('@'), 'INVALID_ARGUMENTS')
        output = value
        index += 1
    _need(output is not None, 'INVALID_ARGUMENTS')
    return output


def _io(operation, *args):
    """Only wrap the individual raw I/O call, never builders or helpers."""
    try:
        return operation(*args)
    except Exception:
        raise _CLIError('OUTPUT_ERROR') from None


def _directory_check(directory, identity=None):
    try:
        return _directory(directory, identity)
    except OSError:
        raise _CLIError('OUTPUT_ERROR') from None


def _preflight(raw):
    try:
        raw.encode('utf-8')
    except UnicodeError:
        raise _CLIError('INVALID_PACKAGE_PATH') from None
    directory = _lexical(raw)
    for parent in reversed(directory.parents):
        info = _io(parent.lstat)
        _signature(info, directory=True)
    try:
        directory.lstat()
    except FileNotFoundError:
        return directory
    except OSError:
        raise _CLIError('OUTPUT_ERROR') from None
    raise _CLIError('OUTPUT_EXISTS') from None


def _members(example):
    _need(type(example) is ReleaseExample, 'INVALID_RESULT')
    try:
        profile, members = example.profile_id, example.members
    except Exception:
        raise _CLIError('INVALID_RESULT') from None
    _need(type(profile) is str and profile == EXAMPLE_PROFILE_ID, 'INVALID_RESULT')
    _need(type(members) is tuple and len(members) == len(EXAMPLE_MEMBER_NAMES), 'INVALID_RESULT')
    limits = dict(EXAMPLE_MEMBER_BYTE_LIMITS)
    total = 0
    for wanted, member in zip(EXAMPLE_MEMBER_NAMES, members):
        _need(type(member) is tuple and len(member) == 2, 'INVALID_RESULT')
        name, payload = member
        _need(type(name) is str and name == wanted and type(payload) is bytes, 'INVALID_RESULT')
        total += len(payload)
        _need(len(payload) <= limits[name] and total <= EXAMPLE_TOTAL_BYTE_LIMIT, 'RESOURCE_LIMIT')
    return members


def _owned_signature(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise _CLIError('PACKAGE_CHANGED') from None
    except OSError:
        raise _CLIError('OUTPUT_ERROR') from None
    return _signature(info)


def _names(directory):
    # Materialize at most four names; the caller then rejects any extra member.
    names = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            names.add(entry.name)
            if len(names) > len(EXAMPLE_MEMBER_NAMES):
                break
    return names


def _inventory(directory, identity, owned):
    _directory_check(directory, identity)
    names = _io(_names, directory)
    _need(names == set(owned), 'PACKAGE_CHANGED')
    seen = set()
    for name, expected in owned.items():
        actual = _owned_signature(directory / name)
        _need(actual[:2] not in seen, 'INVALID_PACKAGE_PATH')
        seen.add(actual[:2])
        _need(actual == expected, 'PACKAGE_CHANGED')
    _directory_check(directory, identity)


def _close_after_error(stream):
    # Closing an owned stream must not replace the original safe exception.
    try:
        stream.close()
    except (Exception, KeyboardInterrupt):
        pass


def _readback(directory, identity, name, expected, limit):
    _directory_check(directory, identity)
    path = directory / name
    _need(_owned_signature(path) == expected, 'PACKAGE_CHANGED')
    stream = _io(path.open, 'rb')
    try:
        _need(_signature(_io(os.fstat, _io(stream.fileno))) == expected, 'PACKAGE_CHANGED')
        actual = _io(stream.read, limit + 1)
        _need(_signature(_io(os.fstat, _io(stream.fileno))) == expected, 'PACKAGE_CHANGED')
    except BaseException:
        _close_after_error(stream)
        raise
    _io(stream.close)
    _directory_check(directory, identity)
    _need(_owned_signature(path) == expected, 'PACKAGE_CHANGED')
    _need(type(actual) is bytes, 'OUTPUT_ERROR')
    _need(len(actual) <= limit, 'RESOURCE_LIMIT')
    return actual


def _write_member(directory, identity, name, payload, owned, remaining):
    _inventory(directory, identity, owned)
    path = directory / name
    try:
        stream = path.open('xb')
    except FileExistsError:
        raise _CLIError('PACKAGE_CHANGED') from None
    except Exception:
        raise _CLIError('OUTPUT_ERROR') from None
    try:
        before = _signature(_io(os.fstat, _io(stream.fileno)))
        _need(before == _owned_signature(path), 'PACKAGE_CHANGED')
        _directory_check(directory, identity)
        count = _io(stream.write, payload)
        _need(type(count) is int and count == len(payload), 'OUTPUT_ERROR')
        _io(stream.flush)
        after = _signature(_io(os.fstat, _io(stream.fileno)))
        _need(after[:4] == before[:4] and after[4] == len(payload)
            and after == _owned_signature(path), 'PACKAGE_CHANGED')
    except BaseException:
        _close_after_error(stream)
        raise
    _io(stream.close)
    _directory_check(directory, identity)
    _need(_owned_signature(path) == after, 'PACKAGE_CHANGED')
    owned[name] = after
    _inventory(directory, identity, owned)
    limit = min(dict(EXAMPLE_MEMBER_BYTE_LIMITS)[name], remaining)
    actual = _readback(directory, identity, name, after, limit)
    _need(actual == payload, 'OUTPUT_ERROR')
    _inventory(directory, identity, owned)
    return actual


def _encode(receipt):
    try:
        payload = (json.dumps(receipt, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    except Exception:
        raise _CLIError('INVALID_RESULT') from None
    _need(len(payload) <= _OUTPUT_LIMIT, 'RESOURCE_LIMIT')
    return payload


def _create(raw):
    directory = _preflight(raw)
    members = _members(build_release_example(source_csv_path=directory / 'artificial.csv'))
    try:
        directory.mkdir()
    except FileExistsError:
        raise _CLIError('OUTPUT_EXISTS') from None
    except OSError:
        raise _CLIError('OUTPUT_ERROR') from None
    identity = _directory_check(directory)
    owned, files = {}, {}
    remaining = EXAMPLE_TOTAL_BYTE_LIMIT
    for name, payload in members:
        actual = _write_member(directory, identity, name, payload, owned, remaining)
        remaining -= len(actual)
        files[name] = dict(byte_count=len(actual), sha256=hashlib.sha256(actual).hexdigest())
    _inventory(directory, identity, owned)
    return _encode(dict(version=1, command='create', status='CREATED',
        profile_id=EXAMPLE_PROFILE_ID, scope='ARTIFICIAL_ENGINEERING_ONLY', files=files,
        source_authentication='NOT_AUTHENTICATED', time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',
        policy_status='AUDIT_ONLY'))


def _write(stream, payload):
    binary = _io(lambda: stream.buffer)
    count = _io(binary.write, payload)
    _need(type(count) is int and count == len(payload), 'OUTPUT_ERROR')
    _io(binary.flush)


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
        raw = _arguments(argv)
        _write(sys.stdout, _HELP if raw is None else _create(raw))
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
    """Keep the owned process exit stable when final buffered flush would fail."""
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
