"""Explicit adapter tests: manual packages and spies; no numerical execution."""
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from dataclasses import replace

import pytest


def api():
    name = 'traffic_anomaly.release_if_learned_cli'
    assert importlib.util.find_spec(name) is not None, 'learned CLI public module missing'
    return importlib.import_module(name)


def test_public_entry_help_and_exact_bytes(capfdbinary):
    cli = api()
    assert cli.main(['--help']) == 0
    streams = capfdbinary.readouterr()
    assert streams.out == (
        b'usage: python -m traffic_anomaly.release_if_learned_cli COMMAND OPTIONS\n'
        b'\ncommands:\n'
        b'  inspect --learned-package ABS\n'
        b'  replay --learned-package ABS --result-package ABS --raw-package ABS --prepared-package ABS\n'
        b'  fit-save --raw-package ABS --prepared-package ABS --view {current13,h30_26} --result-output NEW_ABS --learned-output NEW_ABS\n'
        b'\nChecks saved internal consistency; explicit replay checks numerical agreement.\n'
        b'  -h, --help   show this fixed usage\n')
    assert streams.err == b''


@pytest.mark.parametrize('args', [[], 'inspect', b'inspect', ['--help', 'inspect'],
    ['ins'], ['inspect', '--learned-package', ''], ['inspect', '--learned-package', '--help'],
    ['inspect', '--learned-package=@secret'], ['inspect', '--learned-package=x', '--learned-package=y'],
    ['fit-save', '--raw-package=x', '--prepared-package=y', '--view=bad', '--result-output=z', '--learned-output=a']])
def test_syntax_precedes_path_work(args, monkeypatch, capfdbinary):
    cli = api()
    monkeypatch.setattr(cli, '_paths', lambda *a: pytest.fail('path access on syntax failure'))
    assert cli.main(args) == 2
    streams = capfdbinary.readouterr()
    assert streams.out == b''
    assert streams.err == b'{"error":"INVALID_ARGUMENTS"}\n'


def test_inspect_manual_projection(tmp_path, capfdbinary):
    from tests.core.test_release_if_learned_contract import package
    from traffic_anomaly.release_if_learned_package import save_release_if_learned_package
    from traffic_anomaly.release_if_learned_summary import summarize_release_if_learned
    p = package()
    target = tmp_path / 'learned'
    save_release_if_learned_package(p, target)
    cli = api()
    assert cli.main(['inspect', '--learned-package', str(target)]) == 0
    streams = capfdbinary.readouterr()
    receipt = json.loads(streams.out)
    assert receipt == dict(version=1, profile_id='c17-release-iforest-learned-cli-v1',
        command='inspect', status='INTERNAL_CONSISTENCY_CHECKED',
        summary=summarize_release_if_learned(p), replay=None,
        operations=dict(fresh_fit_calls=0, numerical_replay_calls=0, result_save_calls=0, learned_save_calls=0))
    assert streams.out == (json.dumps(receipt, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    assert streams.err == b''


def test_cold_help_no_product_imports_or_paths():
    script = '''
import builtins, importlib, pathlib, sys
real = builtins.__import__
roots = {'numpy','sklearn','joblib','torch','cloudpickle','pickle'}
allowed = {'traffic_anomaly', 'traffic_anomaly.release_if_learned_cli'}
attempts = []
def forbidden(name):
    return name.split('.')[0] in roots or name.startswith('traffic_anomaly.') and name not in allowed
class Fence:
    def find_spec(self, fullname, path=None, target=None):
        if forbidden(fullname):
            attempts.append(fullname)
            raise AssertionError('forbidden direct resolution')
        return None
sys.meta_path.insert(0, Fence())
def guarded(name, *args, **kwargs):
    if forbidden(name):
        attempts.append(name)
        raise AssertionError('forbidden import on help')
    return real(name, *args, **kwargs)
builtins.__import__ = guarded
for name in ('numpy', 'traffic_anomaly.release_if_learned_package', 'traffic_anomaly.release_if_learned'):
    before = len(attempts)
    try:
        importlib.import_module(name)
    except AssertionError:
        pass
    else:
        raise AssertionError('meta_path fence bypassed')
    assert attempts[before:] == [name]
assert not any(forbidden(name) for name in sys.modules)
attempts.clear()
import traffic_anomaly.release_if_learned_cli as cli
pathlib.Path.lstat = lambda *a, **k: (_ for _ in ()).throw(AssertionError('path operation'))
assert cli.main(['--help']) == 0
assert attempts == []
assert not any(forbidden(name) for name in sys.modules)
'''
    run = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', script], capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.startswith(b'usage: python -m traffic_anomaly.release_if_learned_cli ')
    assert run.stderr == b''


def manual_run(view='current13'):
    """Compose accepted codecs around hand declarations, with no operation fit."""
    from tests.core.release_if_result_cases import hand_pair, hand_result
    from tests.core.test_release_if_learned_contract import manual
    from traffic_anomaly import release_if_learned_contract as c
    from traffic_anomaly.release_if_learned import ReleaseIFLearnedRun
    from traffic_anomaly.release_if_result_contract import make_release_if_result_package
    pair = hand_pair()
    result = hand_result(pair, view)
    saved = make_release_if_result_package(pair, result)
    context, state = manual(view=view, m=17)
    ref = lambda value: c.ReleaseIFLearnedReference(*(getattr(value, name) for name in
        ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')))
    context = replace(context, raw_identity=ref(pair.raw_identity), prepared_identity=ref(pair.prepared_identity),
        result_identity=ref(saved.identity), configuration_sha256=pair.configuration_sha256,
        minute_count=176, train_count=17, calibration_count=4, preprocessing_fit_count=18,
        population_sha256=c._population_sha256(minute_count=176, scored_mask=result.scored_mask,
            train_indices=result.train_indices, calibration_indices=result.calibration_indices,
            preprocessing_fit_indices=result.preprocessing_fit_indices))
    return pair, ReleaseIFLearnedRun(saved, c._make_release_if_learned_package(context, state))


def fit_environment(tmp_path, monkeypatch, *, view='current13'):
    from traffic_anomaly import release_minute_package as raw
    from traffic_anomaly import release_input_package as prepared
    from traffic_anomaly import release_model_inputs as pairing
    from traffic_anomaly import release_if_learned as operation
    from traffic_anomaly import release_if_result_package as result_disk
    from traffic_anomaly import release_if_learned_package as learned_disk
    pair, run = manual_run(view)
    calls = []
    paths = {name: tmp_path / name for name in ('raw', 'prepared', 'result', 'learned')}
    paths['raw'].mkdir()
    paths['prepared'].mkdir()
    def load_raw(path):
        assert path == paths['raw']
        calls.append('raw')
        return 'explicit raw'
    def load_prepared(path):
        assert path == paths['prepared']
        calls.append('prepared')
        return 'explicit prepared'
    def make_pair(a, b):
        assert (a, b) == ('explicit raw', 'explicit prepared')
        calls.append('pair')
        return pair
    def fit(value, *, view):
        assert value is pair and view == run.learned_package.context.view
        calls.append('fit')
        return run
    result_save, learned_save = result_disk.save_release_if_result_package, learned_disk.save_release_if_learned_package
    def save_result(value, path):
        calls.append('result-save')
        assert value is run.result_package
        return result_save(value, path)
    def save_learned(value, path):
        calls.append('learned-save')
        assert value is run.learned_package
        return learned_save(value, path)
    monkeypatch.setattr(raw, 'load_release_minute_package', load_raw)
    monkeypatch.setattr(prepared, 'load_release_input_package', load_prepared)
    monkeypatch.setattr(pairing, 'pair_release_model_inputs', make_pair)
    monkeypatch.setattr(operation, 'fit_release_iforest_learned', fit)
    monkeypatch.setattr(operation, 'replay_release_iforest_learned', lambda *a: pytest.fail('replay on fit'))
    monkeypatch.setattr(result_disk, 'save_release_if_result_package', save_result)
    monkeypatch.setattr(learned_disk, 'save_release_if_learned_package', save_learned)
    args = ['fit-save', '--raw-package', str(paths['raw']), '--prepared-package', str(paths['prepared']),
        '--view', view, '--result-output', str(paths['result']), '--learned-output', str(paths['learned'])]
    return paths, args, calls, pair, run


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_fit_save_one_adapter_call_two_native_savers(tmp_path, monkeypatch, capfdbinary, view):
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch, view=view)
    assert api().main(args) == 0
    output = capfdbinary.readouterr()
    receipt = json.loads(output.out)
    assert receipt['status'] == 'SAVED'
    assert receipt['summary']['view'] == view
    assert receipt['operations'] == dict(fresh_fit_calls=1, numerical_replay_calls=0,
        result_save_calls=1, learned_save_calls=1)
    assert calls == ['raw', 'prepared', 'pair', 'fit', 'result-save', 'learned-save']
    assert output.err == b''
    from traffic_anomaly.release_if_result_package import load_release_if_result_package
    from traffic_anomaly.release_if_learned_package import load_release_if_learned_package
    assert load_release_if_result_package(paths['result']) == run.result_package
    assert load_release_if_learned_package(paths['learned']) == run.learned_package


def test_existing_second_target_precedes_input_load(tmp_path, monkeypatch, capfdbinary):
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    paths['learned'].write_bytes(b'competitor')
    assert api().main(args) == 2
    assert capfdbinary.readouterr().err == b'{"error":"OUTPUT_EXISTS"}\n'
    assert calls == []
    assert paths['learned'].read_bytes() == b'competitor'
    assert not paths['result'].exists()


@pytest.mark.parametrize('layout', ['equal', 'nested', 'input', 'case'])
def test_layout_precedes_existence_and_load(tmp_path, monkeypatch, capfdbinary, layout):
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    target = {'equal': paths['result'], 'nested': paths['result'] / 'child', 'input': paths['raw'],
        'case': Path(str(paths['result']).upper())}[layout]
    if layout == 'case' and sys.platform != 'win32':
        pytest.skip('native case-sensitive filesystem')
    args[-1] = str(target)
    assert api().main(args) == 2
    assert capfdbinary.readouterr().err == b'{"error":"INVALID_PATH_LAYOUT"}\n'
    assert calls == []


@pytest.mark.parametrize('when', ['before-fit', 'after-fit', 'between-saves'])
def test_occupied_target_races_preserve_competitor(tmp_path, monkeypatch, capfdbinary, when):
    from traffic_anomaly import release_if_learned as op
    from traffic_anomaly import release_model_inputs as pairing
    from traffic_anomaly import release_if_result_package as result_disk
    paths, args, calls, pair, run = fit_environment(tmp_path, monkeypatch)
    if when == 'before-fit':
        old = pairing.pair_release_model_inputs
        def race(*a):
            value = old(*a)
            paths['learned'].write_bytes(b'competitor')
            return value
        monkeypatch.setattr(pairing, 'pair_release_model_inputs', race)
    elif when == 'after-fit':
        old = op.fit_release_iforest_learned
        def race(*a, **k):
            value = old(*a, **k)
            paths['learned'].write_bytes(b'competitor')
            return value
        monkeypatch.setattr(op, 'fit_release_iforest_learned', race)
    else:
        old = result_disk.save_release_if_result_package
        def race(*a):
            value = old(*a)
            paths['learned'].write_bytes(b'competitor')
            return value
        monkeypatch.setattr(result_disk, 'save_release_if_result_package', race)
    assert api().main(args) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == b'{"error":"OUTPUT_EXISTS"}\n'
    assert calls == ['raw', 'prepared', 'pair'] + ([] if when == 'before-fit' else ['fit']) + (
        ['result-save'] if when == 'between-saves' else [])
    assert paths['learned'].read_bytes() == b'competitor'
    assert paths['result'].exists() == (when == 'between-saves')


def test_all_lexical_paths_before_layout(tmp_path, monkeypatch, capfdbinary):
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    args[-3] = str(paths['raw'])
    args[-1] = str(tmp_path / '..' / 'bad')
    assert api().main(args) == 2
    assert capfdbinary.readouterr().err == b'{"error":"INVALID_PACKAGE_PATH"}\n'
    assert calls == []


@pytest.mark.parametrize('change', ['wrong-view', 'wrong-reference', 'population', 'count', 'missing-run', 'missing-report'])
def test_false_fit_returns_never_save(tmp_path, monkeypatch, capfdbinary, change):
    from traffic_anomaly import release_if_learned as op
    from traffic_anomaly import release_if_learned_contract as c
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch)
    if change == 'wrong-view':
        _, bad = manual_run('h30_26')
    elif change == 'missing-run':
        bad = object.__new__(op.ReleaseIFLearnedRun)
    elif change == 'missing-report':
        bad = replace(run, result_package=replace(run.result_package,
            load_report=object.__new__(type(run.result_package.load_report))))
    else:
        changes = {'wrong-reference': dict(result_identity=replace(run.learned_package.context.result_identity,
            manifest_sha256='f' * 64)), 'population': dict(population_sha256='f' * 64),
            'count': dict(calibration_count=5)}[change]
        learned = c._make_release_if_learned_package(replace(run.learned_package.context, **changes), run.learned_package.state)
        bad = replace(run, learned_package=learned)
    def false_fit(*a, **k):
        calls.append('fit')
        return bad
    monkeypatch.setattr(op, 'fit_release_iforest_learned', false_fit)
    assert api().main(args) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == b'{"error":"INVALID_RESULT"}\n'
    assert calls == ['raw', 'prepared', 'pair', 'fit']
    assert not paths['result'].exists() and not paths['learned'].exists()


@pytest.mark.parametrize('saver,value', [('result', 'foreign'), ('result', 'missing'),
    ('result', 'bool'), ('result', 'changed'), ('learned', 'foreign'), ('learned', 'missing')])
def test_saver_identity_requires_native_exact_four_slots(tmp_path, monkeypatch, capfdbinary, saver, value):
    from traffic_anomaly import release_if_result_package as result_disk
    from traffic_anomaly import release_if_learned_package as learned_disk
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch)
    identity = run.result_package.identity if saver == 'result' else run.learned_package.identity
    if value == 'foreign':
        from traffic_anomaly.release_if_learned_contract import ReleaseIFLearnedReference
        from traffic_anomaly.release_if_result_contract import ReleaseIFResultIdentity
        kind = ReleaseIFLearnedReference if saver == 'result' else ReleaseIFResultIdentity
        wrong = kind(*(getattr(identity, f) for f in ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')))
    elif value == 'missing':
        wrong = object.__new__(type(identity))
    else:
        wrong = replace(identity, **(dict(manifest_byte_count=True) if value == 'bool' else dict(manifest_sha256='f' * 64)))
    module = result_disk if saver == 'result' else learned_disk
    name = 'save_release_if_' + ('result' if saver == 'result' else 'learned') + '_package'
    original = getattr(module, name)
    def false_saver(*a):
        original(*a)
        return wrong
    monkeypatch.setattr(module, name, false_saver)
    assert api().main(args) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == b'{"error":"INVALID_RESULT"}\n'
    assert calls == ['raw', 'prepared', 'pair', 'fit', 'result-save'] + (['learned-save'] if saver == 'learned' else [])
    assert paths['result'].is_dir()
    assert paths['learned'].exists() == (saver == 'learned')


def replay_environment(tmp_path, monkeypatch):
    from traffic_anomaly import release_if_learned as op
    from traffic_anomaly import release_if_learned_package as learned_disk
    from traffic_anomaly import release_if_result_package as result_disk
    paths, fit_args, calls, pair, run = fit_environment(tmp_path, monkeypatch)
    def load_learned(path):
        assert path == paths['learned']
        calls.append('learned-load')
        return run.learned_package
    def load_result(path):
        assert path == paths['result']
        calls.append('result-load')
        return run.result_package
    report = op.ReleaseIFLearnedReplayReport('c17-release-iforest-learned-package-v1',
        'EXPLICIT_INPUT_NUMERICAL_REPLAY_ONLY', run.learned_package.identity,
        run.learned_package.context.result_identity, 55, 4, 'MATCHED', 'MATCHED', 'MATCHED',
        'NOT_AUTHENTICATED', 'NOT_PERFORMED')
    def replay(learned, actual_pair, saved):
        assert learned is run.learned_package and actual_pair is pair and saved is run.result_package
        calls.append('replay')
        return report
    monkeypatch.setattr(learned_disk, 'load_release_if_learned_package', load_learned)
    monkeypatch.setattr(result_disk, 'load_release_if_result_package', load_result)
    monkeypatch.setattr(op, 'replay_release_iforest_learned', replay)
    monkeypatch.setattr(op, 'fit_release_iforest_learned', lambda *a, **k: pytest.fail('fit on replay'))
    args = ['replay', '--learned-package', str(paths['learned']), '--result-package', str(paths['result']),
        '--raw-package', str(paths['raw']), '--prepared-package', str(paths['prepared'])]
    return paths, args, calls, pair, run, report


def test_explicit_replay_order_counts_and_negative_summary(tmp_path, monkeypatch, capfdbinary):
    _, args, calls, _, run, report = replay_environment(tmp_path, monkeypatch)
    assert api().main(args) == 0
    output = capfdbinary.readouterr()
    receipt = json.loads(output.out)
    assert calls == ['learned-load', 'result-load', 'raw', 'prepared', 'pair', 'replay']
    assert receipt['status'] == 'NUMERICAL_REPLAY_MATCHED'
    assert receipt['replay']['scored_count'] == 55 and receipt['replay']['calibration_count'] == 4
    assert receipt['summary']['checks']['numerical_replay'] == 'NOT_RUN'
    assert receipt['summary']['checks']['result_binding'] == 'NOT_PERFORMED'
    assert receipt['summary']['checks']['source_authentication'] == 'NOT_AUTHENTICATED'
    assert receipt['operations'] == dict(fresh_fit_calls=0, numerical_replay_calls=1, result_save_calls=0, learned_save_calls=0)
    assert output.err == b''


@pytest.mark.parametrize('change', ['missing', 'bool', 'scored', 'calibration', 'identity', 'status'])
def test_false_replay_reports_rejected(tmp_path, monkeypatch, capfdbinary, change):
    from traffic_anomaly import release_if_learned as op
    _, args, calls, _, _, report = replay_environment(tmp_path, monkeypatch)
    bad = object.__new__(type(report)) if change == 'missing' else replace(report, **{
        'bool': dict(scored_count=True), 'scored': dict(scored_count=54),
        'calibration': dict(calibration_count=3),
        'identity': dict(result_identity=replace(report.result_identity, manifest_byte_count=2)),
        'status': dict(source_authentication='AUTHENTICATED')}[change])
    monkeypatch.setattr(op, 'replay_release_iforest_learned', lambda *a: bad)
    assert api().main(args) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == b'{"error":"INVALID_RESULT"}\n'


@pytest.mark.parametrize('stage,code,expected', [('learned', 'INTEGRITY_MISMATCH', []),
    ('result', 'INCONSISTENT_PACKAGE', ['learned-load']),
    ('raw', 'INPUT_UNAVAILABLE', ['learned-load', 'result-load']),
    ('prepared', 'DERIVATION_MISMATCH', ['learned-load', 'result-load', 'raw'])])
def test_replay_first_load_failure_is_authoritative(tmp_path, monkeypatch, capfdbinary, stage, code, expected):
    _, args, calls, _, _, _ = replay_environment(tmp_path, monkeypatch)
    from traffic_anomaly import release_if_learned_package as learned
    from traffic_anomaly import release_if_result_package as result
    from traffic_anomaly import release_minute_package as raw
    from traffic_anomaly import release_input_package as prepared
    module, name, kind = {'learned': (learned, 'load_release_if_learned_package', learned.ReleaseIFLearnedError),
        'result': (result, 'load_release_if_result_package', result.ReleaseIFResultPackageError),
        'raw': (raw, 'load_release_minute_package', raw.ReleaseMinutePackageError),
        'prepared': (prepared, 'load_release_input_package', prepared.ReleaseInputPreparationError)}[stage]
    def fail(*a):
        raise kind(code)
    monkeypatch.setattr(module, name, fail)
    assert api().main(args) == 2
    assert capfdbinary.readouterr().err == ('{"error":"' + code + '"}\n').encode()
    assert calls == expected


@pytest.mark.parametrize('equal_leaf', [True, False])
def test_observed_parent_alias_checks_native_leaf(tmp_path, monkeypatch, capfdbinary, equal_leaf):
    from traffic_anomaly import release_if_learned_package as disk
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    parents = [tmp_path / 'parent-a', tmp_path / 'parent-b']
    for parent in parents:
        parent.mkdir()
    a, b = parents[0] / 'output', parents[1] / ('OUTPUT' if equal_leaf else 'other')
    args[-3], args[-1] = str(a), str(b)
    originals = [parent.lstat() for parent in parents]
    real_signature = disk._signature
    def signature(info, **kwargs):
        value = real_signature(info, **kwargs)
        return (value[0], originals[0].st_ino, *value[2:]) if info.st_ino == originals[1].st_ino else value
    monkeypatch.setattr(disk, '_signature', signature)
    status = api().main(args)
    output = capfdbinary.readouterr()
    if equal_leaf and sys.platform == 'win32':
        assert status == 2 and output.err == b'{"error":"INVALID_PATH_LAYOUT"}\n'
        assert calls == [] and not a.exists() and not b.exists()
    else:
        assert status == 0 and output.err == b''
        assert calls == ['raw', 'prepared', 'pair', 'fit', 'result-save', 'learned-save']


@pytest.mark.parametrize('which', ['result', 'learned'])
def test_both_output_ancestor_input_identity_alias(tmp_path, monkeypatch, capfdbinary, which):
    from traffic_anomaly import release_if_learned_package as disk
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    parent = tmp_path / 'separate-parent'
    parent.mkdir()
    args[-3 if which == 'result' else -1] = str(parent / which)
    raw_info, parent_info = paths['raw'].lstat(), parent.lstat()
    real = disk._signature
    def signature(info, **kwargs):
        value = real(info, **kwargs)
        return (value[0], raw_info.st_ino, *value[2:]) if info.st_ino == parent_info.st_ino else value
    monkeypatch.setattr(disk, '_signature', signature)
    assert api().main(args) == 2
    assert capfdbinary.readouterr().err == b'{"error":"INVALID_PATH_LAYOUT"}\n'
    assert calls == ['raw', 'prepared', 'pair']


@pytest.mark.parametrize('stage', ['before-fit', 'after-fit', 'between-saves'])
def test_recorded_learned_parent_replacement_preserves_first(tmp_path, monkeypatch, capfdbinary, stage):
    from traffic_anomaly import release_model_inputs as pairing
    from traffic_anomaly import release_if_learned as op
    from traffic_anomaly import release_if_result_package as result_disk
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    parent = tmp_path / 'learned-parent'
    parent.mkdir()
    args[-1] = str(parent / 'new-output')
    module, name = {'before-fit': (pairing, 'pair_release_model_inputs'),
        'after-fit': (op, 'fit_release_iforest_learned'),
        'between-saves': (result_disk, 'save_release_if_result_package')}[stage]
    original = getattr(module, name)
    def replacement(*a, **k):
        value = original(*a, **k)
        parent.rename(tmp_path / 'preserved-parent')
        parent.mkdir()
        (parent / 'competitor').write_bytes(b'preserve')
        return value
    monkeypatch.setattr(module, name, replacement)
    assert api().main(args) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == b'{"error":"PACKAGE_CHANGED"}\n'
    assert calls == ['raw', 'prepared', 'pair'] + ([] if stage == 'before-fit' else ['fit']) + (
        ['result-save'] if stage == 'between-saves' else [])
    assert (parent / 'competitor').read_bytes() == b'preserve'
    assert (tmp_path / 'preserved-parent').is_dir()
    assert paths['result'].exists() == (stage == 'between-saves')


def test_initial_missing_parent_is_output_error(tmp_path, monkeypatch, capfdbinary):
    _, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    args[-1] = str(tmp_path / 'missing-parent' / 'new')
    assert api().main(args) == 2
    assert capfdbinary.readouterr().err == b'{"error":"OUTPUT_ERROR"}\n'
    assert calls == []


def test_receipt_bound_exact_lf_and_before_saves(tmp_path, monkeypatch, capfdbinary):
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch)
    cli = api()
    receipt = cli._receipt('fit-save', run.learned_package)
    exact = cli._encode(receipt)
    assert exact.endswith(b'\n') and not exact.endswith(b'\n\n')
    monkeypatch.setattr(cli, '_OUTPUT_LIMIT', len(exact))
    assert cli._encode(receipt) == exact
    monkeypatch.setattr(cli, '_OUTPUT_LIMIT', len(exact) - 1)
    assert cli.main(args) == 2
    streams = capfdbinary.readouterr()
    assert streams.out == b'' and streams.err == b'{"error":"RESOURCE_LIMIT"}\n'
    assert calls == ['raw', 'prepared', 'pair', 'fit']
    assert not paths['result'].exists() and not paths['learned'].exists()


def test_component_similar_input_output_sibling_is_legal(tmp_path, monkeypatch, capfdbinary):
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    args[-3] = str(tmp_path / 'raw-extra')
    assert api().main(args) == 0
    streams = capfdbinary.readouterr()
    assert streams.err == b'' and json.loads(streams.out)['status'] == 'SAVED'
    assert calls == ['raw', 'prepared', 'pair', 'fit', 'result-save', 'learned-save']


def test_original_spelling_and_canonical_flag_order(monkeypatch, capfdbinary):
    from traffic_anomaly import release_if_learned_package as disk
    seen = []
    def lexical(value):
        seen.append(value)
        if len(seen) == 3:
            raise disk.ReleaseIFLearnedError('INVALID_PACKAGE_PATH')
        return Path(value)
    monkeypatch.setattr(disk, '_lexical', lexical)
    args = ['replay', '--prepared-package=C:/p/../kept', '--raw-package=C:/raw',
        '--result-package=C:/result', '--learned-package=C:/learned']
    assert api().main(args) == 2
    assert seen == ['C:/learned', 'C:/result', 'C:/raw']
    assert capfdbinary.readouterr().err == b'{"error":"INVALID_PACKAGE_PATH"}\n'


def test_result_codec_error_precedes_cross_object_comparison(tmp_path, monkeypatch, capfdbinary):
    from traffic_anomaly import release_if_learned as op
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch)
    wrong = replace(run.result_package, result=replace(run.result_package.result, threshold=0.0))
    def fit(*a, **k):
        calls.append('fit')
        return replace(run, result_package=wrong)
    monkeypatch.setattr(op, 'fit_release_iforest_learned', fit)
    assert api().main(args) == 2
    streams = capfdbinary.readouterr()
    assert streams.out == b'' and streams.err == b'{"error":"INCONSISTENT_PACKAGE"}\n'
    assert calls == ['raw', 'prepared', 'pair', 'fit']
    assert not paths['result'].exists()


def test_pair_configuration_reference_is_exact_primitive_before_comparison(tmp_path, monkeypatch, capfdbinary):
    from traffic_anomaly import release_model_inputs as pairing
    from traffic_anomaly import release_if_learned as op
    paths, args, calls, pair, run = fit_environment(tmp_path, monkeypatch)
    reads = []
    class FalseReference:
        def __eq__(self, other):
            reads.append(True)
            return True
    bad_pair = replace(pair, configuration_sha256=FalseReference())
    def false_pair(*a):
        calls.append('pair')
        return bad_pair
    def fit(*a, **k):
        calls.append('fit')
        return run
    monkeypatch.setattr(pairing, 'pair_release_model_inputs', false_pair)
    monkeypatch.setattr(op, 'fit_release_iforest_learned', fit)
    assert api().main(args) == 2
    streams = capfdbinary.readouterr()
    assert streams.out == b'' and streams.err == b'{"error":"INVALID_RESULT"}\n'
    assert reads == []
    assert calls == ['raw', 'prepared', 'pair', 'fit']
    assert not paths['result'].exists()


@pytest.mark.parametrize('variant', ['malformed', 'valid-once', 'learned-code', 'path-code',
    'memory', 'interrupt', 'self-raise', 'known-raise'])
def test_recheck_error_code_is_admitted_once_before_comparison(tmp_path, monkeypatch, capfdbinary, variant):
    from traffic_anomaly import release_if_learned_package as disk
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    callbacks = []
    class ForeignCode:
        def __eq__(self, other):
            callbacks.append('foreign equality')
            return True
    error = disk.ReleaseIFLearnedError('OUTPUT_ERROR')
    second = api()._result_disk().ReleaseIFResultPackageError('OUTPUT_EXISTS')
    reads = []
    def code(self):
        reads.append(True)
        if variant == 'memory':
            raise MemoryError('private')
        if variant == 'interrupt':
            raise KeyboardInterrupt('private')
        if variant == 'self-raise':
            raise error
        if variant == 'known-raise':
            raise second
        if variant == 'malformed':
            return ForeignCode()
        return {'learned-code': 'LEARNED_ERROR', 'path-code': 'INVALID_PACKAGE_PATH'}.get(variant, 'OUTPUT_ERROR')
    monkeypatch.setattr(disk.ReleaseIFLearnedError, 'code', property(code), raising=False)
    original = disk._signature
    def signature(*a, **k):
        if 'pair' in calls:
            raise error
        return original(*a, **k)
    monkeypatch.setattr(disk, '_signature', signature)
    # Isolate the recorded-ancestor recheck rather than the preceding input
    # root observation, which also uses this accepted signature helper.
    monkeypatch.setattr(api(), '_input_alias_preflight', lambda *a: None)
    assert api().main(args) == 2
    expected = {'malformed': 'INTERNAL_ERROR', 'valid-once': 'OUTPUT_ERROR',
        'learned-code': 'LEARNED_ERROR', 'path-code': 'PACKAGE_CHANGED',
        'self-raise': 'INTERNAL_ERROR', 'known-raise': 'INTERNAL_ERROR',
        'memory': 'RESOURCE_LIMIT', 'interrupt': 'INTERRUPTED'}[variant]
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == ('{"error":"' + expected + '"}\n').encode()
    assert callbacks == [] and reads == [True]
    assert calls == ['raw', 'prepared', 'pair']
    assert not paths['result'].exists() and not paths['learned'].exists()


@pytest.mark.parametrize('stage', ['before-fit', 'between-saves'])
@pytest.mark.parametrize('error_kind', [PermissionError, OSError])
def test_unavailable_ancestor_observation_is_output_error(tmp_path, monkeypatch, capfdbinary, stage, error_kind):
    paths, args, calls, _, run = fit_environment(tmp_path, monkeypatch)
    parent = tmp_path / 'ordinary-learned-parent'
    parent.mkdir()
    args[-1] = str(parent / 'new')
    native = type(parent)
    original = native.lstat
    def stat(path, *a, **k):
        active = 'pair' in calls if stage == 'before-fit' else 'result-save' in calls
        if path == parent and active:
            raise error_kind('private observation failure')
        return original(path, *a, **k)
    monkeypatch.setattr(native, 'lstat', stat)
    assert api().main(args) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == b'{"error":"OUTPUT_ERROR"}\n'
    assert calls == ['raw', 'prepared', 'pair'] + ([] if stage == 'before-fit' else ['fit', 'result-save'])
    assert parent.is_dir()
    assert paths['result'].exists() == (stage == 'between-saves')
    if stage == 'between-saves':
        from traffic_anomaly.release_if_result_package import load_release_if_result_package
        assert load_release_if_result_package(paths['result']) == run.result_package


@pytest.mark.skipif(sys.platform != 'win32', reason='native Windows drive roots')
@pytest.mark.parametrize('case,expected', [('absent', 'OUTPUT_ERROR'), ('occupied', 'OUTPUT_EXISTS'),
    ('overlap', 'INVALID_PATH_LAYOUT')])
def test_controlled_windows_output_root_boundary(tmp_path, monkeypatch, capfdbinary, case, expected):
    paths, args, calls, _, _ = fit_environment(tmp_path, monkeypatch)
    root = Path('Q:/') if tmp_path.drive.lower() != 'q:' else Path('R:/')
    if case == 'overlap':
        root = Path(tmp_path.anchor)
    native = type(root)
    original = native.lstat
    observed = []
    def stat(path, *a, **k):
        if path == root:
            observed.append(True)
            if case == 'absent':
                raise FileNotFoundError('controlled unavailable drive')
            return original(tmp_path)
        return original(path, *a, **k)
    monkeypatch.setattr(native, 'lstat', stat)
    args[-3] = str(root)
    assert api().main(args) == 2
    output = capfdbinary.readouterr()
    assert output.out == b'' and output.err == ('{"error":"' + expected + '"}\n').encode()
    assert calls == []
    assert observed == ([] if case == 'overlap' else [True])
