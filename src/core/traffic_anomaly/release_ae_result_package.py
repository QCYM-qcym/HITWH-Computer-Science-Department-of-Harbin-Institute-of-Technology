"""Fixed three-member AE storage, without upstream or model execution.

Signatures detect observed changes, not atomic snapshots or crash durability.
Failed exclusive saves retain residue, possibly a complete loadable package.
"""
from __future__ import annotations

import os
from pathlib import Path

from .release_ae_result_contract import (
    ReleaseAEResultIdentity, ReleaseAEResultPackage, ReleaseAEResultPackageError,
    PACKAGE_MEMBER_NAMES, PACKAGE_MEMBER_BYTE_LIMITS, PACKAGE_TOTAL_BYTE_LIMIT,
    encode_release_ae_result_package, decode_release_ae_result_package,
)

_NATIVE_PATH = type(Path())
_LIMITS = dict(PACKAGE_MEMBER_BYTE_LIMITS)
_READ_ORDER = ('COMPLETE.json', 'manifest.json', 'result.json')


def _fail(code):
    raise ReleaseAEResultPackageError(code) from None


def _getter_failure(error):
    kind = type(error)
    if issubclass(kind, (KeyboardInterrupt, SystemExit)):
        raise error from None
    _fail('RESOURCE_LIMIT' if issubclass(kind, MemoryError) else 'PACKAGE_ERROR')


def _owned_failure(error):
    # Called only after exact owning-type admission. No foreign getters.
    try:
        code = error.code
    except BaseException as failure:
        _getter_failure(failure)
    _fail(code if type(code) is str else 'PACKAGE_ERROR')


def _raise_safe(error, io_code):
    kind = type(error)
    if issubclass(kind, (KeyboardInterrupt, SystemExit, MemoryError)):
        _getter_failure(error)
    if kind is ReleaseAEResultPackageError:
        _owned_failure(error)
    if issubclass(kind, OSError):
        _fail(io_code)
    if kind is ModuleNotFoundError:
        try:
            name = error.name
        except BaseException as failure:
            _getter_failure(failure)
        _fail('NUMERICAL_DEPENDENCY_UNAVAILABLE'
              if type(name) is str and name == 'numpy' else 'PACKAGE_ERROR')
    _fail('PACKAGE_ERROR')


def _path_call(name, *args, **kwargs):
    # Reuse only the four no-format path/stat primitives. Their module's
    # prepared inventory, codec, reads/writes and numerical functions are unused.
    # Import lazily so importing this module itself requires no NumPy.
    from .release_input_package import _lexical, _ancestors, _signature, _directory
    from .release_inputs import ReleaseInputPreparationError
    operations = dict(lexical=_lexical, ancestors=_ancestors,
                      signature=_signature, directory=_directory)
    try:
        return operations[name](*args, **kwargs)
    except BaseException as error:
        if type(error) is ReleaseInputPreparationError:
            _owned_failure(error)
        raise


def _path(value):
    if type(value) not in (str, _NATIVE_PATH):
        _fail('INVALID_PACKAGE_ARGUMENTS')
    return _path_call('lexical', value)


def _directory(path, expected=None):
    try:
        return _path_call('directory', path, expected)
    except FileNotFoundError:
        if expected is not None:
            _fail('PACKAGE_CHANGED')
        raise


def _observed_signature(path):
    try:
        return _path_call('signature', path.lstat())
    except FileNotFoundError:
        _fail('PACKAGE_CHANGED')


def _close(resource, primary):
    """Keep the first failure actually received by this new orchestration."""
    try:
        resource.close()
    except BaseException as error:
        if primary is None:
            primary = error
    return primary


def _inventory(directory, directory_identity, expected=None):
    """Bound and validate the entire observed set before opening a member."""
    _directory(directory, directory_identity)
    wanted = set(PACKAGE_MEMBER_NAMES) if expected is None else set(expected)
    changed_code = 'INVALID_PACKAGE' if expected is None else 'PACKAGE_CHANGED'
    names, count, primary = set(), 0, None
    entries = os.scandir(directory)
    try:
        for entry in entries:
            count += 1
            if (count > len(PACKAGE_MEMBER_NAMES) or entry.name not in PACKAGE_MEMBER_NAMES
                    or entry.name in names):
                _fail(changed_code)
            names.add(entry.name)
        if names != wanted:
            _fail(changed_code)
    except BaseException as error:
        primary = error
    finally:
        primary = _close(entries, primary)
    if primary is not None:
        raise primary from None
    signatures, entities, total = {}, set(), 0
    for name in PACKAGE_MEMBER_NAMES:
        if name not in names:
            continue
        signature = _observed_signature(directory / name)
        if signature[:2] in entities:
            _fail('INVALID_PACKAGE_PATH')
        entities.add(signature[:2])
        total += signature[4]
        if signature[4] > _LIMITS[name] or total > PACKAGE_TOTAL_BYTE_LIMIT:
            _fail('RESOURCE_LIMIT')
        signatures[name] = signature
    if expected is not None and signatures != expected:
        _fail('PACKAGE_CHANGED')
    _directory(directory, directory_identity)
    return signatures


def _read(directory, directory_identity, name, expected, remaining):
    """One bounded read from one handle; retain its exact bytes for decoding."""
    path = directory / name
    _directory(directory, directory_identity)
    if _observed_signature(path) != expected:
        _fail('PACKAGE_CHANGED')
    limit = min(_LIMITS[name], remaining)
    stream = path.open('rb')
    primary, payload = None, None
    try:
        if _path_call('signature', os.fstat(stream.fileno())) != expected:
            _fail('PACKAGE_CHANGED')
        payload = stream.read(limit + 1)
        if _path_call('signature', os.fstat(stream.fileno())) != expected:
            _fail('PACKAGE_CHANGED')
        if type(payload) is not bytes:
            _fail('INPUT_UNAVAILABLE')
        if len(payload) > limit:
            _fail('RESOURCE_LIMIT')
        if len(payload) != expected[4]:
            _fail('PACKAGE_CHANGED')
    except BaseException as error:
        primary = error
    finally:
        primary = _close(stream, primary)
    if primary is not None:
        raise primary from None
    _directory(directory, directory_identity)
    if _observed_signature(path) != expected:
        _fail('PACKAGE_CHANGED')
    _directory(directory, directory_identity)
    return payload


def _write(directory, directory_identity, name, payload, owned, remaining):
    """Exclusive write/flush/close, then exactly one retained readback."""
    _inventory(directory, directory_identity, owned)
    if len(payload) > min(_LIMITS[name], remaining):
        _fail('RESOURCE_LIMIT')
    path = directory / name
    stream = path.open('xb')
    primary, written = None, None
    try:
        opened = _path_call('signature', os.fstat(stream.fileno()))
        if opened != _observed_signature(path):
            _fail('PACKAGE_CHANGED')
        _directory(directory, directory_identity)
        count = stream.write(payload)
        if type(count) is not int or count != len(payload):
            _fail('OUTPUT_ERROR')
        stream.flush()
        written = _path_call('signature', os.fstat(stream.fileno()))
        if (written[:4] != opened[:4] or written[4] != len(payload)
                or written != _observed_signature(path)):
            _fail('PACKAGE_CHANGED')
    except BaseException as error:
        primary = error
    finally:
        primary = _close(stream, primary)
    if primary is not None:
        raise primary from None
    _directory(directory, directory_identity)
    if _observed_signature(path) != written:
        _fail('PACKAGE_CHANGED')
    owned[name] = written
    _inventory(directory, directory_identity, owned)
    actual = _read(directory, directory_identity, name, written, remaining)
    if actual != payload:
        _fail('INTEGRITY_MISMATCH')
    _inventory(directory, directory_identity, owned)
    return actual


def save_release_ae_result_package(
        package: ReleaseAEResultPackage, output_directory: Path | str,
) -> ReleaseAEResultIdentity:
    """Validate before creation; keep all residue on every failure."""
    try:
        directory = _path(output_directory)
        encoded = encode_release_ae_result_package(package)
        _path_call('ancestors', directory)
        try:
            directory.mkdir()
        except FileExistsError:
            _fail('OUTPUT_EXISTS')
        directory_identity = _directory(directory)
        retained, owned, remaining = {}, {}, PACKAGE_TOTAL_BYTE_LIMIT
        for name, payload in encoded:
            retained[name] = _write(directory, directory_identity, name, payload, owned, remaining)
            remaining -= len(retained[name])
        _inventory(directory, directory_identity, owned)
        loaded = decode_release_ae_result_package(retained)
        _inventory(directory, directory_identity, owned)
        return loaded.identity
    except BaseException as error:
        _raise_safe(error, 'OUTPUT_ERROR')


def load_release_ae_result_package(directory: Path | str) -> ReleaseAEResultPackage:
    """Load only the movable package's exact three members, once each."""
    try:
        directory = _path(directory)
        directory_identity = _directory(directory)
        signatures = _inventory(directory, directory_identity)
        retained, remaining = {}, PACKAGE_TOTAL_BYTE_LIMIT
        for name in _READ_ORDER:
            retained[name] = _read(directory, directory_identity, name, signatures[name], remaining)
            remaining -= len(retained[name])
        _inventory(directory, directory_identity, signatures)
        loaded = decode_release_ae_result_package(retained)
        _inventory(directory, directory_identity, signatures)
        return loaded
    except BaseException as error:
        _raise_safe(error, 'INPUT_UNAVAILABLE')
