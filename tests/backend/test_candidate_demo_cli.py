"""Fixed demo orchestration uses fake stages; no repeated model training."""
import importlib
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tomllib
from unittest.mock import Mock

import pytest


def api():
    name = 'traffic_api.candidate_demo_cli'
    assert importlib.util.find_spec(name) is not None, 'installable fixed demo entry is required'
    return importlib.import_module(name)


def test_prepare_requires_explicit_policy_and_does_not_create_workspace(tmp_path, capsys):
    module = api()
    workspace = tmp_path / 'new'
    assert module.main(['prepare', '--workspace', str(workspace)]) == 2
    assert not workspace.exists()
    assert json.loads(capsys.readouterr().err)['error'] == 'INVALID_ARGUMENTS'


def comparison(policy='P_B'):
    payload = (Path(__file__).parents[1] / 'fixtures/g13u-records-v1.json').read_bytes()
    return dict(evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        shared_context=dict(selected_policy=policy, source_replay='VERIFIED',
            minute_count=144, score_valid_count=24, fit_count=6, calibration_count=6,
            test_denominators_by_policy={'P_U': {'scored_test_minutes': 6}},
            five_provenance={'source_fixture': {'sha256': hashlib.sha256(payload).hexdigest(), 'byte_count': len(payload)}}),
        runs=[dict(slot=slot, run_id=run_id) for slot, run_id in zip(
            ['iforest_current13', 'current_ae13', 'history_ae26_h15', 'history_ae26_h30'],
            ['demo-if-current13', 'demo-ae-current13', 'demo-ae-history15', 'demo-ae-history30'])],
        limitations={'model_origin': 'NOT_AUTHENTICATED'})


def fake_stages(module, monkeypatch, *, failure=None):
    calls = []
    def run(name, arguments, **kwargs):
        calls.append((name, arguments))
        if failure == len(calls):
            raise module.DemoError('STAGE_FAILED')
        output = Path(arguments[arguments.index('--output') + 1])
        output.mkdir()
        names = (['manifest.json', 'minute-fixture.json', 'label-audit.json'] if len(calls) == 1 else
            ['manifest.json', 'candidate-inputs.json', 'preprocess.json'] if len(calls) == 2 else
            ['manifest.json', 'model-state.json', 'scores.json', 'evaluation.json',
                'weights.bin' if len(calls) == 3 else 'weights.json'])
        for filename in names:
            value = dict(status='COMPLETE', evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY', selected_policy='P_B')
            if '--run-id' in arguments:
                value['run_id'] = arguments[arguments.index('--run-id') + 1]
            (output / filename).write_text(json.dumps(value), encoding='utf-8')
    monkeypatch.setattr(module, '_run_stage', run)
    monkeypatch.setattr(module, '_compare', lambda workspace: comparison())
    return calls


def test_prepare_fixed_six_stages_and_manifest_after_comparison(tmp_path, monkeypatch):
    module = api()
    calls = fake_stages(module, monkeypatch)
    workspace = tmp_path / '中文 demo'
    result = module.prepare_demo(workspace, policy='P_B')
    assert result['status'] == 'COMPLETE'
    assert len(calls) == 6
    assert [name for name, _ in calls] == ['traffic_anomaly.candidate_record_cli',
        'traffic_anomaly.candidate_cli', 'traffic_anomaly.candidate_if_cli',
        'traffic_anomaly.candidate_ae_cli', 'traffic_anomaly.candidate_ae_cli',
        'traffic_anomaly.candidate_ae_cli']
    assert calls[0][1][2:4] == ['--policy', 'P_B']
    assert calls[1][1][:2] == ['--fixture', str(workspace / 'records' / 'minute-fixture.json')]
    assert [args[args.index('--run-id') + 1] for _, args in calls[2:]] == [
        'demo-if-current13', 'demo-ae-current13', 'demo-ae-history15', 'demo-ae-history30']
    assert calls[4][1][-2:] == ['--history-window', '15']
    assert calls[5][1][-2:] == ['--history-window', '30']
    for _, args in calls:
        for flag in ('--fixture', '--records', '--inputs', '--source-fixture', '--output'):
            if flag in args:
                assert Path(args[args.index(flag) + 1]).is_absolute()
    reference = Path(__file__).parents[1] / 'fixtures' / 'g13u-records-v1.json'
    assert (workspace / 'source.json').read_bytes() == reference.read_bytes()
    assert module.verify_demo(workspace)['limitations']['model_origin'] == 'NOT_AUTHENTICATED'
    before = (workspace / 'demo.json').read_bytes()
    with pytest.raises(module.DemoError):
        module.prepare_demo(workspace, policy='P_B')
    assert (workspace / 'demo.json').read_bytes() == before


@pytest.mark.parametrize('failure', range(1, 7))
def test_failure_stops_without_completion_and_retains_partial(tmp_path, monkeypatch, failure):
    module = api()
    calls = fake_stages(module, monkeypatch, failure=failure)
    workspace = tmp_path / 'partial'
    with pytest.raises(module.DemoError):
        module.prepare_demo(workspace, policy='P_B')
    assert len(calls) == failure
    assert (workspace / 'source.json').is_file()
    assert not (workspace / 'demo.json').exists()


@pytest.mark.parametrize('mutation', ['source', 'missing', 'layout', 'policy', 'duplicate', 'large'])
def test_verify_and_serve_reject_invalid_workspace_before_delegation(tmp_path, monkeypatch, mutation):
    module = api()
    fake_stages(module, monkeypatch)
    workspace = tmp_path / 'demo'
    module.prepare_demo(workspace, policy='P_B')
    manifest = workspace / 'demo.json'
    if mutation == 'source':
        (workspace / 'source.json').write_text('{}')
    elif mutation == 'missing':
        (workspace / 'runs/ae-history30/weights.json').unlink()
    elif mutation == 'duplicate':
        manifest.write_text('{"schema_version":1,"schema_version":1}')
    elif mutation == 'large':
        manifest.write_bytes(b' ' * (65536 + 1))
    else:
        value = json.loads(manifest.read_text())
        value['layout_version' if mutation == 'layout' else 'selected_policy'] = '../private'
        manifest.write_text(json.dumps(value))
    for operation in (module.verify_demo, module.serve_demo):
        with pytest.raises(module.DemoError):
            operation(workspace)


def test_serve_delegates_comparison_once_without_verify(tmp_path, monkeypatch):
    module = api()
    fake_stages(module, monkeypatch)
    workspace = tmp_path / 'demo'
    module.prepare_demo(workspace, policy='P_B')
    monkeypatch.setattr(module, '_compare', lambda *a: pytest.fail('serve compared twice'))
    monkeypatch.setattr(module, 'verify_demo', lambda *a: pytest.fail('serve called verify'))
    launcher = importlib.import_module('traffic_api.candidate_serve_cli')
    captured = []
    identities = []
    def serve(args, *, expected_run_identities, expected_source_fixture, expected_comparison_identities):
        captured.append(args)
        identities.append(expected_run_identities)
        assert expected_source_fixture == json.loads((workspace / 'demo.json').read_text())['fixture']
        assert expected_comparison_identities == (('iforest_current13', 'demo-if-current13'),
            ('current_ae13', 'demo-ae-current13'), ('history_ae26_h15', 'demo-ae-history15'),
            ('history_ae26_h30', 'demo-ae-history30'))
        return 130
    monkeypatch.setattr(launcher, 'main', serve)
    assert module.serve_demo(workspace, port=1234, shutdown_after_seconds=3) == 130
    assert captured[0].count('--comparison') == 1
    assert captured[0][-4:] == ['--port', '1234', '--shutdown-after-seconds', '3']
    assert captured[0][captured[0].index('--source-fixture') + 1] == str(workspace / 'source.json')
    assert identities == [(('demo-if-current13', 'P_B'), ('demo-ae-current13', 'P_B'),
        ('demo-ae-history15', 'P_B'), ('demo-ae-history30', 'P_B'))]


def test_demo_serve_rejects_consistent_history_slot_swap_before_listening(tmp_path, monkeypatch, capsys):
    from .test_candidate_serve_cli import demo_slot_case
    module = api()
    _, _, listener, comparison, expected = demo_slot_case(monkeypatch, swapped=True)
    index = {'fixture': expected['expected_source_fixture'],
             'selected_policy': expected['expected_run_identities'][0][1]}
    monkeypatch.setattr(module, '_check_workspace', lambda _: (tmp_path, index))
    assert module.serve_demo(tmp_path) == 2
    assert json.loads(capsys.readouterr().err) == {'error': 'INVALID_REGISTRATION'}
    comparison.assert_called_once()
    listener.bind.assert_not_called()


@pytest.mark.parametrize('reason', ['timeout', 'interrupt', 'failed'])
def test_stage_reaps_direct_child_and_suppresses_output(monkeypatch, reason):
    module = api()
    child = Mock()
    child.wait.side_effect = ([subprocess.TimeoutExpired('secret', 120), subprocess.TimeoutExpired('secret', 5), 0]
        if reason == 'timeout' else [KeyboardInterrupt(), 0] if reason == 'interrupt' else [9])
    launch = Mock(return_value=child)
    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    with pytest.raises((module.DemoError, KeyboardInterrupt)):
        module._run_stage('traffic_anomaly.candidate_cli', ['--fixture', 'absolute'])
    args, kwargs = launch.call_args
    assert args[0] == [sys.executable, '-X', 'utf8', '-m', 'traffic_anomaly.candidate_cli', '--fixture', 'absolute']
    assert kwargs['stdout'] == kwargs['stderr'] == subprocess.DEVNULL
    assert kwargs.get('shell', False) is False
    if reason != 'failed':
        child.terminate.assert_called_once()
        assert child.wait.call_count >= 2
    if reason == 'timeout':
        child.kill.assert_called_once()


def test_parent_missing_and_invalid_policy_never_create(tmp_path):
    module = api()
    for workspace, policy in [(tmp_path / 'missing/child', 'P_U'), (tmp_path / 'new', 'invalid')]:
        with pytest.raises(module.DemoError):
            module.prepare_demo(workspace, policy=policy)
        assert not workspace.exists()


def test_resource_is_byte_identical_and_explicitly_packaged():
    module = api()
    reference = (Path(__file__).parents[1] / 'fixtures/g13u-records-v1.json').read_bytes()
    assert module._source_bytes() == reference
    project = Path(__file__).parents[2] / 'src/backend/pyproject.toml'
    package_data = tomllib.loads(project.read_text('utf-8'))['tool']['setuptools']['package-data']['traffic_api']
    assert 'candidate_demo/g13u-records-v1.json' in package_data
    assert not any('*' in entry for entry in package_data)


def test_import_and_all_help_are_standard_library_only_and_do_not_create(tmp_path):
    script = '''
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('traffic_anomaly', 'torch', 'sklearn', 'numpy', 'uvicorn', 'fastapi')):
        raise AssertionError('help imported model or service code')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from traffic_api.candidate_demo_cli import main
for args in (['--help'], ['prepare','--help'], ['verify','--help'], ['serve','--help']):
    try:
        main(args)
    except SystemExit as exc:
        assert exc.code == 0
'''
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', script], cwd=tmp_path,
                            capture_output=True, timeout=15, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('extra', [['--fixture', 'private'], ['--resume'], ['--overwrite'], ['--policy', 'P_U'],
    ['--host', '0.0.0.0'], ['--port', '-1'], ['--port', '65536'], ['--port', '１'],
    ['--shutdown-after-seconds', '0'], ['--shutdown-after-seconds', '3601']])
def test_readonly_cli_rejects_unsupported_or_invalid_options_without_access(tmp_path, capsys, extra):
    module = api()
    assert module.main(['serve', '--workspace', str(tmp_path / 'missing'), *extra]) == 2
    assert json.loads(capsys.readouterr().err)['error'] == 'INVALID_ARGUMENTS'


def test_final_comparison_source_must_match_fixed_demo_before_complete(tmp_path, monkeypatch):
    module = api()
    fake_stages(module, monkeypatch)
    report = comparison()
    report['shared_context']['five_provenance']['source_fixture'] = {'sha256': 'different', 'byte_count': 1}
    monkeypatch.setattr(module, '_compare', lambda _: report)
    workspace = tmp_path / 'swapped'
    with pytest.raises(module.DemoError):
        module.prepare_demo(workspace, policy='P_B')
    assert not (workspace / 'demo.json').exists()


def test_stop_escalates_and_reaps_when_terminate_reports_error(monkeypatch):
    module = api()
    child = Mock()
    child.terminate.side_effect = OSError('private child handle')
    child.wait.return_value = 0
    module._stop_child(child)
    child.kill.assert_called_once()
    child.wait.assert_called_once_with(timeout=5)


def test_actual_timeout_reaps_a_controlled_direct_child(monkeypatch):
    module = api()
    launch = module.subprocess.Popen
    children = []
    def record(*args, **kwargs):
        child = launch(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(module.subprocess, 'Popen', record)
    with pytest.raises(module.DemoError, match='STAGE_TIMEOUT'):
        module._run_stage('timeit', ['-n', '1', '-r', '1', 'import time; time.sleep(30)'], timeout_seconds=0.1)
    assert len(children) == 1 and children[0].poll() is not None


def test_index_write_failure_cannot_leave_a_complete_demo(tmp_path, monkeypatch):
    module = api()
    fake_stages(module, monkeypatch)
    original = Path.open
    class FailedClose:
        def __init__(self, path):
            self.stream = original(path, 'xb')
        def __enter__(self):
            return self.stream
        def __exit__(self, *args):
            self.stream.close()
            raise OSError('private disk failure')
    def opening(path, *args, **kwargs):
        return FailedClose(path) if path.name == 'demo.json' and args == ('xb',) else original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', opening)
    workspace = tmp_path / 'failed-index'
    with pytest.raises(module.DemoError):
        module.prepare_demo(workspace, policy='P_B')
    assert not (workspace / 'demo.json').exists()


def test_stage_exception_is_safe_and_keeps_recovery_directory(tmp_path, monkeypatch, capsys):
    module = api()
    def failed(*args, **kwargs):
        raise OSError('PRIVATE_PATH_SENTINEL untrusted child diagnostics')
    monkeypatch.setattr(module, '_run_stage', failed)
    workspace = tmp_path / 'partial'
    assert module.main(['prepare', '--workspace', str(workspace), '--policy', 'P_A']) == 2
    captured = capsys.readouterr()
    value = json.loads(captured.err)
    assert value == {'error': 'PREPARE_FAILED', 'stage': 'records', 'recovery': '保留本次目录；换新目录重新准备'}
    assert 'PRIVATE_PATH_SENTINEL' not in captured.out + captured.err
    assert (workspace / 'source.json').is_file() and not (workspace / 'demo.json').exists()


def test_verify_binds_final_comparison_after_early_source_check(tmp_path, monkeypatch):
    module = api()
    fake_stages(module, monkeypatch)
    workspace = tmp_path / 'demo'
    module.prepare_demo(workspace, policy='P_B')
    report = comparison()
    report['shared_context']['five_provenance']['source_fixture'] = {'sha256': 'replacement', 'byte_count': 1}
    monkeypatch.setattr(module, '_compare', lambda _: report)
    with pytest.raises(module.DemoError):
        module.verify_demo(workspace)
