"""Prepared-input fixed I/O boundaries; codec doubles are not joint evidence."""
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

NAMES = ('preprocess.json', 'inputs.json', 'labels.json', 'manifest.json', 'COMPLETE.json')
LIMITS = dict(zip(NAMES, (16384, 16777216, 2097152, 65536, 4096)))
PAYLOADS = {name: ('{"member":"' + name + '"}\n').encode() for name in NAMES}
SOURCE = Path(__file__).parents[2] / 'src/core/traffic_anomaly/release_input_package.py'


class BoundaryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@pytest.fixture
def boundary():
    return make_boundary


def make_boundary():
    assert SOURCE.is_file(), 'prepared input package filesystem module is required'
    codec = ModuleType('traffic_anomaly.release_inputs')
    codec.PACKAGE_MEMBER_NAMES = NAMES
    codec.PACKAGE_MEMBER_BYTE_LIMITS = tuple(LIMITS.items())
    codec.PACKAGE_TOTAL_BYTE_LIMIT = 20971520
    codec.ReleaseInputPreparationError = BoundaryError
    codec.ReleasePreparedInputs = codec.ReleaseInputIdentity = SimpleNamespace
    identity = object()
    snapshot = SimpleNamespace(identity=identity)
    calls = []

    def decode(members):
        assert type(members) is dict and members == PAYLOADS
        calls.append(dict(members))
        return snapshot

    codec.decode_release_input_package = decode
    codec.encode_release_input_package = lambda saved: tuple(PAYLOADS.items())
    spec = importlib.util.spec_from_file_location('traffic_anomaly._input_storage_boundary', SOURCE)
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
    assert module.load_release_input_package(package) is snapshot
    assert order == ['COMPLETE.json', 'manifest.json', *NAMES[:3]]
    assert calls == [PAYLOADS]


@pytest.mark.parametrize('change', ['missing', 'sixth', 'nested'])
def test_load_rejects_sixth_or_missing_member(boundary, package, change):
    module, _, calls = boundary()
    if change == 'missing': (package / 'COMPLETE.json').unlink()
    elif change == 'sixth': (package / 'extra').write_bytes(b'x')
    else:
        (package / 'preprocess.json').unlink()
        (package / 'preprocess.json').mkdir()
    rejected(module, ('INVALID_PACKAGE', 'INVALID_PACKAGE_PATH'),
             lambda: module.load_release_input_package(package))
    assert not calls


@pytest.mark.parametrize('value', ['', 'relative', 'relative/../package', 'bad\0path'])
def test_invalid_lexical_paths(boundary, value):
    module, _, _ = boundary()
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_input_package(value))


@pytest.mark.skipif(os.name != 'nt', reason='Windows native path semantics')
@pytest.mark.parametrize('value', ['\\package', '/package', 'C:package', '\\\\server\\share\\package',
                                  '\\\\?\\C:\\package', 'C:\\package:stream'])
def test_windows_root_relative_unc_device_and_ads_rejected(boundary, value):
    module, _, _ = boundary()
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_input_package(value))


@pytest.mark.skipif(os.name == 'nt', reason='POSIX native absolute path semantics')
def test_posix_absolute_path(boundary, package):
    module, snapshot, _ = boundary()
    assert module.load_release_input_package(package) is snapshot


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
    rejected(module, 'PACKAGE_CHANGED', lambda: module.load_release_input_package(package))
    assert handles and all(handle.closed for handle in handles) and not calls


def test_short_read_cannot_hide_stable_file_tail(boundary, package, monkeypatch):
    module, _, calls = boundary()
    (package / 'COMPLETE.json').write_bytes(PAYLOADS['COMPLETE.json'] + b'junk')
    handles = intercept(monkeypatch, package, 'COMPLETE.json', 'rb',
                        lambda raw: Stream(raw, read=lambda file, size: file.read(len(PAYLOADS['COMPLETE.json']))))
    rejected(module, 'PACKAGE_CHANGED', lambda: module.load_release_input_package(package))
    assert handles and all(handle.closed for handle in handles) and not calls


@pytest.mark.parametrize('member', ['COMPLETE.json', 'labels.json'])
@pytest.mark.parametrize('stage', ['read', 'close'])
def test_read_and_close_failures_never_return_snapshot(boundary, package, monkeypatch, member, stage):
    module, _, calls = boundary()
    def fail(*args): raise OSError('private source path')
    handles = intercept(monkeypatch, package, member, 'rb', lambda raw: Stream(raw, **{stage: fail}))
    rejected(module, 'INPUT_UNAVAILABLE', lambda: module.load_release_input_package(package))
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
    assert module.load_release_input_package(package) is snapshot
    assert requests == [(name, LIMITS[name] + 1) for name in ['COMPLETE.json', 'manifest.json', *NAMES[:3]]]


@pytest.mark.parametrize('member', NAMES)
def test_physical_member_limits_precede_open(boundary, package, monkeypatch, member):
    module, _, calls = boundary()
    with (package / member).open('wb') as stream: stream.truncate(LIMITS[member] + 1)
    monkeypatch.setattr(Path, 'open', lambda *a, **k: pytest.fail('oversize opened'))
    rejected(module, 'RESOURCE_LIMIT', lambda: module.load_release_input_package(package))
    assert not calls


def test_hardlink_outside_package_rejected_but_copy_allowed(boundary, package, tmp_path):
    module, snapshot, _ = boundary()
    copied = tmp_path / 'ordinary-copy'
    shutil.copytree(package, copied)
    assert module.load_release_input_package(copied) is snapshot
    try: os.link(package / 'preprocess.json', tmp_path / 'outside-hardlink')
    except OSError as exc: unavailable_link('hardlink', exc)
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_input_package(package))


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
            (package / 'preprocess.json').rename(target)
            (package / 'preprocess.json').symlink_to(target)
            link = package
    except OSError as exc: unavailable_link('symlink_' + kind, exc)
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_input_package(link))


def test_save_validates_before_exclusive_creation(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    def invalid(*args): raise BoundaryError('INCONSISTENT_PACKAGE')
    monkeypatch.setattr(module, 'encode_release_input_package', invalid)
    target = tmp_path / 'not-created'
    rejected(module, 'INCONSISTENT_PACKAGE', lambda: module.save_release_input_package(None, target))
    assert not target.exists()


@pytest.mark.parametrize('nonempty', [False, True])
def test_existing_directory_untouched(boundary, tmp_path, nonempty):
    module, _, _ = boundary()
    target = tmp_path / 'existing'
    target.mkdir()
    if nonempty: (target / 'owned-by-other').write_bytes(b'untouched')
    before = target.stat()
    rejected(module, 'OUTPUT_EXISTS', lambda: module.save_release_input_package(None, target))
    after = target.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
    assert list(target.iterdir()) == ([target / 'owned-by-other'] if nonempty else [])


def test_five_member_roundtrip_and_ordinary_copy(boundary, tmp_path, monkeypatch):
    module, snapshot, _ = boundary()
    target, copied = tmp_path / 'new', tmp_path / 'copy'
    writes = []
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        if mode == 'xb': writes.append(path.name)
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    assert module.save_release_input_package(None, target) is snapshot.identity
    assert writes == list(NAMES)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == PAYLOADS
    shutil.copytree(target, copied)
    assert module.load_release_input_package(copied) is snapshot


@pytest.mark.parametrize('member', NAMES)
@pytest.mark.parametrize('stage', ['write', 'flush', 'close', 'readback'])
def test_write_flush_close_and_reread_failures_preserve_residue(boundary, tmp_path, monkeypatch, member, stage):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    def fail(*args): raise OSError('private output location')
    mode = 'rb' if stage == 'readback' else 'xb'
    if stage == 'write': factory = lambda raw: Stream(raw, write=lambda file, value: file.write(value[:3]))
    else: factory = lambda raw: Stream(raw, **{('read' if stage == 'readback' else stage): fail})
    handles = intercept(monkeypatch, target, member, mode, factory)
    rejected(module, ('OUTPUT_ERROR', 'INPUT_UNAVAILABLE'), lambda: module.save_release_input_package(None, target))
    assert handles and all(handle.closed for handle in handles)
    assert target.is_dir() and (target / member).is_file()
    if member != 'COMPLETE.json': assert not (target / 'COMPLETE.json').exists()


def test_keyboard_interrupt_preserves_residue(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'interrupted'
    def stop(*args): raise KeyboardInterrupt
    handles = intercept(monkeypatch, target, 'preprocess.json', 'xb', lambda raw: Stream(raw, write=stop))
    with pytest.raises(KeyboardInterrupt): module.save_release_input_package(None, target)
    assert target.is_dir() and (target / 'preprocess.json').is_file()
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
    rejected(module, 'PACKAGE_CHANGED', lambda: module.load_release_input_package(package))
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
    rejected(module, ('PACKAGE_CHANGED', 'RESOURCE_LIMIT'), lambda: module.load_release_input_package(package))
    assert sizes == [(4097, 4097)] and all(handle.closed for handle in handles)


def test_internal_read_respects_remaining_total_budget(boundary, package, monkeypatch):
    module, _, _ = boundary()
    observed = []
    def read(file, size):
        value = file.read(size)
        observed.append((size, len(value)))
        return value
    intercept(monkeypatch, package, 'inputs.json', 'rb', lambda raw: Stream(raw, read=read))
    identity = module._directory(package)
    signature = module._signature((package / 'inputs.json').lstat())
    rejected(module, 'RESOURCE_LIMIT',
             lambda: module._read(package, identity, 'inputs.json', signature, 5))
    assert observed == [(6, 6)]


def test_save_readback_uses_remaining_total_budget(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    # A small contract double exercises the same budget depletion without
    # allocating large JSON; this is not evidence for the real codec's limits.
    monkeypatch.setattr(module, 'PACKAGE_TOTAL_BYTE_LIMIT', 100)
    monkeypatch.setattr(module, '_LIMITS', dict.fromkeys(NAMES, 64))
    monkeypatch.setattr(module, 'encode_release_input_package', lambda *a:
                        tuple((name, b'x' * size) for name, size in zip(NAMES, (20, 20, 10, 10, 5))))
    target = tmp_path / 'new'
    observed = []
    def read(file, size):
        with (target / 'labels.json').open('ab') as output: output.write(b'x' * 74)
        value = file.read(size)
        observed.append((size, len(value)))
        return value
    intercept(monkeypatch, target, 'labels.json', 'rb', lambda raw: Stream(raw, read=read))
    rejected(module, ('PACKAGE_CHANGED', 'RESOURCE_LIMIT'), lambda: module.save_release_input_package(None, target))
    assert observed == [(61, 61)]
    assert not (target / 'COMPLETE.json').exists()


def test_missing_package_and_missing_parent_safe_errors(boundary, tmp_path):
    module, _, _ = boundary()
    rejected(module, 'INPUT_UNAVAILABLE', lambda: module.load_release_input_package(tmp_path / 'missing'))
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_input_package(None, tmp_path / 'missing' / 'new'))
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
    rejected(module, 'OUTPUT_EXISTS', lambda: module.save_release_input_package(None, target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == {'other-owner': b'keep'}


def test_exclusive_file_race_does_not_overwrite(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        if path == target / 'preprocess.json' and mode == 'xb':
            with original(path, 'wb') as file: file.write(b'other-owner')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_input_package(None, target))
    assert (target / 'preprocess.json').read_bytes() == b'other-owner'
    assert not (target / 'COMPLETE.json').exists()


def test_wrong_real_write_handle_is_rejected(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target, other = tmp_path / 'new', tmp_path / 'other-real-file'
    other.write_bytes(b'')
    original = Path.open
    handles = []
    def opened(path, mode='r', *args, **kwargs):
        raw = original(path, mode, *args, **kwargs)
        if path == target / 'preprocess.json' and mode == 'xb':
            raw.close()
            raw = original(other, 'r+b')
            handles.append(raw)
        return raw
    monkeypatch.setattr(Path, 'open', opened)
    rejected(module, 'PACKAGE_CHANGED', lambda: module.save_release_input_package(None, target))
    assert handles and all(handle.closed for handle in handles)
    assert other.read_bytes() == b'' and (target / 'preprocess.json').read_bytes() == b''


@pytest.mark.parametrize('change', ['member', 'directory', 'sixth', 'tamper'])
def test_replaced_entity_not_cleaned_up(boundary, tmp_path, monkeypatch, change):
    module, _, _ = boundary()
    target, saved = tmp_path / 'new', tmp_path / 'original'
    def mutate():
        if change == 'member':
            (target / 'preprocess.json').rename(saved)
            (target / 'preprocess.json').write_bytes(b'other-owner')
        elif change == 'directory':
            target.rename(saved)
            target.mkdir()
            (target / 'other-owner').write_bytes(b'keep')
        elif change == 'sixth': (target / 'other-owner').write_bytes(b'keep')
        else:
            path = target / 'preprocess.json'
            before = path.stat()
            path.write_bytes(b'x' * len(PAYLOADS['preprocess.json']))
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    handles = intercept(monkeypatch, target, 'preprocess.json', 'xb', lambda raw: Stream(raw, close=mutate))
    rejected(module, ('PACKAGE_CHANGED', 'INTEGRITY_MISMATCH'),
             lambda: module.save_release_input_package(None, target))
    assert handles and all(handle.closed for handle in handles)
    assert target.exists() and not (target / 'COMPLETE.json').exists()
    if change in ('member', 'directory'): assert saved.exists()
    if change == 'directory': assert (target / 'other-owner').read_bytes() == b'keep'


def test_unknown_member_before_marker_preserves_residue(boundary, tmp_path, monkeypatch):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    def insert(): (target / 'sixth').write_bytes(b'untouched')
    intercept(monkeypatch, target, 'manifest.json', 'rb', lambda raw: Stream(raw, close=insert))
    rejected(module, 'PACKAGE_CHANGED', lambda: module.save_release_input_package(None, target))
    assert (target / 'manifest.json').read_bytes() == PAYLOADS['manifest.json']
    assert (target / 'sixth').read_bytes() == b'untouched' and not (target / 'COMPLETE.json').exists()


def test_late_failure_may_leave_loadable_package(boundary, tmp_path, monkeypatch):
    module, snapshot, decode_calls = boundary()
    target = tmp_path / 'complete-but-save-failed'
    original = module._inventory
    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        if decode_calls: raise BoundaryError('OUTPUT_ERROR')
        return result
    with monkeypatch.context() as local:
        local.setattr(module, '_inventory', late)
        rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_input_package(None, target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == PAYLOADS
    assert module.load_release_input_package(target) is snapshot


@pytest.mark.parametrize('member', NAMES)
def test_member_open_failure_keeps_prior_members(boundary, tmp_path, monkeypatch, member):
    module, _, _ = boundary()
    target = tmp_path / 'new'
    original = Path.open
    def opened(path, mode='r', *args, **kwargs):
        if path == target / member and mode == 'xb': raise PermissionError('private output path')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_input_package(None, target))
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
    rejected(module, 'OUTPUT_ERROR', lambda: module.save_release_input_package(None, target))
    assert not target.exists() and marker.read_bytes() == b'keep'


def test_simulated_windows_reparse_attribute_rejected(boundary, package, monkeypatch):
    module, _, calls = boundary()
    original = Path.lstat
    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == package / 'preprocess.json':
            return SimpleNamespace(**{name: (0x400 if name == 'st_file_attributes' else getattr(info, name))
                for name in ('st_dev', 'st_ino', 'st_mode', 'st_file_attributes',
                             'st_size', 'st_mtime_ns', 'st_nlink')})
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    rejected(module, 'INVALID_PACKAGE_PATH', lambda: module.load_release_input_package(package))
    assert not calls


def real_case():
    """Small artificial upstream; never an A9 shape or an A10 runtime receipt."""
    codec = importlib.import_module('traffic_anomaly.release_inputs')
    storage = importlib.import_module('traffic_anomaly.release_input_package')
    raw_codec = importlib.import_module('traffic_anomaly.release_minute_contract')
    raw_cases = importlib.import_module('.release_minute_package_cases', __package__)
    from traffic_anomaly._release_minutes import ReleaseSegment
    start = datetime(2026, 1, 1)
    segments = (ReleaseSegment('artificial-input-train', 'train', start, start + timedelta(minutes=32)),)
    rows = tuple({'id': str(i), 'Timestamp': (start + timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M:%S.%f')}
                 for i in range(32))
    minutes = raw_cases.make_result((rows,), segments)
    upstream = raw_codec.decode_release_minute_package(dict(raw_codec.encode_release_minute_package(minutes, segments)))
    config = codec.ReleasePreparationConfig(schema_version=1,
        numeric_rules_id='c17-release-log1p-mad-input-rules-v1', feature_names=minutes.feature_names,
        windows=(15, 30), fit_window=30, epsilon=1e-6, audit_fit_policy='P_U', policy_status='AUDIT_ONLY')
    return codec, storage, raw_codec, codec.prepare_release_inputs(upstream, config)


def test_real_five_member_roundtrip_and_ordinary_copy(tmp_path):
    codec, storage, _, saved = real_case()
    expected = dict(codec.encode_release_input_package(saved))
    target, copied = tmp_path / 'prepared', tmp_path / 'ordinary-copy'
    identity = storage.save_release_input_package(saved, target)
    assert identity == saved.identity
    assert identity.manifest_sha256 == hashlib.sha256(expected['manifest.json']).hexdigest()
    assert identity.manifest_byte_count == len(expected['manifest.json'])
    assert {p.name: p.read_bytes() for p in target.iterdir()} == expected
    shutil.copytree(target, copied)
    assert storage.load_release_input_package(target) == saved
    assert storage.load_release_input_package(copied) == saved


def recording_guard(attempts, operation):
    def forbidden(*args, **kwargs):
        attempts.append(operation)
        pytest.fail('forbidden operation: ' + operation)
    return forbidden


def test_forbidden_guard_records_even_when_failure_is_caught():
    attempts = []
    guarded = recording_guard(attempts, 'self-check')
    try:
        guarded()
    except pytest.fail.Exception:
        pass  # Deliberately simulate a consumer swallowing the guard failure.
    assert attempts == ['self-check']
    with pytest.raises(AssertionError):
        assert attempts == []


def test_real_fixed_load_order_and_no_upstream_access(tmp_path, monkeypatch):
    import math
    import statistics
    import numpy as np
    codec, storage, raw_codec, saved = real_case()
    target = tmp_path / 'prepared'
    storage.save_release_input_package(saved, target)
    joined = {window: saved.joined(window) for window in (15, 30)}
    opened, attempts = [], []
    original = Path.open

    def only_members(path, mode='r', *args, **kwargs):
        if not (path.parent == target and path.name in NAMES and mode == 'rb'):
            recording_guard(attempts, 'unexpected_load_path')()
        opened.append(path.name)
        return original(path, mode, *args, **kwargs)

    forbidden = recording_guard(attempts, 'upstream_or_numerical_derivation')
    with monkeypatch.context() as local:
        local.setattr(Path, 'open', only_members)
        local.setattr(codec, 'prepare_release_inputs', forbidden)
        local.setattr(codec, 'verify_release_input_derivation', forbidden)
        local.setattr(raw_codec, 'encode_release_minute_package', forbidden)
        # W1 binds the raw encoder locally; reductions may use ndarray methods.
        # Guard those actual numerical entries, leaving _history_structure and
        # other legal structure/qualification checks available to decode.
        for name in ('encode_release_minute_package', '_bind_upstream', '_fit_statistics',
                     '_fit_state', '_transform', '_history'):
            local.setattr(codec, name, forbidden)
        for name in ('log1p', 'mean', 'std', 'median'): local.setattr(np, name, forbidden)
        local.setattr(math, 'log1p', forbidden)
        for name in ('mean', 'fmean', 'pstdev', 'median'): local.setattr(statistics, name, forbidden)
        loaded = storage.load_release_input_package(target)
        assert opened == ['COMPLETE.json', 'manifest.json', 'preprocess.json', 'inputs.json', 'labels.json']
        target.rename(tmp_path / 'moved-prepared')
        local.setattr(Path, 'open', recording_guard(attempts, 'returned_snapshot_path_open'))
        assert loaded == saved
        for window in (15, 30): assert loaded.joined(window) == joined[window]
        assert loaded.load_report.scope == 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY'
        assert loaded.load_report.upstream_replay == loaded.load_report.transform_history_replay == 'NOT_PERFORMED'
        assert loaded.load_report.fit_parameters == 'NOT_REESTIMATED'
    assert attempts == []


def test_real_bad_saved_value_rejected_before_creation(tmp_path):
    codec = importlib.import_module('traffic_anomaly.release_inputs')
    storage = importlib.import_module('traffic_anomaly.release_input_package')
    target = tmp_path / 'not-created'
    with pytest.raises(codec.ReleaseInputPreparationError) as caught:
        storage.save_release_input_package(None, target)
    assert caught.value.code == str(caught.value) == 'INVALID_PACKAGE_ARGUMENTS'
    assert not target.exists()


@pytest.mark.parametrize('operation', ['load', 'save'])
@pytest.mark.parametrize('value', [None, 1, False, b'package', object()],
                         ids=['none', 'int', 'bool', 'bytes', 'object'])
def test_real_path_argument_types_are_invalid_arguments(tmp_path, operation, value):
    if operation == 'save':
        codec, storage, _, saved = real_case()
    else:
        codec = importlib.import_module('traffic_anomaly.release_inputs')
        storage = importlib.import_module('traffic_anomaly.release_input_package')
    with pytest.raises(codec.ReleaseInputPreparationError) as caught:
        if operation == 'save': storage.save_release_input_package(saved, value)
        else: storage.load_release_input_package(value)
    assert caught.value.code == str(caught.value) == 'INVALID_PACKAGE_ARGUMENTS'
    assert list(tmp_path.iterdir()) == []


