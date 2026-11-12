"""Foreground loopback launcher; import and help use only the standard library."""
from __future__ import annotations
import asyncio
from collections.abc import Sequence
import importlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import sys

_HELP = (
    'usage: python -m traffic_api.release_if_learned_serve_cli --raw-package ABS --prepared-package ABS --current-result ABS --current-learned ABS --h30-result ABS --h30-learned ABS [--port PORT] [--serve-seconds SECONDS]\n'
    'View registered saved learned declarations on 127.0.0.1; no fitting, scoring or replay.\n'
    '-h, --help  show this fixed usage (use alone)\n').encode()
_PATHS = ('--raw-package', '--prepared-package', '--current-result', '--current-learned', '--h30-result', '--h30-learned')
_COMMON = frozenset(('INVALID_PACKAGE_ARGUMENTS INVALID_PACKAGE INCOMPATIBLE_PACKAGE RESOURCE_LIMIT '
    'INTEGRITY_MISMATCH INCONSISTENT_PACKAGE INVALID_PACKAGE_PATH INPUT_UNAVAILABLE OUTPUT_EXISTS PACKAGE_CHANGED OUTPUT_ERROR').split())
_PREPARED = _COMMON | frozenset(('INVALID_PREPARATION_CONFIG UPSTREAM_IDENTITY_MISMATCH NO_TRAINING_NORMAL_MINUTES NONFINITE_FIT_STATE DERIVATION_MISMATCH').split())
_RESULT = _COMMON | {'INPUT_BINDING_MISMATCH'}
_LEARNED = frozenset(('INVALID_LEARNED_ARGUMENTS INVALID_LEARNED_PACKAGE INCOMPATIBLE_LEARNED_PACKAGE '
    'RESOURCE_LIMIT INTEGRITY_MISMATCH INPUT_BINDING_MISMATCH NO_TRAINING_NORMAL NO_CALIBRATION_NORMAL '
    'INVALID_INPUT_NUMERIC MODEL_UNAVAILABLE MODEL_ERROR INVALID_MODEL_STATE INVALID_MODEL_SCORES '
    'SCORE_MISMATCH CALIBRATION_MISMATCH PREDICTION_MISMATCH INCOMPATIBLE_RUNTIME INVALID_PACKAGE_PATH '
    'INPUT_UNAVAILABLE OUTPUT_EXISTS PACKAGE_CHANGED OUTPUT_ERROR LEARNED_ERROR').split())
_VIEW = frozenset(('INVALID_VIEW_ARGUMENTS INPUT_BINDING_MISMATCH RESOURCE_LIMIT VIEW_UNAVAILABLE').split())
_CODES = _COMMON | _PREPARED | _RESULT | _LEARNED | _VIEW | frozenset((
    'INVALID_ARGUMENTS INVALID_PACKAGE_PATH RESOURCE_LIMIT OUTPUT_ERROR INCOMPATIBLE_RUNTIME '
    'INTERNAL_ERROR BIND_FAILED STARTUP_FAILED SERVER_FAILED').split())
_LOGGERS = ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'uvicorn.asgi')
_DRAIN_SECONDS = 5


class _LaunchError(ValueError):
    def __init__(self, code): self.code = code; super().__init__(code)


def _need(condition, code):
    if not condition: raise _LaunchError(code)


def _arguments(argv):
    if argv is None: argv = sys.argv[1:]
    _need(not isinstance(argv, (str, bytes)) and isinstance(argv, Sequence), 'INVALID_ARGUMENTS')
    values = list(argv)
    _need(all(type(v) is str and not v.startswith('@') for v in values), 'INVALID_ARGUMENTS')
    if values in (['-h'], ['--help']): return None
    options = {}; i = 0
    while i < len(values):
        name, equal, value = values[i].partition('=')
        _need(name in (*_PATHS, '--port', '--serve-seconds') and name not in options, 'INVALID_ARGUMENTS')
        if not equal:
            i += 1
            _need(i < len(values), 'INVALID_ARGUMENTS')
            value = values[i]
        _need(bool(value) and not value.startswith(('@', '-')), 'INVALID_ARGUMENTS')
        options[name] = value; i += 1
    _need(all(p in options for p in _PATHS), 'INVALID_ARGUMENTS')
    for name, default, digits, maximum in (('--port', '8769', 5, 65535), ('--serve-seconds', '300', 3, 300)):
        value = options.get(name, default)
        _need(re.fullmatch('[0-9]{1,' + str(digits) + '}', value) is not None, 'INVALID_ARGUMENTS')
        number = int(value); _need(1 <= number <= maximum, 'INVALID_ARGUMENTS'); options[name] = number
    return options


def _lexical(raw):
    _need(bool(raw) and '\0' not in raw and not raw.startswith(('\\\\', '//')), 'INVALID_PACKAGE_PATH')
    path = Path(raw)
    _need(path.is_absolute() and '..' not in path.parts, 'INVALID_PACKAGE_PATH')
    if os.name == 'nt':
        _need(len(path.drive) == 2 and path.drive[0].isascii() and path.drive[0].isalpha()
            and path.drive[1] == ':' and not any(':' in p or os.path.isreserved(p) for p in path.parts[1:]), 'INVALID_PACKAGE_PATH')
    return path


def _import(name):
    try: return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if type(error) is ModuleNotFoundError and type(error.name) is str and error.name.split('.')[0] == 'numpy':
            raise _LaunchError('INCOMPATIBLE_RUNTIME') from None
        raise


def _call(function, expected, codes, *args):
    try: return function(*args)
    except MemoryError: raise
    except Exception as error:
        if type(error) is expected:
            try: code = error.code
            except MemoryError: raise
            except Exception: raise _LaunchError('INTERNAL_ERROR') from None
            if type(code) is str and code in codes: raise _LaunchError(code) from None
        raise _LaunchError('INTERNAL_ERROR') from None


def _load_app(paths):
    specs = (
        ('traffic_anomaly.release_minute_package', 'load_release_minute_package', 'ReleaseMinutePackageError', _COMMON),
        ('traffic_anomaly.release_input_package', 'load_release_input_package', 'ReleaseInputPreparationError', _PREPARED),
        ('traffic_anomaly.release_if_result_package', 'load_release_if_result_package', 'ReleaseIFResultPackageError', _RESULT),
        ('traffic_anomaly.release_if_learned_package', 'load_release_if_learned_package', 'ReleaseIFLearnedError', _LEARNED))
    values = []
    for index, spec_index in enumerate((0, 1, 2, 3, 2, 3)):
        name, function, error, codes = specs[spec_index]; module = _import(name)
        values.append(_call(getattr(module, function), getattr(module, error), codes, paths[index]))
    view = _import('traffic_api.release_if_learned_view')
    return _call(view.create_release_if_learned_view_app, view.ReleaseIFLearnedViewError, _VIEW, *values)


def _json_bytes(value):
    result = bytearray()
    for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).iterencode(value):
        chunk = chunk.encode(); _need(len(result) + len(chunk) + 1 <= 65536, 'OUTPUT_ERROR'); result.extend(chunk)
    result.extend(b'\n'); return bytes(result)


def _write_stream(stream, payload):
    try:
        size = stream.buffer.write(payload)
        _need(type(size) is int and size == len(payload), 'OUTPUT_ERROR')
        stream.buffer.flush()
    except MemoryError: raise
    except Exception: raise _LaunchError('OUTPUT_ERROR') from None


def _error(code):
    try:
        payload = ('{"error":"' + code + '"}\n').encode('ascii')
        if len(payload) <= 128: _write_stream(sys.stderr, payload)
    except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit): pass
    return 2


def _event(event, port):
    _write_stream(sys.stdout, _json_bytes(dict(schema_version=1, event=event,
        scope='REGISTERED_SAVED_LEARNED_TUPLE_INSPECTION_ONLY', host='127.0.0.1', port=port,
        url=f'http://127.0.0.1:{port}/release/learned', pid=os.getpid(), parent_pid=os.getppid())))


class _DiagnosticHandler(logging.Handler):
    def __init__(self): super().__init__(); self.attempted = False
    def emit(self, record):
        if self.attempted: return
        self.attempted = True
        try: _write_stream(sys.stderr, b'{"error":"SERVER_DIAGNOSTIC"}\n')
        except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit): pass
    def handleError(self, record): pass


class _LoggingState:
    def __init__(self): self.saved = []; self.handler = _DiagnosticHandler()
    def install(self):
        for name in _LOGGERS:
            logger = logging.getLogger(name)
            self.saved.append((logger, logger.handlers, logger.filters, logger.level, logger.propagate, logger.disabled))
            logger.handlers = [self.handler]; logger.filters = []; logger.setLevel(logging.WARNING)
            logger.propagate = False; logger.disabled = False
    def restore(self):
        primary = None
        for logger, handlers, filters, level, propagate, disabled in self.saved:
            # Attempt each independent state field even if a host setter fails.
            for name, value in (('handlers', handlers), ('filters', filters), ('level', level),
                    ('propagate', propagate), ('disabled', disabled)):
                try:
                    if name == 'level': logger.setLevel(value)
                    else: setattr(logger, name, value)
                except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit) as error:
                    if primary is None: primary = error
        try: self.handler.close()
        except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit) as error:
            if primary is None: primary = error
        if primary is not None: raise primary


def _lifespan_ok(server):
    life = getattr(server, 'lifespan', None)
    return life is not None and all(getattr(life, name, None) is False for name in
        ('startup_failed', 'shutdown_failed', 'error_occurred'))


def _make_server(uvicorn, config, *, port, serve_seconds):
    class _LearnedServer(uvicorn.Server):
        def __init__(self):
            super().__init__(config)
            self.ready_sent = False; self.shutdown_completed = False
            self._drain_attempted = False; self._wait_completed = False
            self._wait_failed = False; self._timer = None
        def cancel_timer(self):
            if self._timer is not None: self._timer.cancel(); self._timer = None
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            _need(self.started and _lifespan_ok(self), 'STARTUP_FAILED')
            _event('SERVER_READY', port); self.ready_sent = True
            self._timer = asyncio.get_running_loop().call_later(serve_seconds, lambda: setattr(self, 'should_exit', True))
        async def _wait_tasks_to_complete(self):
            try: await super()._wait_tasks_to_complete()
            except (asyncio.CancelledError, TimeoutError): self._wait_failed = True; raise
            self._wait_completed = True
        async def shutdown(self, sockets=None):
            if self._drain_attempted: return
            self._drain_attempted = True
            try:
                await asyncio.wait_for(super().shutdown(sockets=sockets), timeout=_DRAIN_SECONDS)
            except (asyncio.CancelledError, TimeoutError): self._wait_failed = True; raise
            _need(not self.force_exit and self._wait_completed and not self._wait_failed
                and _lifespan_ok(self) and not self.server_state.tasks and not self.server_state.connections, 'SERVER_FAILED')
            self.shutdown_completed = True
        async def serve(self, sockets=None):
            primary = None
            try: await super().serve(sockets=sockets)
            except BaseException as error: primary = error; raise
            finally:
                if self.started and not self._drain_attempted:
                    try: await self.shutdown(sockets=sockets)
                    except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                        if primary is None: raise
    return _LearnedServer()


def _failure(error, stage):
    if issubclass(type(error), KeyboardInterrupt): return None, 130
    if issubclass(type(error), MemoryError): return 'RESOURCE_LIMIT', 2
    if type(error) is _LaunchError:
        try: code = error.code
        except KeyboardInterrupt: return None, 130
        except MemoryError: return 'RESOURCE_LIMIT', 2
        except (Exception, asyncio.CancelledError, SystemExit): return 'INTERNAL_ERROR', 2
        return (code if type(code) is str and code in _CODES else 'INTERNAL_ERROR'), 2
    return stage, 2


def main(argv: Sequence[str] | None = None) -> int:
    listener = server = logging_state = None
    code = None; status = 2; stage = 'INTERNAL_ERROR'; primary = None
    try:
        args = _arguments(argv)
        if args is None: _write_stream(sys.stdout, _HELP); return 0
        paths = tuple(_lexical(args[name]) for name in _PATHS)
        app = _load_app(paths)
        uvicorn = _import('uvicorn')
        stage = 'BIND_FAILED'
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('127.0.0.1', args['--port']))
        address = listener.getsockname()
        _need(type(address) is tuple and len(address) == 2 and address[0] == '127.0.0.1'
            and type(address[1]) is int and address[1] == args['--port'], 'BIND_FAILED')
        stage = 'STARTUP_FAILED'
        logging_state = _LoggingState(); logging_state.install()
        config = uvicorn.Config(app, host='127.0.0.1', port=address[1], workers=1, reload=False,
            access_log=False, log_config=None, log_level=None, loop='asyncio', http='h11', ws='none',
            proxy_headers=False, lifespan='on', timeout_graceful_shutdown=3)
        server = _make_server(uvicorn, config, port=address[1], serve_seconds=args['--serve-seconds'])
        server.run(sockets=[listener])
        _need(server.started and server.ready_sent and server.shutdown_completed and not server.force_exit,
            'SERVER_FAILED' if server.started else 'STARTUP_FAILED')
        status = 0
    except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit) as error:
        primary = error
        if server is not None and server.started: stage = 'SERVER_FAILED'
        code, status = _failure(error, stage)
    finally:
        steps = []
        if server is not None: steps.append(server.cancel_timer)
        if listener is not None: steps.append(listener.close)
        if logging_state is not None: steps.append(logging_state.restore)
        for cleanup in steps:
            try: cleanup()
            except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit) as error:
                if primary is None:
                    primary = error; code, status = _failure(error, 'SERVER_FAILED')
    if status == 0:
        try: _event('SERVER_STOPPED', args['--port'])
        except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit) as error:
            code, status = _failure(error, 'SERVER_FAILED')
    return _error(code) if code is not None else status


def _cli_entrypoint():
    status = main()
    if status != 0:
        for stream in (sys.stdout, sys.stderr):
            try:
                target = stream.fileno(); null_fd = os.open(os.devnull, os.O_WRONLY)
                try: os.dup2(null_fd, target)
                finally:
                    if null_fd != target: os.close(null_fd)
            except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit): pass
    return status


if __name__ == '__main__': raise SystemExit(_cli_entrypoint())
