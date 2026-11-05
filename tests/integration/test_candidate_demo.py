"""One real fixed artificial pipeline; boundary cases use fake-stage unit tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def snapshot(directory):
    return {str(path.relative_to(directory)): (hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size, path.stat().st_mtime_ns) for path in directory.rglob('*') if path.is_file()}


def test_fixed_artificial_prepare_then_readonly_verification_outside_checkout(tmp_path):
    from traffic_api.candidate_demo_cli import prepare_demo, verify_demo, _compare
    workspace = tmp_path / '新目录 demo'
    index = prepare_demo(workspace, policy='P_U')
    assert index['status'] == 'COMPLETE'
    source = json.loads((workspace / 'source.json').read_bytes())
    assert len(source['minutes']) == 144 and len(source['records']) == 576
    before = snapshot(workspace)
    report = verify_demo(workspace)
    assert (report['minute_count'], report['score_valid_count'], report['fit_count'], report['calibration_count']) == (144, 24, 6, 6)
    assert list(report['test_denominators_by_policy']) == ['P_U', 'P_B', 'P_A']
    for population in report['test_denominators_by_policy'].values():
        assert population['calendar_test_minutes'] == 36
        assert population['scored_test_minutes'] == 6
    comparison = _compare(workspace)
    assert [row['parameter_count'] for row in comparison['runs']] == [None, 288, 509, 509]
    for row in comparison['runs']:
        for policy in row['policies'].values():
            assert policy['metrics']['precision'] is None
            assert policy['metrics']['fnr'] == 1.0
    # A fresh process demonstrates verify without importing training/model or
    # production-worker modules, independently of prepare's isolated stages.
    script = '''
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('torch', 'sklearn', 'joblib') or name in ('traffic_api.app', 'traffic_api.worker'):
        raise AssertionError('forbidden model/production import')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from traffic_api.candidate_demo_cli import main
raise SystemExit(main(['verify', '--workspace', sys.argv[1]]))
'''
    completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', script, str(workspace)],
        cwd=tmp_path, capture_output=True, timeout=30, encoding='utf-8')
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['status'] == 'VERIFIED'
    assert snapshot(workspace) == before
