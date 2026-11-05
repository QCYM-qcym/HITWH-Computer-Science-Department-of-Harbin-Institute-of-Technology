"""Rebuild one fixed artificial demo; verify/serve never train.

The completion index is convenience metadata, not model-origin authentication.
Stage timeouts cover the direct child only, with bounded terminate/kill waits;
they are not a whole-workflow time, memory, or descendant-process-tree bound.
Import/help use the standard library only and do not create files.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import resources
import json
from pathlib import Path
import subprocess
import sys

_MAX_SOURCE = 1024 * 1024
_MAX_INDEX = 64 * 1024
_POLICIES = ('P_U', 'P_B', 'P_A')
_RUNS = (
    ('iforest_current13', 'if-current13', 'demo-if-current13', 'iforest'),
    ('current_ae13', 'ae-current13', 'demo-ae-current13', 'autoencoder'),
    ('history_ae26_h15', 'ae-history15', 'demo-ae-history15', 'autoencoder'),
    ('history_ae26_h30', 'ae-history30', 'demo-ae-history30', 'autoencoder'),
)
_STAGES = ('records', 'inputs', 'if-current13', 'ae-current13', 'ae-history15', 'ae-history30')


class DemoError(ValueError):
    """Only fixed, path-free diagnostics cross the terminal boundary."""
    def __init__(self, code, *, stage=None):
        self.code, self.stage = code, stage
        super().__init__(code)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise DemoError('INVALID_ARGUMENTS')


def _digest(payload):
    return dict(sha256=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))


def _source_bytes():
    resource = resources.files('traffic_api').joinpath('candidate_demo', 'g13u-records-v1.json')
    with resource.open('rb') as stream:
        payload = stream.read(_MAX_SOURCE + 1)
    if not 0 < len(payload) <= _MAX_SOURCE:
        raise DemoError('RESOURCE_LIMIT')
    return payload


def _index(policy, source):
    return dict(schema_version=1, layout_version=1, status='COMPLETE',
        evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY', scope='ENGINEERING_TOY_ONLY',
        selected_policy=policy, fixture=_digest(source),
        runs=[dict(slot=slot, run_id=run_id) for slot, _, run_id, _ in _RUNS])


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def _read_json(path, limit):
    from traffic_anomaly.candidate_artifacts import _read
    return _read(path, limit)[1]


def _layout(workspace, *, complete):
    from traffic_anomaly.candidate_artifacts import _directory, _ordinary
    _directory(workspace, {'source.json', 'records', 'inputs', 'runs'} | ({'demo.json'} if complete else set()))
    _ordinary(workspace / 'source.json')
    _directory(workspace / 'records', {'manifest.json', 'minute-fixture.json', 'label-audit.json'})
    _directory(workspace / 'inputs', {'manifest.json', 'candidate-inputs.json', 'preprocess.json'})
    _directory(workspace / 'runs', {directory for _, directory, _, _ in _RUNS})
    for _, directory, _, family in _RUNS:
        path = workspace / 'runs' / directory
        files = {'manifest.json', 'model-state.json', 'scores.json', 'evaluation.json',
                 'weights.bin' if family == 'iforest' else 'weights.json'}
        _directory(path, files)
        for name in files:
            _ordinary(path / name)


def _identities(workspace, policy):
    # Identity-only bounded reads: full loading/comparison remains the existing
    # verifier/launcher's responsibility. Index values never supply paths.
    record = _read_json(workspace / 'records' / 'manifest.json', _MAX_INDEX)
    values = [record]
    for _, directory, run_id, _ in _RUNS:
        value = _read_json(workspace / 'runs' / directory / 'manifest.json', 16 * 1024 * 1024)
        if value.get('run_id') != run_id:
            raise DemoError('INVALID_DEMO')
        values.append(value)
    if any(value.get('status') != 'COMPLETE' or value.get('selected_policy') != policy
           or value.get('evidence_kind') != 'SYNTHETIC_ONLY'
           or value.get('policy_status') != 'AUDIT_ONLY' for value in values):
        raise DemoError('INVALID_DEMO')


def _check_workspace(workspace):
    workspace = Path(workspace)
    _layout(workspace, complete=True)
    value = _read_json(workspace / 'demo.json', _MAX_INDEX)
    policy = value.get('selected_policy')
    if type(policy) is not str or policy not in _POLICIES:
        raise DemoError('INVALID_DEMO')
    expected_source = _source_bytes()
    # Compare JSON bytes to retain exact types (True must not equal version 1).
    if _json_bytes(value) != _json_bytes(_index(policy, expected_source)):
        raise DemoError('INVALID_DEMO')
    from traffic_anomaly.candidate_artifacts import _ancestors, _ordinary
    source = workspace / 'source.json'
    _ancestors(source)
    before = _ordinary(source)
    if before.st_size != len(expected_source):
        raise DemoError('INVALID_DEMO')
    with source.open('rb') as stream:
        actual_source = stream.read(_MAX_SOURCE + 1)
    after = _ordinary(source)
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if actual_source != expected_source or identity(before) != identity(after):
        raise DemoError('INVALID_DEMO')
    _identities(workspace, policy)
    return workspace.resolve(strict=True), value


def _compare(workspace):
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun, compare_candidate_runs
    return compare_candidate_runs([CandidateComparisonRun(family, workspace / 'runs' / directory)
        for _, directory, _, family in _RUNS], workspace / 'records', workspace / 'inputs',
        source_fixture=workspace / 'source.json')


def _check_comparison(report, policy):
    from traffic_anomaly.candidate_artifacts import _same
    if (report['evidence_kind'] != 'SYNTHETIC_ONLY' or report['policy_status'] != 'AUDIT_ONLY'
            or report['shared_context']['selected_policy'] != policy
            or report['shared_context']['source_replay'] != 'VERIFIED'
            or not _same(report['shared_context']['five_provenance']['source_fixture'], _digest(_source_bytes()))
            or [dict(slot=row['slot'], run_id=row['run_id']) for row in report['runs']]
               != [dict(slot=slot, run_id=run_id) for slot, _, run_id, _ in _RUNS]):
        raise DemoError('INVALID_DEMO')


def _stop_child(child):
    """Reap the direct child; no promise about arbitrary descendants."""
    try:
        child.terminate()
    except OSError:
        try:
            child.kill()
        except ProcessLookupError:
            pass
        child.wait(timeout=5)
        return
    try:
        child.wait(timeout=5)
        return
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        pass
    try:
        child.kill()
    except ProcessLookupError:
        pass
    child.wait(timeout=5)


def _run_stage(module: str, arguments: list[str], *, timeout_seconds: int = 120):
    child = subprocess.Popen([sys.executable, '-X', 'utf8', '-m', module, *arguments],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        result = child.wait(timeout=timeout_seconds)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        _stop_child(child)
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise DemoError('STAGE_TIMEOUT') from None
    except BaseException:
        _stop_child(child)
        raise
    if result != 0:
        raise DemoError('STAGE_FAILED')


def _event(event, stage):
    print(json.dumps(dict(event=event, stage=stage, evidence_kind='SYNTHETIC_ONLY',
                          policy_status='AUDIT_ONLY'), separators=(',', ':')), flush=True)


def prepare_demo(workspace: Path, *, policy: str) -> dict:
    """Execute the fixed six synthetic stages in a new, exclusive leaf directory."""
    if type(policy) is not str or policy not in _POLICIES:
        raise DemoError('INVALID_ARGUMENTS')
    workspace = Path(workspace)
    try:
        from traffic_anomaly.candidate_artifacts import _ancestors
        _ancestors(workspace)
        workspace.mkdir()
    except FileExistsError:
        raise DemoError('OUTPUT_EXISTS') from None
    except Exception:
        raise DemoError('INVALID_WORKSPACE') from None
    stage = None
    try:
        workspace = workspace.resolve(strict=True)
        source = _source_bytes()
        with (workspace / 'source.json').open('xb') as stream:
            stream.write(source)
        (workspace / 'runs').mkdir()
        common = ['--records', str(workspace / 'records'), '--inputs', str(workspace / 'inputs'),
                  '--source-fixture', str(workspace / 'source.json')]
        commands = [
            ('traffic_anomaly.candidate_record_cli', ['--fixture', str(workspace / 'source.json'),
                '--policy', policy, '--output', str(workspace / 'records')]),
            ('traffic_anomaly.candidate_cli', ['--fixture', str(workspace / 'records' / 'minute-fixture.json'),
                '--output', str(workspace / 'inputs')]),
        ]
        for i, (_, directory, run_id, family) in enumerate(_RUNS):
            arguments = common + ['--run-id', run_id, '--output', str(workspace / 'runs' / directory)]
            if family == 'autoencoder':
                arguments += ['--method', 'current_ae' if i == 1 else 'history_ae']
                if i > 1:
                    arguments += ['--history-window', '15' if i == 2 else '30']
            commands.append(('traffic_anomaly.candidate_if_cli' if family == 'iforest'
                             else 'traffic_anomaly.candidate_ae_cli', arguments))
        for stage, (module, arguments) in zip(_STAGES, commands):
            _event('STAGE_STARTED', stage)
            _run_stage(module, arguments)
            _event('STAGE_COMPLETE', stage)
        stage = None
        _layout(workspace, complete=False)
        _identities(workspace, policy)
        _check_comparison(_compare(workspace), policy)
        value = _index(policy, source)
        payload = _json_bytes(value)
        if len(payload) > _MAX_INDEX:
            raise DemoError('RESOURCE_LIMIT')
        index_path = workspace / 'demo.json'
        stream = index_path.open('xb')
        try:
            with stream:
                stream.write(payload)
        except BaseException:
            # Only our newly created completion marker is removed. Retain every
            # upstream artifact/partial directory; an existing index is never opened.
            index_path.unlink(missing_ok=True)
            raise
        return value
    except KeyboardInterrupt:
        raise
    except DemoError as exc:
        raise DemoError(exc.code, stage=stage) from None
    except Exception:
        raise DemoError('PREPARE_FAILED', stage=stage) from None


def verify_demo(workspace: Path) -> dict:
    """Read-only stored consistency; no model import, fit or deserialization."""
    try:
        workspace, index = _check_workspace(workspace)
        report = _compare(workspace)
        _check_comparison(report, index['selected_policy'])
        context = report['shared_context']
        return dict(schema_version=1, status='VERIFIED', evidence_kind='SYNTHETIC_ONLY',
            policy_status='AUDIT_ONLY', scope='ENGINEERING_TOY_ONLY', selected_policy=index['selected_policy'],
            runs=index['runs'], **{key: context[key] for key in ('minute_count', 'score_valid_count',
                'fit_count', 'calibration_count', 'test_denominators_by_policy')}, limitations=report['limitations'])
    except DemoError:
        raise
    except Exception:
        raise DemoError('INVALID_DEMO') from None


def serve_demo(workspace: Path, *, port: int = 0, shutdown_after_seconds: int | None = None) -> int:
    """Delegate one full admission/comparison to the existing foreground server."""
    if (type(port) is not int or not 0 <= port <= 65535 or shutdown_after_seconds is not None
            and (type(shutdown_after_seconds) is not int or not 1 <= shutdown_after_seconds <= 3600)):
        raise DemoError('INVALID_ARGUMENTS')
    try:
        workspace, index = _check_workspace(workspace)
    except DemoError:
        raise
    except Exception:
        raise DemoError('INVALID_DEMO') from None
    from .candidate_serve_cli import main as serve
    arguments = ['--records', str(workspace / 'records'), '--inputs', str(workspace / 'inputs'),
                 '--source-fixture', str(workspace / 'source.json')]
    for _, directory, _, family in _RUNS:
        arguments += ['--if-run' if family == 'iforest' else '--ae-run', str(workspace / 'runs' / directory)]
    arguments += ['--comparison', '--port', str(port)]
    if shutdown_after_seconds is not None:
        arguments += ['--shutdown-after-seconds', str(shutdown_after_seconds)]
    expected = tuple((run_id, index['selected_policy']) for _, _, run_id, _ in _RUNS)
    expected_comparison = tuple((slot, run_id) for slot, _, run_id, _ in _RUNS)
    return serve(arguments, expected_run_identities=expected, expected_source_fixture=index['fixture'],
                 expected_comparison_identities=expected_comparison)


def _integer(value):
    if not value.isascii() or not value.isdecimal():
        raise DemoError('INVALID_ARGUMENTS')
    try:
        return int(value)
    except ValueError:
        raise DemoError('INVALID_ARGUMENTS') from None


def main(argv=None):
    parser = _Parser(description='Fixed SYNTHETIC_ONLY / AUDIT_ONLY / ENGINEERING_TOY_ONLY demo',
                     allow_abbrev=False)
    commands = parser.add_subparsers(dest='command', required=True, parser_class=_Parser)
    for name, description in (
        ('prepare', 'Execute fixed artificial IF and three AE training/scoring stages for engineering demonstration only'),
        ('verify', 'Read-only saved-artifact consistency check; never trains'),
        ('serve', 'Read-only foreground viewer; never trains')):
        command = commands.add_parser(name, description=description, help=description, allow_abbrev=False)
        command.add_argument('--workspace', type=Path, required=True)
        if name == 'prepare':
            command.add_argument('--policy', choices=_POLICIES, required=True,
                                 help='Explicit audit identity, not research-policy approval')
        if name == 'serve':
            command.add_argument('--port', type=_integer, default=0)
            command.add_argument('--shutdown-after-seconds', type=_integer)
    args = None
    try:
        args = parser.parse_args(argv)
        if args.command == 'serve':
            return serve_demo(args.workspace, port=args.port, shutdown_after_seconds=args.shutdown_after_seconds)
        value = prepare_demo(args.workspace, policy=args.policy) if args.command == 'prepare' else verify_demo(args.workspace)
        print(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')), flush=True)
        return 0
    except KeyboardInterrupt:
        code = 'INTERRUPTED'
    except DemoError as exc:
        value = dict(error=exc.code)
        if exc.stage in _STAGES:
            value['stage'] = exc.stage
        code = None
    except Exception:
        code = 'DEMO_FAILED'
    if code is not None:
        value = dict(error=code)
    if args is not None and args.command == 'prepare':
        value['recovery'] = '保留本次目录；换新目录重新准备'
    print(json.dumps(value, ensure_ascii=False, separators=(',', ':')), file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
