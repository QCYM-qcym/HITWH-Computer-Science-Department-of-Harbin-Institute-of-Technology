"""Bounded saved-result disk protocol, without upstream access or model work.

Signatures detect observable changes; they are not atomic snapshots. Failed
saves preserve residue, which may include an independently loadable package.
"""
from __future__ import annotations

from pathlib import Path
import os

from .release_if_result_contract import (
    ReleaseIFResultIdentity, ReleaseIFResultPackage, ReleaseIFResultPackageError,
    encode_release_if_result_package, decode_release_if_result_package,
    PACKAGE_MEMBER_NAMES, PACKAGE_MEMBER_BYTE_LIMITS, PACKAGE_TOTAL_BYTE_LIMIT,
)
from .release_inputs import ReleaseInputPreparationError
# These helpers inspect only paths/stat results and have no format constants.
# The prepared package's inventory/read/write helpers remain format-specific.
from .release_input_package import _lexical, _ancestors, _signature, _directory

_LIMITS = dict(PACKAGE_MEMBER_BYTE_LIMITS)
_READ_ORDER = ('COMPLETE.json', 'manifest.json', 'result.json')


def _fail(code):
    raise ReleaseIFResultPackageError(code) from None


def _inventory(directory, identity, expected=None):
    """Inspect the fixed three-member set and all budgets before any open."""
    _directory(directory, identity)
    names = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.name not in PACKAGE_MEMBER_NAMES or len(names) >= len(PACKAGE_MEMBER_NAMES):
                _fail('INVALID_PACKAGE' if expected is None else 'PACKAGE_CHANGED')
            names.add(entry.name)
    if names != (set(PACKAGE_MEMBER_NAMES) if expected is None else set(expected)):
        _fail('INVALID_PACKAGE' if expected is None else 'PACKAGE_CHANGED')
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


def _read(directory, identity, name, signature, remaining):
    """Read one checked handle once, retaining exactly those bounded bytes."""
    try:
        path = directory / name
        _directory(directory, identity)
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
            _fail('INPUT_UNAVAILABLE')
        if len(payload) > limit:
            _fail('RESOURCE_LIMIT')
        if len(payload) != signature[4]:
            _fail('PACKAGE_CHANGED')
        _directory(directory, identity)
        return payload
    except (ReleaseIFResultPackageError, ReleaseInputPreparationError):
        raise
    except Exception:
        _fail('INPUT_UNAVAILABLE')


def load_release_if_result_package(directory: Path) -> ReleaseIFResultPackage:
    """Decode exactly the bytes read from the three fixed members."""
    try:
        directory = _lexical(directory)
        identity = _directory(directory)
        signatures = _inventory(directory, identity)
        members, remaining = {}, PACKAGE_TOTAL_BYTE_LIMIT
        for name in _READ_ORDER:
            members[name] = _read(directory, identity, name, signatures[name], remaining)
            remaining -= len(members[name])
        _inventory(directory, identity, signatures)
        result = decode_release_if_result_package(members)
        _inventory(directory, identity, signatures)
        return result
    except ReleaseIFResultPackageError:
        raise
    except ReleaseInputPreparationError as error:
        _fail(error.code)
    except Exception:
        _fail('INPUT_UNAVAILABLE')


def _write(directory, identity, name, payload, owned, remaining):
    """Exclusively write, flush and check the member before its one readback."""
    _inventory(directory, identity, owned)
    path = directory / name
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
    _directory(directory, identity)
    if _signature(path.lstat()) != written:
        _fail('PACKAGE_CHANGED')
    owned[name] = written
    _inventory(directory, identity, owned)
    actual = _read(directory, identity, name, written, remaining)
    if actual != payload:
        _fail('INTEGRITY_MISMATCH')
    _inventory(directory, identity, owned)
    return actual


def save_release_if_result_package(
    package: ReleaseIFResultPackage, output_directory: Path,
) -> ReleaseIFResultIdentity:
    """Validate before exclusive creation; never overwrite or remove residue."""
    encoded = encode_release_if_result_package(package)
    try:
        directory = _lexical(output_directory)
        _ancestors(directory)
        try:
            directory.mkdir()
        except FileExistsError:
            _fail('OUTPUT_EXISTS')
        identity = _directory(directory)
        members, owned, remaining = {}, {}, PACKAGE_TOTAL_BYTE_LIMIT
        for name, payload in encoded:
            members[name] = _write(directory, identity, name, payload, owned, remaining)
            remaining -= len(members[name])
        _inventory(directory, identity, owned)
        result = decode_release_if_result_package(members)
        _inventory(directory, identity, owned)
        return result.identity
    except ReleaseIFResultPackageError:
        raise
    except ReleaseInputPreparationError as error:
        _fail(error.code)
    except Exception:
        _fail('OUTPUT_ERROR')
