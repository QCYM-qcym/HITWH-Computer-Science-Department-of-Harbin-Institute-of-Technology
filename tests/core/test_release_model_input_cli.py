"""CLI orchestration only: loaders, pairing and summary are independent stubs."""
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest


class BinaryOutput:
    def __init__(self, events=None, name='output'):
        self.data = bytearray()
        self.events = events if events is not None else []
        self.name = name
        self.closed = False

    def write(self, payload):
        self.events.append((self.name, 'write'))
        self.data.extend(payload)
        return len(payload)

    def flush(self):
        self.events.append((self.name, 'flush'))

    def close(self):
        self.closed = True


@pytest.fixture
def command(monkeypatch):
    m = importlib.import_module('traffic_anomaly.release_model_input_cli')
    events = []
    raw, saved, paired = object(), object(), object()
    result = {'status': 'INPUTS_PAIRED', 'version': 1}
    out, err = BinaryOutput(events, 'stdout'), BinaryOutput(events, 'stderr')
    monkeypatch.setattr(m, 'sys', SimpleNamespace(
        stdout=SimpleNamespace(buffer=out), stderr=SimpleNamespace(buffer=err), argv=['prog']))

    def raw_load(path):
        events.append(('raw', path))
        return raw

    def prepared_load(path):
        events.append(('prepared', path))
        return saved

    def pair(actual_raw, actual_saved):
        assert actual_raw is raw and actual_saved is saved
        events.append(('pair',))
        return paired

    def summary(actual_pair):
        assert actual_pair is paired
        events.append(('summary',))
        return result

    monkeypatch.setattr(m, 'load_release_minute_package', raw_load)
    monkeypatch.setattr(m, 'load_release_input_package', prepared_load)
    monkeypatch.setattr(m, 'pair_release_model_inputs', pair)
    monkeypatch.setattr(m, 'summarize_release_model_inputs', summary)
    return SimpleNamespace(m=m, events=events, result=result, out=out, err=err)


ARGS = ['--raw-package', 'raw/run=@daily', '--prepared-package=saved/未打开']


def test_cli_order(command):
    c = command
    assert c.m.main(ARGS) == 0
    assert c.events == [
        ('raw', Path('raw/run=@daily')), ('prepared', Path('saved/未打开')),
        ('pair',), ('summary',), ('stdout', 'write'), ('stdout', 'flush'),
    ]
    assert bytes(c.out.data) == b'{"status":"INPUTS_PAIRED","version":1}\n'
    assert not c.err.data


BAD_ARGUMENTS = [
    [], ['--raw-package'], ['--raw-package', 'raw'],
    ['--raw-pack', 'raw', '--prepared-package', 'saved'],
    ARGS + ['--unknown', 'private'], ARGS + ['positional-private'],
    ARGS + ['--raw-package', 'again'], ARGS + ['--raw-package=again'],
    ['--raw-package=raw', '--raw-package=again', '--prepared-package=saved'],
    ['--raw-package', '@private', '--prepared-package=saved'],
    ['--raw-package=@private', '--prepared-package=saved'],
    ARGS + ['@private'], ARGS + ['--help'], ARGS + ['-h'],
    ['--help', '--help'], ['-h', '--help'], ['--help=private'],
    ['--raw-package', '--prepared-package', 'saved'],
    ['--raw-package=', '--prepared-package=saved'],
    ['--raw-package', 'raw', '--prepared-package', 2],
    '--raw-package=raw --prepared-package=saved', b'private', 2,
    [str.__new__(type('Text', (str,), {}), '--help')],
]


@pytest.mark.parametrize('argv', BAD_ARGUMENTS, ids=lambda value: type(value).__name__)
def test_cli_arguments_reject_without_loading(command, argv):
    c = command
    try:
        status = c.m.main(argv)
    except BaseException:
        pytest.fail('main must return a safe argument error')
    assert status == 2
    assert bytes(c.err.data) == b'{"error":"INVALID_ARGUMENTS"}\n'
    assert not c.out.data
    assert c.events == [('stderr', 'write'), ('stderr', 'flush')]


@pytest.mark.parametrize('argv', [
    ['--raw-package=raw', '--prepared-package', 'saved'],
    ['--prepared-package=saved', '--raw-package', 'raw'],
    ('--raw-package=raw', '--prepared-package=saved'),
])
def test_cli_arguments_valid_forms(command, argv):
    assert command.m.main(argv) == 0
    assert command.events[:2] == [('raw', Path('raw')), ('prepared', Path('saved'))]


@pytest.mark.parametrize('option', ['-h', '--help'])
def test_cli_help_is_static_and_load_free(command, option):
    c = command
    assert c.m.main([option]) == 0
    assert bytes(c.out.data) == (
        b'usage: python -m traffic_anomaly.release_model_input_cli '
        b'--raw-package ABS_DIR --prepared-package ABS_DIR\n'
        b'\nRead-only pairing of saved release inputs; model execution is not granted.\n'
        b'  -h, --help   show this fixed usage\n')
    assert c.events == [('stdout', 'write'), ('stdout', 'flush')]
    assert not c.err.data


def test_cli_argv_none_uses_host_arguments(command):
    command.m.sys.argv = ['prog', *ARGS]
    assert command.m.main() == 0


def _safe_call(c, argv=ARGS):
    try:
        return c.m.main(argv)
    except BaseException:
        pytest.fail('main leaked an exception instead of a safe exit code')


def test_cli_utf8_compact_sorted_single_lf(command):
    c = command
    c.result.update(z='中文\n', a=0)
    assert c.m.main(ARGS) == 0
    assert bytes(c.out.data) == '{"a":0,"status":"INPUTS_PAIRED","version":1,"z":"中文\\n"}\n'.encode('utf-8')
    assert bytes(c.out.data).count(b'\n') == 1


@pytest.mark.parametrize('size,expected', [(65536, 0), (65537, 2)])
def test_cli_total_byte_cap_includes_lf(command, size, expected):
    c = command
    overhead = len(b'{"status":"INPUTS_PAIRED","text":""}\n')
    c.result.clear()
    c.result.update(status='INPUTS_PAIRED', text='x' * (size - overhead))
    assert _safe_call(c) == expected
    if expected == 0:
        assert len(c.out.data) == 65536
    else:
        assert not c.out.data
        assert bytes(c.err.data) == b'{"error":"RESOURCE_LIMIT"}\n'


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), object(), '\ud800'])
def test_cli_encoding_failure_has_no_stdout(command, bad):
    c = command
    c.result['bad'] = bad
    assert _safe_call(c) == 2
    assert not c.out.data
    assert bytes(c.err.data) == b'{"error":"INVALID_RESULT"}\n'


@pytest.mark.parametrize('bad', [[], None, {'status': 'WRONG'}, {'version': 1}])
def test_cli_invalid_summary_cannot_exit_success(command, monkeypatch, bad):
    c = command
    monkeypatch.setattr(c.m, 'summarize_release_model_inputs', lambda pair: bad)
    assert _safe_call(c) == 2
    assert not c.out.data
    assert bytes(c.err.data) == b'{"error":"INVALID_RESULT"}\n'


PAIR_CODES = [
    'INVALID_PAIR_ARGUMENTS', 'INVALID_PAIR_STRUCTURE', 'INCOMPATIBLE_PAIR',
    'RESOURCE_LIMIT', 'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH',
]
LOAD_CODES = [
    'INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE',
    'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE',
    'INVALID_PACKAGE_PATH', 'INPUT_UNAVAILABLE', 'PACKAGE_CHANGED', 'INVALID_PREPARATION_CONFIG',
]


@pytest.mark.parametrize('code', PAIR_CODES + LOAD_CODES)
def test_cli_known_error_codes_are_safe(command, monkeypatch, code):
    from traffic_anomaly.release_inputs import ReleaseInputPreparationError
    from traffic_anomaly.release_model_inputs import ReleaseModelInputPairError
    c = command
    error_type = ReleaseModelInputPairError if code in PAIR_CODES else ReleaseInputPreparationError
    error = error_type(code)
    def fail(path):
        raise error
    monkeypatch.setattr(c.m, 'load_release_minute_package', fail)
    assert _safe_call(c) == 2
    assert not c.out.data
    assert bytes(c.err.data) == ('{"error":"' + code + '"}\n').encode('utf-8')


@pytest.mark.parametrize('code', ['PRIVATE\nLEAK', None, [], True,
    type('Text', (str,), {})('INVALID_PACKAGE'), 'OUTPUT_EXISTS', 'DERIVATION_MISMATCH'])
def test_cli_mutated_error_code_becomes_internal(command, monkeypatch, code):
    from traffic_anomaly.release_inputs import ReleaseInputPreparationError
    c = command
    error = ReleaseInputPreparationError('INVALID_PACKAGE')
    error.code = code
    def fail(path):
        raise error
    monkeypatch.setattr(c.m, 'load_release_input_package', fail)
    assert _safe_call(c) == 2
    assert bytes(c.err.data) == b'{"error":"INTERNAL_ERROR"}\n'
    assert not c.out.data
    assert c.events[0] == ('raw', Path('raw/run=@daily'))


@pytest.mark.parametrize('stage', [
    'load_release_minute_package', 'load_release_input_package',
    'pair_release_model_inputs', 'summarize_release_model_inputs',
])
@pytest.mark.parametrize('error,code', [(RuntimeError('private exception'), 'INTERNAL_ERROR'),
    (KeyboardInterrupt('private interrupt'), 'INTERRUPTED')])
def test_cli_stage_failure_stops_without_retry(command, monkeypatch, stage, error, code):
    c = command
    calls = []
    def fail(*args):
        calls.append(1)
        raise error
    monkeypatch.setattr(c.m, stage, fail)
    assert _safe_call(c) == 2
    assert calls == [1]
    assert not c.out.data
    assert bytes(c.err.data) == ('{"error":"' + code + '"}\n').encode('utf-8')


@pytest.mark.parametrize('return_value', [0, 1, -1, True, None, 1.0,
    type('Count', (int,), {})(38)])
def test_cli_bad_write_count_is_output_error(command, monkeypatch, return_value):
    c = command
    calls = []
    def write(payload):
        calls.append(payload)
        c.out.data.extend(payload[:1])
        return return_value
    monkeypatch.setattr(c.out, 'write', write)
    assert _safe_call(c) == 2
    assert len(calls) == 1 and bytes(c.out.data) == b'{'
    assert bytes(c.err.data) == b'{"error":"OUTPUT_ERROR"}\n'
    assert ('stdout', 'flush') not in c.events


@pytest.mark.parametrize('stage', ['write', 'flush'])
@pytest.mark.parametrize('error,code', [
    (BrokenPipeError('private pipe'), 'OUTPUT_ERROR'),
    (RuntimeError('private output'), 'OUTPUT_ERROR'),
    (KeyboardInterrupt('private stop'), 'INTERRUPTED'),
])
@pytest.mark.parametrize('argv', [ARGS, ['--help']])
def test_cli_output_failure_returns_two_without_retry(command, monkeypatch, stage, error, code, argv):
    c = command
    calls = []
    def fail(*args):
        calls.append(1)
        raise error
    monkeypatch.setattr(c.out, stage, fail)
    assert _safe_call(c, argv) == 2
    assert calls == [1]
    assert bytes(c.err.data) == ('{"error":"' + code + '"}\n').encode('utf-8')


@pytest.mark.parametrize('stage', ['write', 'flush'])
@pytest.mark.parametrize('error', [RuntimeError('private stderr'), KeyboardInterrupt('private stop')])
def test_cli_stderr_failure_still_returns_two(command, monkeypatch, stage, error):
    c = command
    calls = []
    def fail(*args):
        calls.append(1)
        raise error
    monkeypatch.setattr(c.err, stage, fail)
    assert _safe_call(c, []) == 2
    assert calls == [1]


def test_cli_main_never_redirects_or_closes_host_streams(command, monkeypatch):
    c = command
    def forbidden(*args):
        pytest.fail('callable main must not own host descriptors')
    monkeypatch.setattr(c.m, 'os', SimpleNamespace(open=forbidden, dup2=forbidden, close=forbidden))
    streams = (c.m.sys.stdout, c.m.sys.stderr)
    assert c.m.main([]) == 2
    assert streams == (c.m.sys.stdout, c.m.sys.stderr)
    assert not c.out.closed and not c.err.closed


def test_cli_entrypoint_failure_seals_both_descriptors(command, monkeypatch):
    c = command
    operations = []
    c.m.sys.stdout.fileno = lambda: 1
    c.m.sys.stderr.fileno = lambda: 2
    monkeypatch.setattr(c.m, 'main', lambda: 2)
    monkeypatch.setattr(c.m, 'os', SimpleNamespace(
        devnull='null', O_WRONLY=1,
        open=lambda name, flags: operations.append(('open', name, flags)) or 19,
        dup2=lambda source, target: operations.append(('dup2', source, target)),
        close=lambda fd: operations.append(('close', fd)),
    ))
    assert c.m._cli_entrypoint() == 2
    assert operations == [
        ('open', 'null', 1), ('dup2', 19, 1), ('close', 19),
        ('open', 'null', 1), ('dup2', 19, 2), ('close', 19),
    ]
    assert not c.out.closed and not c.err.closed


def test_cli_entrypoint_success_does_not_touch_streams(command, monkeypatch):
    c = command
    def forbidden(*args):
        pytest.fail('successful entrypoint must leave streams alone')
    monkeypatch.setattr(c.m, 'main', lambda: 0)
    monkeypatch.setattr(c.m, 'os', SimpleNamespace(open=forbidden, dup2=forbidden, close=forbidden))
    assert c.m._cli_entrypoint() == 0


def test_cli_entrypoint_sealing_failure_is_silent_and_attempts_other_stream(command, monkeypatch):
    c = command
    calls = []
    c.m.sys.stdout.fileno = lambda: 1
    c.m.sys.stderr.fileno = lambda: 2
    monkeypatch.setattr(c.m, 'main', lambda: 2)
    def fail_open(name, flags):
        calls.append(1)
        raise RuntimeError('private descriptor failure')
    monkeypatch.setattr(c.m, 'os', SimpleNamespace(devnull='null', O_WRONLY=1, open=fail_open))
    assert c.m._cli_entrypoint() == 2
    assert calls == [1, 1]
    assert not c.out.data and not c.err.data
