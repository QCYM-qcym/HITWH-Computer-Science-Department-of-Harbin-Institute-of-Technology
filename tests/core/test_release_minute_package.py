"""Fixed-member filesystem boundaries; codec doubles are not joint evidence."""
from datetime import datetime, timedelta
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

NAMES = ('minutes.json', 'labels.json', 'diagnostics.json', 'manifest.json', 'COMPLETE.json')
LIMITS = dict(zip(NAMES, (8388608, 8388608, 8388608, 65536, 4096)))
PAYLOADS = {name: ('{"member":"' + name + '"}\n').encode() for name in NAMES}
SOURCE = Path(__file__).parents[2] / 'src/core/traffic_anomaly/release_minute_package.py'


class BoundaryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@pytest.fixture
def boundary():
    return make_boundary


def make_boundary():
    assert SOURCE.is_file(), 'release minute package filesystem module is required'
    codec = ModuleType('traffic_anomaly.release_minute_contract')
    codec.PACKAGE_MEMBER_NAMES = NAMES
    codec.PACKAGE_MEMBER_BYTE_LIMITS = tuple(LIMITS.items())
    codec.PACKAGE_TOTAL_BYTE_LIMIT = 20971520
    codec.ReleaseMinutePackageError = BoundaryError
    codec.ReleaseMinutePackage = codec.ReleaseMinutePackageIdentity = SimpleNamespace
    identity = object()
    snapshot = SimpleNamespace(identity=identity)
    calls = []

    def decode(members):
        assert type(members) is dict and members == PAYLOADS
        calls.append(dict(members))
        return snapshot

    codec.decode_release_minute_package = decode
    codec.encode_release_minute_package = lambda minutes, segments: tuple(PAYLOADS.items())
    spec = importlib.util.spec_from_file_location('traffic_anomaly._minute_storage_boundary', SOURCE)
    module = importlib.util.module_from_spec(spec)
    # Load an isolated copy: never replace the real W1 module for joint tests.
    with patch.dict(sys.modules, {codec.__name__: codec}):
        spec.loader.exec_module(module)
    return module, snapshot, calls


@pytest.fixture
def package(tmp_path):
    directory = tmp_path / 'package'
    directory.mkdir()
    for name, value in PAYLOADS.items():
        (directory / name).write_bytes(value)
    return directory


def rejected(module, code, operation):
    with pytest.raises(BoundaryError) as caught:
        operation()
    assert caught.value.code in ((code,) if isinstance(code, str) else code)
    assert str(caught.value) == caught.value.code
    assert 'private' not in str(caught.value)


def unavailable_link(kind, exc):
    reason = f'real {kind} unavailable: {type(exc).__name__} errno={exc.errno} winerror={getattr(exc, "winerror", None)}'
    print('PLATFORM_SKIP:', reason)  # No paths; retained by the guarded -s receipt.
    pytest.skip(reason)


class Stream:
    """Fault wrapper retaining the actual OS file handle."""
    def __init__(self, raw, *, read=None, write=None, flush=None, close=None):
        self.raw = raw
        self.read_hook, self.write_hook = read, write
        self.flush_hook, self.close_hook = flush, close
    def __enter__(self): return self
    def __exit__(self, *args):
        self.raw.close()
        if self.close_hook: self.close_hook()
    def fileno(self): return self.raw.fileno()
    def read(self, size=-1):
        return self.read_hook(self.raw, size) if self.read_hook else self.raw.read(size)
    def write(self, value):
        return self.write_hook(self.raw, value) if self.write_hook else self.raw.write(value)
    def flush(self):
        return self.flush_hook(self.raw) if self.flush_hook else self.raw.flush()


def intercept(monkeypatch, directory, name, mode, factory):
    original = Path.open
    handles = []
    expected_mode = mode
    def opened(path, mode='r', *args, **kwargs):
        raw = original(path, mode, *args, **kwargs)
        if path == directory / name and mode == expected_mode:
            handles.append(raw)
            return factory(raw)
        return raw
    monkeypatch.setattr(Path, 'open', opened)
    return handles


def test_loads_five_ordinary_members(boundary, package, monkeypatch):
    module, snapshot, calls = boundary()
    order = []
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        order.append(path.name)
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    assert module.load_release_minute_package(package) is snapshot
    assert order == ['COMPLETE.json', 'manifest.json', *NAMES[:3]]
    assert calls == [PAYLOADS]


@pytest.mark.parametrize('change', ['missing', 'sixth', 'nested'])
def test_load_rejects_sixth_or_missing_member(boundary, package, change):
    module, _, calls = boundary()
    if change == 'missing': (package / 'COMPLETE.json').unlink()
    elif change == 'sixth': (package / 'extra').write_bytes(b'x')
    else:
        (package / 'minutes.json').unlink()
        (package / 'minutes.json').mkdir()
    rejected(module, ('INVALID_PACKAGE', 'INVALID_PACKAGE_PATH'),
             lambda: module.load_release_minute_package(package))
    assert not calls


@pytest.mark.parametrize('value', [None, '', 'relative', 'relative/../package', 'bad\0path'])
def test_invalid_lexical_paths(boundary, value):
    module, _, _ = boundary()
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_minute_package(value))


@pytest.mark.skipif(os.name != 'nt', reason='Windows native path semantics')
@pytest.mark.parametrize('value', ['\\package', '/package', 'C:package', '\\\\server\\share\\package',
                                  '\\\\?\\C:\\package', 'C:\\package:stream'])
def test_windows_root_relative_unc_device_and_ads_rejected(boundary, value):
    module, _, _ = boundary()
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_minute_package(value))


@pytest.mark.skipif(os.name == 'nt', reason='POSIX native absolute path semantics')
def test_posix_absolute_path(boundary, package):
    module, snapshot, _ = boundary()
    assert module.load_release_minute_package(package) is snapshot


def test_wrong_real_open_handle_is_rejected(boundary, package, tmp_path, monkeypatch):
    module, _, calls = boundary()
    other = tmp_path / 'different-real-file'
    other.write_bytes(PAYLOADS['COMPLETE.json'])
    original = Path.open
    handles = []
    def opened(path, mode='r', *args, **kwargs):
        raw = original(other if path == package / 'COMPLETE.json' else path, mode, *args, **kwargs)
        handles.append(raw)
        return raw
    monkeypatch.setattr(Path, 'open', opened)
    rejected(module, 'PACKAGE_CHANGED', lambda: module.load_release_minute_package(package))
    assert handles and all(handle.closed for handle in handles) and not calls


def test_short_read_cannot_hide_stable_file_tail(boundary, package, monkeypatch):
    module, _, calls = boundary()
    (package / 'COMPLETE.json').write_bytes(PAYLOADS['COMPLETE.json'] + b'junk')
    handles = intercept(monkeypatch, package, 'COMPLETE.json', 'rb',
                        lambda raw: Stream(raw, read=lambda file, size: file.read(len(PAYLOADS['COMPLETE.json']))))
    rejected(module, 'PACKAGE_CHANGED', lambda: module.load_release_minute_package(package))
    assert handles and all(handle.closed for handle in handles) and not calls


@pytest.mark.parametrize('member', ['COMPLETE.json', 'diagnostics.json'])
@pytest.mark.parametrize('stage', ['read', 'close'])
def test_read_and_close_failures_never_return_snapshot(boundary, package, monkeypatch, member, stage):
    module, _, calls = boundary()
    def fail(*args): raise OSError('private source path')
    handles = intercept(monkeypatch, package, member, 'rb', lambda raw: Stream(raw, **{stage: fail}))
    rejected(module, 'INPUT_UNAVAILABLE', lambda: module.load_release_minute_package(package))
    assert handles and all(handle.closed for handle in handles) and not calls


def test_byte_read_request_is_bounded(boundary, package, monkeypatch):
    module, snapshot, _ = boundary()
    requests = []
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        raw = original(path, mode, *args, **kwargs)
        def read(file, size):
            requests.append((path.name, size))
            return file.read(size)
        return Stream(raw, read=read)
    monkeypatch.setattr(Path, 'open', opened)
    assert module.load_release_minute_package(package) is snapshot
    assert requests == [(name, LIMITS[name] + 1) for name in ['COMPLETE.json', 'manifest.json', *NAMES[:3]]]


@pytest.mark.parametrize('kind', ['member', 'total'])
def test_physical_byte_limits_precede_open(boundary, package, monkeypatch, kind):
    module, _, calls = boundary()
    if kind == 'member':
        with (package / 'COMPLETE.json').open('wb') as stream: stream.truncate(4097)
    else:
        for name in NAMES[:3]:
            with (package / name).open('wb') as stream: stream.truncate(8 * 1024 * 1024)
    monkeypatch.setattr(Path, 'open', lambda *a, **k: pytest.fail('oversize opened'))
    rejected(module, 'RESOURCE_LIMIT', lambda: module.load_release_minute_package(package))
    assert not calls


def test_hardlink_outside_package_rejected_but_copy_allowed(boundary, package, tmp_path):
    module, snapshot, _ = boundary()
    copied = tmp_path / 'ordinary-copy'
    shutil.copytree(package, copied)
    assert module.load_release_minute_package(copied) is snapshot
    try: os.link(package / 'minutes.json', tmp_path / 'outside-hardlink')
    except OSError as exc: unavailable_link('hardlink', exc)
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_minute_package(package))


@pytest.mark.parametrize('kind', ['file', 'directory', 'ancestor'])
def test_actual_symlink_rejected(boundary, package, tmp_path, kind):
    module, _, _ = boundary()
    link = tmp_path / 'linked-package'
    try:
        if kind == 'directory': link.symlink_to(package, target_is_directory=True)
        elif kind == 'ancestor':
            parent = tmp_path / 'ordinary-parent'
            parent.mkdir()
            package.rename(parent / package.name)
            linked_parent = tmp_path / 'linked-parent'
            linked_parent.symlink_to(parent, target_is_directory=True)
            link = linked_parent / package.name
            assert link.is_dir() and not link.is_symlink()
            assert link.parent.is_symlink()
        else:
            target = tmp_path / 'moved-member'
            (package / 'minutes.json').rename(target)
            (package / 'minutes.json').symlink_to(target)
            link = package
    except OSError as exc: unavailable_link('symlink_' + kind, exc)
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_minute_package(link))


def test_validation_precedes_output_creation(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    def invalid(*args): raise BoundaryError('INCONSISTENT_PACKAGE')
    monkeypatch.setattr(module, 'encode_release_minute_package', invalid)
    target = tmp_path / 'not-created'
    rejected(module, 'INCONSISTENT_PACKAGE', lambda: module.save_release_minute_package(None, (), target))
    assert not target.exists()


@pytest.mark.parametrize('nonempty', [False, True])
def test_existing_empty_directory_is_not_owned(boundary, tmp_path, nonempty):
    module, _, _ = boundary()
    target = tmp_path / 'existing'
    target.mkdir()
    if nonempty: (target / 'owned-by-other').write_bytes(b'untouched')
    before = target.stat()
    rejected(module, 'OUTPUT_EXISTS', lambda: module.save_release_minute_package(None, (), target))
    after = target.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
    assert list(target.iterdir()) == ([target / 'owned-by-other'] if nonempty else [])


def test_save_load_and_copy_roundtrip(boundary, tmp_path, monkeypatch):
    module, snapshot, _ = boundary()
    target, copied = tmp_path / 'new', tmp_path / 'copy'
    writes = []
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        if mode == 'xb': writes.append(path.name)
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    assert module.save_release_minute_package(None, (), target) is snapshot.identity
    assert writes == list(NAMES)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == PAYLOADS
    shutil.copytree(target, copied)
    assert module.load_release_minute_package(copied) is snapshot


@pytest.mark.parametrize('member', NAMES)
@pytest.mark.parametrize('stage', ['write', 'flush', 'close', 'readback'])
def test_partial_write_or_pre_marker_failure_preserves_residue(boundary, tmp_path, monkeypatch, member, stage):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    def fail(*args): raise OSError('private output location')
    mode = 'rb' if stage == 'readback' else 'xb'
    if stage == 'write': factory = lambda raw: Stream(raw, write=lambda file, value: file.write(value[:3]))
    else: factory = lambda raw: Stream(raw, **{('read' if stage == 'readback' else stage): fail})
    handles = intercept(monkeypatch, target, member, mode, factory)
    rejected(module, ('OUTPUT_ERROR', 'INPUT_UNAVAILABLE'), lambda: module.save_release_minute_package(None, (), target))
    assert handles and all(handle.closed for handle in handles)
    assert target.is_dir() and (target / member).is_file()
    if member != 'COMPLETE.json': assert not (target / 'COMPLETE.json').exists()


def test_keyboard_interrupt_preserves_residue(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'interrupted'
    def stop(*args): raise KeyboardInterrupt
    handles = intercept(monkeypatch, target, 'minutes.json', 'xb', lambda raw: Stream(raw, write=stop))
    with pytest.raises(KeyboardInterrupt): module.save_release_minute_package(None, (), target)
    assert target.is_dir() and (target / 'minutes.json').is_file()
    assert handles and all(handle.closed for handle in handles)


@pytest.mark.parametrize('change', ['replace_member', 'replace_directory', 'insert_member', 'grow_member'])
def test_observed_read_replacement_and_insertion_rejected(boundary, package, tmp_path, monkeypatch, change):
    module, _, calls = boundary()
    saved = tmp_path / 'original-entity'
    def mutate():
        if change == 'replace_member':
            (package / 'COMPLETE.json').rename(saved)
            (package / 'COMPLETE.json').write_bytes(PAYLOADS['COMPLETE.json'])
        elif change == 'replace_directory':
            package.rename(saved)
            shutil.copytree(saved, package)
        elif change == 'insert_member': (package / 'sixth').write_bytes(b'other')
        else:
            with (package / 'COMPLETE.json').open('ab') as file: file.write(b'x')
    handles = intercept(monkeypatch, package, 'COMPLETE.json', 'rb', lambda raw: Stream(raw, close=mutate))
    rejected(module, 'PACKAGE_CHANGED', lambda: module.load_release_minute_package(package))
    assert handles and all(handle.closed for handle in handles) and not calls
    assert package.exists()
    if change.startswith('replace'): assert saved.exists()


def test_read_growth_observes_at_most_limit_plus_one(boundary, package, monkeypatch):
    module, _, _ = boundary()
    sizes = []
    def read(file, size):
        with (package / 'COMPLETE.json').open('ab') as output: output.write(b'x' * 8192)
        value = file.read(size)
        sizes.append((size, len(value)))
        return value
    handles = intercept(monkeypatch, package, 'COMPLETE.json', 'rb', lambda raw: Stream(raw, read=read))
    rejected(module, ('PACKAGE_CHANGED', 'RESOURCE_LIMIT'), lambda: module.load_release_minute_package(package))
    assert sizes == [(4097, 4097)] and all(handle.closed for handle in handles)


def test_read_request_uses_remaining_total_budget(boundary, package, monkeypatch):
    module, snapshot, _ = boundary()
    for name in NAMES[:2]:
        with (package / name).open('wb') as file: file.truncate(8388608)
    monkeypatch.setattr(module, 'decode_release_minute_package', lambda members: snapshot)
    requests = []
    def read(file, size):
        requests.append(size)
        return file.read(size)
    intercept(monkeypatch, package, 'diagnostics.json', 'rb', lambda raw: Stream(raw, read=read))
    assert module.load_release_minute_package(package) is snapshot
    assert requests == [20971520 - 2 * 8388608 - len(PAYLOADS['manifest.json']) - len(PAYLOADS['COMPLETE.json']) + 1]


def test_save_readback_uses_remaining_total_budget(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    # A small contract double exercises the same budget depletion without
    # allocating large JSON; this is not evidence for the real codec's limits.
    monkeypatch.setattr(module, 'PACKAGE_TOTAL_BYTE_LIMIT', 100)
    monkeypatch.setattr(module, '_LIMITS', dict.fromkeys(NAMES, 64))
    monkeypatch.setattr(module, 'encode_release_minute_package', lambda *a:
                        tuple((name, b'x' * size) for name, size in zip(NAMES, (20, 20, 10, 10, 5))))
    target = tmp_path / 'new'
    observed = []
    def read(file, size):
        with (target / 'diagnostics.json').open('ab') as output: output.write(b'x' * 74)
        value = file.read(size)
        observed.append((size, len(value)))
        return value
    intercept(monkeypatch, target, 'diagnostics.json', 'rb', lambda raw: Stream(raw, read=read))
    rejected(module, ('PACKAGE_CHANGED', 'RESOURCE_LIMIT'), lambda: module.save_release_minute_package(None, (), target))
    assert observed == [(61, 61)]
    assert not (target / 'COMPLETE.json').exists()


def test_missing_package_and_missing_parent_safe_errors(boundary, tmp_path):
    module, _, _ = boundary()
    rejected(module, 'INPUT_UNAVAILABLE', lambda: module.load_release_minute_package(tmp_path / 'missing'))
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_minute_package(None, (), tmp_path / 'missing' / 'new'))
    assert not (tmp_path / 'missing').exists()


def test_exclusive_mkdir_race_does_not_take_ownership(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'raced'
    original = Path.mkdir
    def mkdir(path, *args, **kwargs):
        if path == target:
            original(path)
            (path / 'other-owner').write_bytes(b'keep')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    rejected(module, 'OUTPUT_EXISTS', lambda: module.save_release_minute_package(None, (), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {'other-owner': b'keep'}


def test_exclusive_file_race_does_not_overwrite(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        if path == target / 'minutes.json' and mode == 'xb':
            with original(path, 'wb') as file: file.write(b'other-owner')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_minute_package(None, (), target))
    assert (target / 'minutes.json').read_bytes() == b'other-owner'
    assert not (target / 'COMPLETE.json').exists()


def test_wrong_real_write_handle_is_rejected(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target, other = tmp_path / 'new', tmp_path / 'other-real-file'
    other.write_bytes(b'')
    original = Path.open
    handles = []
    def opened(path, mode='r', *args, **kwargs):
        raw = original(path, mode, *args, **kwargs)
        if path == target / 'minutes.json' and mode == 'xb':
            raw.close()
            raw = original(other, 'r+b')
            handles.append(raw)
        return raw
    monkeypatch.setattr(Path, 'open', opened)
    rejected(module, 'PACKAGE_CHANGED', lambda: module.save_release_minute_package(None, (), target))
    assert handles and all(handle.closed for handle in handles)
    assert other.read_bytes() == b'' and (target / 'minutes.json').read_bytes() == b''


@pytest.mark.parametrize('change', ['member', 'directory', 'sixth', 'tamper'])
def test_replacement_not_removed_or_overwritten(boundary, tmp_path, monkeypatch, change):
    module, _, _ = boundary()
    target, saved = tmp_path / 'new', tmp_path / 'original'
    def mutate():
        if change == 'member':
            (target / 'minutes.json').rename(saved)
            (target / 'minutes.json').write_bytes(b'other-owner')
        elif change == 'directory':
            target.rename(saved)
            target.mkdir()
            (target / 'other-owner').write_bytes(b'keep')
        elif change == 'sixth': (target / 'other-owner').write_bytes(b'keep')
        else:
            path = target / 'minutes.json'
            before = path.stat()
            path.write_bytes(b'x' * len(PAYLOADS['minutes.json']))
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    handles = intercept(monkeypatch, target, 'minutes.json', 'xb', lambda raw: Stream(raw, close=mutate))
    rejected(module, ('PACKAGE_CHANGED', 'INTEGRITY_MISMATCH'),
             lambda: module.save_release_minute_package(None, (), target))
    assert handles and all(handle.closed for handle in handles)
    assert target.exists() and not (target / 'COMPLETE.json').exists()
    if change in ('member', 'directory'): assert saved.exists()
    if change == 'directory': assert (target / 'other-owner').read_bytes() == b'keep'


def test_unknown_member_before_marker_preserves_residue(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    def insert(): (target / 'sixth').write_bytes(b'untouched')
    intercept(monkeypatch, target, 'manifest.json', 'rb', lambda raw: Stream(raw, close=insert))
    rejected(module, 'PACKAGE_CHANGED', lambda: module.save_release_minute_package(None, (), target))
    assert (target / 'manifest.json').read_bytes() == PAYLOADS['manifest.json']
    assert (target / 'sixth').read_bytes() == b'untouched' and not (target / 'COMPLETE.json').exists()


def test_late_failure_can_leave_loadable_complete_package(boundary, tmp_path, monkeypatch):
    module, snapshot, decode_calls = boundary()
    target = tmp_path / 'complete-but-save-failed'
    original = module._inventory
    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        if decode_calls: raise BoundaryError('OUTPUT_ERROR')
        return result
    with monkeypatch.context() as local:
        local.setattr(module, '_inventory', late)
        rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_minute_package(None, (), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == PAYLOADS
    assert module.load_release_minute_package(target) is snapshot


@pytest.mark.parametrize('member', NAMES)
def test_member_open_failure_keeps_prior_members(boundary, tmp_path, monkeypatch, member):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        if path == target / member and mode == 'xb': raise PermissionError('private output path')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_minute_package(None, (), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {
        name: PAYLOADS[name] for name in NAMES[:NAMES.index(member)]}


def test_mkdir_failure_does_not_create_or_clean_parent(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    marker = tmp_path / 'other-owner'
    marker.write_bytes(b'keep')
    original = Path.mkdir
    def mkdir(path, *args, **kwargs):
        if path == target: raise PermissionError('private parent path')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_minute_package(None, (), target))
    assert not target.exists() and marker.read_bytes() == b'keep'


def test_simulated_windows_reparse_attribute_rejected(boundary, package, monkeypatch):
    module, _, calls = boundary()
    original = Path.lstat
    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == package / 'minutes.json':
            return SimpleNamespace(**{name: (0x400 if name == 'st_file_attributes' else getattr(info, name))
                for name in ('st_dev', 'st_ino', 'st_mode', 'st_file_attributes',
                             'st_size', 'st_mtime_ns', 'st_nlink')})
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_minute_package(package))
    assert not calls


def real_case():
    assert SOURCE.is_file(), 'release minute package filesystem module is required'
    codec = importlib.import_module('traffic_anomaly.release_minute_contract')
    storage = importlib.import_module('traffic_anomaly.release_minute_package')
    helpers = importlib.import_module('.release_minute_package_cases', __package__)
    from traffic_anomaly._release_minutes import ReleaseSegment
    start = datetime(2026, 1, 1)
    segments = (ReleaseSegment('artificial', 'train', start, start + timedelta(minutes=2)),)
    minutes = helpers.make_result((({'id': 'ordinary', 'Timestamp': '2026-01-01 00:00:00.000000'},),), segments)
    return codec, storage, minutes, segments


def test_real_contract_save_load_and_copy_roundtrip(tmp_path, monkeypatch):
    codec, storage, minutes, segments = real_case()
    expected = dict(codec.encode_release_minute_package(minutes, segments))
    target, copied = tmp_path / 'real-contract', tmp_path / 'copied'
    identity = storage.save_release_minute_package(minutes, segments, target)
    assert identity.manifest_sha256 == hashlib.sha256(expected['manifest.json']).hexdigest()
    assert identity.manifest_byte_count == len(expected['manifest.json'])
    assert {p.name: p.read_bytes() for p in target.iterdir()} == expected
    shutil.copytree(target, copied)
    for location in (target, copied):
        result = storage.load_release_minute_package(location)
        assert result.identity == identity and result.minutes == minutes and result.segments == segments
        assert result.scope == 'PACKAGE_INTERNAL_CONSISTENCY_ONLY'
        moved = location.with_name(location.name + '-moved')
        location.rename(moved)
        with monkeypatch.context() as local:
            local.setattr(Path, 'open', lambda *a, **k: pytest.fail('returned value reopened a path'))
            assert result.minutes == minutes and result.identity == identity


@pytest.mark.parametrize('case,code', [
    ('missing_complete', 'INVALID_PACKAGE'),
    ('minutes_append_unbound_space', 'INTEGRITY_MISMATCH'),
    ('sixth_member', 'INVALID_PACKAGE'),
    ('input_ordinary_file', 'INVALID_PACKAGE_PATH'),
    ('save_existing_empty', 'OUTPUT_EXISTS'),
])
def test_real_contract_task6_negative_cases(tmp_path, case, code):
    codec, storage, minutes, segments = real_case()
    directory = tmp_path / 'new-package'
    storage.save_release_minute_package(minutes, segments, directory)
    if case == 'missing_complete': (directory / 'COMPLETE.json').unlink()
    elif case == 'minutes_append_unbound_space':
        with (directory / 'minutes.json').open('ab') as file: file.write(b' ')
    elif case == 'sixth_member': (directory / 'sixth.json').write_bytes(b'{}\n')
    elif case == 'input_ordinary_file': directory = directory / 'minutes.json'
    elif case == 'save_existing_empty':
        directory = tmp_path / 'existing-empty'
        directory.mkdir()
    with pytest.raises(codec.ReleaseMinutePackageError) as caught:
        if case == 'save_existing_empty': storage.save_release_minute_package(minutes, segments, directory)
        else: storage.load_release_minute_package(directory)
    assert caught.value.code == code and str(caught.value) == code
    assert str(tmp_path) not in str(caught.value)
    if case == 'save_existing_empty': assert list(directory.iterdir()) == []
