"""Launcher unit seams: fake listener/server, never an actual service or signal."""
import asyncio
import importlib
import json
import logging
from pathlib import Path
import sys
from types import ModuleType,SimpleNamespace

import pytest


PRIVATE='/private-sentinel/not-a-package'
PATH='C:/handwritten=@daily'


def api():return importlib.import_module('traffic_api.release_input_serve_cli')


@pytest.fixture(autouse=True)
def no_numerical_or_package_actions(monkeypatch):
    from traffic_anomaly import release_inputs as core,release_input_package as package,release_minute_package as raw
    attempts=[]
    def forbidden(*a,**k):attempts.append('forbidden action');raise AssertionError('forbidden action')
    for name in ('prepare_release_inputs','verify_release_input_derivation','_fit_state','_fit_statistics',
            '_transform','_history','_bind_upstream','encode_release_input_package','decode_release_input_package'):
        monkeypatch.setattr(core,name,forbidden)
    for module,name in ((package,'load_release_input_package'),(package,'save_release_input_package'),
            (raw,'load_release_minute_package'),(raw,'save_release_minute_package')):monkeypatch.setattr(module,name,forbidden)
    yield attempts
    assert attempts==[]


@pytest.fixture
def world(monkeypatch):
    from traffic_anomaly import release_input_package as package
    from traffic_api import release_input_view as view
    w=SimpleNamespace(events=[],sockets=[],servers=[],configs=[],stage=None,force=False,close_error=False,
        saved=object(),app=object(),real_factory=view.create_release_input_view_app)
    def load(path):
        w.events.append(('load',path))
        if w.stage=='load':raise w.error
        return w.saved
    def factory(saved):
        assert saved is w.saved;w.events.append('factory')
        if w.stage=='factory':raise w.error
        return w.app
    monkeypatch.setattr(package,'load_release_input_package',load)
    monkeypatch.setattr(view,'create_release_input_view_app',factory)
    class Listener:
        def __init__(self):self.closed=False;w.sockets.append(self)
        def bind(self,address):
            w.events.append(('bind',address));self.port=address[1] or 43210
            if w.stage=='bind':raise OSError(PRIVATE)
        def getsockname(self):return ('127.0.0.1',self.port)
        def close(self):
            w.events.append('close');self.closed=True
            if w.close_error:raise OSError(PRIVATE)
    def socket(*a):w.events.append('socket');return Listener()
    w.socket=SimpleNamespace(AF_INET=2,SOCK_STREAM=1,socket=socket)
    class Timer:
        def __init__(self,callback):self.callback=callback;self.cancelled=False
        def cancel(self):assert not self.cancelled;self.cancelled=True;w.events.append('timer cancel')
    def later(seconds,callback):
        w.events.append(('timer',seconds));w.timer=Timer(callback);return w.timer
    w.loop=SimpleNamespace(call_later=later)
    uvicorn=ModuleType('uvicorn')
    def config(app,**kwargs):
        assert app is w.app;w.events.append('config');w.configs.append(kwargs);return SimpleNamespace()
    class Server:
        def __init__(self,config):
            self.started=False;self.force_exit=False;self.should_exit=False;w.servers.append(self)
        async def startup(self,sockets=None):
            w.events.append('startup')
            if w.stage=='startup':raise RuntimeError(PRIVATE)
            self.started=True
        async def shutdown(self,sockets=None):
            w.events.append('shutdown')
            if w.stage=='shutdown':raise RuntimeError(PRIVATE)
            self.force_exit=w.force
        async def serve(self,sockets=None):
            await self.startup(sockets=sockets)
            if w.stage=='runtime':raise RuntimeError(PRIVATE)
            if w.stage=='interrupt':raise KeyboardInterrupt(PRIVATE)
            await self.shutdown(sockets=sockets)
        def run(self,sockets=None):
            w.events.append(('run',sockets));assert sockets==[w.sockets[-1]]
            asyncio.run(self.serve(sockets=sockets))
    uvicorn.Server=Server;uvicorn.Config=config
    monkeypatch.setitem(sys.modules,'uvicorn',uvicorn)
    return w


def bind_world(monkeypatch,w):
    m=api();monkeypatch.setattr(m,'socket',w.socket)
    monkeypatch.setattr(m,'asyncio',SimpleNamespace(get_running_loop=lambda:w.loop))
    writer=m._write_stream
    def write(stream,payload):
        doc=json.loads(payload)
        if 'event' in doc:w.events.append(('event write',doc['event']))
        result=writer(stream,payload)
        if 'event' in doc:w.events.append(('event flushed',doc['event']))
        return result
    monkeypatch.setattr(m,'_write_stream',write)
    return m


_BAD=[[],['--prepared-package'],['--prepared-pack',PATH],['--prepared-package',PATH,'extra'],
    ['--prepared-package',PATH,'--host','0.0.0.0'],['--prepared-package',PATH,'--prepared-package='+PATH],
    ['--prepared-package=@args'],['@args'],['--help','--prepared-package',PATH],['-h','--help'],
    ['--help=PRIVATE'],['--prepared-package',PATH,'--port','65536'],['--prepared-package',PATH,'--port','-1'],
    ['--prepared-package',PATH,'--port','+1'],['--prepared-package',PATH,'--port','１２'],
    ['--prepared-package',PATH,'--port',' 1'],['--prepared-package',PATH,'--port','1.0'],
    ['--prepared-package',PATH,'--port','000000'],['--prepared-package',PATH,'--shutdown-after-seconds','0'],
    ['--prepared-package',PATH,'--shutdown-after-seconds','3601'],['--prepared-package',PATH,'--shutdown-after-seconds','00001'],
    ['--prepared-package',PATH,'--shutdown-after-seconds','+1'],['--prepared-package',PATH,'--shutdown-after-seconds','١'],
    ['--prepared-package',PATH,'--port=1','--port=2'],'string',b'bytes',[1]]


@pytest.mark.parametrize('argv',[['--help'],['-h'],*_BAD],ids=[f'argv-{i}' for i in range(len(_BAD)+2)])
def test_help_and_invalid_args_before_product_import(monkeypatch,capfdbinary,argv):
    m=api();attempts=[]
    import builtins
    original=builtins.__import__
    def importing(name,*a,**k):
        if name.startswith(('traffic_anomaly','traffic_api','release_input','uvicorn')):
            attempts.append(name);raise AssertionError('product import')
        return original(name,*a,**k)
    def io(*a,**k):attempts.append('I/O');raise AssertionError('I/O')
    monkeypatch.setattr(builtins,'__import__',importing);monkeypatch.setattr(Path,'open',io)
    monkeypatch.setattr(m,'socket',SimpleNamespace(socket=io))
    rc=m.main(argv);out,err=capfdbinary.readouterr()
    if argv in (['--help'],['-h']):assert rc==0 and out.startswith(b'usage: python -m traffic_api.release_input_serve_cli') and err==b''
    else:assert rc==2 and out==b'' and err==b'{"error":"INVALID_ARGUMENTS"}\n'
    assert attempts==[]


@pytest.mark.parametrize('port',[0,65535])
@pytest.mark.parametrize('seconds',[None,1,3600])
def test_equal_at_path_same_owned_socket_and_ready_relative_timer(monkeypatch,world,capfdbinary,port,seconds):
    w=world;m=bind_world(monkeypatch,w)
    argv=['--prepared-package='+PATH,'--port',str(port)]
    if seconds is not None:argv+=['--shutdown-after-seconds',str(seconds)]
    assert m.main(argv)==0
    out,err=capfdbinary.readouterr();events=[json.loads(line) for line in out.splitlines()]
    assert err==b'' and [e['event'] for e in events]==['SERVER_READY','SERVER_STOPPED']
    expected_port=port or 43210
    assert all(set(e)=={'schema_version','event','scope','host','port','url','pid','parent_pid'} for e in events)
    assert all(e['host']=='127.0.0.1' and e['port']==expected_port and e['scope']=='RELEASE_INPUT_SUMMARY_VIEW'
        and e['url']==f'http://127.0.0.1:{expected_port}/release/inputs' for e in events)
    assert events[1]==dict(events[0],event='SERVER_STOPPED')
    assert w.events[:4]==[('load',Path(PATH)),'factory','socket',('bind',('127.0.0.1',port))]
    assert len(w.sockets)==len(w.servers)==1 and w.sockets[0].closed and w.events.count('close')==1
    assert w.configs==[dict(host='127.0.0.1',port=expected_port,workers=1,reload=False,access_log=False,
        log_config=None,log_level=None,loop='asyncio',http='h11',ws='none',proxy_headers=False)]
    if seconds is not None:
        assert w.events.index(('timer',seconds))>w.events.index(('event flushed','SERVER_READY'))
        assert w.timer.cancelled and not w.servers[0].should_exit
        w.timer.callback();assert w.servers[0].should_exit
    else:assert not hasattr(w,'timer')


@pytest.mark.parametrize('stage,code',[('load','INVALID_PACKAGE'),('factory','VIEWER_ASSETS_UNAVAILABLE'),
    ('bind','BIND_FAILED'),('startup','STARTUP_FAILED'),('runtime','SERVER_FAILED'),('shutdown','SERVER_FAILED')])
def test_admission_before_bind_and_safe_stage_errors(monkeypatch,world,capfdbinary,stage,code):
    w=world;w.stage=stage
    from traffic_anomaly.release_inputs import ReleaseInputPreparationError
    from traffic_api.release_input_view import ReleaseInputViewError
    w.error=ReleaseInputPreparationError(code) if stage=='load' else ReleaseInputViewError(code)
    m=bind_world(monkeypatch,w);assert m.main(['--prepared-package',PATH])==2
    out,err=capfdbinary.readouterr();assert json.loads(err)=={'error':code} and PRIVATE.encode() not in out+err
    if stage in ('load','factory'):assert w.sockets==[] and out==b''
    else:assert len(w.sockets)==1 and w.sockets[0].closed
    assert b'SERVER_STOPPED' not in out


@pytest.mark.parametrize('stage',['load','factory'])
@pytest.mark.parametrize('code',[None,[],{},True,'PRIVATE_UNKNOWN'],ids=['none','list','dict','bool','unknown'])
def test_invalid_error_codes_are_internal(monkeypatch,world,capfdbinary,stage,code):
    w=world;w.stage=stage
    from traffic_anomaly.release_inputs import ReleaseInputPreparationError
    from traffic_api.release_input_view import ReleaseInputViewError
    error=ReleaseInputPreparationError('INVALID_PACKAGE') if stage=='load' else ReleaseInputViewError('INVALID_VIEW_INPUT')
    error.code=code;error.args=(PRIVATE,);error.__cause__=RuntimeError(PRIVATE);w.error=error
    m=bind_world(monkeypatch,w);assert m.main(['--prepared-package',PATH])==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"INTERNAL_ERROR"}\n' and not w.sockets


@pytest.mark.parametrize('kind',['short','flush','interrupt'])
def test_ready_write_failure_has_no_stopped_or_timer_and_cleans_server(monkeypatch,world,capfdbinary,kind):
    w=world;m=bind_world(monkeypatch,w);writes=[]
    class Sink:
        def write(self,payload):
            writes.append('write')
            if kind=='interrupt':raise KeyboardInterrupt(PRIVATE)
            return len(payload)-1 if kind=='short' else len(payload)
        def flush(self):writes.append('flush');raise OSError(PRIVATE)
    monkeypatch.setattr(m,'sys',SimpleNamespace(stdout=SimpleNamespace(buffer=Sink()),stderr=sys.stderr))
    assert m.main(['--prepared-package',PATH,'--shutdown-after-seconds','1'])==(130 if kind=='interrupt' else 2)
    out,err=capfdbinary.readouterr();assert b'SERVER_STOPPED' not in out and PRIVATE.encode() not in err
    if kind!='interrupt':assert err==b'{"error":"OUTPUT_ERROR"}\n'
    assert not hasattr(w,'timer') and not w.servers[0].ready_sent and w.sockets[0].closed
    assert 'shutdown' in w.events


def test_force_exit_is_not_normal_stop(monkeypatch,world,capfdbinary):
    w=world;w.force=True;m=bind_world(monkeypatch,w)
    assert m.main(['--prepared-package',PATH,'--shutdown-after-seconds','1'])==2
    out,err=capfdbinary.readouterr();assert b'SERVER_READY' in out and b'SERVER_STOPPED' not in out
    assert err==b'{"error":"SERVER_FAILED"}\n' and w.timer.cancelled and w.sockets[0].closed


def test_timer_cancelled_logger_restored_and_sequential_instances(monkeypatch,world,capfdbinary):
    w=world;m=bind_world(monkeypatch,w);names=('uvicorn','uvicorn.error','uvicorn.access','uvicorn.asgi')
    def snapshot():return {n:(l.handlers,l.filters,l.level,l.propagate,l.disabled) for n in names for l in [logging.getLogger(n)]}
    before=snapshot()
    for _ in range(2):assert m.main(['--prepared-package',PATH,'--shutdown-after-seconds','1'])==0;assert snapshot()==before
    out,err=capfdbinary.readouterr();assert len(out.splitlines())==4 and err==b''
    assert len(w.servers)==len(w.sockets)==2 and w.servers[0] is not w.servers[1] and all(s.closed for s in w.sockets)
    assert w.events.count('timer cancel')==2


def test_logging_discards_private_exception_and_stack(monkeypatch,world,capfdbinary):
    m=bind_world(monkeypatch,world)
    with m._safe_uvicorn_logging():
        try:raise RuntimeError(PRIVATE)
        except RuntimeError:logging.getLogger('uvicorn.error').error(PRIVATE,exc_info=True,stack_info=True)
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"SERVER_DIAGNOSTIC"}\n'


@pytest.mark.parametrize('stage',['interrupt','close'])
def test_interrupt_130_and_close_failure_never_succeed(monkeypatch,world,capfdbinary,stage):
    w=world
    if stage=='interrupt':w.stage=stage
    else:w.close_error=True
    m=bind_world(monkeypatch,w)
    assert m.main(['--prepared-package',PATH])==(130 if stage=='interrupt' else 2)
    out,err=capfdbinary.readouterr();assert PRIVATE.encode() not in out+err and all(s.closed for s in w.sockets)
    if stage=='close':assert err==b'{"error":"SERVER_FAILED"}\n'


def test_actual_factory_and_shared_summary_still_precede_fake_bind(monkeypatch,world,capfdbinary):
    from .test_release_input_view import hand_saved,ResourceTree,ASSETS,FIXTURE
    from traffic_api import release_input_view as view
    from traffic_anomaly import release_input_summary as shared
    w=world;w.saved=hand_saved(json.loads(FIXTURE.read_bytes())['cases']['zero_calibration'])
    calls=[];reads=[];real=shared.summarize_release_inputs
    def summary(saved):calls.append(saved);return real(saved)
    monkeypatch.setattr(view,'summarize_release_inputs',summary)
    monkeypatch.setattr(view.resources,'files',lambda name:ResourceTree(dict(ASSETS),reads))
    def factory(saved):
        assert not w.sockets;w.events.append('factory');w.app=w.real_factory(saved);return w.app
    monkeypatch.setattr(view,'create_release_input_view_app',factory)
    m=bind_world(monkeypatch,w);assert m.main(['--prepared-package',PATH])==0
    out,err=capfdbinary.readouterr();assert err==b'' and len(calls)==1 and len([r for r in reads if r[0]=='read'])==3


_LOAD_CODES=('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE','OUTPUT_EXISTS',
    'PACKAGE_CHANGED','OUTPUT_ERROR','INVALID_PREPARATION_CONFIG','UPSTREAM_IDENTITY_MISMATCH',
    'NO_TRAINING_NORMAL_MINUTES','NONFINITE_FIT_STATE','DERIVATION_MISMATCH')
_FACTORY_CODES=('INVALID_VIEW_INPUT','INVALID_RESULT','RESOURCE_LIMIT','VIEWER_ASSETS_UNAVAILABLE')
@pytest.mark.parametrize('stage,code',[('load',c) for c in _LOAD_CODES]+[('factory',c) for c in _FACTORY_CODES])
def test_each_admission_code_is_exact_and_zero_bind(monkeypatch,world,capfdbinary,stage,code):
    w=world;w.stage=stage
    from traffic_anomaly.release_inputs import ReleaseInputPreparationError
    from traffic_api.release_input_view import ReleaseInputViewError
    w.error=ReleaseInputPreparationError(code) if stage=='load' else ReleaseInputViewError(code)
    w.error.args=(PRIVATE,);w.error.__cause__=RuntimeError(PRIVATE)
    m=bind_world(monkeypatch,w);assert m.main(['--prepared-package',PATH])==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==('{"error":"'+code+'"}\n').encode() and w.sockets==[]


@pytest.mark.parametrize('stage',['load','factory'])
def test_unknown_admission_exception_never_binds(monkeypatch,world,capfdbinary,stage):
    w=world;w.stage=stage;w.error=RuntimeError(PRIVATE)
    m=bind_world(monkeypatch,w);assert m.main(['--prepared-package',PATH])==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"INTERNAL_ERROR"}\n' and not w.sockets


def test_none_argv_preserves_space_form_equal_at_path(monkeypatch,world,capfdbinary):
    w=world;m=bind_world(monkeypatch,w)
    monkeypatch.setattr(m,'sys',SimpleNamespace(argv=['fixed','--prepared-package',PATH],stdout=sys.stdout,stderr=sys.stderr))
    assert m.main()==0 and w.events[0]==('load',Path(PATH))
    out,err=capfdbinary.readouterr();assert len(out.splitlines())==2 and err==b''


def test_stopped_short_write_is_not_marked_success(monkeypatch,world,capfdbinary):
    w=world;m=bind_world(monkeypatch,w);writes=[];flushes=[]
    class Sink:
        def write(self,payload):
            writes.append(json.loads(payload)['event'])
            return len(payload) if len(writes)==1 else len(payload)-1
        def flush(self):flushes.append('flush')
    monkeypatch.setattr(m,'sys',SimpleNamespace(stdout=SimpleNamespace(buffer=Sink()),stderr=sys.stderr))
    assert m.main(['--prepared-package',PATH,'--shutdown-after-seconds','1'])==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"OUTPUT_ERROR"}\n'
    assert writes==['SERVER_READY','SERVER_STOPPED'] and flushes==['flush']
    assert not w.servers[0].stopped_sent and w.timer.cancelled and w.sockets[0].closed


@pytest.mark.parametrize('status,fail_dup',[(0,False),(2,False),(2,True),(130,False)])
def test_owned_module_entrypoint_redirects_only_failed_process_streams(monkeypatch,status,fail_dup):
    m=api();events=[]
    class FakeOS:
        devnull='UNIT_NULL';O_WRONLY=1
        def open(self,path,flags):assert path==self.devnull and flags==1;events.append('open');return 17
        def dup2(self,source,target):
            assert source==17 and target in (1,2);events.append(('dup',target))
            if fail_dup:raise OSError('unavailable')
        def close(self,fd):assert fd==17;events.append('close')
    monkeypatch.setattr(m,'os',FakeOS());monkeypatch.setattr(m,'main',lambda:status)
    monkeypatch.setattr(m,'sys',SimpleNamespace(stdout=SimpleNamespace(fileno=lambda:1),stderr=SimpleNamespace(fileno=lambda:2)))
    import ast
    entry=ast.parse(Path(m.__file__).read_text(encoding='utf-8')).body[-1]
    assert isinstance(entry,ast.If)
    with pytest.raises(SystemExit) as caught:
        exec(compile(ast.Module(body=[entry],type_ignores=[]),m.__file__,'exec'),dict(vars(m),__name__='__main__'))
    assert caught.value.code==status
    assert events==([] if status==0 else ['open',('dup',1),'close','open',('dup',2),'close'])


@pytest.mark.parametrize('fault',['success','write','flush'])
def test_event_success_marker_requires_complete_write_and_flush(monkeypatch,fault):
    m=api();steps=[];payloads=[];returns=[]
    class Sink:
        def write(self,payload):
            steps.append('write');payloads.append(payload)
            if fault=='write':raise OSError(PRIVATE)
            return len(payload)
        def flush(self):
            steps.append('flush')
            if fault=='flush':raise OSError(PRIVATE)
    monkeypatch.setattr(m,'sys',SimpleNamespace(stdout=SimpleNamespace(buffer=Sink())))
    if fault=='success':
        returns.append(m._event('SERVER_READY',43210));steps.append('returned')
        assert returns[0] is True and steps==['write','flush','returned']
    else:
        with pytest.raises(m._LaunchError) as caught:returns.append(m._event('SERVER_READY',43210))
        assert caught.value.code=='OUTPUT_ERROR' and returns==[]
        assert steps==(['write'] if fault=='write' else ['write','flush'])
    expected=dict(schema_version=1,event='SERVER_READY',scope='RELEASE_INPUT_SUMMARY_VIEW',host='127.0.0.1',
        port=43210,url='http://127.0.0.1:43210/release/inputs',pid=m.os.getpid(),parent_pid=m.os.getppid())
    assert payloads==[(json.dumps(expected,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')]
