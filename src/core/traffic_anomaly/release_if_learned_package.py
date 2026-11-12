"""Fixed learned-state disk protocol using only stdlib and the learned codec.

Signatures detect observable changes, not atomic snapshots or crash durability.
Failed saves preserve residue, including potentially complete loadable packages.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat

from .release_if_learned_contract import (
    ReleaseIFLearnedError, ReleaseIFLearnedPackage, ReleaseIFLearnedReference,
    PACKAGE_MEMBER_NAMES, PACKAGE_MEMBER_BYTE_LIMITS, PACKAGE_TOTAL_BYTE_LIMIT,
    encode_release_if_learned_package, decode_release_if_learned_package,
)

_NATIVE_PATH = type(Path())
_LIMITS = dict(PACKAGE_MEMBER_BYTE_LIMITS)
_READ_ORDER = ('COMPLETE.json', 'manifest.json', 'numeric-state.json')
_OS_ERRORS = frozenset((OSError, BlockingIOError, ChildProcessError,
    ConnectionError, BrokenPipeError, ConnectionAbortedError,
    ConnectionRefusedError, ConnectionResetError, FileExistsError,
    FileNotFoundError, InterruptedError, IsADirectoryError, NotADirectoryError,
    PermissionError, ProcessLookupError, TimeoutError))


def _fail(code):
    raise ReleaseIFLearnedError(code) from None


@contextmanager
def _disk_scope(code):
    """Map only builtin filesystem errors within explicit disk operations."""
    try:
        yield
    except MemoryError:
        _fail('RESOURCE_LIMIT')
    except Exception as error:
        if type(error) in _OS_ERRORS:
            _fail(code)
        raise


def _lexical(value: object) -> Path:
    if type(value) not in (str, _NATIVE_PATH):
        _fail('INVALID_LEARNED_ARGUMENTS')
    raw = str(value)
    if not raw or '\0' in raw or raw.startswith(('\\\\', '//')):
        _fail('INVALID_PACKAGE_PATH')
    path = Path(raw)
    if not path.is_absolute() or '..' in path.parts:
        _fail('INVALID_PACKAGE_PATH')
    if os.name == 'nt':
        if (len(path.drive) != 2 or not path.drive[0].isascii()
                or not path.drive[0].isalpha() or path.drive[1] != ':'
                or any(':' in part or os.path.isreserved(part) for part in path.parts[1:])):
            _fail('INVALID_PACKAGE_PATH')
    return path


def _signature(info: os.stat_result, *, directory: bool = False) -> tuple[int, ...]:
    if (getattr(info, 'st_file_attributes', 0) & 0x400
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or not directory and info.st_nlink != 1):
        _fail('INVALID_PACKAGE_PATH')
    identity = (info.st_dev, info.st_ino, info.st_mode, getattr(info, 'st_file_attributes', 0))
    return identity if directory else identity + (info.st_size, info.st_mtime_ns, info.st_nlink)


def _ancestors(path: Path) -> None:
    for parent in reversed(path.parents):
        _signature(parent.lstat(), directory=True)


def _directory(path: Path, expected: tuple[int, ...] | None = None) -> tuple[int, ...]:
    try:
        _ancestors(path)
        current = _signature(path.lstat(), directory=True)
    except FileNotFoundError as error:
        if type(error) is FileNotFoundError and expected is not None:
            _fail('PACKAGE_CHANGED')
        raise
    if expected is not None and current != expected:
        _fail('PACKAGE_CHANGED')
    return current


def _inventory(directory, identity, expected=None):
    try:
        _directory(directory, identity)
        names = set()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.name not in PACKAGE_MEMBER_NAMES or len(names) >= len(PACKAGE_MEMBER_NAMES):
                        _fail('INVALID_LEARNED_PACKAGE' if expected is None else 'PACKAGE_CHANGED')
                    names.add(entry.name)
        except FileNotFoundError as error:
            if type(error) is FileNotFoundError:
                _fail('PACKAGE_CHANGED')
            raise
        if names != (set(PACKAGE_MEMBER_NAMES) if expected is None else set(expected)):
            _fail('INVALID_LEARNED_PACKAGE' if expected is None else 'PACKAGE_CHANGED')
        found, entities, total = {}, set(), 0
        for name in PACKAGE_MEMBER_NAMES:
            if name not in names:
                continue
            signature = _signature((directory / name).lstat())
            if signature[:2] in entities:
                _fail('INVALID_PACKAGE_PATH')
            entities.add(signature[:2])
            total += signature[4]
            if signature[4] > _LIMITS[name] or total > PACKAGE_TOTAL_BYTE_LIMIT:
                _fail('RESOURCE_LIMIT')
            found[name] = signature
        if expected is not None and found != expected:
            _fail('PACKAGE_CHANGED')
        _directory(directory, identity)
        return found
    except FileNotFoundError as error:
        if type(error) is FileNotFoundError and expected is not None:
            _fail('PACKAGE_CHANGED')
        raise


def _read(directory, identity, name, signature, remaining, *, saving=False):
    try:
        _directory(directory, identity)
        path = directory / name
        if _signature(path.lstat()) != signature:
            _fail('PACKAGE_CHANGED')
        limit = min(_LIMITS[name], remaining)
        with path.open('rb') as stream:
            if _signature(os.fstat(stream.fileno())) != signature:
                _fail('PACKAGE_CHANGED')
            payload = stream.read(limit + 1)
            if _signature(os.fstat(stream.fileno())) != signature:
                _fail('PACKAGE_CHANGED')
        _directory(directory, identity)
        if _signature(path.lstat()) != signature:
            _fail('PACKAGE_CHANGED')
        if type(payload) is not bytes:
            _fail('OUTPUT_ERROR' if saving else 'INPUT_UNAVAILABLE')
        if len(payload) > limit:
            _fail('RESOURCE_LIMIT')
        if len(payload) != signature[4]:
            _fail('PACKAGE_CHANGED')
        _directory(directory, identity)
        return payload
    except FileNotFoundError as error:
        if type(error) is FileNotFoundError:
            _fail('PACKAGE_CHANGED')
        raise


def load_release_if_learned_package(directory: Path) -> ReleaseIFLearnedPackage:
    """Load exactly three checked bounded byte strings without numerical work."""
    try:
        directory = _lexical(directory)
        with _disk_scope('INPUT_UNAVAILABLE'):
            identity = _directory(directory)
            signatures = _inventory(directory, identity)
            members, remaining = {}, PACKAGE_TOTAL_BYTE_LIMIT
            for name in _READ_ORDER:
                members[name] = _read(directory, identity, name, signatures[name], remaining)
                remaining -= len(members[name])
            _inventory(directory, identity, signatures)
        result = decode_release_if_learned_package(members)
        with _disk_scope('INPUT_UNAVAILABLE'):
            _inventory(directory, identity, signatures)
        return result
    except MemoryError:
        _fail('RESOURCE_LIMIT')
    except Exception as error:
        if type(error) is ReleaseIFLearnedError:
            raise
        _fail('LEARNED_ERROR')


def _write(directory, identity, name, payload, owned, remaining):
    _inventory(directory, identity, owned)
    if len(payload) > _LIMITS[name] or len(payload) > remaining:
        _fail('RESOURCE_LIMIT')
    path = directory / name
    try:
        with path.open('xb') as stream:
            opened = _signature(os.fstat(stream.fileno()))
            if opened != _signature(path.lstat()):
                _fail('PACKAGE_CHANGED')
            _directory(directory, identity)
            count = stream.write(payload)
            if type(count) is not int or count != len(payload):
                _fail('OUTPUT_ERROR')
            stream.flush()
            written = _signature(os.fstat(stream.fileno()))
            if (written[:4] != opened[:4] or written[4] != len(payload)
                    or written != _signature(path.lstat())):
                _fail('PACKAGE_CHANGED')
    except FileNotFoundError as error:
        if type(error) is FileNotFoundError:
            _fail('PACKAGE_CHANGED')
        raise
    _directory(directory, identity)
    try:
        current = _signature(path.lstat())
    except FileNotFoundError as error:
        if type(error) is FileNotFoundError:
            _fail('PACKAGE_CHANGED')
        raise
    if current != written:
        _fail('PACKAGE_CHANGED')
    owned[name] = written
    _inventory(directory, identity, owned)
    actual = _read(directory, identity, name, written, remaining, saving=True)
    if actual != payload:
        _fail('INTEGRITY_MISMATCH')
    _inventory(directory, identity, owned)
    return actual


def save_release_if_learned_package(
    package: ReleaseIFLearnedPackage, output_directory: Path,
) -> ReleaseIFLearnedReference:
    """Validate before exclusive creation; preserve every failed-save residue."""
    try:
        encoded = encode_release_if_learned_package(package)
        directory = _lexical(output_directory)
        with _disk_scope('OUTPUT_ERROR'):
            _ancestors(directory)
            try:
                directory.mkdir()
            except FileExistsError as error:
                if type(error) is FileExistsError:
                    _fail('OUTPUT_EXISTS')
                raise
            identity = _directory(directory)
            members, owned, remaining = {}, {}, PACKAGE_TOTAL_BYTE_LIMIT
            for name, payload in encoded:
                members[name] = _write(directory, identity, name, payload, owned, remaining)
                remaining -= len(members[name])
            _inventory(directory, identity, owned)
        result = decode_release_if_learned_package(members)
        with _disk_scope('OUTPUT_ERROR'):
            _inventory(directory, identity, owned)
        return result.identity
    except MemoryError:
        _fail('RESOURCE_LIMIT')
    except Exception as error:
        if type(error) is ReleaseIFLearnedError:
            raise
        _fail('LEARNED_ERROR')
