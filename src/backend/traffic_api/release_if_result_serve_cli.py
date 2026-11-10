"""Foreground loopback launcher for two frozen saved IF result views."""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import re
import socket
import sys


_HELP=(
    'usage: python -m traffic_api.release_if_result_serve_cli --current-dir ABS_DIR --h30-dir ABS_DIR '
    '[--port PORT] [--serve-seconds SECONDS]\n'
    'View two saved result packages on 127.0.0.1; no fitting or scoring.\n'
    '-h, --help  show this fixed usage (use alone)\n'
).encode('utf-8')
_RELEASE_CODES=frozenset(('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE','OUTPUT_EXISTS',
    'PACKAGE_CHANGED','OUTPUT_ERROR','INPUT_BINDING_MISMATCH'))
_VIEW_CODES=frozenset(('INVALID_VIEW_ARGUMENTS','INCOMPATIBLE_RESULT_PAIR','RESOURCE_LIMIT','VIEW_UNAVAILABLE'))
_LOGGERS=('uvicorn','uvicorn.error','uvicorn.access','uvicorn.asgi')


class _LaunchError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)


class _Parser(argparse.ArgumentParser):
    def error(self,message):raise _LaunchError('INVALID_ARGUMENTS')
    def exit(self,status=0,message=None):raise _LaunchError('INVALID_ARGUMENTS')


def _integer(value,*,digits,lower,upper):
    if re.fullmatch('[0-9]{1,'+str(digits)+'}',value) is None:raise _LaunchError('INVALID_ARGUMENTS')
    number=int(value)
    if not lower<=number<=upper:raise _LaunchError('INVALID_ARGUMENTS')
    return number


def _arguments(argv):
    if argv is None:argv=sys.argv[1:]
    if isinstance(argv,(str,bytes)) or not isinstance(argv,Sequence):raise _LaunchError('INVALID_ARGUMENTS')
    values=list(argv)
    if any(type(value) is not str for value in values):raise _LaunchError('INVALID_ARGUMENTS')
    if values in (['-h'],['--help']):return None
    seen=set()
    for value in values:
        if value in ('-h','--help') or value.startswith('@'):raise _LaunchError('INVALID_ARGUMENTS')
        if value.startswith('--'):
            option,separator,argument=value.partition('=')
            if option in seen or separator and argument.startswith('@'):raise _LaunchError('INVALID_ARGUMENTS')
            seen.add(option)
    parser=_Parser(prog='python -m traffic_api.release_if_result_serve_cli',allow_abbrev=False,add_help=False)
    parser.add_argument('--current-dir',required=True)
    parser.add_argument('--h30-dir',required=True)
    parser.add_argument('--port',default=8768,type=lambda v:_integer(v,digits=5,lower=1,upper=65535))
    parser.add_argument('--serve-seconds',default=300,type=lambda v:_integer(v,digits=3,lower=1,upper=300))
    args=parser.parse_args(values)
    if not all(Path(path).is_absolute() for path in (args.current_dir,args.h30_dir)):
        raise _LaunchError('INVALID_ARGUMENTS')
    return args


def _json_bytes(value):
    try:payload=(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
    except Exception:raise _LaunchError('OUTPUT_ERROR') from None
    if len(payload)>65536:raise _LaunchError('OUTPUT_ERROR')
    return payload


def _write_stream(stream,payload):
    try:
        written=stream.buffer.write(payload)
        if type(written) is not int or written!=len(payload):raise _LaunchError('OUTPUT_ERROR')
        stream.buffer.flush()
    except KeyboardInterrupt:raise
    except Exception:raise _LaunchError('OUTPUT_ERROR') from None


def _error(code):
    try:_write_stream(sys.stderr,_json_bytes({'error':code}))
    except (Exception,KeyboardInterrupt):pass
    return 2


def _event(event,port):
    payload=_json_bytes(dict(schema_version=1,event=event,scope='SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY',
        host='127.0.0.1',port=port,url=f'http://127.0.0.1:{port}/release/results',
        pid=os.getpid(),parent_pid=os.getppid()))
    _write_stream(sys.stdout,payload)
    return True


class _SafeFormatter(logging.Formatter):
    def format(self,record):return '{"error":"SERVER_DIAGNOSTIC"}'


class _SafeHandler(logging.StreamHandler):
    def handleError(self,record):
        # The default handler prints an exception/stack if stderr itself fails.
        pass


@contextmanager
def _safe_uvicorn_logging():
    handler=_SafeHandler(sys.stderr);handler.setFormatter(_SafeFormatter());saved=[]
    try:
        for name in _LOGGERS:
            logger=logging.getLogger(name)
            saved.append((logger,logger.handlers,logger.filters,logger.level,logger.propagate,logger.disabled))
            logger.handlers=[handler];logger.filters=[];logger.setLevel(logging.WARNING)
            logger.propagate=False;logger.disabled=False
        yield
    finally:
        for logger,handlers,filters,level,propagate,disabled in saved:
            logger.handlers=handlers;logger.filters=filters;logger.setLevel(level)
            logger.propagate=propagate;logger.disabled=disabled
        handler.close()


def _make_server(uvicorn,config,*,port,serve_seconds):
    class _ResultServer(uvicorn.Server):
        def __init__(self):
            super().__init__(config)
            self.ready_sent=False;self.stopped_sent=False;self.shutdown_completed=False
            self._shutdown_attempted=False;self._timer=None

        def cancel_timer(self):
            if self._timer is not None:
                self._timer.cancel();self._timer=None

        async def startup(self,sockets=None):
            await super().startup(sockets=sockets)
            if not self.started:raise _LaunchError('STARTUP_FAILED')
            _event('SERVER_READY',port)
            self.ready_sent=True
            if serve_seconds is not None:
                self._timer=asyncio.get_running_loop().call_later(
                    serve_seconds,lambda:setattr(self,'should_exit',True))

        async def shutdown(self,sockets=None):
            self._shutdown_attempted=True;self.cancel_timer()
            await super().shutdown(sockets=sockets)
            if self.force_exit or not self.ready_sent:return
            self.shutdown_completed=True
            _event('SERVER_STOPPED',port)
            self.stopped_sent=True

        async def serve(self,sockets=None):
            primary=None
            try:await super().serve(sockets=sockets)
            except BaseException as error:primary=error;raise
            finally:
                self.cancel_timer()
                if self.started and not self._shutdown_attempted:
                    self._shutdown_attempted=True
                    # Uvicorn does not run shutdown if startup's READY write or
                    # main loop raises. Drain here without emitting STOPPED.
                    try:await super().shutdown(sockets=sockets)
                    except (Exception,KeyboardInterrupt,SystemExit):
                        if primary is None:raise _LaunchError('SERVER_FAILED') from None
    return _ResultServer()


def _safe_code(error,stage,release_errors,view_error):
    if isinstance(error,_LaunchError):return error.code
    if release_errors and isinstance(error,release_errors):
        code=getattr(error,'code',None)
        return code if type(code) is str and code in _RELEASE_CODES else 'INTERNAL_ERROR'
    if view_error is not None and isinstance(error,view_error):
        code=getattr(error,'code',None)
        return code if type(code) is str and code in _VIEW_CODES else 'INTERNAL_ERROR'
    return stage or 'INTERNAL_ERROR'


def main(argv: Sequence[str] | None = None) -> int:
    listener=None;server=None;stage=None;code=None;status=2
    release_errors=();view_error=None
    try:
        args=_arguments(argv)
        if args is None:
            _write_stream(sys.stdout,_HELP);return 0
        from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
        release_errors=(ReleaseIFResultPackageError,)
        from traffic_anomaly.release_if_result_package import load_release_if_result_package
        current=load_release_if_result_package(Path(args.current_dir))
        h30=load_release_if_result_package(Path(args.h30_dir))
        from .release_if_result_view import create_release_if_result_view_app,ReleaseIFResultViewError
        view_error=ReleaseIFResultViewError
        app=create_release_if_result_view_app(current,h30)
        import uvicorn
        stage='BIND_FAILED'
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        listener.bind(('127.0.0.1',args.port))
        port=listener.getsockname()[1]
        if type(port) is not int or not 1<=port<=65535:raise _LaunchError('BIND_FAILED')
        stage='STARTUP_FAILED'
        with _safe_uvicorn_logging():
            config=uvicorn.Config(app,host='127.0.0.1',port=port,workers=1,reload=False,access_log=False,
                log_config=None,log_level=None,loop='asyncio',http='h11',ws='none',proxy_headers=False)
            server=_make_server(uvicorn,config,port=port,serve_seconds=args.serve_seconds)
            server.run(sockets=[listener])
            if not (server.started and server.ready_sent and server.stopped_sent
                    and server.shutdown_completed and not server.force_exit):
                raise _LaunchError('SERVER_FAILED' if server.started else 'STARTUP_FAILED')
            status=0
    except KeyboardInterrupt:status=130
    except (Exception,SystemExit) as error:
        if server is not None and server.started:stage='SERVER_FAILED'
        code=_safe_code(error,stage,release_errors,view_error)
    finally:
        if server is not None:
            try:server.cancel_timer()
            except (Exception,KeyboardInterrupt,SystemExit):
                if code is None:code='SERVER_FAILED';status=2
        if listener is not None:
            try:listener.close()
            except (Exception,KeyboardInterrupt,SystemExit):
                if code is None:code='SERVER_FAILED';status=2
    return _error(code) if code is not None else status


def _cli_entrypoint():
    """Only the module owns failed process streams; embedded main stays local."""
    status=main()
    if status!=0:
        for stream in (sys.stdout,sys.stderr):
            try:
                target=stream.fileno();null_fd=os.open(os.devnull,os.O_WRONLY)
                try:os.dup2(null_fd,target)
                finally:
                    if null_fd!=target:os.close(null_fd)
            except (AttributeError,OSError,ValueError):pass
    return status


if __name__=='__main__':
    raise SystemExit(_cli_entrypoint())
