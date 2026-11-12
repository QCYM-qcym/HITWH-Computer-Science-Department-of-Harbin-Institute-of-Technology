"""Manual learned-state disk cases; real handles, no estimator operations."""
import importlib
import inspect
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


NAMES = ('numeric-state.json', 'manifest.json', 'COMPLETE.json')


def storage():
    return importlib.import_module('traffic_anomaly.release_if_learned_package')


def _manual():
    import importlib
    c = importlib.import_module('traffic_anomaly.release_if_learned_contract')
    p = importlib.import_module('traffic_anomaly.iforest_numeric_state')
    state = p.IForestNumericState(p.NUMERIC_STATE_VERSION, p.NUMERIC_STATE_PROFILE_ID,
        p.NUMERIC_STATE_ALGORITHM_ID, 13, tuple(range(13)), 1,
        (p.IForestNumericTree((p.IForestNumericNode(None, None, None, None, 1),)),) * 16)
    def ref(profile, letter):
        return c.ReleaseIFLearnedReference(profile, letter * 64, letter * 64, 123)
    context = c.ReleaseIFLearnedContext(c.LEARNED_PACKAGE_PROFILE_ID, 'current13',
        ref('c17-release-minute-package-v1', 'a'),
        ref('c17-release-prepared-input-package-v1', 'b'),
        ref('c17-release-iforest-result-package-v1', 'c'), 'd' * 64,
        2, 1, 1, 1, 'e' * 64, 'c17-release-log1p-mad-input-rules-v1',
        c._feature_columns('current13'),
        c.ReleaseIFLearnedConfiguration(13, 16, 1, 1.0, False, 'auto', 42, 1),
        c.LEARNED_FIT_RUNTIME_ID)
    return c._make_release_if_learned_package(context, state)


def rejected(code, operation):
    c = importlib.import_module('traffic_anomaly.release_if_learned_contract')
    with pytest.raises(c.ReleaseIFLearnedError) as caught:
        operation()
    error = caught.value
    assert type(error) is c.ReleaseIFLearnedError
    assert error.code == code
    assert str(error) == code and error.args == (code,)
    assert error.__suppress_context__


@pytest.fixture
def disk(tmp_path):
    module = storage()
    target = tmp_path / 'saved'
    module.save_release_if_learned_package(_manual(), target)
    return module, target


class Stream:
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
    def read(self, size):
        return self.hooks['read'](self.raw, size) if 'read' in self.hooks else self.raw.read(size)
    def write(self, payload):
        return self.hooks['write'](self.raw, payload) if 'write' in self.hooks else self.raw.write(payload)
    def flush(self):
        return self.hooks['flush'](self.raw) if 'flush' in self.hooks else self.raw.flush()


def intercept(monkeypatch, path, wanted_mode, factory):
    original, handles = Path.open, []
    def opened(value, mode='r', *args, **kwargs):
        raw = original(value, mode, *args, **kwargs)
        if value == path and mode == wanted_mode:
            handles.append(raw)
            return factory(raw)
        return raw
    monkeypatch.setattr(Path, 'open', opened)
    return handles


def test_fixed_members_roundtrip_moved_and_exact_order(tmp_path, monkeypatch):
    module = storage()
    c = importlib.import_module('traffic_anomaly.release_if_learned_contract')
    package, target = _manual(), tmp_path / 'package'
    expected = dict(c.encode_release_if_learned_package(package))
    observed, original = [], Path.open
    def opened(path, mode='r', *args, **kwargs):
        observed.append((path.name, mode))
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opened)
    assert module.save_release_if_learned_package(package, target) == package.identity
    assert observed == [(name, mode) for name in NAMES for mode in ('xb', 'rb')]
    observed.clear()
    assert module.load_release_if_learned_package(target) == package
    assert observed == [(name, 'rb') for name in reversed(NAMES)]
    monkeypatch.setattr(Path, 'open', original)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == expected
    copied = tmp_path / 'moved'
    shutil.copytree(target, copied)
    target.rename(tmp_path / 'old-location')
    assert module.load_release_if_learned_package(copied) == package
    assert package.load_report.numerical_replay == 'NOT_RUN'


def test_validation_precedes_all_output_io(tmp_path, monkeypatch):
    module = storage()
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('io')
        raise AssertionError('must not inspect output')
    for name in ('lstat', 'mkdir', 'open'):
        monkeypatch.setattr(Path, name, forbidden)
    rejected('INVALID_LEARNED_ARGUMENTS', lambda: module.save_release_if_learned_package(None, object()))
    assert attempts == []


@pytest.mark.parametrize('nonempty', [False, True])
def test_existing_output_is_preserved(tmp_path, nonempty):
    module = storage()
    target = tmp_path / 'owned'
    target.mkdir()
    if nonempty:
        (target / 'owner').write_bytes(b'keep')
    rejected('OUTPUT_EXISTS', lambda: module.save_release_if_learned_package(_manual(), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == ({'owner': b'keep'} if nonempty else {})


class ForeignPath:
    def __fspath__(self):
        raise AssertionError('foreign path protocol called')


class StringSubclass(str):
    def __str__(self):
        raise AssertionError('foreign string conversion called')


class NativePathSubclass(type(Path())):
    def __str__(self):
        raise AssertionError('foreign path conversion called')


@pytest.mark.parametrize('value', [None, False, 1, b'path', ForeignPath(), StringSubclass('bad'), NativePathSubclass('bad')])
@pytest.mark.parametrize('operation', ['load', 'save'])
def test_only_exact_native_path_or_string_arguments(value, operation, tmp_path):
    module = storage()
    rejected('INVALID_LEARNED_ARGUMENTS', lambda:
        module.load_release_if_learned_package(value) if operation == 'load' else
        module.save_release_if_learned_package(_manual(), value))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('value', ['', 'relative', 'bad\0path', '//server/share/path',
    '\\\\server\\share\\path', 'C:relative', 'C:\\parent\\..\\package',
    'C:\\NUL\\package', 'C:\\package:stream', '\\\\?\\C:\\package'])
def test_lexical_paths_rejected_before_stat(value, monkeypatch):
    module = storage()
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('stat')
        raise AssertionError('lexical rejection must precede stat')
    monkeypatch.setattr(Path, 'lstat', forbidden)
    rejected('INVALID_PACKAGE_PATH', lambda: module.load_release_if_learned_package(value))
    assert attempts == []


@pytest.mark.parametrize('change', ['missing', 'extra', 'directory', *NAMES])
def test_inventory_and_real_member_caps_precede_first_open(disk, monkeypatch, change):
    module, target = disk
    limits = {'numeric-state.json': 262144, 'manifest.json': 8192, 'COMPLETE.json': 4096}
    if change == 'missing':
        (target / NAMES[0]).unlink()
    elif change == 'extra':
        (target / 'foreign').write_bytes(b'keep')
    elif change == 'directory':
        (target / NAMES[0]).unlink()
        (target / NAMES[0]).mkdir()
    else:
        with (target / change).open('wb') as stream:
            stream.truncate(limits[change] + 1)
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('open')
        raise AssertionError('inventory must precede open')
    monkeypatch.setattr(Path, 'open', forbidden)
    expected = ('INVALID_LEARNED_PACKAGE' if change in ('missing', 'extra') else
                'INVALID_PACKAGE_PATH' if change == 'directory' else 'RESOURCE_LIMIT')
    rejected(expected, lambda: module.load_release_if_learned_package(target))
    assert attempts == []


def test_real_hardlink_rejected(disk, tmp_path):
    module, target = disk
    os.link(target / NAMES[0], tmp_path / 'hardlink')
    rejected('INVALID_PACKAGE_PATH', lambda: module.load_release_if_learned_package(target))


@pytest.mark.parametrize('kind', ['member', 'directory', 'ancestor'])
def test_real_symlink_rejected_when_host_allows_it(disk, tmp_path, kind):
    module, target = disk
    if kind == 'member':
        destination = tmp_path / 'original-member'
        (target / NAMES[0]).rename(destination)
        link, input_path = target / NAMES[0], target
    else:
        destination = target if kind == 'directory' else tmp_path
        link = tmp_path / 'linked'
        input_path = link if kind == 'directory' else link / target.name
    try:
        link.symlink_to(destination, target_is_directory=kind != 'member')
    except OSError as error:
        pytest.skip('host does not permit real symlink creation: ' + type(error).__name__)
    rejected('INVALID_PACKAGE_PATH', lambda: module.load_release_if_learned_package(input_path))


@pytest.mark.parametrize('defect', ['reparse', 'duplicate'])
def test_stat_reparse_and_duplicate_entity_rejected(disk, monkeypatch, defect):
    module, target = disk
    original = Path.lstat
    first = original(target / NAMES[0])
    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target / NAMES[1]:
            fields = {name: getattr(info, name, 0) for name in ('st_dev', 'st_ino', 'st_mode',
                'st_file_attributes', 'st_size', 'st_mtime_ns', 'st_nlink')}
            if defect == 'reparse':
                fields['st_file_attributes'] |= 0x400
            else:
                fields.update(st_dev=first.st_dev, st_ino=first.st_ino)
            return SimpleNamespace(**fields)
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    rejected('INVALID_PACKAGE_PATH', lambda: module.load_release_if_learned_package(target))


@pytest.mark.parametrize('change', ['member', 'directory', 'extra', 'delete', 'grow'])
def test_captured_package_changes_reject(disk, tmp_path, monkeypatch, change):
    module, target = disk
    old = tmp_path / 'old'
    original_payload = (target / NAMES[-1]).read_bytes()
    def mutate():
        if change == 'member':
            path = target / NAMES[-1]
            path.rename(old)
            path.write_bytes(original_payload)
        elif change == 'directory':
            target.rename(old)
            shutil.copytree(old, target)
        elif change == 'extra':
            (target / 'extra').write_bytes(b'keep')
        elif change == 'delete':
            (target / NAMES[-1]).unlink()
        else:
            with (target / NAMES[-1]).open('ab') as stream:
                stream.write(b'x')
    handles = intercept(monkeypatch, target / NAMES[-1], 'rb', lambda raw: Stream(raw, close=mutate))
    rejected('PACKAGE_CHANGED', lambda: module.load_release_if_learned_package(target))
    assert handles and all(handle.closed for handle in handles)


@pytest.mark.parametrize('operation', ['load', 'save'])
def test_wrong_handle_rejected_before_access(disk, tmp_path, monkeypatch, operation):
    module, target = disk
    other = tmp_path / 'other'
    other.write_bytes(b'keep')
    output = tmp_path / 'output'
    path, mode = (target / NAMES[-1], 'rb') if operation == 'load' else (output / NAMES[0], 'xb')
    def different(raw):
        raw.close()
        return Stream(other.open('r+b'))
    intercept(monkeypatch, path, mode, different)
    rejected('PACKAGE_CHANGED', lambda:
        module.load_release_if_learned_package(target) if operation == 'load' else
        module.save_release_if_learned_package(_manual(), output))
    assert other.read_bytes() == b'keep'


@pytest.mark.parametrize('kind', ['short', 'nonbytes'])
def test_bad_read_returns_rejected(disk, monkeypatch, kind):
    module, target = disk
    handles = intercept(monkeypatch, target / NAMES[-1], 'rb', lambda raw:
        Stream(raw, read=lambda stream, size: stream.read(1) if kind == 'short' else bytearray(b'x')))
    rejected('PACKAGE_CHANGED' if kind == 'short' else 'INPUT_UNAVAILABLE',
             lambda: module.load_release_if_learned_package(target))
    assert all(handle.closed for handle in handles)


@pytest.mark.parametrize('member', NAMES)
@pytest.mark.parametrize('stage', ['short_write', 'nonint_write', 'flush', 'close', 'readback'])
def test_save_failures_preserve_residue_and_refuse_reuse(tmp_path, monkeypatch, member, stage):
    module = storage()
    target = tmp_path / 'new'
    def fail(*args):
        raise PermissionError('private detail')
    function = (lambda stream, payload: stream.write(payload[:1])) if stage == 'short_write' else (
        (lambda stream, payload: True) if stage == 'nonint_write' else fail)
    hook = 'write' if stage.endswith('write') else 'read' if stage == 'readback' else stage
    with monkeypatch.context() as local:
        handles = intercept(local, target / member, 'rb' if stage == 'readback' else 'xb',
                            lambda raw: Stream(raw, **{hook: function}))
        rejected('OUTPUT_ERROR', lambda: module.save_release_if_learned_package(_manual(), target))
    assert handles and all(handle.closed for handle in handles)
    assert (target / member).exists()
    if member != NAMES[-1]:
        assert not (target / NAMES[-1]).exists()
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    rejected('OUTPUT_EXISTS', lambda: module.save_release_if_learned_package(_manual(), target))
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before


def test_readback_same_length_corruption_is_integrity_failure(tmp_path, monkeypatch):
    module = storage()
    target = tmp_path / 'new'
    def tamper():
        path = target / NAMES[0]
        info = path.stat()
        path.write_bytes(b'x' * info.st_size)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    intercept(monkeypatch, target / NAMES[0], 'xb', lambda raw: Stream(raw, close=tamper))
    rejected('INTEGRITY_MISMATCH', lambda: module.save_release_if_learned_package(_manual(), target))
    assert (target / NAMES[0]).exists() and not (target / NAMES[-1]).exists()


def test_late_failure_can_leave_valid_loadable_package(tmp_path, monkeypatch):
    module = storage()
    target, package = tmp_path / 'late', _manual()
    original = module.decode_release_if_learned_package
    def fail(members):
        original(members)
        raise RuntimeError('late private failure')
    with monkeypatch.context() as local:
        local.setattr(module, 'decode_release_if_learned_package', fail)
        rejected('LEARNED_ERROR', lambda: module.save_release_if_learned_package(package, target))
    assert module.load_release_if_learned_package(target) == package
    rejected('OUTPUT_EXISTS', lambda: module.save_release_if_learned_package(package, target))


class ForeignOSError(OSError):
    @property
    def code(self):
        raise AssertionError('foreign exception code read')


ForeignOSError.__module__ = 'builtins'


@pytest.mark.parametrize('exception,code', [(PermissionError, 'INPUT_UNAVAILABLE'),
    (ForeignOSError, 'LEARNED_ERROR'), (MemoryError, 'RESOURCE_LIMIT')])
def test_finite_load_io_error_mapping(disk, monkeypatch, exception, code):
    module, target = disk
    def fail(*args):
        raise exception('private text')
    handles = intercept(monkeypatch, target / NAMES[-1], 'rb', lambda raw: Stream(raw, read=fail))
    rejected(code, lambda: module.load_release_if_learned_package(target))
    assert all(handle.closed for handle in handles)


@pytest.mark.parametrize('operation', ['load', 'save'])
def test_interrupt_propagates_and_handles_close(disk, tmp_path, monkeypatch, operation):
    module, target = disk
    output = tmp_path / 'interrupted'
    def fail(*args):
        raise KeyboardInterrupt
    path, mode, hook = ((target / NAMES[-1], 'rb', 'read') if operation == 'load' else
                        (output / NAMES[0], 'xb', 'write'))
    handles = intercept(monkeypatch, path, mode, lambda raw: Stream(raw, **{hook: fail}))
    with pytest.raises(KeyboardInterrupt):
        if operation == 'load':
            module.load_release_if_learned_package(target)
        else:
            module.save_release_if_learned_package(_manual(), output)
    assert all(handle.closed for handle in handles)


def test_initial_unavailable_and_missing_output_parent(tmp_path):
    module = storage()
    rejected('INPUT_UNAVAILABLE', lambda: module.load_release_if_learned_package(tmp_path / 'missing'))
    rejected('OUTPUT_ERROR', lambda: module.save_release_if_learned_package(_manual(), tmp_path / 'missing' / 'new'))
    assert list(tmp_path.iterdir()) == []


def test_initial_inventory_directory_disappearance_after_capture(disk, monkeypatch):
    module, target = disk
    original = os.scandir
    def disappeared(path):
        if path == target:
            raise FileNotFoundError('directory captured before inventory')
        return original(path)
    monkeypatch.setattr(os, 'scandir', disappeared)
    rejected('PACKAGE_CHANGED', lambda: module.load_release_if_learned_package(target))


def test_captured_write_path_disappearance_is_package_changed(tmp_path, monkeypatch):
    module = storage()
    target = tmp_path / 'new'
    path, missing = target / NAMES[0], []
    original = Path.lstat
    def lstat(value, *args, **kwargs):
        if value == path and missing:
            raise FileNotFoundError('captured member disappeared')
        return original(value, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', lstat)
    def flush(stream):
        stream.flush()
        missing.append(True)
    handles = intercept(monkeypatch, path, 'xb', lambda raw: Stream(raw, flush=flush))
    rejected('PACKAGE_CHANGED', lambda: module.save_release_if_learned_package(_manual(), target))
    assert handles and all(handle.closed for handle in handles)


@pytest.mark.parametrize('operation', ['load', 'save'])
def test_final_inventory_detects_change_after_decode(disk, tmp_path, monkeypatch, operation):
    module, source = disk
    target = source if operation == 'load' else tmp_path / 'new'
    old = tmp_path / 'old-member'
    original = module.decode_release_if_learned_package
    def changed(members):
        result = original(members)
        (target / NAMES[0]).rename(old)
        (target / NAMES[0]).write_bytes(members[NAMES[0]])
        return result
    with monkeypatch.context() as local:
        local.setattr(module, 'decode_release_if_learned_package', changed)
        rejected('PACKAGE_CHANGED', lambda:
            module.load_release_if_learned_package(target) if operation == 'load' else
            module.save_release_if_learned_package(_manual(), target))
    assert old.exists() and module.load_release_if_learned_package(target) == _manual()


@pytest.mark.parametrize('value,code', [(bytearray(b'bad'), 'OUTPUT_ERROR'), (b'x', 'PACKAGE_CHANGED')])
def test_save_readback_bad_types_and_lengths(tmp_path, monkeypatch, value, code):
    module = storage()
    target = tmp_path / 'new'
    intercept(monkeypatch, target / NAMES[0], 'rb', lambda raw: Stream(raw, read=lambda *args: value))
    rejected(code, lambda: module.save_release_if_learned_package(_manual(), target))
    assert (target / NAMES[0]).exists() and not (target / NAMES[-1]).exists()


def test_growing_read_is_bounded_to_limit_plus_one(disk, monkeypatch):
    module, target = disk
    observed = []
    def growing(stream, size):
        with (target / NAMES[-1]).open('ab') as writer:
            writer.write(b'x' * 8192)
        payload = stream.read(size)
        observed.append((size, len(payload)))
        return payload
    handles = intercept(monkeypatch, target / NAMES[-1], 'rb', lambda raw: Stream(raw, read=growing))
    rejected('PACKAGE_CHANGED', lambda: module.load_release_if_learned_package(target))
    assert observed == [(4097, 4097)] and all(handle.closed for handle in handles)


@pytest.mark.parametrize('race', ['directory', 'member'])
def test_exclusive_creation_race_preserves_other_owner(tmp_path, monkeypatch, race):
    module = storage()
    target = tmp_path / 'raced'
    if race == 'directory':
        original = Path.mkdir
        def mkdir(path, *args, **kwargs):
            if path == target:
                original(path)
                (path / 'owner').write_bytes(b'keep')
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, 'mkdir', mkdir)
        marker = target / 'owner'
    else:
        original = Path.open
        def opened(path, mode='r', *args, **kwargs):
            if path == target / NAMES[0] and mode == 'xb':
                with original(path, 'wb') as stream:
                    stream.write(b'keep')
            return original(path, mode, *args, **kwargs)
        monkeypatch.setattr(Path, 'open', opened)
        marker = target / NAMES[0]
    rejected('OUTPUT_EXISTS' if race == 'directory' else 'OUTPUT_ERROR',
             lambda: module.save_release_if_learned_package(_manual(), target))
    assert marker.read_bytes() == b'keep' and not (target / NAMES[-1]).exists()


@pytest.mark.parametrize('operation', ['load', 'save'])
def test_foreign_learned_error_subclass_is_never_trusted(disk, tmp_path, monkeypatch, operation):
    module, target = disk
    c = importlib.import_module('traffic_anomaly.release_if_learned_contract')
    class ForeignError(c.ReleaseIFLearnedError):
        def __init__(self):
            ValueError.__init__(self, 'foreign message')
        @property
        def code(self):
            raise AssertionError('must not inspect foreign code')
    def fail(*args):
        raise ForeignError()
    monkeypatch.setattr(module, 'decode_release_if_learned_package', fail)
    rejected('LEARNED_ERROR', lambda:
        module.load_release_if_learned_package(target) if operation == 'load' else
        module.save_release_if_learned_package(_manual(), tmp_path / 'new'))


def test_disk_codec_import_fence_in_fresh_process(tmp_path):
    storage()
    script = '''
import builtins, importlib, sys
from pathlib import Path
blocked = {'numpy', 'sklearn', 'joblib', 'torch', 'pickle', 'cloudpickle'}
assert not any(name.split('.')[0] in blocked for name in sys.modules)
attempts = []
original = builtins.__import__
original_module = importlib.import_module
def check(name):
    if name.lstrip('.').split('.')[0] in blocked:
        attempts.append(name)
        raise AssertionError('forbidden dependency')
def guarded(name, *args, **kwargs):
    check(name)
    return original(name, *args, **kwargs)
def guarded_module(name, *args, **kwargs):
    check(name)
    return original_module(name, *args, **kwargs)
builtins.__import__ = guarded
importlib.import_module = guarded_module
''' + inspect.getsource(_manual) + '''
for name in ('release_if_learned_contract', 'release_if_learned', 'release_if_learned_package'):
    importlib.import_module('traffic_anomaly.' + name)
disk = importlib.import_module('traffic_anomaly.release_if_learned_package')
package = _manual()
target = Path(sys.argv[1])
assert disk.save_release_if_learned_package(package, target) == package.identity
assert disk.load_release_if_learned_package(target) == package
assert attempts == []
assert not any(name.split('.')[0] in blocked for name in sys.modules)
assert not any(name in sys.modules for name in ('traffic_anomaly.release_inputs',
    'traffic_anomaly.release_input_package', 'traffic_anomaly.release_if_result_package',
    'traffic_anomaly.candidate_inputs'))
print('COLD_CODEC_DISK_PASS')
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-B', '-c', script, str(tmp_path / 'cold')],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == 'COLD_CODEC_DISK_PASS'
