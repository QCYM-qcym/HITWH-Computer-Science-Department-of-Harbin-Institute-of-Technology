"""Manual disk/adapter integration only. Actual numerical Task I is NOT_RUN."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.core.test_release_if_learned_cli import api, fit_environment


def test_cold_moved_learned_only_inspect_with_model_pickle_numpy_blocked(tmp_path):
    from tests.core.test_release_if_learned_contract import package
    from traffic_anomaly.release_if_learned_package import save_release_if_learned_package
    original = tmp_path / 'saved'
    save_release_if_learned_package(package(), original)
    moved = tmp_path / 'moved'
    original.rename(moved)
    script = '''
import builtins, importlib, os, pathlib, sys
real = builtins.__import__
forbidden_roots = {'numpy','sklearn','joblib','torch','cloudpickle','pickle'}
allowed_product = {'traffic_anomaly', 'traffic_anomaly.release_if_learned_cli',
    'traffic_anomaly.release_if_learned_contract', 'traffic_anomaly.release_if_learned_package',
    'traffic_anomaly.release_if_learned_summary', 'traffic_anomaly.iforest_numeric_state'}
denied_attempts = []
def forbidden(name):
    return (name.split('.')[0] in forbidden_roots or
        name.startswith('traffic_anomaly.') and name not in allowed_product)
class Fence:
    def find_spec(self, fullname, path=None, target=None):
        if forbidden(fullname):
            denied_attempts.append(fullname)
            raise AssertionError('forbidden module resolution')
        return None
sys.meta_path.insert(0, Fence())
def guarded(name, *a, **k):
    if forbidden(name):
        denied_attempts.append(name)
        raise AssertionError('forbidden import')
    return real(name, *a, **k)
builtins.__import__ = guarded
# Prove the finder blocks importlib's direct resolution, which bypasses the
# builtins hook. These probes never execute the forbidden module's code.
for name in ('numpy', 'traffic_anomaly.release_if_learned',
        'traffic_anomaly.release_if_result_package', 'traffic_anomaly.release_minute_package',
        'traffic_anomaly.release_input_package', 'traffic_anomaly.release_inputs',
        'traffic_anomaly.release_model_inputs'):
    before = len(denied_attempts)
    try:
        importlib.import_module(name)
    except AssertionError:
        pass
    else:
        raise AssertionError('meta_path fence bypassed')
    assert denied_attempts[before:] == [name]
assert not any(forbidden(name) for name in sys.modules)
denied_attempts.clear()
import traffic_anomaly.release_if_learned_cli as cli
target = pathlib.Path(sys.argv[1])
real_open, real_stat, real_scan = pathlib.Path.open, pathlib.Path.lstat, os.scandir
def check(path):
    p = pathlib.Path(path)
    assert p == target or p in target.parents or target in p.parents
def bounded_open(path, *a, **k):
    check(path)
    assert path.parent == target and path.name in {'COMPLETE.json','manifest.json','numeric-state.json'}
    return real_open(path, *a, **k)
def bounded_stat(path, *a, **k):
    check(path)
    return real_stat(path, *a, **k)
def bounded_scan(path):
    assert pathlib.Path(path) == target
    return real_scan(path)
pathlib.Path.open, pathlib.Path.lstat, os.scandir = bounded_open, bounded_stat, bounded_scan
assert cli.main(['inspect','--learned-package',str(target)]) == 0
assert denied_attempts == []
assert not any(forbidden(name) for name in sys.modules)
'''
    run = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', script, str(moved)], capture_output=True)
    assert run.returncode == 0, run.stderr
    receipt = json.loads(run.stdout)
    assert receipt['status'] == 'INTERNAL_CONSISTENCY_CHECKED'
    assert receipt['summary']['checks']['numerical_replay'] == 'NOT_RUN'
    assert run.stderr == b'' and str(moved).encode() not in run.stdout


@pytest.mark.parametrize('where', ['result-partial', 'result-late', 'learned-partial', 'learned-late'])
def test_failed_native_saver_keeps_every_residue(tmp_path, monkeypatch, capfdbinary, where):
    from traffic_anomaly import release_if_result_package as result_disk
    from traffic_anomaly import release_if_learned_package as learned_disk
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch)
    result = where.startswith('result')
    module = result_disk if result else learned_disk
    name = 'save_release_if_' + ('result' if result else 'learned') + '_package'
    original = getattr(module, name)
    kind = result_disk.ReleaseIFResultPackageError if result else learned_disk.ReleaseIFLearnedError
    def failing(value, path):
        if where.endswith('late'):
            original(value, path)
        else:
            calls.append('result-save' if result else 'learned-save')
            path.mkdir()
            (path / 'partial.bin').write_bytes(b'partial-preserved')
        raise kind('OUTPUT_ERROR')
    monkeypatch.setattr(module, name, failing)
    assert api().main(args) == 2
    streams = capfdbinary.readouterr()
    assert streams.out == b'' and streams.err == b'{"error":"OUTPUT_ERROR"}\n'
    assert calls == ['raw','prepared','pair','fit','result-save'] + ([] if result else ['learned-save'])
    target = paths['result' if result else 'learned']
    if where.endswith('partial'):
        assert (target / 'partial.bin').read_bytes() == b'partial-preserved'
    elif result:
        assert result_disk.load_release_if_result_package(target) == run.result_package
    else:
        assert learned_disk.load_release_if_learned_package(target) == run.learned_package
    if result:
        assert not paths['learned'].exists()
    else:
        assert result_disk.load_release_if_result_package(paths['result']) == run.result_package


def test_stdout_flush_failure_keeps_both_complete_packages(tmp_path, monkeypatch):
    from tests.core.test_release_if_learned_cli_error_exit import Binary, Stream
    from traffic_anomaly.release_if_result_package import load_release_if_result_package
    from traffic_anomaly.release_if_learned_package import load_release_if_learned_package
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch)
    out, err = Binary(flush_error=BrokenPipeError), Binary()
    monkeypatch.setattr(sys, 'stdout', Stream(out))
    monkeypatch.setattr(sys, 'stderr', Stream(err))
    assert api().main(args) == 2
    assert len(out.writes) == 1 and out.flushes == 1
    assert err.writes == [b'{"error":"OUTPUT_ERROR"}\n'] and err.flushes == 1
    assert calls == ['raw','prepared','pair','fit','result-save','learned-save']
    assert load_release_if_result_package(paths['result']) == run.result_package
    assert load_release_if_learned_package(paths['learned']) == run.learned_package
