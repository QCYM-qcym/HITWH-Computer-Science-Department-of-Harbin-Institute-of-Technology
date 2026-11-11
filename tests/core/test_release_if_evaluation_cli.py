"""Strict readonly orchestration and stream handling for saved-prediction audit.

Positive fixture setup seals artificial inputs and fits their preprocessing;
the observed command itself only reads bound values and computes label counts.
"""
from __future__ import annotations

from importlib import import_module
import builtins
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def _cli():
    try:
        module = import_module('traffic_anomaly.release_if_evaluation_cli')
    except ModuleNotFoundError as error:
        if error.name != 'traffic_anomaly.release_if_evaluation_cli':
            raise
        pytest.fail('public readonly saved-prediction evaluation CLI is missing')
    assert callable(getattr(module, 'main', None)), 'public evaluation main is missing'
    return module


def _args(tmp_path):
    return ['evaluate', '--result-package', str(tmp_path / 'result'), '--raw-package',
        str(tmp_path / 'raw'), '--prepared-package', str(tmp_path / 'prepared')]


def _invoke(cli, capsys, args):
    status = cli.main(args)
    captured = capsys.readouterr()
    return status, captured.out, captured.err


def _error(actual, code):
    assert actual == (2, '', '{"error":"' + code + '"}\n')


def _forbid(*args, **kwargs):
    raise AssertionError('unexpected business or path action')


def _sealed():
    from tests.core.release_if_evaluation_cases import sealed_evaluation_case
    return sealed_evaluation_case()


def _chain(cli, monkeypatch, case):
    monkeypatch.setattr(cli, 'load_release_if_result_package', lambda path: case.package)
    monkeypatch.setattr(cli, 'load_release_minute_package', lambda path: case.raw)
    monkeypatch.setattr(cli, 'load_release_input_package', lambda path: case.prepared)
    monkeypatch.setattr(cli, 'pair_release_model_inputs', lambda raw, prepared: case.pair)


def test_evaluate_loads_result_raw_prepared_then_pairs_once(tmp_path, monkeypatch, capsys):
    cli = _cli()
    from tests.core.release_if_evaluation_cases import sealed_evaluation_case

    case = sealed_evaluation_case()
    paths = {key: tmp_path / key for key in ('result', 'raw', 'prepared')}
    events = []
    real_pair = cli.pair_release_model_inputs
    real_evaluate = cli.evaluate_release_if_result
    real_lexical = cli._lexical
    pure = import_module('traffic_anomaly.release_if_evaluation')
    real_verify = pure.verify_release_if_result_pair
    verified = []

    def verify(package, actual_pair):
        assert package is case.package and actual_pair == case.pair
        verified.append('verify')
        return real_verify(package, actual_pair)

    monkeypatch.setattr(pure, 'verify_release_if_result_pair', verify)

    def lexical(raw):
        events.append(('lexical', raw))
        return real_lexical(raw)

    def load_result(path):
        assert path == paths['result']
        events.append(('result',))
        return case.package

    def load_raw(path):
        assert path == paths['raw']
        events.append(('raw',))
        return case.raw

    def load_prepared(path):
        assert path == paths['prepared']
        events.append(('prepared',))
        return case.prepared

    def pair(raw, prepared):
        assert raw is case.raw and prepared is case.prepared
        events.append(('pair',))
        return real_pair(raw, prepared)

    def evaluate(package, actual_pair):
        assert package is case.package
        assert actual_pair == case.pair
        events.append(('evaluate',))
        return real_evaluate(package, actual_pair)

    for name, function in (('_lexical', lexical), ('load_release_if_result_package', load_result),
            ('load_release_minute_package', load_raw), ('load_release_input_package', load_prepared),
            ('pair_release_model_inputs', pair), ('evaluate_release_if_result', evaluate)):
        monkeypatch.setattr(cli, name, function)
    # Fixture setup above performed artificial preparation. For this command
    # boundary, disk loaders are narrow substitutes; producers and file writes
    # are forbidden while the real pair verifier and evaluator execute.
    from traffic_anomaly import release_inputs, release_iforest
    monkeypatch.setattr(release_inputs, 'prepare_release_inputs', _forbid)
    monkeypatch.setattr(release_iforest, 'fit_release_iforest', _forbid)
    monkeypatch.setattr(builtins, 'open', _forbid)
    monkeypatch.setattr(Path, 'open', _forbid)
    monkeypatch.setattr(Path, 'mkdir', _forbid)
    args = ['evaluate', '--result-package', str(paths['result']), '--raw-package',
        str(paths['raw']), '--prepared-package', str(paths['prepared'])]
    assert cli.main(args) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    report = json.loads(captured.out)
    assert report['status'] == 'SAVED_PREDICTION_LABEL_AUDIT'
    assert report['audit_fit_policy'] == 'P_U'
    assert report['prediction_basis'] == 'FIXED_SAVED_PREDICTIONS_NO_REFIT'
    assert report['policies']['P_U']['confusion_counts'] == {'tp': 1, 'fp': 1, 'tn': 11, 'fn': 1}
    assert report['policies']['P_B']['confusion_counts'] == {'tp': 1, 'fp': 2, 'tn': 12, 'fn': 1}
    assert report['policies']['P_A']['confusion_counts'] == {'tp': 2, 'fp': 1, 'tn': 11, 'fn': 2}
    assert events == [('lexical', str(paths['result'])), ('lexical', str(paths['raw'])),
        ('lexical', str(paths['prepared'])), ('result',), ('raw',), ('prepared',), ('pair',), ('evaluate',)]
    assert verified == ['verify']
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('args', [[], ['evaluate'], ['inspect'], ['--help', 'evaluate'],
    ['evaluate', '--help'], ['evaluate', '--result-package'],
    ['evaluate', '--result-package='], ['evaluate', '--result', 'unused'],
    ['evaluate', '--result-package', 'one', '--result-package=two'],
    ['evaluate', '--result-package', '@secret'], ['@args'], ['evaluate', 'unused'],
    ['evaluate', '--result-package', 1], ['evaluate', '--result-package', '--help'],
    'evaluate', b'evaluate', 7, [None]])
def test_invalid_syntax_has_no_load_or_path_action(args, monkeypatch, capsys):
    cli = _cli()
    for name in ('_lexical', 'load_release_if_result_package', 'load_release_minute_package',
            'load_release_input_package', 'pair_release_model_inputs', 'evaluate_release_if_result'):
        monkeypatch.setattr(cli, name, _forbid)
    _error(_invoke(cli, capsys, args), 'INVALID_ARGUMENTS')


@pytest.mark.parametrize('args', [['-h'], ['--help']])
def test_standalone_help_has_no_load_or_path_action(args, monkeypatch, capsys):
    cli = _cli()
    for name in ('_lexical', 'load_release_if_result_package', 'load_release_minute_package',
            'load_release_input_package', 'pair_release_model_inputs', 'evaluate_release_if_result'):
        monkeypatch.setattr(cli, name, _forbid)
    status, out, err = _invoke(cli, capsys, args)
    assert status == 0 and err == ''
    assert out.startswith('usage: python -m traffic_anomaly.release_if_evaluation_cli evaluate')
    assert out.endswith('\n') and not out.endswith('\n\n')


def test_none_reads_host_argv_and_equals_options(tmp_path, monkeypatch, capsys):
    cli = _cli()
    case = _sealed()
    _chain(cli, monkeypatch, case)
    args = ['evaluate', '--result-package=' + str(tmp_path / '结果 空格'),
        '--prepared-package=' + str(tmp_path / 'prepared'), '--raw-package=' + str(tmp_path / 'raw')]
    monkeypatch.setattr(sys, 'argv', ['program', *args])
    status, out, err = _invoke(cli, capsys, None)
    assert status == 0 and err == ''
    assert json.loads(out)['policies']['P_U']['scored_test_minutes'] == 18


@pytest.mark.parametrize('index', [2, 4, 6])
@pytest.mark.parametrize('damage', ['relative', 'traversal', 'nul', 'surrogate', 'unc'])
def test_all_original_path_spellings_are_checked_before_load(tmp_path, monkeypatch, capsys, index, damage):
    cli = _cli()
    args = _args(tmp_path)
    args[index] = {'relative': 'relative', 'traversal': str(tmp_path / '..' / 'target'),
        'nul': str(tmp_path / 'target') + '\0', 'surrogate': str(tmp_path / 'target') + '\ud800',
        'unc': '//server/share/target'}[damage]
    for name in ('load_release_if_result_package', 'load_release_minute_package',
            'load_release_input_package', 'pair_release_model_inputs', 'evaluate_release_if_result'):
        monkeypatch.setattr(cli, name, _forbid)
    _error(_invoke(cli, capsys, args), 'INVALID_PACKAGE_PATH')


@pytest.mark.skipif(os.name != 'nt', reason='Windows local-drive spelling rules')
@pytest.mark.parametrize('bad', ['C:/temporary/NUL', 'C:/temporary/member:stream'])
def test_windows_reserved_or_ads_paths_rejected_before_load(tmp_path, monkeypatch, capsys, bad):
    cli = _cli()
    args = _args(tmp_path)
    args[6] = bad
    monkeypatch.setattr(cli, 'load_release_if_result_package', _forbid)
    _error(_invoke(cli, capsys, args), 'INVALID_PACKAGE_PATH')


@pytest.mark.parametrize('stage', ['result', 'raw', 'prepared', 'pair', 'evaluate'])
def test_operation_failure_stops_all_later_stages(tmp_path, monkeypatch, capsys, stage):
    cli = _cli()
    case = _sealed()
    events = []
    functions = [('result', 'load_release_if_result_package', case.package),
        ('raw', 'load_release_minute_package', case.raw),
        ('prepared', 'load_release_input_package', case.prepared),
        ('pair', 'pair_release_model_inputs', case.pair),
        ('evaluate', 'evaluate_release_if_result', b'not reached\n')]

    def action(name, value):
        def call(*args, **kwargs):
            events.append(name)
            if name == stage:
                raise ValueError('PRIVATE')
            return value
        return call

    for name, function, value in functions:
        monkeypatch.setattr(cli, function, action(name, value))
    _error(_invoke(cli, capsys, _args(tmp_path)), 'INTERNAL_ERROR')
    assert events == ['result', 'raw', 'prepared', 'pair', 'evaluate'][:
        ['result', 'raw', 'prepared', 'pair', 'evaluate'].index(stage) + 1]


_READ_CODES = ('INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE', 'RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE', 'INVALID_PACKAGE_PATH',
    'INPUT_UNAVAILABLE', 'PACKAGE_CHANGED')
_ALLOWED = [('_CLIError', code) for code in ('INVALID_ARGUMENTS', 'INVALID_PACKAGE_PATH',
    'INVALID_RESULT', 'RESOURCE_LIMIT', 'OUTPUT_ERROR')]
_ALLOWED += [('ReleaseIFEvaluationError', code) for code in ('INVALID_EVALUATION_ARGUMENTS',
    'RESOURCE_LIMIT', 'INPUT_BINDING_MISMATCH', 'INVALID_EVALUATION_INPUT', 'EVALUATION_ERROR')]
_ALLOWED += [('ReleaseMinutePackageError', code) for code in _READ_CODES]
_ALLOWED += [('ReleaseInputPreparationError', code) for code in (*_READ_CODES, 'INVALID_PREPARATION_CONFIG')]
_ALLOWED += [('ReleaseIFResultPackageError', code) for code in _READ_CODES]
_ALLOWED += [('ReleaseModelInputPairError', code) for code in ('INVALID_PAIR_ARGUMENTS',
    'INVALID_PAIR_STRUCTURE', 'INCOMPATIBLE_PAIR', 'RESOURCE_LIMIT',
    'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH')]


@pytest.mark.parametrize('kind,code', _ALLOWED)
def test_exact_exception_class_exposes_only_its_reachable_codes(tmp_path, monkeypatch, capsys, kind, code):
    cli = _cli()
    error = getattr(cli, kind)(code)

    def fail(path):
        raise error

    monkeypatch.setattr(cli, 'load_release_if_result_package', fail)
    _error(_invoke(cli, capsys, _args(tmp_path)), code)


@pytest.mark.parametrize('kind,code', [
    ('ReleaseMinutePackageError', 'OUTPUT_EXISTS'), ('ReleaseMinutePackageError', 'OUTPUT_ERROR'),
    ('ReleaseInputPreparationError', 'DERIVATION_MISMATCH'),
    ('ReleaseInputPreparationError', 'NONFINITE_FIT_STATE'),
    ('ReleaseInputPreparationError', 'NO_TRAINING_NORMAL_MINUTES'),
    ('ReleaseInputPreparationError', 'INVALID_PACKAGE_ARGUMENTS'),
    ('ReleaseIFResultPackageError', 'INPUT_BINDING_MISMATCH'),
    ('ReleaseIFResultPackageError', 'MODEL_ERROR'),
    ('ReleaseModelInputPairError', 'INPUT_UNAVAILABLE'),
    ('ReleaseIFEvaluationError', 'OUTPUT_ERROR'),
    ('_CLIError', 'INTERRUPTED'), ('_CLIError', 'INTERNAL_ERROR'), ('_CLIError', 'PACKAGE_CHANGED'),
    ('_CLIError', 7)])
def test_save_prepare_model_or_cross_domain_codes_are_not_exposed(tmp_path, monkeypatch, capsys, kind, code):
    cli = _cli()
    error = getattr(cli, kind)('PRIVATE')
    error.code = code

    def fail(path):
        raise error

    monkeypatch.setattr(cli, 'load_release_if_result_package', fail)
    _error(_invoke(cli, capsys, _args(tmp_path)), 'INTERNAL_ERROR')


@pytest.mark.parametrize('value', [None, bytearray(b'{}\n'), '{}\n', b'', 1])
def test_evaluator_return_must_be_nonempty_exact_bytes(tmp_path, monkeypatch, capsys, value):
    cli = _cli()
    _chain(cli, monkeypatch, _sealed())
    monkeypatch.setattr(cli, 'evaluate_release_if_result', lambda *args: value)
    _error(_invoke(cli, capsys, _args(tmp_path)), 'INVALID_RESULT')


def test_cli_consumes_original_bytes_without_second_json_decoder(tmp_path, monkeypatch, capsys):
    cli = _cli()
    _chain(cli, monkeypatch, _sealed())
    # The evaluator owns report semantics; this isolates the exact byte consumer.
    original = b'evaluator-byte-consumer-boundary\n'
    monkeypatch.setattr(cli, 'evaluate_release_if_result', lambda *args: original)
    actual = _invoke(cli, capsys, _args(tmp_path))
    assert actual == (0, original.decode('utf-8'), '')


def test_output_limit_includes_every_returned_byte(tmp_path, monkeypatch, capsys):
    cli = _cli()
    _chain(cli, monkeypatch, _sealed())
    monkeypatch.setattr(cli, 'evaluate_release_if_result', lambda *args: b'x' * 16384)
    status, out, err = _invoke(cli, capsys, _args(tmp_path))
    assert status == 0 and len(out) == 16384 and err == ''
    monkeypatch.setattr(cli, 'evaluate_release_if_result', lambda *args: b'x' * 16384 + b'\n')
    _error(_invoke(cli, capsys, _args(tmp_path)), 'RESOURCE_LIMIT')


class _BrokenOutput:
    def __init__(self, fault):
        self.buffer = self
        self.fault = fault
        self.data = bytearray()

    def write(self, payload):
        if self.fault == 'write':
            raise OSError('PRIVATE')
        if self.fault == 'short':
            self.data.extend(payload[:1])
            return 1
        self.data.extend(payload)
        return len(payload)

    def flush(self):
        if self.fault == 'flush':
            raise OSError('PRIVATE')


@pytest.mark.parametrize('fault', ['write', 'short', 'flush'])
def test_stdout_faults_return_safe_code_without_owning_host_stream(tmp_path, monkeypatch, capsys, fault):
    cli = _cli()
    _chain(cli, monkeypatch, _sealed())
    payload = b'bounded original bytes\n'
    monkeypatch.setattr(cli, 'evaluate_release_if_result', lambda *args: payload)
    broken = _BrokenOutput(fault)
    host = sys.stdout
    monkeypatch.setattr(sys, 'stdout', broken)
    assert cli.main(_args(tmp_path)) == 2
    assert sys.stdout is broken
    monkeypatch.setattr(sys, 'stdout', host)
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == '{"error":"OUTPUT_ERROR"}\n'
    assert bytes(broken.data) == {'write': b'', 'short': payload[:1], 'flush': payload}[fault]


def test_stdout_buffer_access_failure_is_output_error(tmp_path, monkeypatch, capsys):
    cli = _cli()
    _chain(cli, monkeypatch, _sealed())

    class MissingBuffer:
        @property
        def buffer(self):
            raise OSError('PRIVATE')

    broken = MissingBuffer()
    host = sys.stdout
    monkeypatch.setattr(sys, 'stdout', broken)
    assert cli.main(_args(tmp_path)) == 2
    assert sys.stdout is broken
    monkeypatch.setattr(sys, 'stdout', host)
    assert capsys.readouterr().err == '{"error":"OUTPUT_ERROR"}\n'


def test_unknown_code_property_is_not_read(tmp_path, monkeypatch, capsys):
    cli = _cli()
    reads = []

    class ForeignError(ValueError):
        @property
        def code(self):
            reads.append('read')
            raise KeyboardInterrupt

    def fail(path):
        raise ForeignError('PRIVATE')

    monkeypatch.setattr(cli, 'load_release_if_result_package', fail)
    _error(_invoke(cli, capsys, _args(tmp_path)), 'INTERNAL_ERROR')
    assert reads == []


@pytest.mark.parametrize('interrupted', [False, True])
def test_known_code_getter_failure_has_safe_terminal_exit(tmp_path, monkeypatch, capsys, interrupted):
    cli = _cli()
    error = cli._CLIError('OUTPUT_ERROR')

    def getter(self):
        if interrupted:
            raise KeyboardInterrupt
        raise ValueError('PRIVATE')

    monkeypatch.setattr(cli._CLIError, 'code', property(getter), raising=False)

    def fail(path):
        raise error

    monkeypatch.setattr(cli, 'load_release_if_result_package', fail)
    _error(_invoke(cli, capsys, _args(tmp_path)), 'INTERRUPTED' if interrupted else 'INTERNAL_ERROR')


def test_exception_subclass_with_allowed_code_is_not_exposed(tmp_path, monkeypatch, capsys):
    cli = _cli()

    class ChildError(cli.ReleaseIFEvaluationError):
        pass

    def fail(path):
        raise ChildError('INPUT_BINDING_MISMATCH')

    monkeypatch.setattr(cli, 'load_release_if_result_package', fail)
    _error(_invoke(cli, capsys, _args(tmp_path)), 'INTERNAL_ERROR')


def test_business_interrupt_and_failed_stderr_still_return_two(tmp_path, monkeypatch):
    cli = _cli()
    broken = _BrokenOutput('write')

    def interrupt(path):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, 'load_release_if_result_package', interrupt)
    monkeypatch.setattr(sys, 'stderr', broken)
    assert cli.main(_args(tmp_path)) == 2
    assert sys.stderr is broken


def test_actual_module_invalid_arguments_exit_two_without_traceback(tmp_path):
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src' / 'core')
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-m',
        'traffic_anomaly.release_if_evaluation_cli', 'evaluate', '--unknown'],
        cwd=tmp_path, env=environment, capture_output=True, timeout=10)
    assert result.returncode == 2 and result.stdout == b''
    assert result.stderr == b'{"error":"INVALID_ARGUMENTS"}\n'


def test_actual_module_closed_help_stdout_keeps_physical_exit_two(tmp_path):
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src' / 'core')
    process = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', '-m',
        'traffic_anomaly.release_if_evaluation_cli', '--help'], cwd=tmp_path,
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.stdout.close()
    process.stdout = None
    try:
        _, error = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)
        raise
    assert process.returncode == 2
    assert error == b'{"error":"OUTPUT_ERROR"}\n'
    assert list(tmp_path.iterdir()) == []
