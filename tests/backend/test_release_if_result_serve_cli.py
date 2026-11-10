"""Foreground launcher contract; controlled server, never a real listener."""
import asyncio
from importlib import import_module
import json
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


CURRENT = str(Path.cwd() / 'test-current-result')
H30 = str(Path.cwd() / 'test-h30-result')
PRIVATE = '/private-sentinel/not-a-public-result'


def api():
    try:
        return import_module('traffic_api.release_if_result_serve_cli')
    except ModuleNotFoundError as exc:
        if exc.name == 'traffic_api.release_if_result_serve_cli':
            pytest.fail('foreground saved-result launcher feature has not been implemented')
        raise


def arguments(*extra):
    return ['--current-dir', CURRENT, '--h30-dir', H30, *extra]


@pytest.fixture
def world(monkeypatch):
    from traffic_anomaly import release_if_result_package as package
    from traffic_api import release_if_result_view as view
    w = SimpleNamespace(events=[], sockets=[], servers=[], configs=[], stage=None,
        error=RuntimeError(PRIVATE), force=False, close_error=False, current=object(), h30=object(), app=object())
    w.real_factory = view.create_release_if_result_view_app
    w.real_loader = package.load_release_if_result_package
    def load(path):
        w.events.append(('load', path))
        if w.stage == 'load':
            raise w.error
        assert path in (Path(CURRENT), Path(H30))
        return w.current if path == Path(CURRENT) else w.h30
    def factory(current, h30):
        assert current is w.current and h30 is w.h30
        w.events.append('factory')
        if w.stage == 'factory':
            raise w.error
        return w.app
    monkeypatch.setattr(package, 'load_release_if_result_package', load)
    monkeypatch.setattr(view, 'create_release_if_result_view_app', factory)
    class Listener:
        def __init__(self):
            self.closed = False
            w.sockets.append(self)
        def bind(self, address):
            w.events.append(('bind', address))
            self.port = address[1]
            if w.stage == 'bind':
                raise OSError(PRIVATE)
        def getsockname(self):
            return ('127.0.0.1', self.port)
        def close(self):
            w.events.append('close')
            self.closed = True
            if w.close_error:
                raise OSError(PRIVATE)
    def socket(*args):
        w.events.append('socket')
        return Listener()
    w.socket = SimpleNamespace(AF_INET=2, SOCK_STREAM=1, socket=socket)
    class Timer:
        def __init__(self, callback):
            self.callback, self.cancelled = callback, False
        def cancel(self):
            assert not self.cancelled
            self.cancelled = True
            w.events.append('timer cancel')
    def later(seconds, callback):
        w.events.append(('timer', seconds))
        w.timer = Timer(callback)
        return w.timer
    w.loop = SimpleNamespace(call_later=later)
    uvicorn = ModuleType('uvicorn')
    def config(app, **kwargs):
        assert app is w.app
        w.events.append('config')
        w.configs.append(kwargs)
        return SimpleNamespace()
    class Server:
        def __init__(self, config):
            self.started = self.force_exit = self.should_exit = False
            w.servers.append(self)
        async def startup(self, sockets=None):
            w.events.append('startup')
            if w.stage == 'startup':
                raise RuntimeError(PRIVATE)
            self.started = True
        async def shutdown(self, sockets=None):
            w.events.append('shutdown')
            if w.stage == 'shutdown':
                raise RuntimeError(PRIVATE)
            self.force_exit = w.force
        async def serve(self, sockets=None):
            await self.startup(sockets=sockets)
            if w.stage == 'runtime':
                raise RuntimeError(PRIVATE)
            if w.stage == 'interrupt':
                raise KeyboardInterrupt(PRIVATE)
            await self.shutdown(sockets=sockets)
        def run(self, sockets=None):
            assert sockets == [w.sockets[-1]]
            w.events.append('run')
            asyncio.run(self.serve(sockets=sockets))
    uvicorn.Config, uvicorn.Server = config, Server
    monkeypatch.setitem(sys.modules, 'uvicorn', uvicorn)
    return w


def bind_world(monkeypatch, w):
    m = api()
    monkeypatch.setattr(m, 'socket', w.socket)
    monkeypatch.setattr(m, 'asyncio', SimpleNamespace(get_running_loop=lambda: w.loop))
    return m


BAD = [[], ['--current-dir', CURRENT], ['--h30-dir', H30],
    arguments('--host', '0.0.0.0'), arguments('--port', '0'), arguments('--port', '65536'),
    arguments('--port', '+1'), arguments('--port', '１２'), arguments('--port', '1.0'),
    arguments('--serve-seconds', '0'), arguments('--serve-seconds', '301'),
    arguments('--serve-seconds', '+1'), arguments('--serve-seconds', '١'),
    arguments('--port=1', '--port=2'), arguments('--current-dir='+CURRENT),
    ['--current-dir', 'relative', '--h30-dir', H30], ['--help', *arguments()],
    arguments('extra'), arguments('--port', '000001'), '@file', b'bytes', [1]]


@pytest.mark.parametrize('argv', [['--help'], ['-h'], *BAD])
def test_help_and_invalid_arguments_never_import_load_or_bind(monkeypatch, capfdbinary, argv):
    import builtins
    m = api()
    attempts = []
    original = builtins.__import__
    def importing(name, *args, **kwargs):
        if name.startswith(('traffic_anomaly', 'traffic_api', 'uvicorn')):
            attempts.append(name)
            raise AssertionError('product import')
        return original(name, *args, **kwargs)
    def forbidden(*args, **kwargs):
        attempts.append('I/O')
        raise AssertionError('I/O')
    monkeypatch.setattr(builtins, '__import__', importing)
    monkeypatch.setattr(Path, 'open', forbidden)
    monkeypatch.setattr(m, 'socket', SimpleNamespace(socket=forbidden))
    status = m.main(argv)
    out, err = capfdbinary.readouterr()
    if argv in (['--help'], ['-h']):
        assert status == 0 and out.startswith(b'usage: python -m traffic_api.release_if_result_serve_cli') and err == b''
    else:
        assert status == 2 and out == b'' and err == b'{"error":"INVALID_ARGUMENTS"}\n'
    assert attempts == []


@pytest.mark.parametrize('port,seconds', [(8768, 300), (1, 1), (65535, 300)])
def test_load_both_once_freeze_before_fixed_loopback_bind_and_close(monkeypatch, world, capfdbinary, port, seconds):
    w = world
    m = bind_world(monkeypatch, w)
    extra = [] if (port, seconds) == (8768, 300) else ['--port', str(port), '--serve-seconds', str(seconds)]
    assert m.main(arguments(*extra)) == 0
    out, err = capfdbinary.readouterr()
    assert err == b''
    assert w.events[:5] == [('load', Path(CURRENT)), ('load', Path(H30)), 'factory', 'socket', ('bind', ('127.0.0.1', port))]
    assert len(w.sockets) == len(w.servers) == 1 and w.sockets[0].closed
    assert w.events.count('close') == 1 and ('timer', seconds) in w.events and w.timer.cancelled
    assert w.configs == [dict(host='127.0.0.1', port=port, workers=1, reload=False, access_log=False,
        log_config=None, log_level=None, loop='asyncio', http='h11', ws='none', proxy_headers=False)]
    events = [json.loads(line) for line in out.splitlines()]
    assert [e['event'] for e in events] == ['SERVER_READY', 'SERVER_STOPPED']
    assert all(e['host'] == '127.0.0.1' and e['port'] == port and e['url'] == f'http://127.0.0.1:{port}/release/results' for e in events)


@pytest.mark.parametrize('stage,code', [('load', 'INVALID_PACKAGE'), ('factory', 'VIEW_UNAVAILABLE'),
    ('bind', 'BIND_FAILED'), ('startup', 'STARTUP_FAILED'), ('runtime', 'SERVER_FAILED'), ('shutdown', 'SERVER_FAILED')])
def test_safe_failures_close_resources_without_success_claim(monkeypatch, world, capfdbinary, stage, code):
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    from traffic_api.release_if_result_view import ReleaseIFResultViewError
    w = world
    w.stage = stage
    w.error = ReleaseIFResultPackageError(code) if stage == 'load' else ReleaseIFResultViewError(code)
    m = bind_world(monkeypatch, w)
    assert m.main(arguments()) == 2
    out, err = capfdbinary.readouterr()
    assert err == ('{"error":"'+code+'"}\n').encode() and PRIVATE.encode() not in out+err
    assert b'SERVER_STOPPED' not in out
    if stage in ('load', 'factory'):
        assert out == b'' and not w.sockets
    else:
        assert len(w.sockets) == 1 and w.sockets[0].closed


@pytest.mark.parametrize('stage', ['load', 'factory'])
def test_unknown_error_is_safe_and_never_binds(monkeypatch, world, capfdbinary, stage):
    w = world
    w.stage = stage
    m = bind_world(monkeypatch, w)
    assert m.main(arguments()) == 2
    out, err = capfdbinary.readouterr()
    assert out == b'' and err == b'{"error":"INTERNAL_ERROR"}\n' and not w.sockets


LOAD_CODES = ('INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE', 'RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE', 'INVALID_PACKAGE_PATH', 'INPUT_UNAVAILABLE',
    'OUTPUT_EXISTS', 'PACKAGE_CHANGED', 'OUTPUT_ERROR', 'INPUT_BINDING_MISMATCH')
VIEW_CODES = ('INVALID_VIEW_ARGUMENTS', 'INCOMPATIBLE_RESULT_PAIR', 'RESOURCE_LIMIT', 'VIEW_UNAVAILABLE')


@pytest.mark.parametrize('stage,code', [('load', code) for code in LOAD_CODES] + [('factory', code) for code in VIEW_CODES])
def test_declared_admission_codes_propagate_without_details_or_bind(monkeypatch, world, capfdbinary, stage, code):
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    from traffic_api.release_if_result_view import ReleaseIFResultViewError
    w = world
    w.stage = stage
    w.error = ReleaseIFResultPackageError(code) if stage == 'load' else ReleaseIFResultViewError(code)
    w.error.args = (PRIVATE,)
    w.error.__cause__ = RuntimeError(PRIVATE)
    m = bind_world(monkeypatch, w)
    assert m.main(arguments()) == 2
    out, err = capfdbinary.readouterr()
    assert out == b'' and err == ('{"error":"'+code+'"}\n').encode() and not w.sockets


@pytest.mark.parametrize('stage', ['load', 'factory'])
@pytest.mark.parametrize('code', [None, [], {}, True, 'PRIVATE_UNKNOWN'])
def test_malformed_declared_error_code_is_internal(monkeypatch, world, capfdbinary, stage, code):
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    from traffic_api.release_if_result_view import ReleaseIFResultViewError
    w = world
    w.stage = stage
    w.error = ReleaseIFResultPackageError('INVALID_PACKAGE') if stage == 'load' else ReleaseIFResultViewError('VIEW_UNAVAILABLE')
    w.error.code, w.error.args = code, (PRIVATE,)
    m = bind_world(monkeypatch, w)
    assert m.main(arguments()) == 2
    out, err = capfdbinary.readouterr()
    assert out == b'' and err == b'{"error":"INTERNAL_ERROR"}\n' and not w.sockets


@pytest.mark.parametrize('kind', ['short', 'flush', 'interrupt'])
def test_ready_output_failure_closes_server_and_does_not_arm_timer(monkeypatch, world, capfdbinary, kind):
    w = world
    m = bind_world(monkeypatch, w)
    class Sink:
        def write(self, payload):
            if kind == 'interrupt':
                raise KeyboardInterrupt(PRIVATE)
            return len(payload)-1 if kind == 'short' else len(payload)
        def flush(self):
            raise OSError(PRIVATE)
    monkeypatch.setattr(m, 'sys', SimpleNamespace(stdout=SimpleNamespace(buffer=Sink()), stderr=sys.stderr))
    assert m.main(arguments()) == (130 if kind == 'interrupt' else 2)
    out, err = capfdbinary.readouterr()
    assert b'SERVER_STOPPED' not in out and PRIVATE.encode() not in out+err
    assert not hasattr(w, 'timer') and all(s.closed for s in w.sockets) and 'shutdown' in w.events
    if kind != 'interrupt':
        assert err == b'{"error":"OUTPUT_ERROR"}\n'


def test_stopped_short_output_does_not_report_success(monkeypatch, world, capfdbinary):
    w = world
    m = bind_world(monkeypatch, w)
    writes = []
    class Sink:
        def write(self, payload):
            writes.append(json.loads(payload)['event'])
            return len(payload) if len(writes) == 1 else len(payload)-1
        def flush(self):
            pass
    monkeypatch.setattr(m, 'sys', SimpleNamespace(stdout=SimpleNamespace(buffer=Sink()), stderr=sys.stderr))
    assert m.main(arguments()) == 2
    out, err = capfdbinary.readouterr()
    assert out == b'' and err == b'{"error":"OUTPUT_ERROR"}\n'
    assert writes == ['SERVER_READY', 'SERVER_STOPPED'] and not w.servers[0].stopped_sent
    assert w.timer.cancelled and w.sockets[0].closed


@pytest.mark.parametrize('kind', ['interrupt', 'force', 'close'])
def test_interrupt_force_exit_and_close_failure_are_not_success(monkeypatch, world, capfdbinary, kind):
    w = world
    w.stage = 'interrupt' if kind == 'interrupt' else None
    w.force = kind == 'force'
    w.close_error = kind == 'close'
    m = bind_world(monkeypatch, w)
    assert m.main(arguments()) == (130 if kind == 'interrupt' else 2)
    out, err = capfdbinary.readouterr()
    assert PRIVATE.encode() not in out+err and all(s.closed for s in w.sockets) and w.timer.cancelled
    if kind != 'close':
        assert b'SERVER_STOPPED' not in out


def test_actual_pair_factory_freezes_assets_before_controlled_bind(monkeypatch, world, capfdbinary):
    from .test_release_if_result_view import hand_package
    from traffic_api import release_if_result_view as view
    w = world
    w.current, w.h30 = hand_package(), hand_package('h30_26')
    def factory(a, b):
        assert not w.sockets
        w.events.append('factory')
        w.app = w.real_factory(a, b)
        return w.app
    monkeypatch.setattr(view, 'create_release_if_result_view_app', factory)
    m = bind_world(monkeypatch, w)
    assert m.main(arguments('--serve-seconds', '1')) == 0
    out, err = capfdbinary.readouterr()
    assert err == b'' and b'SERVER_STOPPED' in out


def test_actual_saved_directories_load_once_and_freeze_before_controlled_bind(monkeypatch, world, tmp_path, capfdbinary):
    from dataclasses import asdict
    from fastapi.testclient import TestClient
    from traffic_anomaly import release_if_result_package as package
    from traffic_api import release_if_result_view as view
    from .test_release_if_result_view import hand_package, SUMMARY
    w = world
    current, h30 = hand_package(), hand_package('h30_26')
    directories = (tmp_path / 'current', tmp_path / 'h30')
    for saved, directory in zip((current, h30), directories):
        package.save_release_if_result_package(saved, directory)
    before = {str(path): path.read_bytes() for directory in directories for path in directory.iterdir()}
    def load(directory):
        assert not w.sockets and directory in directories
        w.events.append(('actual load', directory))
        return w.real_loader(directory)
    def factory(a, b):
        assert not w.sockets
        w.events.append('actual factory')
        w.app = w.real_factory(a, b)
        return w.app
    monkeypatch.setattr(package, 'load_release_if_result_package', load)
    monkeypatch.setattr(view, 'create_release_if_result_view_app', factory)
    m = bind_world(monkeypatch, w)
    assert m.main(['--current-dir', str(directories[0]), '--h30-dir', str(directories[1]), '--serve-seconds', '1']) == 0
    out, err = capfdbinary.readouterr()
    assert err == b'' and b'SERVER_STOPPED' in out
    assert w.events[:5] == [('actual load', directories[0]), ('actual load', directories[1]),
                            'actual factory', 'socket', ('bind', ('127.0.0.1', 8768))]
    with TestClient(w.app) as client:
        summary = client.get(SUMMARY).json()
    assert summary['result_references'] == dict(current13=asdict(current.identity), h30_26=asdict(h30.identity))
    assert {str(path): path.read_bytes() for directory in directories for path in directory.iterdir()} == before


def test_logging_is_bounded_and_restored(monkeypatch, world, capfdbinary):
    m = bind_world(monkeypatch, world)
    names = ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'uvicorn.asgi')
    def snapshot():
        return {name: (l.handlers, l.filters, l.level, l.propagate, l.disabled)
                for name in names for l in [logging.getLogger(name)]}
    before = snapshot()
    with m._safe_uvicorn_logging():
        try:
            raise RuntimeError(PRIVATE)
        except RuntimeError:
            logging.getLogger('uvicorn.error').error(PRIVATE, exc_info=True, stack_info=True)
    out, err = capfdbinary.readouterr()
    assert snapshot() == before and out == b'' and err == b'{"error":"SERVER_DIAGNOSTIC"}\n'
