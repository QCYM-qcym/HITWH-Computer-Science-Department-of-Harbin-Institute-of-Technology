"""Real saved-result bytes and faulted real filesystem handles; no estimator."""
from dataclasses import replace
import hashlib
import importlib
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from traffic_anomaly.release_if_result_contract import (
    ReleaseIFResultPackageError, decode_release_if_result_package,
)
from .release_if_result_cases import reference_members


def storage():
    source = Path(__file__).parents[2] / 'src/core/traffic_anomaly/release_if_result_package.py'
    assert source.is_file(), 'saved-result disk implementation is required'
    return importlib.import_module('traffic_anomaly.release_if_result_package')


def saved():
    return decode_release_if_result_package(reference_members())


def rejected(code, operation):
    with pytest.raises(ReleaseIFResultPackageError) as caught:
        operation()
    assert caught.value.code in ((code,) if isinstance(code, str) else code)
    assert str(caught.value) == caught.value.code
    assert caught.value.__suppress_context__


def test_real_roundtrip_writes_independent_bytes_and_reopens_copy(tmp_path):
    module = storage()
    package, target = saved(), tmp_path / 'result'
    before = repr(package)
    identity = module.save_release_if_result_package(package, target)
    assert identity == package.identity
    assert identity.manifest_sha256 == hashlib.sha256(reference_members()['manifest.json']).hexdigest()
    assert {p.name: p.read_bytes() for p in target.iterdir()} == reference_members()
    assert repr(package) == before
    copied = tmp_path / 'independently-moved'
    shutil.copytree(target, copied)
    target.rename(tmp_path / 'original-moved-away')
    loaded = module.load_release_if_result_package(copied)
    assert loaded == package
    assert loaded.result.preprocessing_fit_indices[0] == 30
    assert loaded.result.scored_mask[30] is False
    assert loaded.result.scores[31] == 0. and loaded.result.predictions[31] is False
    assert loaded.load_report.source_authentication == 'NOT_AUTHENTICATED'
    assert loaded.load_report.model_execution == 'NOT_AUTHENTICATED'


def test_invalid_package_rejected_before_creating_directory(tmp_path):
    module = storage()
    target = tmp_path / 'never-created'
    rejected('INVALID_PACKAGE_ARGUMENTS', lambda: module.save_release_if_result_package(None, target))
    broken = replace(saved(), identity=replace(saved().identity, context_sha256='0' * 64))
    rejected('INTEGRITY_MISMATCH', lambda: module.save_release_if_result_package(broken, target))
    assert not target.exists()


@pytest.mark.parametrize('nonempty', [False, True])
def test_existing_target_is_never_overwritten(tmp_path, nonempty):
    module = storage()
    target = tmp_path / 'already-owned'
    target.mkdir()
    if nonempty:
        (target / 'owner').write_bytes(b'keep')
    before = target.stat()
    rejected('OUTPUT_EXISTS', lambda: module.save_release_if_result_package(saved(), target))
    after = target.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == ({'owner': b'keep'} if nonempty else {})


def test_member_write_order_and_one_read_each_in_reverse_order(tmp_path, monkeypatch):
    module = storage()
    package, target = saved(), tmp_path / 'package'
    observed = []
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        observed.append((path.name, mode))
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    module.save_release_if_result_package(package, target)
    assert [name for name, mode in observed if mode == 'xb'] == ['result.json', 'manifest.json', 'COMPLETE.json']
    observed.clear()
    assert module.load_release_if_result_package(target) == package
    assert observed == [('COMPLETE.json', 'rb'), ('manifest.json', 'rb'), ('result.json', 'rb')]


@pytest.fixture
def disk(tmp_path):
    directory = tmp_path / 'input'
    directory.mkdir()
    for name, payload in reference_members().items():
        (directory / name).write_bytes(payload)
    return directory


class Stream:
    """Inject one failure while retaining a real, closeable OS file handle."""
    def __init__(self, raw, **hooks):
        self.raw, self.hooks = raw, hooks
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.raw.close()
        if 'close' in self.hooks:
            self.hooks['close']()
    def fileno(self):
        return self.raw.fileno()
    def read(self, size=-1):
        return self.hooks['read'](self.raw, size) if 'read' in self.hooks else self.raw.read(size)
    def write(self, payload):
        return self.hooks['write'](self.raw, payload) if 'write' in self.hooks else self.raw.write(payload)
    def flush(self):
        return self.hooks['flush'](self.raw) if 'flush' in self.hooks else self.raw.flush()


def intercept(monkeypatch, directory, name, wanted_mode, factory):
    original, handles = Path.open, []
    def opened(path, mode='r', *args, **kwargs):
        raw = original(path, mode, *args, **kwargs)
        if path == directory / name and mode == wanted_mode:
            handles.append(raw)
            return factory(raw)
        return raw
    monkeypatch.setattr(Path, 'open', opened)
    return handles


@pytest.mark.parametrize('operation', ['load', 'save'])
@pytest.mark.parametrize('value', [None, 1, False, b'bytes', object()])
def test_invalid_path_types_have_safe_argument_errors(tmp_path, operation, value):
    module = storage()
    rejected('INVALID_PACKAGE_ARGUMENTS', lambda:
        module.load_release_if_result_package(value) if operation == 'load' else
        module.save_release_if_result_package(saved(), value))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('operation', ['load', 'save'])
@pytest.mark.parametrize('value', ['', 'relative', 'relative/../package', 'bad\0path',
    '\\package', pytest.param('/package', marks=pytest.mark.skipif(os.name != 'nt',
        reason='Windows root-relative path; POSIX absolute paths use tmp_path')),
    'C:package', '\\\\server\\share\\package',
    '\\\\?\\C:\\package', 'C:\\package:stream', 'C:\\NUL\\package', 'C:\\parent\\..\\package'])
def test_unsafe_path_is_rejected_without_io(tmp_path, monkeypatch, operation, value):
    module = storage()
    attempts = []
    original = Path.open
    def opened(*args, **kwargs):
        attempts.append('open')
        return original(*args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    rejected('INVALID_PACKAGE_PATH', lambda:
        module.load_release_if_result_package(value) if operation == 'load' else
        module.save_release_if_result_package(saved(), value))
    assert attempts == []


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'nested', 'result_limit', 'manifest_limit', 'complete_limit'])
def test_inventory_and_size_are_checked_before_open(disk, monkeypatch, mutation):
    module = storage()
    if mutation == 'missing':
        (disk / 'COMPLETE.json').unlink()
    elif mutation == 'extra':
        (disk / 'fourth').write_bytes(b'x')
    elif mutation == 'nested':
        (disk / 'result.json').unlink()
        (disk / 'result.json').mkdir()
    else:
        name, size = {'result_limit': ('result.json', 1048577),
            'manifest_limit': ('manifest.json', 65537), 'complete_limit': ('COMPLETE.json', 4097)}[mutation]
        with (disk / name).open('wb') as stream:
            stream.truncate(size)
    attempts = []
    original = Path.open
    def opened(*args, **kwargs):
        attempts.append('open')
        return original(*args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    expected = 'RESOURCE_LIMIT' if mutation.endswith('limit') else ('INVALID_PACKAGE', 'INVALID_PACKAGE_PATH')
    rejected(expected, lambda: module.load_release_if_result_package(disk))
    assert attempts == []


def test_hardlink_member_is_rejected_before_read(disk, tmp_path, monkeypatch):
    module = storage()
    os.link(disk / 'result.json', tmp_path / 'same-file')
    attempts = []
    original = Path.open
    def opened(*args, **kwargs):
        attempts.append('open')
        return original(*args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    rejected('INVALID_PACKAGE_PATH', lambda: module.load_release_if_result_package(disk))
    assert attempts == []


@pytest.mark.parametrize('kind', ['member', 'directory', 'parent'])
def test_real_symlink_paths_are_rejected(disk, tmp_path, kind):
    module = storage()
    if kind == 'member':
        original = tmp_path / 'original-result'
        (disk / 'result.json').rename(original)
        link, destination, is_directory = disk / 'result.json', original, False
        input_path = disk
    else:
        link, destination, is_directory = tmp_path / 'linked', disk, True
        input_path = link
        if kind == 'parent':
            child = disk / 'child'
            child.mkdir()
            for name, payload in reference_members().items():
                (child / name).write_bytes(payload)
            input_path = link / 'child'
    try:
        link.symlink_to(destination, target_is_directory=is_directory)
    except OSError as exc:
        pytest.skip(f'real symlink unavailable: errno={exc.errno} winerror={getattr(exc, "winerror", None)}')
    rejected('INVALID_PACKAGE_PATH', lambda: module.load_release_if_result_package(input_path))


def test_reparse_attribute_is_rejected(disk, monkeypatch):
    module = storage()
    original = Path.lstat
    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == disk / 'result.json':
            return SimpleNamespace(**{name: (0x400 if name == 'st_file_attributes' else getattr(info, name))
                for name in ('st_dev', 'st_ino', 'st_mode', 'st_file_attributes', 'st_size', 'st_mtime_ns', 'st_nlink')})
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    rejected('INVALID_PACKAGE_PATH', lambda: module.load_release_if_result_package(disk))


@pytest.mark.parametrize('change', ['member', 'directory', 'extra', 'grow'])
def test_observed_changes_during_read_are_rejected(disk, tmp_path, monkeypatch, change):
    module = storage()
    original_entity = tmp_path / 'original-entity'
    def mutate():
        if change == 'member':
            (disk / 'COMPLETE.json').rename(original_entity)
            (disk / 'COMPLETE.json').write_bytes(reference_members()['COMPLETE.json'])
        elif change == 'directory':
            disk.rename(original_entity)
            shutil.copytree(original_entity, disk)
        elif change == 'extra':
            (disk / 'extra').write_bytes(b'keep')
        else:
            with (disk / 'COMPLETE.json').open('ab') as stream:
                stream.write(b'x')
    handles = intercept(monkeypatch, disk, 'COMPLETE.json', 'rb', lambda raw: Stream(raw, close=mutate))
    rejected('PACKAGE_CHANGED', lambda: module.load_release_if_result_package(disk))
    assert all(handle.closed for handle in handles)
    assert disk.exists()
    if change in ('member', 'directory'):
        assert original_entity.exists()


@pytest.mark.parametrize('operation', ['load', 'save'])
def test_wrong_real_handle_is_rejected_before_access(disk, tmp_path, monkeypatch, operation):
    module = storage()
    other, target = tmp_path / 'other', tmp_path / 'output'
    other.write_bytes(b'untouched')
    original, handles = Path.open, []
    def opened(path, mode='r', *args, **kwargs):
        raw = original(path, mode, *args, **kwargs)
        if (operation == 'load' and path == disk / 'COMPLETE.json'
                or operation == 'save' and path == target / 'result.json'):
            raw.close()
            raw = original(other, 'r+b')
            handles.append(raw)
        return raw
    monkeypatch.setattr(Path, 'open', opened)
    rejected('PACKAGE_CHANGED', lambda:
        module.load_release_if_result_package(disk) if operation == 'load' else
        module.save_release_if_result_package(saved(), target))
    assert all(handle.closed for handle in handles)
    assert other.read_bytes() == b'untouched'


def test_short_read_of_stable_file_is_rejected(disk, monkeypatch):
    module = storage()
    handles = intercept(monkeypatch, disk, 'COMPLETE.json', 'rb',
        lambda raw: Stream(raw, read=lambda file, size: file.read(3)))
    rejected('PACKAGE_CHANGED', lambda: module.load_release_if_result_package(disk))
    assert all(handle.closed for handle in handles)


def test_read_growth_is_bounded_to_limit_plus_one(disk, monkeypatch):
    module = storage()
    observed = []
    def read(file, size):
        with (disk / 'COMPLETE.json').open('ab') as output:
            output.write(b'x' * 8192)
        value = file.read(size)
        observed.append((size, len(value)))
        return value
    intercept(monkeypatch, disk, 'COMPLETE.json', 'rb', lambda raw: Stream(raw, read=read))
    rejected(('PACKAGE_CHANGED', 'RESOURCE_LIMIT'), lambda: module.load_release_if_result_package(disk))
    assert observed == [(4097, 4097)]


def test_read_exception_has_safe_input_error(disk, monkeypatch):
    module = storage()
    def fail(*args):
        raise OSError('private path and payload')
    handles = intercept(monkeypatch, disk, 'COMPLETE.json', 'rb', lambda raw: Stream(raw, read=fail))
    rejected('INPUT_UNAVAILABLE', lambda: module.load_release_if_result_package(disk))
    assert all(handle.closed for handle in handles)


@pytest.mark.parametrize('member', ['result.json', 'manifest.json', 'COMPLETE.json'])
@pytest.mark.parametrize('stage', ['short_write', 'flush', 'close', 'readback'])
def test_save_failures_preserve_all_residue(tmp_path, monkeypatch, member, stage):
    module = storage()
    target = tmp_path / 'output'
    def fail(*args):
        raise OSError('private path and payload')
    hook = 'write' if stage == 'short_write' else 'read' if stage == 'readback' else stage
    function = (lambda file, payload: file.write(payload[:3])) if stage == 'short_write' else fail
    handles = intercept(monkeypatch, target, member, 'rb' if stage == 'readback' else 'xb',
        lambda raw: Stream(raw, **{hook: function}))
    rejected(('OUTPUT_ERROR', 'INPUT_UNAVAILABLE'), lambda: module.save_release_if_result_package(saved(), target))
    assert handles and all(handle.closed for handle in handles)
    assert target.is_dir() and (target / member).is_file()
    if member != 'COMPLETE.json':
        assert not (target / 'COMPLETE.json').exists()


@pytest.mark.parametrize('operation', ['load', 'save'])
def test_keyboard_interrupt_propagates_and_handles_close(disk, tmp_path, monkeypatch, operation):
    module = storage()
    target = tmp_path / 'interrupted'
    def stop(*args):
        raise KeyboardInterrupt
    handles = intercept(monkeypatch, disk if operation == 'load' else target,
        'COMPLETE.json' if operation == 'load' else 'result.json',
        'rb' if operation == 'load' else 'xb', lambda raw: Stream(raw, **{('read' if operation == 'load' else 'write'): stop}))
    with pytest.raises(KeyboardInterrupt):
        if operation == 'load':
            module.load_release_if_result_package(disk)
        else:
            module.save_release_if_result_package(saved(), target)
    assert handles and all(handle.closed for handle in handles)
    if operation == 'save':
        assert (target / 'result.json').exists() and not (target / 'COMPLETE.json').exists()


@pytest.mark.parametrize('operation', ['load', 'save'])
def test_final_signature_change_after_decode_is_rejected(disk, tmp_path, monkeypatch, operation):
    module = storage()
    target = tmp_path / 'output' if operation == 'save' else disk
    previous = tmp_path / 'previous-result'
    original = module.decode_release_if_result_package
    def decode(members):
        result = original(members)
        (target / 'result.json').rename(previous)
        (target / 'result.json').write_bytes(members['result.json'])
        return result
    with monkeypatch.context() as local:
        local.setattr(module, 'decode_release_if_result_package', decode)
        rejected('PACKAGE_CHANGED', lambda:
            module.load_release_if_result_package(target) if operation == 'load' else
            module.save_release_if_result_package(saved(), target))
    assert previous.exists()
    assert module.load_release_if_result_package(target) == saved()


def test_missing_parent_and_missing_input_have_safe_errors(tmp_path):
    module = storage()
    rejected('INPUT_UNAVAILABLE', lambda: module.load_release_if_result_package(tmp_path / 'missing'))
    rejected('OUTPUT_ERROR', lambda: module.save_release_if_result_package(saved(), tmp_path / 'missing' / 'output'))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('change', ['member', 'directory', 'extra', 'tamper'])
def test_save_change_is_detected_and_never_cleaned(tmp_path, monkeypatch, change):
    module = storage()
    target, previous = tmp_path / 'output', tmp_path / 'previous'
    def mutate():
        if change == 'member':
            (target / 'result.json').rename(previous)
            (target / 'result.json').write_bytes(b'other-owner')
        elif change == 'directory':
            target.rename(previous)
            target.mkdir()
            (target / 'owner').write_bytes(b'keep')
        elif change == 'extra':
            (target / 'owner').write_bytes(b'keep')
        else:
            path = target / 'result.json'
            before = path.stat()
            path.write_bytes(b'x' * before.st_size)
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    handles = intercept(monkeypatch, target, 'result.json', 'xb', lambda raw: Stream(raw, close=mutate))
    rejected(('PACKAGE_CHANGED', 'INTEGRITY_MISMATCH'), lambda: module.save_release_if_result_package(saved(), target))
    assert handles and all(handle.closed for handle in handles)
    assert target.is_dir() and not (target / 'COMPLETE.json').exists()
    if change in ('directory', 'extra'):
        assert (target / 'owner').read_bytes() == b'keep'
    if change in ('member', 'directory'):
        assert previous.exists()


def test_readback_exception_is_input_unavailable(tmp_path, monkeypatch):
    module = storage()
    target = tmp_path / 'output'
    def fail(*args):
        raise OSError('private readback location')
    with monkeypatch.context() as local:
        handles = intercept(local, target, 'result.json', 'rb', lambda raw: Stream(raw, read=fail))
        rejected('INPUT_UNAVAILABLE', lambda: module.save_release_if_result_package(saved(), target))
    assert handles and all(handle.closed for handle in handles)
    assert (target / 'result.json').read_bytes() == reference_members()['result.json']
    assert not (target / 'COMPLETE.json').exists()


def test_complete_package_survives_late_save_error(tmp_path, monkeypatch):
    module = storage()
    target = tmp_path / 'complete-but-failed'
    def fail_after_validation(members):
        decode_release_if_result_package(members)
        raise OSError('private late failure')
    with monkeypatch.context() as local:
        local.setattr(module, 'decode_release_if_result_package', fail_after_validation)
        rejected('OUTPUT_ERROR', lambda: module.save_release_if_result_package(saved(), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == reference_members()
    assert module.load_release_if_result_package(target) == saved()


def test_mkdir_race_keeps_other_owner_files(tmp_path, monkeypatch):
    module = storage()
    target = tmp_path / 'raced'
    original = Path.mkdir
    def mkdir(path, *args, **kwargs):
        if path == target:
            original(path)
            (path / 'owner').write_bytes(b'keep')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    rejected('OUTPUT_EXISTS', lambda: module.save_release_if_result_package(saved(), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {'owner': b'keep'}


def test_member_creation_race_never_overwrites(tmp_path, monkeypatch):
    module = storage()
    target = tmp_path / 'raced'
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        if path == target / 'result.json' and mode == 'xb':
            with original(path, 'wb') as stream:
                stream.write(b'other-owner')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    rejected('OUTPUT_ERROR', lambda: module.save_release_if_result_package(saved(), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {'result.json': b'other-owner'}


def test_read_remaining_budget_is_enforced(disk, monkeypatch):
    module = storage()
    observed = []
    def read(file, size):
        payload = file.read(size)
        observed.append((size, len(payload)))
        return payload
    intercept(monkeypatch, disk, 'result.json', 'rb', lambda raw: Stream(raw, read=read))
    identity = module._directory(disk)
    signature = module._signature((disk / 'result.json').lstat())
    rejected('RESOURCE_LIMIT', lambda: module._read(disk, identity, 'result.json', signature, 5))
    assert observed == [(6, 6)]


def test_load_never_uses_model_or_upstream_and_return_has_no_io(disk, monkeypatch):
    module = storage()
    codec = importlib.import_module('traffic_anomaly.release_if_result_contract')
    engine = importlib.import_module('traffic_anomaly.release_iforest')
    inputs = importlib.import_module('traffic_anomaly.release_inputs')
    expected = saved()
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('forbidden model or upstream operation')
        raise AssertionError('forbidden model or upstream operation')
    for name in ('_validated_inputs', 'make_release_if_result_package', 'verify_release_if_result_pair'):
        monkeypatch.setattr(codec, name, forbidden)
    for name in ('_validated_inputs', 'fit_release_iforest', '_compute'):
        monkeypatch.setattr(engine, name, forbidden)
    for name in ('prepare_release_inputs', 'verify_release_input_derivation'):
        monkeypatch.setattr(inputs, name, forbidden)
    loaded = module.load_release_if_result_package(disk)
    disk.rename(disk.with_name('moved-after-load'))
    monkeypatch.setattr(Path, 'open', forbidden)
    assert loaded == expected
    assert loaded.result.threshold == 2.9699999999999998
    assert loaded.result.scores[0] is None
    assert attempts == []
