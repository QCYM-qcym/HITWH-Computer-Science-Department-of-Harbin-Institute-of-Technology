"""Launcher boundary/lifecycle tests use mocks, no listener or model setup."""
import asyncio
import importlib
import importlib.util
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import Mock

import pytest


def api():
    name='traffic_api.candidate_serve_cli'
    assert importlib.util.find_spec(name) is not None, 'trusted local launcher is required'
    return importlib.import_module(name)


def argv():return ['--records','private-records','--inputs','private-inputs','--if-run','private-if']


def test_expected_demo_identity_binds_admitted_snapshot_before_comparison_or_listen(monkeypatch, capsys):
    module, calls, _, _, _, if_value, _ = setup(monkeypatch)
    if_value.report['selected_policy'] = 'P_B'
    assert module.main(argv(), expected_run_identities=(('saved-if', 'P_U'),)) == 2
    assert json.loads(capsys.readouterr().err) == {'error': 'INVALID_REGISTRATION'}
    calls['socket'].assert_not_called()
    calls['create_candidate_viewer_app'].assert_not_called()


def test_matching_demo_identity_retains_original_launcher_lifecycle(monkeypatch):
    module, calls, _, _, _, if_value, _ = setup(monkeypatch)
    if_value.report['selected_policy'] = 'P_U'
    assert module.main(argv(), expected_run_identities=(('saved-if', 'P_U'),)) == 0
    calls['socket'].assert_called_once()


@pytest.mark.parametrize('digest,replay', [({'sha256': 'other', 'byte_count': 1}, 'VERIFIED'),
    ({'sha256': 'fixed', 'byte_count': True}, 'VERIFIED'),
    ({'sha256': 'fixed', 'byte_count': 1}, 'NOT_PROVIDED')])
def test_expected_demo_source_binds_actual_admission_after_precheck(monkeypatch, capsys, digest, replay):
    module, calls, *_ = setup(monkeypatch)
    # This snapshot stands for a different, internally consistent package swapped
    # after the demo's early filesystem check. No additional model setup is needed.
    calls['load_verified_candidate_artifacts'].return_value = SimpleNamespace(report={
        'source_fixture': digest, 'checks': {'source_replay': replay}})
    assert module.main(argv(), expected_source_fixture={'sha256': 'fixed', 'byte_count': 1}) == 2
    assert json.loads(capsys.readouterr().err)['error'] == 'INVALID_REGISTRATION'
    calls['socket'].assert_not_called()


def test_expected_demo_source_accepts_matching_verified_snapshot(monkeypatch):
    module, calls, *_ = setup(monkeypatch)
    calls['load_verified_candidate_artifacts'].return_value = SimpleNamespace(report={
        'source_fixture': {'sha256': 'fixed', 'byte_count': 1}, 'checks': {'source_replay': 'VERIFIED'}})
    assert module.main(argv(), expected_source_fixture={'sha256': 'fixed', 'byte_count': 1}) == 0


def demo_slot_case(monkeypatch, *, swapped):
    """Internally consistent saved snapshots; retain real viewer/freeze admission."""
    from .test_candidate_comparison_view import fixture
    from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun
    from traffic_anomaly.candidate_artifacts import _deep_freeze
    from traffic_api.candidate_app import CandidateRegistration
    module = api()
    report, registrations = fixture(('if', 'current', 'h30', 'h15') if swapped
                                    else ('if', 'current', 'h15', 'h30'), source=True)
    ids = ('demo-if-current13', 'demo-ae-current13', 'demo-ae-history15', 'demo-ae-history30')
    input_report = registrations[0].inputs.report_dict()
    input_report['source_fixture'] = report['shared_context']['five_provenance']['source_fixture']
    inputs = replace(registrations[0].inputs, report=_deep_freeze(input_report))
    renamed = []
    for registration, run_id in zip(registrations, ids):
        value, scores = registration.run.report_dict(), registration.run.scores_dict()
        old_id = value['run_id']
        value['run_id'] = scores['run_id'] = run_id
        for row in report['runs']:
            if row['run_id'] == old_id:
                row['run_id'] = run_id
        renamed.append(CandidateRegistration(VerifiedCandidateRun(value, scores), inputs))
    monkeypatch.setattr(module, 'load_verified_candidate_artifacts', Mock(return_value=inputs))
    monkeypatch.setattr(module, 'load_verified_candidate_if_run', Mock(return_value=renamed[0].run))
    monkeypatch.setattr(module, 'load_verified_candidate_ae_run', Mock(side_effect=[r.run for r in renamed[1:]]))
    comparison = Mock(return_value=report)
    monkeypatch.setattr(module, 'compare_candidate_runs', comparison)
    listener = Mock()
    listener.getsockname.return_value = ('127.0.0.1', 32123)
    monkeypatch.setattr(module.socket, 'socket', Mock(return_value=listener))
    monkeypatch.setattr(module, '_ViewerServer', Mock(return_value=Mock(started=True, shutdown_completed=True)))
    args = ['--records', 'records', '--inputs', 'inputs', '--source-fixture', 'source.json',
            '--if-run', 'if', '--ae-run', 'current', '--ae-run', 'history15', '--ae-run', 'history30', '--comparison']
    policy = report['shared_context']['selected_policy']
    expected_slots = (('iforest_current13', ids[0]), ('current_ae13', ids[1]),
                      ('history_ae26_h15', ids[2]), ('history_ae26_h30', ids[3]))
    return module, args, listener, comparison, dict(
        expected_run_identities=tuple((run_id, policy) for run_id in ids),
        expected_source_fixture=input_report['source_fixture'], expected_comparison_identities=expected_slots)


@pytest.mark.parametrize('swapped,constrained', [(True, True), (False, True), (True, False)])
def test_demo_slot_identity_binds_final_comparison_but_ordinary_viewer_stays_generic(monkeypatch, capsys, swapped, constrained):
    module, args, listener, comparison, expected = demo_slot_case(monkeypatch, swapped=swapped)
    if not constrained:
        expected = {}
    result = module.main(args, **expected)
    comparison.assert_called_once()
    if swapped and constrained:
        assert result == 2
        assert json.loads(capsys.readouterr().err) == {'error': 'INVALID_REGISTRATION'}
        listener.bind.assert_not_called()
    else:
        assert result == 0
        listener.bind.assert_called_once()


def test_demo_comparison_constraint_cannot_be_silently_ignored_without_comparison(monkeypatch, capsys):
    module, calls, *_ = setup(monkeypatch)
    assert module.main(argv(), expected_comparison_identities=(('iforest_current13', 'saved-if'),)) == 2
    assert json.loads(capsys.readouterr().err) == {'error': 'INVALID_ARGUMENTS'}
    for call in calls.values():
        call.assert_not_called()


def setup(monkeypatch):
    module=api();input_value=object();if_value=SimpleNamespace(report={'run_id':'saved-if'})
    ae_value=SimpleNamespace(report={'run_id':'saved-ae'})
    calls={}
    for name,value in [('load_verified_candidate_artifacts',input_value),
        ('load_verified_candidate_if_run',if_value),('load_verified_candidate_ae_run',ae_value),
        ('create_candidate_viewer_app',object())]:
        calls[name]=Mock(return_value=value);monkeypatch.setattr(module,name,calls[name])
    socket=Mock();socket.getsockname.return_value=('127.0.0.1',32123)
    calls['socket']=Mock(return_value=socket);monkeypatch.setattr(module.socket,'socket',calls['socket'])
    config=Mock();calls['config']=Mock(return_value=config);monkeypatch.setattr(module.uvicorn,'Config',calls['config'])
    server=Mock(started=True,shutdown_completed=True)
    calls['server']=Mock(return_value=server);monkeypatch.setattr(module,'_ViewerServer',calls['server'])
    return module,calls,socket,server,input_value,if_value,ae_value


def failure(module,args,capsys,code):
    assert module.main(args)==2
    captured=capsys.readouterr();assert captured.out==''
    assert json.loads(captured.err)=={'error':code}
    assert all(text not in captured.err for text in ('private','Traceback','RuntimeWarning'))


@pytest.mark.parametrize('args',[[],argv()[2:],argv()[:2]+argv()[4:],argv()[:-2],
    argv()+['--if-run','a','--if-run','b','--ae-run','c','--ae-run','d'],
    argv()+['--host','0.0.0.0'],argv()+['--reload'],argv()+['--workers','2'],
    argv()+['--por','0'],argv()+['--port','-1'],argv()+['--port','65536'],argv()+['--port','True'],
    argv()+['--port','+1'],argv()+['--port','1.5'],argv()+['--port','１'],
    argv()+['--shutdown-after-seconds','0'],argv()+['--shutdown-after-seconds','3601'],
    argv()+['--shutdown-after-seconds','True'],argv()+['--shutdown-after-seconds','1.5']])
def test_invalid_arguments_have_no_load_bind_or_server_side_effects(monkeypatch,capsys,args):
    module,calls,*_=setup(monkeypatch);failure(module,args,capsys,'INVALID_ARGUMENTS')
    for call in calls.values():call.assert_not_called()


def test_help_does_not_load(monkeypatch,capsys):
    module,calls,*_=setup(monkeypatch)
    with pytest.raises(SystemExit) as result:module.main(['--help'])
    assert result.value.code==0;assert 'usage:' in capsys.readouterr().out
    for call in calls.values():call.assert_not_called()


@pytest.mark.parametrize('source',[False,True])
@pytest.mark.parametrize('port,lifetime',[(0,None),(65535,3600),(1,1)])
def test_precise_load_order_admission_and_same_loopback_socket(monkeypatch,capsys,source,port,lifetime):
    module,calls,sock,server,inputs,forest,ae=setup(monkeypatch)
    sequence=[]
    for name in ('load_verified_candidate_artifacts','load_verified_candidate_if_run','load_verified_candidate_ae_run','create_candidate_viewer_app','socket'):
        value=calls[name].return_value
        calls[name].side_effect=lambda *args,_name=name,_value=value,**kwargs:(sequence.append(_name),_value)[1]
    args=argv()+['--ae-run','private-ae','--port',str(port)]
    if source:args+=['--source-fixture','private-source.json']
    if lifetime is not None:args+=['--shutdown-after-seconds',str(lifetime)]
    assert module.main(args)==0
    assert sequence==['load_verified_candidate_artifacts','load_verified_candidate_if_run','load_verified_candidate_ae_run','create_candidate_viewer_app','socket']
    keyword={'source_fixture':Path('private-source.json') if source else None}
    calls['load_verified_candidate_artifacts'].assert_called_once_with(Path('private-records'),Path('private-inputs'),**keyword)
    calls['load_verified_candidate_if_run'].assert_called_once_with(Path('private-if'),Path('private-records'),Path('private-inputs'),**keyword)
    calls['load_verified_candidate_ae_run'].assert_called_once_with(Path('private-ae'),Path('private-records'),Path('private-inputs'),**keyword)
    registrations=calls['create_candidate_viewer_app'].call_args.args[0]
    assert [(item.run,item.inputs) for item in registrations]==[(forest,inputs),(ae,inputs)]
    sock.bind.assert_called_once_with(('127.0.0.1',port));sock.close.assert_called_once()
    server.run.assert_called_once_with(sockets=[sock]);server.cancel_timer.assert_called_once()
    kwargs=calls['config'].call_args.kwargs
    assert kwargs['host']=='127.0.0.1' and kwargs['workers']==1 and kwargs['reload'] is False
    assert kwargs['log_config'] is None and kwargs['access_log'] is False
    assert 'timeout_graceful_shutdown' not in kwargs
    assert calls['server'].call_args.kwargs==dict(port=32123,run_ids=['saved-if','saved-ae'],shutdown_after_seconds=lifetime)
    assert capsys.readouterr().err==''


def test_four_explicit_if_runs_are_not_a_research_slot_restriction(monkeypatch):
    module,calls,*_=setup(monkeypatch)
    calls['load_verified_candidate_if_run'].side_effect=[SimpleNamespace(report={'run_id':f'run-{i}'}) for i in range(4)]
    assert module.main(argv()+['--if-run','b','--if-run','c','--if-run','d'])==0
    assert calls['load_verified_candidate_if_run'].call_count==4
    calls['load_verified_candidate_ae_run'].assert_not_called()


@pytest.mark.parametrize('extra', [[], ['--if-run','b','--if-run','c','--if-run','d']])
def test_comparison_is_strictly_opt_in(monkeypatch, extra):
    module,calls,*_=setup(monkeypatch)
    compare=Mock(side_effect=AssertionError('must not compare'))
    monkeypatch.setattr(module,'compare_candidate_runs',compare,raising=False)
    assert module.main(argv()+extra)==0
    compare.assert_not_called()


def test_comparison_calls_original_verifier_after_snapshots_and_before_bind(monkeypatch):
    module,calls,*_=setup(monkeypatch); events=[]; report={'trusted-startup-report': True}
    for name in ('load_verified_candidate_artifacts','load_verified_candidate_if_run',
                 'load_verified_candidate_ae_run','create_candidate_viewer_app','socket'):
        result=calls[name].return_value
        calls[name].side_effect=lambda *a,_name=name,_result=result,**kw:(events.append(_name),_result)[1]
    compare=Mock(side_effect=lambda *a,**kw:(events.append('compare'),report)[1])
    monkeypatch.setattr(module,'compare_candidate_runs',compare,raising=False)
    assert module.main(argv()+['--ae-run','private-ae','--source-fixture','private-source','--comparison'])==0
    assert events==['load_verified_candidate_artifacts','load_verified_candidate_if_run',
        'load_verified_candidate_ae_run','compare','create_candidate_viewer_app','socket']
    specs,records,inputs=compare.call_args.args
    assert [(s.family,s.directory) for s in specs]==[('iforest',Path('private-if')),('autoencoder',Path('private-ae'))]
    assert (records,inputs)==(Path('private-records'),Path('private-inputs'))
    assert compare.call_args.kwargs=={'source_fixture':Path('private-source')}
    assert calls['create_candidate_viewer_app'].call_args.kwargs=={'comparison':report}


def test_one_run_comparison_rejects_before_loading(monkeypatch,capsys):
    module,calls,*_=setup(monkeypatch)
    failure(module,argv()+['--comparison'],capsys,'INVALID_ARGUMENTS')
    for call in calls.values(): call.assert_not_called()


@pytest.mark.parametrize('code,expected', [('DUPLICATE_RUN_SLOT','DUPLICATE_RUN_SLOT'),
    ('INCOMPARABLE_UPSTREAM','INCOMPARABLE_UPSTREAM'),('private-secret','INVALID_COMPARISON'),
    ({'private':'path'},'INVALID_COMPARISON')])
def test_comparison_errors_are_safe_and_never_fallback_or_bind(monkeypatch,capsys,code,expected):
    from traffic_anomaly.candidate_comparison import CandidateComparisonError
    module,calls,*_=setup(monkeypatch)
    monkeypatch.setattr(module,'compare_candidate_runs',Mock(side_effect=CandidateComparisonError(code)),raising=False)
    failure(module,argv()+['--if-run','private-other','--comparison'],capsys,expected)
    calls['socket'].assert_not_called(); calls['create_candidate_viewer_app'].assert_not_called()


def test_changed_artifact_between_snapshot_and_comparison_rejects_before_bind(monkeypatch,capsys):
    from .test_candidate_comparison_view import fixture
    from traffic_api.candidate_viewer import create_candidate_viewer_app
    report, regs = fixture(('if','current'))
    report['runs'][0]['actual_five_artifacts']['manifest.json']['sha256'] = 'c'*64
    module,calls,*_=setup(monkeypatch)
    calls['load_verified_candidate_artifacts'].return_value = regs[0].inputs
    calls['load_verified_candidate_if_run'].return_value = regs[0].run
    calls['load_verified_candidate_ae_run'].return_value = regs[1].run
    monkeypatch.setattr(module, 'compare_candidate_runs', Mock(return_value=report))
    monkeypatch.setattr(module, 'create_candidate_viewer_app', create_candidate_viewer_app)
    failure(module,argv()+['--ae-run','private-ae','--comparison'],capsys,'INVALID_REGISTRATION')
    calls['socket'].assert_not_called()


@pytest.mark.parametrize('phase,kind,code,expected',[
    ('load_verified_candidate_artifacts','CandidateArtifactError','INPUT_UNAVAILABLE','INPUT_UNAVAILABLE'),
    ('load_verified_candidate_if_run','CandidateRunArtifactError','INTEGRITY_MISMATCH','INTEGRITY_MISMATCH'),
    ('load_verified_candidate_ae_run','CandidateAERunArtifactError','INCOMPATIBLE_RUN','INCOMPATIBLE_RUN'),
    ('load_verified_candidate_if_run','CandidateRunArtifactError','private-secret','INVALID_ARTIFACTS'),
    ('load_verified_candidate_if_run','CandidateRunArtifactError',{'private':'secret'},'INVALID_ARTIFACTS'),
    ('create_candidate_viewer_app','CandidateRegistrationError','private-secret','INVALID_REGISTRATION'),
    ('create_candidate_viewer_app','CandidateViewerError','private-secret','VIEWER_ASSETS_UNAVAILABLE')])
def test_admission_failure_is_safe_before_bind_no_fallback(monkeypatch,capsys,phase,kind,code,expected):
    module,calls,*_=setup(monkeypatch);calls[phase].side_effect=getattr(module,kind)(code)
    failure(module,argv()+['--ae-run','private-ae'],capsys,expected)
    calls['socket'].assert_not_called();calls[phase].assert_called_once()
    if phase=='load_verified_candidate_if_run':calls['load_verified_candidate_ae_run'].assert_not_called()


def test_occupied_port_does_not_fallback_and_closes_owned_socket(monkeypatch,capsys):
    module,calls,sock,*_=setup(monkeypatch);sock.bind.side_effect=OSError('private bind details')
    failure(module,argv(),capsys,'BIND_FAILED');sock.bind.assert_called_once();sock.close.assert_called_once();calls['server'].assert_not_called()


@pytest.mark.parametrize('started,completed,exception,code',[
    (False,False,None,'STARTUP_FAILED'),(True,False,None,'SERVER_FAILED'),
    (False,False,SystemExit(3),'STARTUP_FAILED'),(False,False,RuntimeError('private-start'),'STARTUP_FAILED'),
    (True,False,RuntimeError('private-run'),'SERVER_FAILED')])
def test_server_failure_does_not_fake_success_and_cleans_up(monkeypatch,capsys,started,completed,exception,code):
    module,calls,sock,server,*_=setup(monkeypatch);server.started=started;server.shutdown_completed=completed
    if exception:server.run.side_effect=exception
    failure(module,argv(),capsys,code);sock.close.assert_called_once();server.cancel_timer.assert_called_once()


def test_keyboard_interrupt_is_130_and_cleanup_still_runs(monkeypatch,capsys):
    module,_,sock,server,*_=setup(monkeypatch);server.run.side_effect=KeyboardInterrupt()
    assert module.main(argv())==130;assert capsys.readouterr().err==''
    sock.close.assert_called_once();server.cancel_timer.assert_called_once()


def test_ready_and_stopped_follow_completed_super_hooks(monkeypatch,capsys):
    module=api();order=[]
    async def startup(server,sockets=None):order.append('startup');assert capsys.readouterr().out=='';server.started=True
    async def shutdown(server,sockets=None):order.append('shutdown');assert not server.shutdown_completed
    monkeypatch.setattr(module.uvicorn.Server,'startup',startup);monkeypatch.setattr(module.uvicorn.Server,'shutdown',shutdown)
    server=module._ViewerServer(SimpleNamespace(),port=32123,run_ids=['saved-if'])
    async def exercise():
        await server.startup(sockets=[])
        ready=json.loads(capsys.readouterr().out)
        assert ready['event']=='SERVER_READY' and ready['url']=='http://127.0.0.1:32123/candidate'
        assert set(ready)=={'schema_version','event','evidence_kind','policy_status','scope','host','port','url','run_ids','pid','parent_pid'}
        assert ready['scope']=='SYNTHETIC_SAVED_RUN_VIEWER' and ready['run_ids']==['saved-if'] and ready['pid']>0
        await server.shutdown(sockets=[])
        stopped=json.loads(capsys.readouterr().out);assert stopped==dict(ready,event='SERVER_STOPPED')
    asyncio.run(exercise());assert order==['startup','shutdown'] and server.shutdown_completed


def test_forced_shutdown_does_not_claim_graceful_stopped(monkeypatch,capsys):
    module=api();calls=[];timer=Mock()
    async def shutdown(server,sockets=None):
        assert server.force_exit is True
        calls.append(sockets)
    monkeypatch.setattr(module.uvicorn.Server,'shutdown',shutdown)
    server=module._ViewerServer(SimpleNamespace(),port=32123,run_ids=['saved-if'])
    server.started=True;server.force_exit=True;server._timer=timer
    asyncio.run(server.shutdown(sockets=[]))
    assert calls==[[]];timer.cancel.assert_called_once()
    assert server.shutdown_completed is False
    assert capsys.readouterr().out==''


@pytest.mark.parametrize('seconds',[None,1,3600])
def test_timer_is_readiness_relative_requests_exit_and_is_cancelled(monkeypatch,capsys,seconds):
    module=api();handle=Mock();loop=Mock();loop.call_later.return_value=handle
    async def startup(server,sockets=None):loop.call_later.assert_not_called();server.started=True
    async def shutdown(server,sockets=None):pass
    monkeypatch.setattr(module.uvicorn.Server,'startup',startup);monkeypatch.setattr(module.uvicorn.Server,'shutdown',shutdown)
    server=module._ViewerServer(SimpleNamespace(),port=2,run_ids=['a'],shutdown_after_seconds=seconds)
    async def exercise():
        with monkeypatch.context() as local:
            local.setattr(module.asyncio,'get_running_loop',lambda:loop)
            await server.startup(sockets=[])
            if seconds is None:loop.call_later.assert_not_called()
            else:
                assert loop.call_later.call_args.args[0]==seconds
                callback=loop.call_later.call_args.args[1];assert server.should_exit is False;callback();assert server.should_exit is True
            await server.shutdown(sockets=[])
    asyncio.run(exercise())
    if seconds is not None:handle.cancel.assert_called_once()
    assert len(capsys.readouterr().out.splitlines())==2


@pytest.mark.parametrize('phase',['startup','shutdown','output'])
def test_hook_failure_never_emits_false_stopped(monkeypatch,capsys,phase):
    module=api()
    async def startup(server,sockets=None):
        if phase=='startup':raise RuntimeError('private-start')
        server.started=True
    async def shutdown(server,sockets=None):raise RuntimeError('private-stop')
    monkeypatch.setattr(module.uvicorn.Server,'startup',startup);monkeypatch.setattr(module.uvicorn.Server,'shutdown',shutdown)
    if phase=='output':monkeypatch.setattr(module,'_event',Mock(side_effect=OSError('private-pipe')))
    server=module._ViewerServer(SimpleNamespace(),port=3,run_ids=['a'])
    async def exercise():
        with pytest.raises((RuntimeError,OSError)):
            await server.startup(sockets=[])
            await server.shutdown(sockets=[])
    asyncio.run(exercise());assert 'SERVER_STOPPED' not in capsys.readouterr().out and not server.shutdown_completed


@pytest.mark.parametrize('raises',[False,True])
def test_uvicorn_logging_discards_message_exception_stack_and_restores_configuration(monkeypatch,capsys,raises):
    module=api();names=('uvicorn','uvicorn.error','uvicorn.access','uvicorn.asgi')
    snapshots={name:(logger.handlers,logger.filters,logger.level,logger.propagate,logger.disabled) for name in names for logger in [logging.getLogger(name)]}
    class Halt(Exception):pass
    try:
        with module._safe_uvicorn_logging():
            for name in names:
                try:raise ValueError('private exception body')
                except ValueError:logging.getLogger(name).error('private message',exc_info=True,stack_info=True)
            if raises:raise Halt()
    except Halt:pass
    captured=capsys.readouterr();assert captured.out==''
    assert [json.loads(line) for line in captured.err.splitlines()]==[{'error':'SERVER_DIAGNOSTIC'}]*4
    for name,expected in snapshots.items():
        logger=logging.getLogger(name)
        assert (logger.handlers,logger.filters,logger.level,logger.propagate,logger.disabled)==expected
        assert logger.handlers is expected[0] and logger.filters is expected[1]
