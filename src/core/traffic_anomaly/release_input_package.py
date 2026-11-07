"""Fixed prepared-input I/O, without upstream access or numerical execution.

Signatures detect observable changes, not atomic snapshots or crash durability.
Failed saves preserve residue, possibly including an independently loadable package.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from .release_inputs import (
    PACKAGE_MEMBER_NAMES, PACKAGE_MEMBER_BYTE_LIMITS, PACKAGE_TOTAL_BYTE_LIMIT,
    ReleasePreparedInputs, ReleaseInputPreparationError, ReleaseInputIdentity,
    decode_release_input_package, encode_release_input_package,
)

_LIMITS = dict(PACKAGE_MEMBER_BYTE_LIMITS)
_READ_ORDER = ('COMPLETE.json', 'manifest.json', *PACKAGE_MEMBER_NAMES[:3])


def _fail(code):
    raise ReleaseInputPreparationError(code) from None


def _lexical(value):
    if not isinstance(value, (str, Path)):
        _fail('INVALID_PACKAGE_ARGUMENTS')
    raw = str(value)
    if not raw or '\0' in raw or raw.startswith(('\\\\', '//')):
        _fail('INVALID_PACKAGE_PATH')
    path = Path(raw)
    if not path.is_absolute() or '..' in path.parts:
        _fail('INVALID_PACKAGE_PATH')
    if os.name == 'nt':
        if (len(path.drive) != 2 or path.drive[1] != ':'
                or any(':' in part or os.path.isreserved(part) for part in path.parts[1:])):
            _fail('INVALID_PACKAGE_PATH')
    return path


def _signature(info, *, directory=False):
    if (getattr(info, 'st_file_attributes', 0) & 0x400
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or not directory and info.st_nlink != 1):
        _fail('INVALID_PACKAGE_PATH')
    identity = (info.st_dev, info.st_ino, info.st_mode, getattr(info, 'st_file_attributes', 0))
    return identity if directory else identity + (info.st_size, info.st_mtime_ns, info.st_nlink)


def _ancestors(path):
    for parent in reversed(path.parents):
        _signature(parent.lstat(), directory=True)


def _directory(path, expected=None):
    _ancestors(path)
    current = _signature(path.lstat(), directory=True)
    if expected is not None and current != expected:
        _fail('PACKAGE_CHANGED')
    return current


def _inventory(directory, identity, expected=None):
    _directory(directory, identity)
    names = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            names.add(entry.name)
            if len(names) > len(PACKAGE_MEMBER_NAMES) or entry.name not in PACKAGE_MEMBER_NAMES:
                _fail('INVALID_PACKAGE' if expected is None else 'PACKAGE_CHANGED')
    wanted = set(PACKAGE_MEMBER_NAMES) if expected is None else set(expected)
    if names != wanted:
        _fail('INVALID_PACKAGE' if expected is None else 'PACKAGE_CHANGED')
    signatures, seen, total = {}, set(), 0
    for name in PACKAGE_MEMBER_NAMES:
        if name not in names:
            continue
        signature = _signature((directory / name).lstat())
        if signature[:2] in seen:
            _fail('INVALID_PACKAGE_PATH')
        seen.add(signature[:2])
        size = signature[4]
        total += size
        if size > _LIMITS[name] or total > PACKAGE_TOTAL_BYTE_LIMIT:
            _fail('RESOURCE_LIMIT')
        signatures[name] = signature
    if expected is not None and signatures != expected:
        _fail('PACKAGE_CHANGED')
    _directory(directory, identity)
    return signatures


def _read(directory, identity, name, expected, remaining):
    _directory(directory, identity)
    path = directory / name
    if _signature(path.lstat()) != expected:
        _fail('PACKAGE_CHANGED')
    limit = min(_LIMITS[name], remaining)
    with path.open('rb') as stream:
        if _signature(os.fstat(stream.fileno())) != expected:
            _fail('PACKAGE_CHANGED')
        payload = stream.read(limit + 1)
        if _signature(os.fstat(stream.fileno())) != expected:
            _fail('PACKAGE_CHANGED')
    _directory(directory, identity)
    if _signature(path.lstat()) != expected:
        _fail('PACKAGE_CHANGED')
    if type(payload) is not bytes:
        _fail('INPUT_UNAVAILABLE')
    if len(payload) > limit:
        _fail('RESOURCE_LIMIT')
    if len(payload) != expected[4]:
        _fail('PACKAGE_CHANGED')
    _directory(directory, identity)
    return payload


def load_release_input_package(directory: Path) -> ReleasePreparedInputs:
    """Read five ordinary single-link files once; decode those exact bytes."""
    try:
        directory = _lexical(directory)
        identity = _directory(directory)
        signatures = _inventory(directory, identity)
        members, remaining = {}, PACKAGE_TOTAL_BYTE_LIMIT
        for name in _READ_ORDER:
            payload = _read(directory, identity, name, signatures[name], remaining)
            remaining -= len(payload)
            members[name] = payload
        _inventory(directory, identity, signatures)
        result = decode_release_input_package(members)
        _inventory(directory, identity, signatures)
        return result
    except ReleaseInputPreparationError:
        raise
    except Exception:
        _fail('INPUT_UNAVAILABLE')


def _write(directory, identity, name, payload, owned, remaining):
    _inventory(directory, identity, owned)
    path = directory / name
    with path.open('xb') as stream:
        before = _signature(os.fstat(stream.fileno()))
        if before != _signature(path.lstat()):
            _fail('PACKAGE_CHANGED')
        _directory(directory, identity)
        count = stream.write(payload)
        if type(count) is not int or count != len(payload):
            _fail('OUTPUT_ERROR')
        stream.flush()
        after = _signature(os.fstat(stream.fileno()))
        if after[:4] != before[:4] or after[4] != len(payload) or after != _signature(path.lstat()):
            _fail('PACKAGE_CHANGED')
    _directory(directory, identity)
    if _signature(path.lstat()) != after:
        _fail('PACKAGE_CHANGED')
    owned[name] = after
    _inventory(directory, identity, owned)
    actual = _read(directory, identity, name, after, remaining)
    if actual != payload:
        _fail('INTEGRITY_MISMATCH')
    _inventory(directory, identity, owned)
    return actual


def save_release_input_package(
    saved: ReleasePreparedInputs, output_directory: Path,
) -> ReleaseInputIdentity:
    """Validate before exclusive mkdir; never overwrite, recover or clean residue."""
    # W1 validates saved identity, structure, semantics and byte budgets.
    encoded = encode_release_input_package(saved)
    try:
        directory = _lexical(output_directory)
        _ancestors(directory)
        try:
            directory.mkdir()
        except FileExistsError:
            _fail('OUTPUT_EXISTS')
        identity = _directory(directory)
        owned, members, remaining = {}, {}, PACKAGE_TOTAL_BYTE_LIMIT
        for name, payload in encoded:
            members[name] = _write(directory, identity, name, payload, owned, remaining)
            remaining -= len(members[name])
        _inventory(directory, identity, owned)
        result = decode_release_input_package(members)
        _inventory(directory, identity, owned)
        return result.identity
    except ReleaseInputPreparationError:
        raise
    except Exception:
        _fail('OUTPUT_ERROR')
