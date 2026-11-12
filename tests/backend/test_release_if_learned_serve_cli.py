"""Finite launcher doubles and one authorized cold closed-pipe help child."""
from importlib import import_module
from io import BytesIO
from types import SimpleNamespace
import pytest
import asyncio
import logging
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import threading
import time


def api(): return import_module('traffic_api.release_if_learned_serve_cli')


def test_help_is_exact_and_borrowed_stream_stays_open(monkeypatch):
    m = api(); output = BytesIO()
    monkeypatch.setattr(m.sys, 'stdout', SimpleNamespace(buffer=output))
    assert m.main(['--help']) == 0
    assert output.getvalue() == m._HELP
    assert not output.closed


@pytest.mark.parametrize('argv', [[], '--help', ['--help', '--port=1'], ['--raw-package=@x'], ['--port=١'], ['--port=-1']])
def test_bad_syntax_is_finite(monkeypatch, argv):
    m = api(); error = BytesIO(); monkeypatch.setattr(m.sys, 'stderr', SimpleNamespace(buffer=error))
    assert m.main(argv) == 2
    assert error.getvalue() == b'{"error":"INVALID_ARGUMENTS"}\n'


def arguments():
    return [token for name in api()._PATHS for token in (name, str(Path.cwd() / 'manual'))]


def streams(monkeypatch):
    m = api(); out, err = BytesIO(), BytesIO()
    monkeypatch.setattr(m.sys, 'stdout', SimpleNamespace(buffer=out))
    monkeypatch.setattr(m.sys, 'stderr', SimpleNamespace(buffer=err))
    return out, err


def test_all_syntax_and_paths_precede_import(monkeypatch):
    m = api(); out, err = streams(monkeypatch)
    def forbidden(*a): pytest.fail('import before complete lexical admission')
    monkeypatch.setattr(m, '_import', forbidden)
    for suffix in (['--port=000001'], ['--serve-seconds=301'], ['--host=x'], ['--raw-package=x']):
        err.seek(0); err.truncate(); assert m.main(arguments() + suffix) == 2
        assert err.getvalue() == b'{"error":"INVALID_ARGUMENTS"}\n'
    bad = arguments(); bad[-1] = 'relative'
    assert m.main(bad) == 2
    assert err.getvalue().endswith(b'{"error":"INVALID_PACKAGE_PATH"}\n')


def test_six_loader_order_exact_stage_classes_and_one_factory(monkeypatch):
    m = api(); seen = []; native = []
    names = ('raw', 'prepared', 'result', 'learned')
    attributes = (('load_release_minute_package', 'ReleaseMinutePackageError'),
        ('load_release_input_package', 'ReleaseInputPreparationError'),
        ('load_release_if_result_package', 'ReleaseIFResultPackageError'),
        ('load_release_if_learned_package', 'ReleaseIFLearnedError'))
    modules = []
    for name, (loader, error_name) in zip(names, attributes):
        cls = type(name + 'Error', (ValueError,), {'code': 'INPUT_UNAVAILABLE'}); native.append(cls)
        def load(path, name=name): seen.append(name); return name
        modules.append(SimpleNamespace(**{loader: load, error_name: cls}))
    def factory(*values): seen.append(values); return 'app'
    view_error = type('ViewError', (ValueError,), {})
    view = SimpleNamespace(create_release_if_learned_view_app=factory, ReleaseIFLearnedViewError=view_error)
    mapping = dict(zip(('traffic_anomaly.release_minute_package', 'traffic_anomaly.release_input_package',
        'traffic_anomaly.release_if_result_package', 'traffic_anomaly.release_if_learned_package'), modules))
    mapping['traffic_api.release_if_learned_view'] = view
    monkeypatch.setattr(m, '_import', mapping.__getitem__)
    assert m._load_app((None,) * 6) == 'app'
    assert seen == ['raw', 'prepared', 'result', 'learned', 'result', 'learned',
        ('raw', 'prepared', 'result', 'learned', 'result', 'learned')]
    # An exact learned error escaping raw load must never have its code read.
    modules[0].load_release_minute_package = lambda p: (_ for _ in ()).throw(native[3]())
    native[3].code = property(lambda s: pytest.fail('foreign stage getter'))
    with pytest.raises(m._LaunchError, match='INTERNAL_ERROR'): m._load_app((None,) * 6)


@pytest.mark.parametrize('fault,expected', [(RuntimeError(), 'INTERNAL_ERROR'), (MemoryError(), 'RESOURCE_LIMIT'), (KeyboardInterrupt(), None)])
def test_known_getter_read_once_with_precedence(monkeypatch, fault, expected):
    m = api(); reads = []
    class Native(ValueError):
        @property
        def code(self): reads.append(1); raise fault
    def action(): raise Native()
    if expected is None:
        with pytest.raises(KeyboardInterrupt): m._call(action, Native, {'X'})
    elif expected == 'RESOURCE_LIMIT':
        with pytest.raises(MemoryError): m._call(action, Native, {'X'})
    else:
        with pytest.raises(m._LaunchError, match=expected): m._call(action, Native, {'X'})
    assert reads == [1]


def test_foreign_metaclass_is_never_hashed_compared_or_read():
    m = api()
    class Meta(type):
        def __hash__(cls): pytest.fail('foreign hash')
        def __eq__(cls, other): pytest.fail('foreign equality')
    class Foreign(ValueError, metaclass=Meta):
        @property
        def code(self): pytest.fail('foreign getter')
    def action(): raise Foreign()
    with pytest.raises(m._LaunchError, match='INTERNAL_ERROR'): m._call(action, ValueError, {'X'})


def lifecycle(monkeypatch, *, fault=None, lifespan=None, pending=False, force=False):
    m = api(); seen = []
    class Base:
        def __init__(self, config):
            self.started = False; self.force_exit = force
            self.server_state = SimpleNamespace(tasks=set(), connections=set())
            self.lifespan = SimpleNamespace(startup_failed=False, shutdown_failed=False, error_occurred=False)
            if lifespan: setattr(self.lifespan, lifespan, True)
        async def startup(self, sockets=None): self.started = True
        async def _wait_tasks_to_complete(self):
            seen.append('wait')
            if fault == 'swallow': raise asyncio.CancelledError()
        async def shutdown(self, sockets=None):
            seen.append('drain')
            if fault == 'cancel': raise asyncio.CancelledError()
            if fault == 'hang': await asyncio.Future()
            try: await self._wait_tasks_to_complete()
            except asyncio.CancelledError:
                if fault != 'swallow': raise
            if pending: self.server_state.tasks.add('remaining')
            if fault == 'shutdownflag': self.lifespan.shutdown_failed = True
        async def serve(self, sockets=None):
            await self.startup(sockets)
            if fault == 'main': raise OSError()
            await self.shutdown(sockets)
        def run(self, sockets=None): asyncio.run(self.serve(sockets))
    server = m._make_server(SimpleNamespace(Server=Base), object(), port=8769, serve_seconds=1)
    return m, server, seen


@pytest.mark.parametrize('fault', ['cancel', 'swallow', 'hang', 'main', 'shutdownflag'])
def test_single_drain_cancellation_timeout_and_primary(monkeypatch, fault):
    m, server, seen = lifecycle(monkeypatch, fault=fault)
    streams(monkeypatch); monkeypatch.setattr(m, '_DRAIN_SECONDS', .01)
    with pytest.raises((asyncio.CancelledError, TimeoutError, m._LaunchError, OSError)):
        server.run(sockets=[])
    assert seen.count('drain') == 1
    assert server._drain_attempted
    if fault != 'main': assert not server.shutdown_completed
    server.cancel_timer()


@pytest.mark.parametrize('flag', ['startup_failed', 'shutdown_failed', 'error_occurred'])
def test_silent_lifespan_flags_never_ready(monkeypatch, flag):
    m, server, seen = lifecycle(monkeypatch, lifespan=flag); out, err = streams(monkeypatch)
    with pytest.raises(m._LaunchError, match='STARTUP_FAILED'): server.run([])
    assert not server.ready_sent and not server.shutdown_completed
    assert out.getvalue() == b''


@pytest.mark.parametrize('pending,force', [(True, False), (False, True)])
def test_remaining_owned_work_or_force_suppresses_completion(monkeypatch, pending, force):
    m, server, _ = lifecycle(monkeypatch, pending=pending, force=force); streams(monkeypatch)
    with pytest.raises(m._LaunchError, match='SERVER_FAILED'): server.run([])
    assert not server.shutdown_completed
    server.cancel_timer()


def outer(monkeypatch, *, run_fault=None, close_fault=None, restore_fault=None, timer_fault=None, startup=False, output_buffer=None):
    m = api(); out, err = streams(monkeypatch); seen = []
    if output_buffer is not None: m.sys.stdout.buffer = output_buffer
    monkeypatch.setattr(m, '_load_app', lambda p: object())
    class Listener:
        def bind(self, address): seen.append(('bind', address))
        def getsockname(self): return ('127.0.0.1', 8769)
        def close(self):
            seen.append('close')
            if close_fault: raise close_fault
    listener = Listener(); monkeypatch.setattr(m.socket, 'socket', lambda *a: listener)
    def config(app, **kw):
        assert kw['lifespan'] == 'on' and kw['timeout_graceful_shutdown'] == 3
        assert kw['workers'] == 1 and kw['reload'] is False and kw['proxy_headers'] is False
        return object()
    monkeypatch.setattr(m, '_import', lambda n: SimpleNamespace(Config=config))
    class Server:
        started = not startup; ready_sent = True; shutdown_completed = True; force_exit = False
        def run(self, sockets):
            assert sockets == [listener]; seen.append('run')
            if run_fault: raise run_fault
        def cancel_timer(self):
            seen.append('timer')
            if timer_fault: raise timer_fault
    monkeypatch.setattr(m, '_make_server', lambda *a, **kw: Server())
    class Logs:
        def install(self): seen.append('install')
        def restore(self):
            seen.append('restore')
            if restore_fault: raise restore_fault
    monkeypatch.setattr(m, '_LoggingState', Logs)
    original = m._event
    def event(name, port): seen.append(name); original(name, port)
    monkeypatch.setattr(m, '_event', event)
    return m.main(arguments()), out.getvalue(), err.getvalue(), seen


def test_stopped_after_run_and_every_cleanup(monkeypatch):
    status, out, err, seen = outer(monkeypatch)
    assert status == 0 and err == b''
    assert seen[-5:] == ['run', 'timer', 'close', 'restore', 'SERVER_STOPPED']
    assert b'SERVER_STOPPED' in out


def test_normal_return_without_start_is_startup_failure(monkeypatch):
    status, out, err, seen = outer(monkeypatch, startup=True)
    assert status == 2 and out == b'' and err == b'{"error":"STARTUP_FAILED"}\n'


@pytest.mark.parametrize('slot', ['run_fault', 'close_fault', 'restore_fault', 'timer_fault'])
def test_clean_drain_followed_by_failure_never_stopped(monkeypatch, slot):
    status, out, err, seen = outer(monkeypatch, **{slot: OSError()})
    assert status == 2 and out == b'' and err == b'{"error":"SERVER_FAILED"}\n'
    assert seen[-3:] == ['timer', 'close', 'restore']


@pytest.mark.parametrize('fault,code', [(asyncio.CancelledError(), 'SERVER_FAILED'), (MemoryError(), 'RESOURCE_LIMIT'), (SystemExit(), 'SERVER_FAILED')])
def test_outer_started_faults_are_finite(monkeypatch, fault, code):
    status, out, err, seen = outer(monkeypatch, run_fault=fault)
    assert status == 2 and out == b'' and err == ('{"error":"' + code + '"}\n').encode()


def test_primary_interrupt_wins_over_all_cleanup(monkeypatch):
    status, out, err, seen = outer(monkeypatch, run_fault=KeyboardInterrupt(),
        timer_fault=MemoryError(), close_fault=OSError(), restore_fault=OSError())
    assert status == 130 and out == err == b''
    assert seen[-3:] == ['timer', 'close', 'restore']


def test_lifecycle_never_reads_familiar_error_code(monkeypatch):
    class Foreign(OSError):
        @property
        def code(self): pytest.fail('lifecycle code getter')
    status, out, err, _ = outer(monkeypatch, run_fault=Foreign())
    assert status == 2 and err == b'{"error":"SERVER_FAILED"}\n'


def test_allocate_then_bind_failure_closes_owned_listener(monkeypatch):
    m = api(); out, err = streams(monkeypatch); closed = []
    monkeypatch.setattr(m, '_load_app', lambda p: object())
    monkeypatch.setattr(m, '_import', lambda n: object())
    class Listener:
        def bind(self, address): raise OSError()
        def close(self): closed.append(True)
    monkeypatch.setattr(m.socket, 'socket', lambda *a: Listener())
    assert m.main(arguments()) == 2
    assert closed == [True] and err.getvalue() == b'{"error":"BIND_FAILED"}\n'


@pytest.mark.parametrize('fault,code', [(SystemExit(), 'STARTUP_FAILED'), (asyncio.CancelledError(), 'STARTUP_FAILED'), (MemoryError(), 'RESOURCE_LIMIT')])
def test_config_startup_classification_and_cleanup(monkeypatch, fault, code):
    m = api(); out, err = streams(monkeypatch); closed = []
    monkeypatch.setattr(m, '_load_app', lambda p: object())
    class Listener:
        def bind(self, address): pass
        def getsockname(self): return ('127.0.0.1', 8769)
        def close(self): closed.append(True)
    monkeypatch.setattr(m.socket, 'socket', lambda *a: Listener())
    def config(*a, **kw): raise fault
    monkeypatch.setattr(m, '_import', lambda n: SimpleNamespace(Config=config))
    assert m.main(arguments()) == 2
    assert closed == [True] and err.getvalue() == ('{"error":"' + code + '"}\n').encode()


def test_prelifecycle_standalone_cancellation_is_internal(monkeypatch):
    m = api(); out, err = streams(monkeypatch)
    def load(paths): raise asyncio.CancelledError()
    monkeypatch.setattr(m, '_load_app', load)
    assert m.main(arguments()) == 2 and err.getvalue() == b'{"error":"INTERNAL_ERROR"}\n'


def test_terminal_attempt_and_reentrant_diagnostic_are_independently_finite(monkeypatch):
    m = api(); calls = []; handler = m._DiagnosticHandler()
    class Buffer:
        def write(self, payload):
            calls.append(payload)
            handler.emit(logging.LogRecord('uvicorn', logging.ERROR, '', 1, 'private', (), None))
            raise OSError()
        def flush(self): pytest.fail('flush after failed write')
    monkeypatch.setattr(m.sys, 'stderr', SimpleNamespace(buffer=Buffer()))
    handler.emit(logging.LogRecord('uvicorn', logging.ERROR, '', 1, 'private', (), None))
    assert calls == [b'{"error":"SERVER_DIAGNOSTIC"}\n']
    assert m._error('SERVER_FAILED') == 2
    assert calls == [b'{"error":"SERVER_DIAGNOSTIC"}\n', b'{"error":"SERVER_FAILED"}\n']


def test_restore_attempts_all_loggers_after_a_setter_failure(monkeypatch):
    m = api(); state = m._LoggingState(); state.install(); restored = []
    original = logging.Logger.setLevel
    first = state.saved[0][0]
    def set_level(logger, level):
        restored.append(logger.name)
        if logger is first: raise OSError()
        return original(logger, level)
    with monkeypatch.context() as patch:
        patch.setattr(logging.Logger, 'setLevel', set_level)
        with pytest.raises(OSError): state.restore()
    assert restored == list(m._LOGGERS)
    # Undo the deliberately failed first field so this test borrows host logging.
    original(first, state.saved[0][3])


@pytest.mark.parametrize('code', ['bad"\ncode', None, 1, True])
def test_delta_owned_launch_code_is_finite(monkeypatch, code):
    m = api(); error = m._LaunchError(code)
    assert m._failure(error, 'SERVER_FAILED') == ('INTERNAL_ERROR', 2)


@pytest.mark.parametrize('fault,expected', [(RuntimeError(), ('INTERNAL_ERROR', 2)),
    (MemoryError(), ('RESOURCE_LIMIT', 2)), (KeyboardInterrupt(), (None, 130)),
    (asyncio.CancelledError(), ('INTERNAL_ERROR', 2))])
def test_delta_owned_launch_code_getter_is_read_once(monkeypatch, fault, expected):
    m = api(); error = m._LaunchError('RESOURCE_LIMIT'); reads = []
    def getter(self): reads.append(1); raise fault
    monkeypatch.setattr(m._LaunchError, 'code', property(getter), raising=False)
    try: actual = m._failure(error, 'SERVER_FAILED')
    except BaseException as escaped: actual = ('ESCAPED_' + type(escaped).__name__, 0)
    assert actual == expected
    assert reads == [1]


@pytest.mark.parametrize('spoof', [MemoryError, KeyboardInterrupt])
def test_delta_lifecycle_foreign_class_probe_never_read(monkeypatch, spoof):
    m = api(); reads = []
    class Foreign(OSError):
        @property
        def __class__(self): reads.append(1); return spoof
    status, out, err, seen = outer(monkeypatch, run_fault=Foreign())
    assert status == 2 and err == b'{"error":"SERVER_FAILED"}\n' and out == b''
    assert reads == []


def test_delta_cancelled_terminal_and_diagnostic_end_their_only_attempt(monkeypatch):
    m = api(); calls = []
    class Buffer:
        def write(self, payload): calls.append(payload); raise asyncio.CancelledError()
        def flush(self): pytest.fail('flush after cancellation')
    monkeypatch.setattr(m.sys, 'stderr', SimpleNamespace(buffer=Buffer()))
    assert m._error('SERVER_FAILED') == 2
    handler = m._DiagnosticHandler()
    for _ in range(2): handler.emit(logging.LogRecord('uvicorn', 40, '', 1, '', (), None))
    assert calls == [b'{"error":"SERVER_FAILED"}\n', b'{"error":"SERVER_DIAGNOSTIC"}\n']


def test_delta_cancelled_stopped_is_finite_after_all_cleanup(monkeypatch):
    m = api()
    def cancelled(*a): raise asyncio.CancelledError()
    monkeypatch.setattr(m, '_event', cancelled)
    status, out, err, seen = outer(monkeypatch)
    assert status == 2 and err == b'{"error":"SERVER_FAILED"}\n'
    assert seen[-4:] == ['timer', 'close', 'restore', 'SERVER_STOPPED']


def test_delta_cancelled_logger_restore_continues_all_states(monkeypatch):
    m = api(); state = m._LoggingState(); state.install(); restored = []
    original = logging.Logger.setLevel; first = state.saved[0][0]; closed = []
    def set_level(logger, level):
        restored.append(logger.name)
        if logger is first: raise asyncio.CancelledError()
        return original(logger, level)
    with monkeypatch.context() as patch:
        patch.setattr(logging.Logger, 'setLevel', set_level)
        patch.setattr(state.handler, 'close', lambda: closed.append(True))
        with pytest.raises(asyncio.CancelledError): state.restore()
    original(first, state.saved[0][3])
    assert restored == list(m._LOGGERS) and closed == [True]


@pytest.mark.parametrize('fault', [RuntimeError(), TypeError(), MemoryError(), KeyboardInterrupt(), asyncio.CancelledError()])
def test_delta_descriptor_cleanup_preserves_status_and_attempts_both(monkeypatch, fault):
    m = api(); seen = []
    monkeypatch.setattr(m, 'main', lambda: 130)
    class Stream:
        def __init__(self, name): self.name = name
        def fileno(self): seen.append(self.name); raise fault
    monkeypatch.setattr(m.sys, 'stdout', Stream('stdout'))
    monkeypatch.setattr(m.sys, 'stderr', Stream('stderr'))
    try: status = m._cli_entrypoint()
    except BaseException as escaped: status = 'ESCAPED_' + type(escaped).__name__
    assert status == 130 and seen == ['stdout', 'stderr']


@pytest.mark.parametrize('bad', ['short', 'bool', 'none', 'string', 'flush'])
def test_delta_ready_output_failure_has_no_timer_and_one_drain(monkeypatch, bad):
    m, server, seen = lifecycle(monkeypatch); calls = []
    class Buffer:
        def write(self, payload):
            calls.append(('write', payload))
            return {'short': len(payload)-1, 'bool': True, 'none': None, 'string': str(len(payload))}.get(bad, len(payload))
        def flush(self): calls.append(('flush', None)); raise OSError()
    monkeypatch.setattr(m.sys, 'stdout', SimpleNamespace(buffer=Buffer()))
    with pytest.raises(m._LaunchError, match='OUTPUT_ERROR'): server.run([])
    assert server._timer is None and not server.ready_sent
    assert server._drain_attempted and seen.count('drain') == 1
    assert [name for name, _ in calls] == (['write', 'flush'] if bad == 'flush' else ['write'])
    assert b'SERVER_READY' in calls[0][1] and b'SERVER_STOPPED' not in calls[0][1]


@pytest.mark.parametrize('bad', ['short', 'bool', 'none', 'string', 'flush'])
def test_delta_stopped_output_failure_follows_every_cleanup(monkeypatch, bad):
    calls = []
    class Buffer:
        def write(self, payload):
            calls.append(('write', payload))
            return {'short': len(payload)-1, 'bool': True, 'none': None, 'string': str(len(payload))}.get(bad, len(payload))
        def flush(self): calls.append(('flush', None)); raise OSError()
    status, out, err, seen = outer(monkeypatch, output_buffer=Buffer())
    assert status == 2 and err == b'{"error":"OUTPUT_ERROR"}\n'
    assert seen[-4:] == ['timer', 'close', 'restore', 'SERVER_STOPPED']
    assert [name for name, _ in calls] == (['write', 'flush'] if bad == 'flush' else ['write'])


@pytest.mark.parametrize('event', ['SERVER_READY', 'SERVER_STOPPED'])
def test_delta_exact_event_binary_write_then_flush(monkeypatch, event):
    import json
    m = api(); calls = []
    class Buffer:
        def write(self, payload): calls.append(('write', payload)); return len(payload)
        def flush(self): calls.append(('flush', None))
    monkeypatch.setattr(m.sys, 'stdout', SimpleNamespace(buffer=Buffer()))
    monkeypatch.setattr(m.os, 'getpid', lambda: 101)
    monkeypatch.setattr(m.os, 'getppid', lambda: 100)
    m._event(event, 8769)
    value = dict(schema_version=1, event=event, scope='REGISTERED_SAVED_LEARNED_TUPLE_INSPECTION_ONLY',
        host='127.0.0.1', port=8769, url='http://127.0.0.1:8769/release/learned', pid=101, parent_pid=100)
    expected = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    assert calls == [('write', expected), ('flush', None)] and len(expected) <= 65536


def test_delta_ready_flush_precedes_timer_start_and_no_stopped_inside_shutdown(monkeypatch):
    m, server, seen = lifecycle(monkeypatch); calls = []
    class Buffer:
        def write(self, payload): calls.append(('write', payload)); return len(payload)
        def flush(self): calls.append(('flush', None))
    monkeypatch.setattr(m.sys, 'stdout', SimpleNamespace(buffer=Buffer()))
    class Timer:
        def cancel(self): calls.append(('cancel', None))
    class Loop:
        def call_later(self, seconds, callback):
            assert seconds == 1 and calls[-1] == ('flush', None)
            calls.append(('timer', callback)); return Timer()
    async def run():
        with monkeypatch.context() as local:
            local.setattr(m.asyncio, 'get_running_loop', lambda: Loop())
            await server.startup([])
        await server.shutdown([])
    asyncio.run(run())
    assert server.ready_sent and server.shutdown_completed
    assert len([x for x in calls if x[0] == 'write']) == 1
    assert calls[2][0] == 'timer'
    calls[2][1](); assert server.should_exit
    server.cancel_timer()


@pytest.mark.parametrize('replacement', ['self', 'other_native'])
def test_delta_launch_getter_replacement_is_not_reclassified(monkeypatch, replacement):
    from traffic_anomaly.release_if_learned_contract import ReleaseIFLearnedError
    m = api(); error = m._LaunchError('RESOURCE_LIMIT'); reads = []
    fault = error if replacement == 'self' else ReleaseIFLearnedError('RESOURCE_LIMIT')
    def getter(self): reads.append(1); raise fault
    monkeypatch.setattr(m._LaunchError, 'code', property(getter), raising=False)
    assert m._failure(error, 'SERVER_FAILED') == ('INTERNAL_ERROR', 2)
    assert reads == [1]


def test_delta_every_legitimate_forwarded_code_remains_admitted():
    m = api()
    for code in m._CODES:
        assert m._failure(m._LaunchError(code), 'INTERNAL_ERROR') == (code, 2)


def test_delta_descriptor_dup2_failure_attempts_both_and_closes_null_handles(monkeypatch):
    m = api(); seen = []
    monkeypatch.setattr(m, 'main', lambda: 2)
    monkeypatch.setattr(m.sys, 'stdout', SimpleNamespace(fileno=lambda: 10))
    monkeypatch.setattr(m.sys, 'stderr', SimpleNamespace(fileno=lambda: 11))
    def duplicate(source, target): seen.append(('dup', source, target)); raise TypeError()
    monkeypatch.setattr(m, 'os', SimpleNamespace(open=lambda *a: 30, dup2=duplicate,
        close=lambda handle: seen.append(('close', handle)), devnull=os.devnull, O_WRONLY=os.O_WRONLY))
    assert m._cli_entrypoint() == 2
    assert seen == [('dup', 30, 10), ('close', 30), ('dup', 30, 11), ('close', 30)]


def test_one_nonreentrant_diagnostic_for_four_loggers_and_restore(monkeypatch):
    m = api(); out, err = streams(monkeypatch)
    saved = [(logging.getLogger(n), tuple(logging.getLogger(n).handlers), logging.getLogger(n).level,
        logging.getLogger(n).propagate, logging.getLogger(n).disabled) for n in m._LOGGERS]
    state = m._LoggingState(); state.install()
    for name in m._LOGGERS:
        logging.getLogger(name).error('private')
        logging.getLogger(name).error('private again')
    assert err.getvalue() == b'{"error":"SERVER_DIAGNOSTIC"}\n'
    state.restore()
    for logger, handlers, level, propagate, disabled in saved:
        assert tuple(logger.handlers) == handlers and logger.level == level
        assert logger.propagate == propagate and logger.disabled == disabled


def test_actual_new_module_buffered_closed_pipe_help_physical_exit():
    root = Path(__file__).resolve().parents[2]
    script = textwrap.dedent('''
        import asyncio, builtins, io, os, runpy, socket, sys
        blocked = {'numpy', 'sklearn', 'joblib', 'torch', 'traffic_anomaly', 'uvicorn'}
        original = builtins.__import__
        def guard(name, *args, **kwargs):
            if name.split('.')[0] in blocked: raise AssertionError('forbidden product import')
            return original(name, *args, **kwargs)
        class Fence:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in blocked: raise AssertionError('forbidden product import')
        builtins.__import__ = guard
        sys.meta_path.insert(0, Fence())
        def forbidden(*args, **kwargs): raise AssertionError('listener creation')
        socket.socket = forbidden
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        sys.stdout = io.TextIOWrapper(io.BufferedWriter(io.FileIO(write_fd, 'wb', closefd=True)), encoding='utf-8')
        sys.argv = ['traffic_api.release_if_learned_serve_cli', '--help']
        runpy.run_module('traffic_api.release_if_learned_serve_cli', run_name='__main__')
    ''')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (root, root / 'src/core', root / 'src/backend'))),
        PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', OMP_NUM_THREADS='1',
        OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    child = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', '-c', script], cwd=root,
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    captured = [bytearray(), bytearray()]; overflow = []
    def capture(index, stream):
        while True:
            chunk = stream.read(min(65536, 1048576 - len(captured[index])) or 1)
            if not chunk: break
            if len(captured[index]) + len(chunk) > 1048576:
                overflow.append(index); child.kill(); break
            captured[index].extend(chunk)
    workers = [threading.Thread(target=capture, args=(i, stream), daemon=True)
        for i, stream in enumerate((child.stdout, child.stderr))]
    started = time.monotonic(); watchdog = threading.Timer(20, child.kill); watchdog.start()
    try:
        for worker in workers: worker.start()
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=2); pytest.fail('physical child exceeded ten seconds')
        for worker in workers: worker.join(timeout=2)
        assert all(not worker.is_alive() for worker in workers)
    finally:
        watchdog.cancel()
        child.stdout.close(); child.stderr.close()
    output, error = map(bytes, captured)
    assert time.monotonic() - started < 20 and not overflow
    assert child.returncode == 2, error
    assert output == b'' and error == b'{"error":"OUTPUT_ERROR"}\n'
