"""Capacity launcher boundary tests; mocked admission/socket, no model runs."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from traffic_api import candidate_serve_cli as launcher
from traffic_anomaly.candidate_capacity_contract import CandidateCapacityComparisonError


def argv():
    return ['--records', 'records', '--inputs', 'inputs', '--source-fixture', 'source.json',
            '--ae-run', 'current492', '--ae-run', 'history15', '--capacity-comparison']


def setup(monkeypatch):
    order, calls = [], {}
    snapshot = SimpleNamespace(payload=b'{}\n', run_ids=('current492', 'history15'))
    def load(args):
        order.append('capacity admission')
        return snapshot
    def app(value):
        assert value is snapshot
        order.append('asset admission')
        return 'capacity-only-app'
    calls['load'] = Mock(side_effect=load)
    calls['app'] = Mock(side_effect=app)
    monkeypatch.setattr(launcher, '_load_capacity_snapshot', calls['load'], raising=False)
    monkeypatch.setattr(launcher, 'create_candidate_capacity_app', calls['app'], raising=False)
    for name in ('load_verified_candidate_artifacts', 'load_verified_candidate_if_run',
                 'load_verified_candidate_ae_run', 'compare_candidate_runs', 'create_candidate_viewer_app'):
        calls[name] = Mock(side_effect=AssertionError('classic chain invoked'))
        monkeypatch.setattr(launcher, name, calls[name])
    listener = Mock()
    listener.getsockname.return_value = ('127.0.0.1', 32123)
    def socket(*args):
        order.append('socket')
        return listener
    calls['socket'] = Mock(side_effect=socket)
    monkeypatch.setattr(launcher.socket, 'socket', calls['socket'])
    calls['config'] = Mock(return_value='uvicorn-config')
    monkeypatch.setattr(launcher.uvicorn, 'Config', calls['config'])
    server = Mock(started=True, shutdown_completed=True)
    calls['server'] = Mock(return_value=server)
    monkeypatch.setattr(launcher, '_ViewerServer', calls['server'])
    return calls, order, snapshot, listener, server


def test_capacity_branch_precedes_classic_loaders_and_listen(monkeypatch):
    calls, order, snapshot, listener, server = setup(monkeypatch)
    assert launcher.main(argv()) == 0
    assert order == ['capacity admission', 'asset admission', 'socket']
    calls['load'].assert_called_once()
    args = calls['load'].call_args.args[0]
    assert args.ae_run == [Path('current492'), Path('history15')]
    calls['app'].assert_called_once_with(snapshot)
    listener.bind.assert_called_once_with(('127.0.0.1', 0))
    server.run.assert_called_once_with(sockets=[listener])
    listener.close.assert_called_once()
    calls['server'].assert_called_once_with('uvicorn-config', port=32123, run_ids=['current492', 'history15'],
        shutdown_after_seconds=None, page_path='/candidate/capacity')
    config = calls['config'].call_args.kwargs
    assert config['workers'] == 1 and config['reload'] is False and config['host'] == '127.0.0.1'
    for name in ('load_verified_candidate_artifacts', 'load_verified_candidate_if_run',
                 'load_verified_candidate_ae_run', 'compare_candidate_runs', 'create_candidate_viewer_app'):
        calls[name].assert_not_called()


@pytest.mark.parametrize('args', [
    argv() + ['--comparison'], argv() + ['--if-run', 'if'],
    ['--records', 'records', '--inputs', 'inputs', '--source-fixture', 'source.json',
     '--ae-run', 'one', '--capacity-comparison'],
    argv() + ['--ae-run', 'a', '--ae-run', 'b', '--ae-run', 'c'],
    argv() + ['--host', '0.0.0.0'], argv() + ['--reload'], argv() + ['--workers', '2'],
])
def test_invalid_or_mutually_exclusive_capacity_args_have_no_admission(args, monkeypatch, capsys):
    calls, *_ = setup(monkeypatch)
    assert launcher.main(args) == 2
    result = capsys.readouterr()
    assert result.out == '' and json.loads(result.err) == {'error': 'INVALID_ARGUMENTS'}
    calls['load'].assert_not_called()
    calls['socket'].assert_not_called()


def test_capacity_source_required_before_any_loader(monkeypatch, capsys):
    calls, *_ = setup(monkeypatch)
    args = argv()
    index = args.index('--source-fixture')
    del args[index:index + 2]
    assert launcher.main(args) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': 'SOURCE_REQUIRED'}
    calls['load'].assert_not_called()
    calls['socket'].assert_not_called()


@pytest.mark.parametrize('keyword,value', [('expected_run_identities', ()),
    ('expected_comparison_identities', ()), ('expected_source_fixture', {})])
def test_classic_programmatic_constraints_are_not_ignored_in_capacity_mode(keyword, value, monkeypatch, capsys):
    calls, *_ = setup(monkeypatch)
    assert launcher.main(argv(), **{keyword: value}) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': 'INVALID_ARGUMENTS'}
    calls['load'].assert_not_called()
    calls['socket'].assert_not_called()


@pytest.mark.parametrize('code', ['SOURCE_REQUIRED', 'FIXED_SOURCE_MISMATCH', 'INVALID_CAPACITY_REPORT',
    'REQUIRED_CAPACITY_CONTROLS_MISSING', 'DUPLICATE_RUN_SLOT', 'INCOMPARABLE_UPSTREAM', 'RESOURCE_LIMIT'])
def test_capacity_admission_errors_are_code_only_and_never_listen(code, monkeypatch, capsys):
    calls, *_ = setup(monkeypatch)
    error = CandidateCapacityComparisonError(code)
    calls['load'].side_effect = error
    assert launcher.main(argv()) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': error.code}
    calls['app'].assert_not_called()
    calls['socket'].assert_not_called()


def test_missing_assets_fail_before_socket_or_ready(monkeypatch, capsys):
    from traffic_api.candidate_capacity_view import CandidateCapacityViewError
    calls, *_ = setup(monkeypatch)
    calls['app'].side_effect = CandidateCapacityViewError('VIEWER_ASSETS_UNAVAILABLE')
    assert launcher.main(argv()) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': 'VIEWER_ASSETS_UNAVAILABLE'}
    calls['load'].assert_called_once()
    calls['socket'].assert_not_called()


def test_unexpected_capacity_error_does_not_echo_private_text(monkeypatch, capsys):
    calls, *_ = setup(monkeypatch)
    calls['load'].side_effect = RuntimeError('private path and traceback')
    assert launcher.main(argv()) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': 'STARTUP_FAILED'}
    calls['socket'].assert_not_called()


def test_capacity_ready_and_stopped_events_use_separate_page(monkeypatch, capsys):
    async def startup(server, sockets=None):
        server.started = True
    async def shutdown(server, sockets=None):
        pass
    monkeypatch.setattr(launcher.uvicorn.Server, 'startup', startup)
    monkeypatch.setattr(launcher.uvicorn.Server, 'shutdown', shutdown)
    server = launcher._ViewerServer(SimpleNamespace(), port=32123, run_ids=('current492', 'history15'),
                                   page_path='/candidate/capacity')
    async def exercise():
        await server.startup(sockets=[])
        await server.shutdown(sockets=[])
    asyncio.run(exercise())
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event['event'] for event in events] == ['SERVER_READY', 'SERVER_STOPPED']
    assert all(event['url'] == 'http://127.0.0.1:32123/candidate/capacity' for event in events)
    assert server.shutdown_completed


def test_actual_n1_loader_seam_forwards_explicit_paths_once(monkeypatch):
    from traffic_anomaly import candidate_capacity_snapshot as core
    expected = core.CandidateCapacitySnapshot(b'{}\n', ('a', 'b'))
    load = Mock(return_value=expected)
    monkeypatch.setattr(core, 'load_verified_candidate_capacity_comparison', load)
    args = SimpleNamespace(ae_run=[Path('new492'), Path('h15')], records=Path('records'),
                           inputs=Path('inputs'), source_fixture=Path('source.json'))
    assert launcher._load_capacity_snapshot(args) is expected
    load.assert_called_once_with(args.ae_run, args.records, args.inputs, source_fixture=args.source_fixture)


def test_mutated_view_error_code_cannot_leak(monkeypatch, capsys):
    from traffic_api.candidate_capacity_view import CandidateCapacityViewError
    calls, *_ = setup(monkeypatch)
    error = CandidateCapacityViewError('VIEWER_ASSETS_UNAVAILABLE')
    error.code = 'private/path'
    calls['app'].side_effect = error
    assert launcher.main(argv()) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err) == {'error': 'INVALID_CAPACITY_SNAPSHOT'}
    calls['socket'].assert_not_called()
