"""Filesystem outcomes and strict boundaries of the artificial source command."""
from __future__ import annotations

from importlib import import_module
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def _cli():
    return import_module('traffic_anomaly.release_example_cli')


def _invoke(cli, capsys, args):
    status = cli.main(args)
    captured = capsys.readouterr()
    return status, captured.out, captured.err


def _assert_error(actual, code):
    assert actual == (2, '', '{"error":"' + code + '"}\n')


def _forbid(*args, **kwargs):
    raise AssertionError('unexpected action')


def test_create_calls_builder_once_and_persists_actual_members(tmp_path, monkeypatch, capsys):
    cli = import_module('traffic_anomaly.release_example_cli')
    original = cli.build_release_example
    calls = []

    def build_once(*, source_csv_path):
        calls.append(source_csv_path)
        return original(source_csv_path=source_csv_path)

    monkeypatch.setattr(cli, 'build_release_example', build_once)
    output = tmp_path / 'new artificial source'
    assert cli.main(['create', '--output', str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    receipt = json.loads(captured.out)
    assert receipt['status'] == 'CREATED'
    assert calls == [output / 'artificial.csv']
    assert sorted(p.name for p in output.iterdir()) == [
        'aggregate-spec.json', 'artificial.csv', 'recipe.json']
    for name in ('artificial.csv', 'aggregate-spec.json', 'recipe.json'):
        actual = (output / name).read_bytes()
        assert receipt['files'][name] == {
            'byte_count': len(actual), 'sha256': hashlib.sha256(actual).hexdigest()}
    csv_bytes = (output / 'artificial.csv').read_bytes()
    spec = json.loads((output / 'aggregate-spec.json').read_bytes())
    assert spec['sources'] == [{'path': str(output / 'artificial.csv'),
        'bytes': len(csv_bytes), 'sha256': hashlib.sha256(csv_bytes).hexdigest()}]


@pytest.mark.parametrize('args', [[], ['create'], ['inspect'], ['-h', 'create'],
    ['create', '--help'], ['create', '--output'], ['create', '--output='],
    ['create', '--out', 'unused'], ['create', '--output', 'one', '--output=two'],
    ['create', '--output', '@secret'], ['@args'], ['create', 'unused'],
    ['create', '--output', 1], ['create', '--output', '--help'],
    'create', b'create', 7, [None]])
def test_bad_arguments_have_no_actions(args, monkeypatch, capsys):
    cli = _cli()
    monkeypatch.setattr(cli, 'build_release_example', _forbid)
    monkeypatch.setattr(cli, '_lexical', _forbid)
    monkeypatch.setattr(Path, 'mkdir', _forbid)
    _assert_error(_invoke(cli, capsys, args), 'INVALID_ARGUMENTS')


@pytest.mark.parametrize('args', [['--help'], ['-h']])
def test_help_has_no_actions(args, monkeypatch, capsys):
    cli = _cli()
    monkeypatch.setattr(cli, 'build_release_example', _forbid)
    monkeypatch.setattr(cli, '_lexical', _forbid)
    monkeypatch.setattr(Path, 'mkdir', _forbid)
    status, out, err = _invoke(cli, capsys, args)
    assert status == 0 and err == ''
    assert out.startswith('usage: python -m traffic_anomaly.release_example_cli create --output')
    assert out.endswith('\n') and not out.endswith('\n\n')


def test_none_uses_host_argv_and_equals_form(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / '等号 空格'
    monkeypatch.setattr(sys, 'argv', ['ignored', 'create', '--output=' + str(output)])
    status, out, err = _invoke(cli, capsys, None)
    assert status == 0 and err == '' and json.loads(out)['status'] == 'CREATED'
    assert (output / 'artificial.csv').is_file()


@pytest.mark.parametrize('kind,code', [('directory', 'OUTPUT_EXISTS'),
    ('file', 'OUTPUT_EXISTS'), ('missing-parent', 'OUTPUT_ERROR'),
    ('file-parent', 'INVALID_PACKAGE_PATH'), ('relative', 'INVALID_PACKAGE_PATH'),
    ('parent-traversal', 'INVALID_PACKAGE_PATH'), ('nul', 'INVALID_PACKAGE_PATH'),
    ('surrogate', 'INVALID_PACKAGE_PATH'), ('unc', 'INVALID_PACKAGE_PATH')])
def test_destination_preflight_rejects_before_builder(tmp_path, monkeypatch, capsys, kind, code):
    cli = _cli()
    target = tmp_path / 'target'
    if kind == 'directory':
        target.mkdir()
        (target / 'winner.txt').write_bytes(b'winner')
    elif kind == 'file':
        target.write_bytes(b'winner')
    elif kind == 'missing-parent':
        target = tmp_path / 'absent' / 'target'
    elif kind == 'file-parent':
        (tmp_path / 'parent').write_bytes(b'winner')
        target = tmp_path / 'parent' / 'target'
    raw = {'relative': 'relative', 'parent-traversal': str(tmp_path / '..' / 'target'),
        'nul': str(target) + '\0', 'surrogate': str(target) + '\ud800',
        'unc': '//server/share/target'}.get(kind, str(target))
    monkeypatch.setattr(cli, 'build_release_example', _forbid)
    _assert_error(_invoke(cli, capsys, ['create', '--output', raw]), code)
    if kind == 'directory':
        assert (target / 'winner.txt').read_bytes() == b'winner'
    if kind == 'file':
        assert target.read_bytes() == b'winner'


def test_preflight_permission_failure_is_output_error(tmp_path, monkeypatch, capsys):
    cli = _cli()
    real_lstat = Path.lstat

    def denied(path, *args, **kwargs):
        if path == tmp_path:
            raise PermissionError('PRIVATE')
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'lstat', denied)
    monkeypatch.setattr(cli, 'build_release_example', _forbid)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(tmp_path / 'new')]), 'OUTPUT_ERROR')


def test_preflight_race_preserves_winner(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / 'race'
    original = cli.build_release_example

    def win_before_mkdir(*, source_csv_path):
        built = original(source_csv_path=source_csv_path)
        output.mkdir()
        (output / 'winner.txt').write_bytes(b'preserve')
        return built

    monkeypatch.setattr(cli, 'build_release_example', win_before_mkdir)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'OUTPUT_EXISTS')
    assert [(p.name, p.read_bytes()) for p in output.iterdir()] == [('winner.txt', b'preserve')]


@pytest.mark.parametrize('damage', ['type', 'profile', 'list', 'duplicate', 'order', 'bytes'])
def test_invalid_builder_result_precedes_creation(tmp_path, monkeypatch, capsys, damage):
    cli = _cli()
    output = tmp_path / damage
    built = cli.build_release_example(source_csv_path=output / 'artificial.csv')
    changes = {
        'type': object(), 'profile': replace(built, profile_id='other'),
        'list': replace(built, members=list(built.members)),
        'duplicate': replace(built, members=(built.members[0],) * 3),
        'order': replace(built, members=tuple(reversed(built.members))),
        'bytes': replace(built, members=((built.members[0][0], bytearray(b'a')), *built.members[1:])),
    }
    monkeypatch.setattr(cli, 'build_release_example', lambda **kwargs: changes[damage])
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'INVALID_RESULT')
    assert not output.exists()


def test_member_and_total_caps_precede_creation(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / 'capped'
    monkeypatch.setattr(cli, 'EXAMPLE_TOTAL_BYTE_LIMIT', 1)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'RESOURCE_LIMIT')
    assert not output.exists()


@pytest.mark.parametrize('missing', ['both', 'profile_id', 'members'])
def test_missing_builder_slots_are_invalid_result(tmp_path, monkeypatch, capsys, missing):
    cli = _cli()
    output = tmp_path / 'missing-slots'
    if missing == 'both':
        built = object.__new__(cli.ReleaseExample)
    else:
        built = cli.build_release_example(source_csv_path=output / 'artificial.csv')
        object.__delattr__(built, missing)
    monkeypatch.setattr(cli, 'build_release_example', lambda **kwargs: built)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'INVALID_RESULT')
    assert not output.exists()


class _FileProxy:
    def __init__(self, stream, *, short=False, flush_error=False, wrong_read=False):
        self.stream = stream
        self.short = short
        self.flush_error = flush_error
        self.wrong_read = wrong_read

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def write(self, payload):
        if self.short:
            self.stream.write(payload[:1])
            return 1
        return self.stream.write(payload)

    def flush(self):
        if self.flush_error:
            raise OSError('PRIVATE')
        return self.stream.flush()

    def read(self, size):
        actual = self.stream.read(size)
        return bytes([actual[0] ^ 1]) + actual[1:] if self.wrong_read else actual


@pytest.mark.parametrize('fault', ['short', 'flush_error', 'wrong_read'])
def test_member_io_failures_retain_actual_residue(tmp_path, monkeypatch, capsys, fault):
    cli = _cli()
    output = tmp_path / fault
    real_open = Path.open

    def faulty(path, mode='r', *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        if path == output / 'artificial.csv' and mode == ('rb' if fault == 'wrong_read' else 'xb'):
            return _FileProxy(stream, **{fault: True})
        return stream

    monkeypatch.setattr(Path, 'open', faulty)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'OUTPUT_ERROR')
    assert output.is_dir()
    assert (output / 'artificial.csv').stat().st_size > 0
    assert not (output / 'recipe.json').exists()


def test_extra_member_detected_and_retained(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / 'extra'
    real_open = Path.open

    def injected(path, mode='r', *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        if path == output / 'artificial.csv' and mode == 'xb':
            (output / 'extra.txt').write_bytes(b'preserve')
        return stream

    monkeypatch.setattr(Path, 'open', injected)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'PACKAGE_CHANGED')
    assert (output / 'extra.txt').read_bytes() == b'preserve'


class _BrokenOutput:
    def __init__(self, *, flush_only=False):
        self.buffer = self
        self.saved = bytearray()
        self.flush_only = flush_only

    def write(self, payload):
        if not self.flush_only:
            raise OSError('PRIVATE')
        self.saved.extend(payload)
        return len(payload)

    def flush(self):
        raise OSError('PRIVATE')


@pytest.mark.parametrize('flush_only', [False, True])
def test_stdout_failure_retains_complete_files_and_host_stream(tmp_path, monkeypatch, capsys, flush_only):
    cli = _cli()
    output = tmp_path / 'stdout-failed'
    broken = _BrokenOutput(flush_only=flush_only)
    host = sys.stdout
    monkeypatch.setattr(sys, 'stdout', broken)
    assert cli.main(['create', '--output', str(output)]) == 2
    assert sys.stdout is broken
    monkeypatch.setattr(sys, 'stdout', host)
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == '{"error":"OUTPUT_ERROR"}\n'
    assert sorted(p.name for p in output.iterdir()) == ['aggregate-spec.json', 'artificial.csv', 'recipe.json']
    csv_bytes = (output / 'artificial.csv').read_bytes()
    assert json.loads((output / 'recipe.json').read_bytes())['source']['sha256'] == hashlib.sha256(csv_bytes).hexdigest()
    if flush_only:
        assert json.loads(broken.saved)['status'] == 'CREATED'


@pytest.mark.parametrize('kind,code,expected', [
    ('cli', 'INVALID_ARGUMENTS', 'INVALID_ARGUMENTS'),
    ('cli', 'INVALID_PACKAGE_PATH', 'INVALID_PACKAGE_PATH'),
    ('cli', 'OUTPUT_EXISTS', 'OUTPUT_EXISTS'), ('cli', 'OUTPUT_ERROR', 'OUTPUT_ERROR'),
    ('cli', 'INVALID_RESULT', 'INVALID_RESULT'), ('cli', 'RESOURCE_LIMIT', 'RESOURCE_LIMIT'),
    ('cli', 'PACKAGE_CHANGED', 'PACKAGE_CHANGED'), ('cli', 'INTERRUPTED', 'INTERNAL_ERROR'),
    ('cli', 'EXAMPLE_ERROR', 'INTERNAL_ERROR'),
    ('builder', 'INVALID_EXAMPLE_ARGUMENTS', 'INVALID_EXAMPLE_ARGUMENTS'),
    ('builder', 'RESOURCE_LIMIT', 'RESOURCE_LIMIT'), ('builder', 'EXAMPLE_ERROR', 'EXAMPLE_ERROR'),
    ('builder', 'OUTPUT_EXISTS', 'INTERNAL_ERROR'),
    ('helper', 'INVALID_PACKAGE_PATH', 'INVALID_PACKAGE_PATH'),
    ('helper', 'PACKAGE_CHANGED', 'PACKAGE_CHANGED'),
    ('helper', 'RESOURCE_LIMIT', 'INTERNAL_ERROR'),
    ('helper', 'INVALID_PACKAGE_ARGUMENTS', 'INTERNAL_ERROR'),
    ('other', 'OUTPUT_EXISTS', 'INTERNAL_ERROR'), ('cli', 7, 'INTERNAL_ERROR'),
    ('subclass', 'OUTPUT_ERROR', 'INTERNAL_ERROR')])
def test_only_exact_exception_class_and_its_codes_are_exposed(tmp_path, monkeypatch, capsys, kind, code, expected):
    cli = _cli()
    kinds = {'cli': cli._CLIError, 'builder': cli.ReleaseExampleError,
        'helper': cli.ReleaseInputPreparationError, 'other': ValueError,
        'subclass': type('PrivateSubclass', (cli._CLIError,), {})}
    error = kinds[kind]('PRIVATE')
    error.code = code

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(cli, 'build_release_example', fail)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(tmp_path / 'new')]), expected)


def test_interrupt_and_failed_stderr_return_two_without_replacing_stream(tmp_path, monkeypatch):
    cli = _cli()
    broken = _BrokenOutput()

    def interrupt(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, 'build_release_example', interrupt)
    monkeypatch.setattr(sys, 'stderr', broken)
    assert cli.main(['create', '--output', str(tmp_path / 'new')]) == 2
    assert sys.stderr is broken and not (tmp_path / 'new').exists()


def test_receipt_bound_counts_final_lf_and_retains_files(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / 'tiny-receipt'
    monkeypatch.setattr(cli, '_OUTPUT_LIMIT', 1)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'RESOURCE_LIMIT')
    assert len(list(output.iterdir())) == 3


def test_member_creation_race_does_not_overwrite_winner(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / 'member-race'
    real_open = Path.open
    competed = False

    def compete(path, mode='r', *args, **kwargs):
        nonlocal competed
        if path == output / 'artificial.csv' and mode == 'xb' and not competed:
            competed = True
            with real_open(path, 'xb') as stream:
                stream.write(b'winner')
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', compete)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'PACKAGE_CHANGED')
    assert (output / 'artificial.csv').read_bytes() == b'winner'
    assert len(list(output.iterdir())) == 1


def test_changed_directory_identity_is_detected_without_cleanup(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / 'changed'
    real_directory = cli._directory
    real_open = Path.open
    changed = False

    def after_open(path, mode='r', *args, **kwargs):
        nonlocal changed
        stream = real_open(path, mode, *args, **kwargs)
        if path == output / 'artificial.csv' and mode == 'xb':
            changed = True
        return stream

    def directory(path, expected=None):
        actual = real_directory(path, expected)
        if changed and expected is not None:
            raise cli.ReleaseInputPreparationError('PACKAGE_CHANGED')
        return actual

    monkeypatch.setattr(Path, 'open', after_open)
    monkeypatch.setattr(cli, '_directory', directory)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'PACKAGE_CHANGED')
    assert output.is_dir() and (output / 'artificial.csv').exists()


def test_file_handle_failure_is_an_output_error(tmp_path, monkeypatch, capsys):
    cli = _cli()
    output = tmp_path / 'handle-failure'
    real_open = Path.open

    class FailedHandle(_FileProxy):
        def fileno(self):
            raise OSError('PRIVATE')

    def broken_handle(path, mode='r', *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        return FailedHandle(stream) if path == output / 'artificial.csv' and mode == 'xb' else stream

    monkeypatch.setattr(Path, 'open', broken_handle)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(output)]), 'OUTPUT_ERROR')
    assert (output / 'artificial.csv').exists()


def test_foreign_helper_code_is_not_washed_by_io_mapping(tmp_path, monkeypatch, capsys):
    cli = _cli()

    def bad_signature(*args, **kwargs):
        error = cli.ReleaseInputPreparationError('RESOURCE_LIMIT')
        raise error

    monkeypatch.setattr(cli, '_signature', bad_signature)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(tmp_path / 'new')]), 'INTERNAL_ERROR')
    assert not (tmp_path / 'new').exists()


def test_broken_code_property_is_not_exposed(tmp_path, monkeypatch, capsys):
    cli = _cli()
    error = cli._CLIError('OUTPUT_ERROR')

    def broken_code(self):
        raise ValueError('PRIVATE')

    monkeypatch.setattr(cli._CLIError, 'code', property(broken_code), raising=False)

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(cli, 'build_release_example', fail)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(tmp_path / 'new')]), 'INTERNAL_ERROR')


def test_unknown_error_code_getter_is_never_read(tmp_path, monkeypatch, capsys):
    cli = _cli()
    reads = []

    class UnknownError(ValueError):
        @property
        def code(self):
            reads.append('read')
            raise KeyboardInterrupt

    def fail(**kwargs):
        raise UnknownError('PRIVATE')

    monkeypatch.setattr(cli, 'build_release_example', fail)
    try:
        result = cli.main(['create', '--output', str(tmp_path / 'unknown-error')])
    except KeyboardInterrupt:
        result = 'ESCAPED_KEYBOARD_INTERRUPT'
    captured = capsys.readouterr()
    assert result == 2
    assert reads == []
    assert captured.out == '' and captured.err == '{"error":"INTERNAL_ERROR"}\n'
    assert not (tmp_path / 'unknown-error').exists()


def test_known_error_getter_interrupt_reaches_safe_terminal_exit(tmp_path, monkeypatch, capsys):
    cli = _cli()
    error = cli._CLIError('OUTPUT_ERROR')
    reads = []

    def interrupted_code(self):
        reads.append('read')
        raise KeyboardInterrupt

    monkeypatch.setattr(cli._CLIError, 'code', property(interrupted_code), raising=False)

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(cli, 'build_release_example', fail)
    try:
        result = cli.main(['create', '--output', str(tmp_path / 'known-error')])
    except KeyboardInterrupt:
        result = 'ESCAPED_KEYBOARD_INTERRUPT'
    captured = capsys.readouterr()
    assert result == 2
    assert reads == ['read']
    assert captured.out == '' and captured.err == '{"error":"INTERRUPTED"}\n'
    assert not (tmp_path / 'known-error').exists()


def test_receipt_exact_limit_includes_terminating_lf(tmp_path, monkeypatch, capsys):
    cli = _cli()
    first = _invoke(cli, capsys, ['create', '--output', str(tmp_path / 'one')])
    assert first[0] == 0
    limit = len(first[1].encode('utf-8'))
    monkeypatch.setattr(cli, '_OUTPUT_LIMIT', limit - 1)
    _assert_error(_invoke(cli, capsys, ['create', '--output', str(tmp_path / 'two')]), 'RESOURCE_LIMIT')
    monkeypatch.setattr(cli, '_OUTPUT_LIMIT', limit)
    assert _invoke(cli, capsys, ['create', '--output', str(tmp_path / 'six')])[0] == 0


def test_actual_module_bad_arguments_exit_two_without_traceback(tmp_path):
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src' / 'core')
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-m',
        'traffic_anomaly.release_example_cli', 'create', '--unknown'],
        cwd=tmp_path, env=environment, capture_output=True, timeout=10)
    assert result.returncode == 2
    assert result.stdout == b''
    assert result.stderr == b'{"error":"INVALID_ARGUMENTS"}\n'


def test_actual_module_closed_stdout_exits_two_and_keeps_generated_files(tmp_path):
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src' / 'core')
    output = tmp_path / 'closed-stdout'
    process = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', '-m',
        'traffic_anomaly.release_example_cli', 'create', '--output', str(output)],
        cwd=tmp_path, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    assert sorted(p.name for p in output.iterdir()) == ['aggregate-spec.json', 'artificial.csv', 'recipe.json']
    actual = (output / 'artificial.csv').read_bytes()
    assert json.loads((output / 'recipe.json').read_bytes())['source']['sha256'] == hashlib.sha256(actual).hexdigest()
