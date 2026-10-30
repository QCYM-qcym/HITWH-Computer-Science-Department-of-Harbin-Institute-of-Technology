"""CLI-boundary tests use hand-written values; they do not train toy models."""
import importlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest


def module():
    name = 'traffic_anomaly.candidate_view_cli'
    assert importlib.util.find_spec(name) is not None, 'candidate inspection CLI is required'
    return importlib.import_module(name)


def arguments(family='if', command='series', source=False):
    values = ['--records', 'private-records', '--inputs', 'private-inputs',
              '--' + family + '-run', 'private-run']
    if source:
        values += ['--source-fixture', 'private-source.json']
    return values + [command] + (['--timestamp', '2026-01-01T00:00'] if command == 'detail' else [])


def setup(monkeypatch, result=None):
    cli = module()
    run, inputs = object(), object()
    result = {'evidence_kind': 'SYNTHETIC_ONLY', 'score': None} if result is None else result
    calls = {}
    for name, value in [('load_verified_candidate_if_run', run),
            ('load_verified_candidate_ae_run', run), ('load_verified_candidate_artifacts', inputs),
            ('candidate_series_page', result), ('candidate_minute_detail', result)]:
        calls[name] = Mock(return_value=value)
        monkeypatch.setattr(cli, name, calls[name])
    return cli, calls, run, inputs


def safe_failure(cli, argv, capsys, code):
    assert cli.main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert json.loads(captured.err) == {'error': code}
    assert captured.err.count('\n') == 1
    assert all(word not in captured.err for word in ('private', 'Traceback', 'RuntimeWarning'))


@pytest.mark.parametrize('slot', ['if_current', 'ae_current', 'ae_h15', 'ae_h30'])
@pytest.mark.parametrize('command', ['series', 'detail'])
@pytest.mark.parametrize('source', [False, True])
def test_exact_dispatch_result_and_source_proof(monkeypatch, capsys, slot, command, source):
    proof = 'VERIFIED' if source else 'NOT_PROVIDED'
    result = dict(slot=slot, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        source_replay=proof if command == 'series' else dict(run=proof, inputs=proof, combined=proof),
        point=dict(score=-0.0, alarm=None, valid=False), history=dict(residual=[None] * 13))
    cli, calls, run, inputs = setup(monkeypatch, result)
    family = 'if' if slot.startswith('if') else 'ae'
    argv = arguments(family, command, source)
    if command == 'series':
        argv += ['--start', '2026-01-01T00:00', '--end', '2026-01-01T01:00', '--page', '2', '--page-size', '17']
    assert cli.main(argv) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert captured.out == json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'
    assert '-0.0' in captured.out and 'null' in captured.out
    loader = 'load_verified_candidate_if_run' if family == 'if' else 'load_verified_candidate_ae_run'
    other = 'load_verified_candidate_ae_run' if family == 'if' else 'load_verified_candidate_if_run'
    paths = (Path('private-run'), Path('private-records'), Path('private-inputs'))
    calls[loader].assert_called_once_with(*paths, source_fixture=Path('private-source.json') if source else None)
    calls[other].assert_not_called()
    if command == 'series':
        calls['load_verified_candidate_artifacts'].assert_not_called()
        calls['candidate_minute_detail'].assert_not_called()
        calls['candidate_series_page'].assert_called_once_with(run,
            start='2026-01-01T00:00', end='2026-01-01T01:00', page=2, page_size=17)
    else:
        calls['load_verified_candidate_artifacts'].assert_called_once_with(*paths[1:],
            source_fixture=Path('private-source.json') if source else None)
        calls['candidate_minute_detail'].assert_called_once_with(run, inputs, '2026-01-01T00:00')
        calls['candidate_series_page'].assert_not_called()


def test_series_default_arguments_and_empty_page_are_unchanged(monkeypatch, capsys):
    result = dict(total=7, returned=0, items=[],
        evaluation_reference=dict(scope='FULL_STORED_RUN', run_id='saved', artifact=dict(sha256='a'*64, byte_count=300)))
    cli, calls, run, _ = setup(monkeypatch, result)
    assert cli.main(arguments()) == 0
    calls['candidate_series_page'].assert_called_once_with(run, start=None, end=None, page=1, page_size=100)
    assert json.loads(capsys.readouterr().out) == result


@pytest.mark.parametrize('argv', [[], ['series'],
    arguments()[:-1], arguments()[2:], arguments()[:2]+arguments()[4:],
    ['--records', 'private-records', '--inputs', 'private-inputs', 'series'],
    arguments()[:-1]+['--ae-run', 'private-other', 'series'],
    arguments()+['--private-unknown', 'private-secret'],
    ['--rec', 'private-records', *arguments()[2:]],
    arguments()+['--page-s', '17'], arguments()+['--sta', '2026-01-01T00:00'],
    arguments()+['--page', 'True'], arguments()+['--page', '1.2'],
    arguments()+['--page-size', 'private-invalid'],
    arguments(command='detail')[:-2], arguments(command='detail')[:-2]+['--time', '2026-01-01T00:00'],
    arguments()+['--output-file', 'private-output'], arguments()+['detail']])
def test_parse_errors_are_safe_and_never_load(monkeypatch, capsys, argv):
    cli, calls, _, _ = setup(monkeypatch)
    safe_failure(cli, argv, capsys, 'INVALID_ARGUMENTS')
    for call in calls.values():
        call.assert_not_called()


@pytest.mark.parametrize('argv', [['--help'], arguments()+['--help'], arguments(command='detail')[:-2]+['--help']])
def test_help_exits_success_without_loading(monkeypatch, capsys, argv):
    cli, calls, _, _ = setup(monkeypatch)
    with pytest.raises(SystemExit) as caught:
        cli.main(argv)
    assert caught.value.code == 0
    captured = capsys.readouterr()
    assert 'usage:' in captured.out and captured.err == ''
    for call in calls.values():
        call.assert_not_called()


@pytest.mark.parametrize('family,command,phase,exception_name,code', [
    ('if','series','load_verified_candidate_if_run','CandidateRunArtifactError','INTEGRITY_MISMATCH'),
    ('ae','series','load_verified_candidate_ae_run','CandidateAERunArtifactError','INPUT_UNAVAILABLE'),
    ('if','detail','load_verified_candidate_artifacts','CandidateArtifactError','REPLAY_MISMATCH'),
    ('ae','detail','candidate_minute_detail','CandidateDetailError','MINUTE_NOT_FOUND'),
    ('if','detail','candidate_minute_detail','CandidateDetailError','INCOMPATIBLE_SNAPSHOTS'),
    ('ae','series','candidate_series_page','CandidateSeriesError','INCOMPATIBLE_SNAPSHOT'),
    ('if','series','candidate_series_page','CandidateSeriesError','INVALID_QUERY'),
    ('if','detail','candidate_minute_detail','CandidateDetailError','INVALID_QUERY')])
def test_domain_errors_are_code_only_without_retry_or_fallback(monkeypatch, capsys, family, command, phase, exception_name, code):
    cli, calls, _, _ = setup(monkeypatch)
    error = getattr(cli, exception_name)(code)
    error.__cause__ = RuntimeError('private-source path must not be echoed')
    calls[phase].side_effect = error
    safe_failure(cli, arguments(family, command), capsys, code)
    calls[phase].assert_called_once()
    other = 'load_verified_candidate_ae_run' if family == 'if' else 'load_verified_candidate_if_run'
    calls[other].assert_not_called()
    for call in calls.values():
        assert call.call_count <= 1


@pytest.mark.parametrize('result', [dict(value=float('nan')), dict(value=float('inf')),
    dict(value=float('-inf')), dict(value={1}), dict(value=object()), dict(value='\ud800')])
def test_unserializable_or_nonfinite_result_prints_no_partial_stdout(monkeypatch, capsys, result):
    cli, _, _, _ = setup(monkeypatch, result)
    safe_failure(cli, arguments(), capsys, 'INVALID_RESULT')


def test_circular_result_is_safe(monkeypatch, capsys):
    result = {}; result['self'] = result
    cli, _, _, _ = setup(monkeypatch, result)
    safe_failure(cli, arguments(), capsys, 'INVALID_RESULT')


@pytest.mark.parametrize('extra', [-1, 0, 1])
def test_utf8_output_limit_includes_one_newline(monkeypatch, capsys, extra):
    result = {'value': '网络'}
    cli, _, _, _ = setup(monkeypatch, result)
    assert cli.MAX_OUTPUT_BYTES == 1024 * 1024
    text = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'
    monkeypatch.setattr(cli, 'MAX_OUTPUT_BYTES', len(text.encode('utf-8')) + extra)
    if extra < 0:
        safe_failure(cli, arguments(), capsys, 'RESOURCE_LIMIT')
    else:
        assert cli.main(arguments()) == 0
        captured = capsys.readouterr()
        assert captured.out == text and captured.err == ''


def test_actual_one_mib_limit_rejects_oversize(monkeypatch, capsys):
    cli, _, _, _ = setup(monkeypatch, {'value': 'a' * (1024 * 1024)})
    safe_failure(cli, arguments(), capsys, 'RESOURCE_LIMIT')


def test_actual_stdout_bytes_are_counted_without_windows_newline_expansion(monkeypatch):
    result = {'value': '网络'}
    cli, _, _, _ = setup(monkeypatch, result)
    payload = (json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    monkeypatch.setattr(cli, 'MAX_OUTPUT_BYTES', len(payload))
    sink = io.BytesIO()
    stdout = io.TextIOWrapper(sink, encoding='utf-8', newline='\r\n')
    monkeypatch.setattr(sys, 'stdout', stdout)
    assert cli.main(arguments()) == 0
    stdout.flush()
    assert sink.getvalue() == payload


def test_cli_wrapper_does_no_artifact_io(monkeypatch, capsys):
    cli, _, _, _ = setup(monkeypatch)
    def forbidden(*args, **kwargs):
        raise AssertionError('CLI wrapper attempted artifact I/O')
    for name in ('open', 'read_bytes', 'read_text', 'write_bytes', 'write_text', 'mkdir', 'unlink'):
        monkeypatch.setattr(Path, name, forbidden)
    assert cli.main(arguments()) == 0
    assert capsys.readouterr().err == ''
    assert cli.main(arguments(command='detail')) == 0
    assert capsys.readouterr().err == ''
