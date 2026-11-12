"""Finite error and stream boundaries; owned process exits are observed."""
import json
import subprocess
import sys

import pytest

from traffic_anomaly import release_if_learned_cli as cli


def failing_operation(monkeypatch, error):
    monkeypatch.setattr(cli, '_arguments', lambda argv: ('inspect', {}))
    monkeypatch.setattr(cli, '_paths', lambda *a: {})
    def fail(*a):
        raise error
    monkeypatch.setattr(cli, '_execute', fail)
    return cli.main([])


@pytest.mark.parametrize('error,code', [(MemoryError('private'), 'RESOURCE_LIMIT'),
    (KeyboardInterrupt('private'), 'INTERRUPTED'), (ValueError('private'), 'INTERNAL_ERROR')])
def test_direct_failures_are_finite(monkeypatch, capfdbinary, error, code):
    assert failing_operation(monkeypatch, error) == 2
    streams = capfdbinary.readouterr()
    assert streams.out == b''
    assert streams.err == ('{"error":"' + code + '"}\n').encode()


def test_unknown_error_never_reads_hostile_getter(monkeypatch, capfdbinary):
    calls = []
    class Foreign(ValueError):
        @property
        def code(self):
            calls.append(True)
            raise KeyboardInterrupt('private')
    assert failing_operation(monkeypatch, Foreign('private')) == 2
    assert calls == []
    assert capfdbinary.readouterr().err == b'{"error":"INTERNAL_ERROR"}\n'


@pytest.mark.parametrize('failure,code', [(MemoryError, 'RESOURCE_LIMIT'),
    (KeyboardInterrupt, 'INTERRUPTED'), (ValueError, 'INTERNAL_ERROR')])
def test_registered_getter_failures_are_terminal(monkeypatch, capfdbinary, failure, code):
    error = cli._CLIError('INVALID_ARGUMENTS')
    calls = []
    def bad(self):
        calls.append(True)
        raise failure('private')
    monkeypatch.setattr(cli._CLIError, 'code', property(bad), raising=False)
    assert failing_operation(monkeypatch, error) == 2
    assert calls == [True]
    assert capfdbinary.readouterr().err == ('{"error":"' + code + '"}\n').encode()


@pytest.mark.parametrize('name,code', [('numpy', 'INCOMPATIBLE_RUNTIME'), ('numpy.core', 'INCOMPATIBLE_RUNTIME'),
    ('traffic_anomaly.missing', 'INTERNAL_ERROR'), ('unrelated', 'INTERNAL_ERROR')])
def test_cli_owned_exact_missing_dependency_mapping(monkeypatch, capfdbinary, name, code):
    def fail(*a):
        raise ModuleNotFoundError('private', name=name)
    monkeypatch.setattr(cli.importlib, 'import_module', fail)
    assert cli.main(['inspect', '--learned-package', 'C:/absolute']) == 2
    assert capfdbinary.readouterr().err == ('{"error":"' + code + '"}\n').encode()


class Binary:
    def __init__(self, *, count='full', write_error=None, flush_error=None):
        self.count, self.write_error, self.flush_error = count, write_error, flush_error
        self.writes, self.flushes, self.closed = [], 0, False

    def write(self, payload):
        self.writes.append(payload)
        if self.write_error:
            raise self.write_error('private')
        return len(payload) if self.count == 'full' else self.count

    def flush(self):
        self.flushes += 1
        if self.flush_error:
            raise self.flush_error('private')

    def close(self):
        self.closed = True


class Stream:
    def __init__(self, binary):
        self.buffer = binary

    def close(self):
        self.buffer.close()


@pytest.mark.parametrize('kind,code,flushes', [
    ('short', 'OUTPUT_ERROR', 0), ('bool', 'OUTPUT_ERROR', 0), ('none', 'OUTPUT_ERROR', 0),
    ('pipe', 'OUTPUT_ERROR', 0), ('write-memory', 'RESOURCE_LIMIT', 0),
    ('flush', 'OUTPUT_ERROR', 1), ('flush-memory', 'RESOURCE_LIMIT', 1),
    ('interrupt', 'INTERRUPTED', 0)])
def test_stdout_one_attempt_keeps_host_streams(monkeypatch, kind, code, flushes):
    kwargs = {'short': dict(count=1), 'bool': dict(count=True), 'none': dict(count=None),
        'pipe': dict(write_error=BrokenPipeError), 'write-memory': dict(write_error=MemoryError),
        'flush': dict(flush_error=OSError), 'flush-memory': dict(flush_error=MemoryError),
        'interrupt': dict(write_error=KeyboardInterrupt)}[kind]
    out, err = Binary(**kwargs), Binary()
    stdout, stderr = Stream(out), Stream(err)
    monkeypatch.setattr(sys, 'stdout', stdout)
    monkeypatch.setattr(sys, 'stderr', stderr)
    assert cli.main(['--help']) == 2
    assert sys.stdout is stdout and sys.stderr is stderr
    assert len(out.writes) == 1 and out.flushes == flushes
    assert err.writes == [('{' + '"error":"' + code + '"}\n').encode()]
    assert err.flushes == 1
    assert not out.closed and not err.closed


@pytest.mark.parametrize('failure', [MemoryError, KeyboardInterrupt, BrokenPipeError])
def test_stderr_failure_ends_single_attempt(monkeypatch, failure):
    out, err = Binary(), Binary(flush_error=failure)
    stdout, stderr = Stream(out), Stream(err)
    monkeypatch.setattr(sys, 'stdout', stdout)
    monkeypatch.setattr(sys, 'stderr', stderr)
    assert cli.main([]) == 2
    assert out.writes == [] and len(err.writes) == 1 and err.flushes == 1
    assert not out.closed and not err.closed


def test_owned_entrypoint_physical_exit_not_shutdown_120(tmp_path):
    # An actual buffered descriptor whose flush cannot finish is repaired only
    # by the owned entrypoint. main's host-stream behavior is tested separately.
    script = '''
import io, os, runpy, sys
r, w = os.pipe()
os.close(r)
sys.stdout = io.TextIOWrapper(io.BufferedWriter(io.FileIO(w, 'wb', closefd=False)), encoding='utf-8')
sys.argv = ['traffic_anomaly.release_if_learned_cli', '--help']
runpy.run_module('traffic_anomaly.release_if_learned_cli', run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', script], capture_output=True)
    (tmp_path / 'stdout.bin').write_bytes(result.stdout)
    (tmp_path / 'stderr.bin').write_bytes(result.stderr)
    assert result.returncode == 2
    assert result.stdout == b''
    assert result.stderr == b'{"error":"OUTPUT_ERROR"}\n'


@pytest.mark.parametrize('variant', ['mutated', 'subclass', 'wrong-class-code'])
def test_known_errors_admit_only_exact_class_specific_codes(monkeypatch, capfdbinary, variant):
    from traffic_anomaly.release_if_learned_contract import ReleaseIFLearnedError
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    cli._learned_disk()
    cli._result_disk()
    if variant == 'subclass':
        class Derived(ReleaseIFLearnedError):
            pass
        error = Derived('SCORE_MISMATCH')
    elif variant == 'wrong-class-code':
        error = ReleaseIFResultPackageError('OUTPUT_ERROR')
        error.code = 'DERIVATION_MISMATCH'
    else:
        error = ReleaseIFLearnedError('SCORE_MISMATCH')
        error.code = 'private/unknown'
    assert failing_operation(monkeypatch, error) == 2
    assert capfdbinary.readouterr().err == b'{"error":"INTERNAL_ERROR"}\n'


@pytest.mark.parametrize('variant', ['direct-memory', 'translated-memory'])
def test_observable_memory_and_pretranslated_dependency_error(monkeypatch, capfdbinary, variant):
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    cli._result_disk()
    error = MemoryError('private') if variant == 'direct-memory' else ReleaseIFResultPackageError('OUTPUT_ERROR')
    assert failing_operation(monkeypatch, error) == 2
    code = 'RESOURCE_LIMIT' if variant == 'direct-memory' else 'OUTPUT_ERROR'
    assert capfdbinary.readouterr().err == ('{"error":"' + code + '"}\n').encode()


def test_foreign_exception_metaclass_is_never_hashed_or_compared(monkeypatch, capfdbinary):
    from traffic_anomaly.release_if_learned_contract import ReleaseIFLearnedError
    cli._learned_disk()
    callbacks = []
    class ForeignMeta(type):
        def __hash__(cls):
            callbacks.append('hash')
            return hash(ReleaseIFLearnedError)
        def __eq__(cls, other):
            callbacks.append('class equality')
            return True
    class ForeignError(ValueError, metaclass=ForeignMeta):
        @property
        def code(self):
            callbacks.append('code getter')
            return 'OUTPUT_ERROR'
    assert failing_operation(monkeypatch, ForeignError('private')) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == b'{"error":"INTERNAL_ERROR"}\n'
    assert callbacks == []


def test_error_payload_closed_set_and_bound():
    for code in cli._CLI_CODES | cli._LEARNED_CODES | cli._PACKAGE_CODES:
        payload = ('{"error":"' + code + '"}\n').encode('ascii')
        assert len(payload) <= 128
        assert json.loads(payload) == {'error': code}
