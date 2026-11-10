"""Result CLI orchestration and stream tests; no estimator is executed."""
from dataclasses import asdict, replace
import builtins
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.core.release_if_result_cases import hand_result, reference_members
from traffic_anomaly.release_if_result_contract import decode_release_if_result_package


def api():
    try:
        module = importlib.import_module('traffic_anomaly.release_if_result_cli')
    except ModuleNotFoundError as error:
        if error.name != 'traffic_anomaly.release_if_result_cli':
            raise
        pytest.fail('public saved-result CLI module is missing')
    assert callable(getattr(module, 'main', None)), 'public main is missing'
    return module


class BinaryOutput:
    def __init__(self, events, name):
        self.data = bytearray()
        self.events, self.name = events, name
        self.closed = False

    def write(self, payload):
        self.events.append((self.name, 'write'))
        self.data.extend(payload)
        return len(payload)

    def flush(self):
        self.events.append((self.name, 'flush'))

    def close(self):
        self.closed = True


def build_command(tmp_path, monkeypatch, view='current13'):
    module = api()
    raw_dir, prepared_dir, result_dir = (tmp_path / name for name in ('raw', 'prepared', 'result'))
    for directory in (raw_dir, prepared_dir, result_dir):
        directory.mkdir()
        (directory / 'unchanged').write_bytes(b'kept')
    output = tmp_path / 'new-result'
    events = []
    raw, prepared, pair = object(), object(), object()
    result = hand_result(view=view)
    package = decode_release_if_result_package(reference_members(view=view))
    out, err = BinaryOutput(events, 'stdout'), BinaryOutput(events, 'stderr')
    monkeypatch.setattr(module, 'sys', SimpleNamespace(argv=['program'],
        stdout=SimpleNamespace(buffer=out), stderr=SimpleNamespace(buffer=err)))

    def raw_load(path):
        assert path == raw_dir
        events.append(('raw', path))
        return raw
    def prepared_load(path):
        assert path == prepared_dir
        events.append(('prepared', path))
        return prepared
    def pair_inputs(actual_raw, actual_prepared):
        assert actual_raw is raw and actual_prepared is prepared
        events.append(('pair',))
        return pair
    def fit(actual_pair, *, view):
        assert actual_pair is pair
        events.append(('fit', view))
        return result
    def make(actual_pair, actual_result):
        assert actual_pair is pair and actual_result is result
        events.append(('make',))
        return package
    def save(actual_package, path):
        assert actual_package is package and path == output
        events.append(('save', path))
        return package.identity
    def load(path):
        assert path == result_dir
        events.append(('result', path))
        return package
    def verify(actual_package, actual_pair):
        assert actual_package is package and actual_pair is pair
        events.append(('verify',))
    for name, function in (
        ('load_release_minute_package', raw_load), ('load_release_input_package', prepared_load),
        ('pair_release_model_inputs', pair_inputs), ('fit_release_iforest', fit),
        ('make_release_if_result_package', make), ('save_release_if_result_package', save),
        ('load_release_if_result_package', load), ('verify_release_if_result_pair', verify)):
        monkeypatch.setattr(module, name, function)
    return SimpleNamespace(m=module, events=events, out=out, err=err, package=package,
        raw=raw_dir, prepared=prepared_dir, result_dir=result_dir, output=output,
        argv=['run', '--raw-package', str(raw_dir), '--prepared-package', str(prepared_dir),
              '--view', view, '--output', str(output)])


@pytest.fixture
def command(tmp_path, monkeypatch):
    return build_command(tmp_path, monkeypatch)


def expected_receipt(c, name):
    return dict(version=1, command=name, status={'run': 'SAVED',
        'inspect': 'INTERNAL_CONSISTENCY_CHECKED', 'verify': 'INPUT_BINDING_MATCHED'}[name],
        result_identity=asdict(c.package.identity), view='current13', threshold=2.9699999999999998,
        configuration_sha256=c.package.context.configuration_sha256,
        input_references=dict(raw=asdict(c.package.context.raw_identity),
                              prepared=asdict(c.package.context.prepared_identity)),
        counts=dict(total=176, scored=55, training=17, calibration=4, preprocessing_fit=18),
        checks=dict(internal_consistency='MATCHED', saved_score_q99='MATCHED',
            input_pair_binding='NOT_PERFORMED' if name == 'inspect' else 'MATCHED',
            source_authentication='NOT_AUTHENTICATED', model_execution='NOT_AUTHENTICATED'),
        operations=dict(model_fit_score='PERFORMED' if name == 'run' else 'NOT_PERFORMED'))


def test_run_calls_each_operation_once_then_projects_actual_saved_identity(tmp_path, monkeypatch):
    c = build_command(tmp_path, monkeypatch)
    assert c.m.main(c.argv) == 0
    assert c.events == [('raw', c.raw), ('prepared', c.prepared), ('pair',),
        ('fit', 'current13'), ('make',), ('save', c.output), ('stdout', 'write'), ('stdout', 'flush')]
    expected = expected_receipt(c, 'run')
    assert json.loads(c.out.data) == expected
    assert bytes(c.out.data) == (json.dumps(expected, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    assert not c.err.data


@pytest.mark.parametrize('name', ['inspect', 'verify'])
def test_readonly_commands_use_saved_package_and_never_fit(command, name):
    c = command
    argv = [name, '--result-package', str(c.result_dir)]
    events = [('result', c.result_dir)]
    if name == 'verify':
        argv += ['--raw-package', str(c.raw), '--prepared-package', str(c.prepared)]
        events += [('raw', c.raw), ('prepared', c.prepared), ('pair',), ('verify',)]
    assert c.m.main(argv) == 0
    assert c.events == events + [('stdout', 'write'), ('stdout', 'flush')]
    assert json.loads(c.out.data) == expected_receipt(c, name)
    assert not c.err.data


BAD_ARGUMENTS = [[], '', b'run', 7, ['inspect'], ['run'], ['verify'],
    ['inspect', '--result-pack', 'somewhere'], ['inspect', '--result-package='],
    ['inspect', '--result-package', '--help'], ['inspect', '--result-package', '-value'],
    ['inspect', '--result-package=@private'], ['inspect', '--result-package', '@private'],
    ['inspect', '--result-package=a', '--result-package', 'b'],
    ['inspect', '--result-package=a', '--result-package=b'],
    ['inspect', '--result-package=a', '--raw-package=b'],
    ['inspect', '--result-package=a', 'extra'], ['inspect', '--result-package=a', '--'],
    ['inspect', '--result-package=a', '-h'], ['--help', 'inspect'], ['--help', '--help'],
    ['-h', '--help'], ['--help=1'], ['inspect', '--result-package', 1], [None],
    ['@file'], ['inspect', '--result-package=a', '@file'],
    ['run', '--raw-package=a', '--prepared-package=b', '--view=unknown', '--output=c'],
    ['run', '--raw-package=a', '--prepared-package=b', '--view=current13', '--output=c', '--view=h30_26'],
    [str.__new__(type('Text', (str,), {}), '--help')]]


def error_bytes(code):
    return ('{"error":"' + code + '"}\n').encode('utf-8')


@pytest.mark.parametrize('argv', BAD_ARGUMENTS, ids=lambda value: type(value).__name__)
def test_invalid_syntax_rejects_before_paths_loaders_or_models(command, monkeypatch, argv):
    c = command
    def forbidden(*args, **kwargs):
        raise AssertionError('syntax reached path or business')
    monkeypatch.setattr(c.m, '_lexical', forbidden)
    assert c.m.main(argv) == 2
    assert not c.out.data
    assert bytes(c.err.data) == error_bytes('INVALID_ARGUMENTS')
    assert c.events == [('stderr', 'write'), ('stderr', 'flush')]


@pytest.mark.parametrize('option', ['-h', '--help'])
def test_help_is_standalone_static_and_no_sklean_import_or_path_work(command, monkeypatch, option):
    c = command
    def forbidden(*args, **kwargs):
        raise AssertionError('help attempted path work')
    monkeypatch.setattr(c.m, '_lexical', forbidden)
    original = builtins.__import__
    def guard(name, *args, **kwargs):
        if name == 'sklearn' or name.startswith('sklearn.'):
            raise AssertionError('help imported model')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guard)
    assert c.m.main([option]) == 0
    text = bytes(c.out.data).decode('utf-8')
    assert text.endswith('\n') and not text.endswith('\n\n')
    for usage in ('run --raw-package', 'inspect --result-package', 'verify --result-package'):
        assert usage in text
    assert c.events == [('stdout', 'write'), ('stdout', 'flush')]
    assert not c.err.data


@pytest.mark.parametrize('form', ['mixed', 'equals', 'tuple', 'argv_none'])
def test_valid_option_forms_and_host_argv(command, form):
    c = command
    argv = ['run', '--output=' + str(c.output), '--view=current13',
        '--prepared-package=' + str(c.prepared), '--raw-package=' + str(c.raw)]
    if form == 'mixed':
        argv[-1:] = ['--raw-package', str(c.raw)]
    elif form == 'tuple':
        argv = tuple(argv)
    elif form == 'argv_none':
        c.m.sys.argv = ['program', *argv]
        argv = None
    assert c.m.main(argv) == 0
    assert json.loads(c.out.data) == expected_receipt(c, 'run')


@pytest.mark.parametrize('raw', ['relative', '../raw', '\\rooted', '/package',
    '\\\\host\\share\\raw', '//host/share/raw', 'C:/raw/../path', 'C:/nul',
    'C:/raw:file', 'C:/raw\x00bad'])
def test_unsafe_raw_paths_reject_before_loader_or_fit(command, raw):
    if os.name != 'nt' and raw in ('/package', '\\rooted', 'C:/nul', 'C:/raw:file'):
        pytest.skip('Windows lexical path rules')
    c = command
    c.argv[2] = raw
    assert c.m.main(c.argv) == 2
    assert not c.out.data
    assert bytes(c.err.data) == error_bytes('INVALID_PACKAGE_PATH')
    assert c.events == [('stderr', 'write'), ('stderr', 'flush')]


@pytest.mark.parametrize('relation', ['same_raw', 'under_raw', 'above_raw',
    'same_prepared', 'under_prepared', 'above_prepared', 'case_variant'])
def test_component_layout_precedes_target_exists_and_never_fits(command, relation):
    c = command
    if relation == 'same_raw': target = c.raw
    elif relation == 'under_raw': target = c.raw / 'new'
    elif relation == 'above_raw': target = c.raw.parent
    elif relation == 'same_prepared': target = c.prepared
    elif relation == 'under_prepared': target = c.prepared / 'new'
    elif relation == 'above_prepared': target = c.prepared.parent
    else:
        if os.name != 'nt': pytest.skip('Windows case folding')
        target = Path(str(c.raw).upper())
    c.argv[-1] = str(target)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes('INVALID_PATH_LAYOUT')
    assert not c.out.data
    assert c.events == [('stderr', 'write'), ('stderr', 'flush')]
    assert (c.raw / 'unchanged').read_bytes() == b'kept'
    assert (c.prepared / 'unchanged').read_bytes() == b'kept'


@pytest.mark.parametrize(('condition', 'code'), [('missing_parent', 'OUTPUT_ERROR'),
    ('file_parent', 'INVALID_PACKAGE_PATH'), ('file_target', 'OUTPUT_EXISTS'),
    ('directory_target', 'OUTPUT_EXISTS')])
def test_output_stat_preflight_before_input_load_or_fit(command, condition, code):
    c = command
    if condition == 'missing_parent':
        target = c.output.parent / 'missing' / 'out'
    elif condition == 'file_parent':
        parent = c.output.parent / 'file'
        parent.write_bytes(b'kept')
        target = parent / 'out'
    else:
        target = c.output
        if condition == 'file_target': target.write_bytes(b'kept')
        else: target.mkdir()
    c.argv[-1] = str(target)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes(code)
    assert c.events == [('stderr', 'write'), ('stderr', 'flush')]
    assert not c.out.data


def test_complete_components_allow_similar_sibling_names(command, monkeypatch):
    c = command
    target = c.raw.with_name(c.raw.name + '-results')
    c.argv[-1] = str(target)
    def save(package, path):
        assert path == target
        c.events.append(('save', path))
        return package.identity
    monkeypatch.setattr(c.m, 'save_release_if_result_package', save)
    assert c.m.main(c.argv) == 0
    assert ('fit', 'current13') in c.events


def test_observed_input_root_alias_of_output_ancestor_rejects_before_fit(command, monkeypatch):
    c = command
    actual = c.m._directory
    # Different lexical spellings, one observed device/file identity. The
    # returned identity comes from a real lstat of the output parent directory.
    parent_identity = actual(c.output.parent)
    def directory(path, *args, **kwargs):
        return parent_identity if path == c.raw else actual(path, *args, **kwargs)
    monkeypatch.setattr(c.m, '_directory', directory)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes('INVALID_PATH_LAYOUT')
    assert c.events == [('raw', c.raw), ('prepared', c.prepared), ('pair',),
                        ('stderr', 'write'), ('stderr', 'flush')]


def test_preflight_race_preserves_exclusive_save_winner_without_retry(command, monkeypatch):
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    c = command
    def competing_save(package, path):
        path.mkdir()
        (path / 'winner').write_bytes(b'kept')
        c.events.append(('save', path))
        raise ReleaseIFResultPackageError('OUTPUT_EXISTS')
    monkeypatch.setattr(c.m, 'save_release_if_result_package', competing_save)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes('OUTPUT_EXISTS')
    assert not c.out.data
    assert c.events.count(('fit', 'current13')) == 1
    assert (c.output / 'winner').read_bytes() == b'kept'


@pytest.mark.parametrize('bad', ['dictionary', 'changed', 'boolean_count'])
def test_run_never_publishes_saved_with_wrong_save_identity(command, monkeypatch, bad):
    c = command
    identity = c.package.identity
    if bad == 'dictionary': identity = asdict(identity)
    elif bad == 'changed': identity = replace(identity, manifest_sha256='f' * 64)
    else: identity = replace(identity, manifest_byte_count=True)
    monkeypatch.setattr(c.m, 'save_release_if_result_package', lambda package, path: identity)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes('INVALID_RESULT')
    assert not c.out.data


@pytest.mark.parametrize('bad', ['package_dict', 'report_false', 'identity_dict', 'threshold_nan',
    'mask_int', 'calibration_list'])
def test_unshaped_or_false_projection_is_invalid_result(command, monkeypatch, bad):
    c = command
    package = c.package
    if bad == 'package_dict': package = asdict(package)
    elif bad == 'report_false': package = replace(package, load_report=replace(package.load_report, structure='FAILED'))
    elif bad == 'identity_dict': package = replace(package, identity=asdict(package.identity))
    elif bad == 'threshold_nan': package = replace(package, result=replace(package.result, threshold=float('nan')))
    elif bad == 'mask_int': package = replace(package, result=replace(package.result,
        scored_mask=(0,) + package.result.scored_mask[1:]))
    else: package = replace(package, result=replace(package.result,
        calibration_indices=list(package.result.calibration_indices)))
    monkeypatch.setattr(c.m, 'load_release_if_result_package', lambda path: package)
    assert c.m.main(['inspect', '--result-package', str(c.result_dir)]) == 2
    assert bytes(c.err.data) == error_bytes('INVALID_RESULT')
    assert not c.out.data


@pytest.mark.parametrize(('kind', 'original', 'mutated', 'want'), [
    ('ReleaseMinutePackageError', 'INVALID_PACKAGE', None, 'INVALID_PACKAGE'),
    ('ReleaseInputPreparationError', 'DERIVATION_MISMATCH', None, 'DERIVATION_MISMATCH'),
    ('ReleaseIFResultPackageError', 'INPUT_BINDING_MISMATCH', None, 'INPUT_BINDING_MISMATCH'),
    ('ReleaseModelInputPairError', 'PAIR_ALIGNMENT_MISMATCH', None, 'PAIR_ALIGNMENT_MISMATCH'),
    ('ReleaseIFError', 'MODEL_UNAVAILABLE', None, 'MODEL_UNAVAILABLE'),
    ('ReleaseMinutePackageError', 'INVALID_PACKAGE', 'MODEL_ERROR', 'INTERNAL_ERROR'),
    ('ReleaseIFError', 'MODEL_ERROR', 'OUTPUT_EXISTS', 'INTERNAL_ERROR'),
    ('ReleaseInputPreparationError', 'INVALID_PACKAGE', ['INVALID_PACKAGE'], 'INTERNAL_ERROR'),
    ('ReleaseIFResultPackageError', 'INVALID_PACKAGE', True, 'INTERNAL_ERROR'),
])
def test_known_errors_respect_their_own_class_allowlist(command, monkeypatch, kind, original, mutated, want):
    c = command
    error = getattr(c.m, kind)(original)
    if mutated is not None: error.code = mutated
    def fail(path): raise error
    monkeypatch.setattr(c.m, 'load_release_minute_package', fail)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes(want)
    assert not c.out.data


@pytest.mark.parametrize(('error', 'want'), [(RuntimeError('private details'), 'INTERNAL_ERROR'),
    (KeyboardInterrupt('private details'), 'INTERRUPTED')])
def test_unknown_or_interrupted_business_stops_once(command, monkeypatch, error, want):
    c = command
    def fail(*args, **kwargs): raise error
    monkeypatch.setattr(c.m, 'fit_release_iforest', fail)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes(want)
    assert not c.out.data
    assert c.events == [('raw', c.raw), ('prepared', c.prepared), ('pair',),
                        ('stderr', 'write'), ('stderr', 'flush')]


@pytest.mark.parametrize('count', [0, 1, -1, True, None, 1.0])
def test_partial_or_wrong_type_stdout_write_is_one_attempt(command, monkeypatch, count):
    c = command
    writes = []
    def write(payload):
        writes.append(payload)
        c.out.data.extend(payload[:1])
        return count
    monkeypatch.setattr(c.out, 'write', write)
    assert c.m.main(c.argv) == 2
    assert len(writes) == 1 and bytes(c.out.data) == b'{'
    assert ('stdout', 'flush') not in c.events
    assert bytes(c.err.data) == error_bytes('OUTPUT_ERROR')


@pytest.mark.parametrize('stage', ['write', 'flush'])
@pytest.mark.parametrize(('error', 'want'), [(BrokenPipeError('private'), 'OUTPUT_ERROR'),
    (KeyboardInterrupt('private'), 'INTERRUPTED')])
def test_output_failures_keep_safe_status_after_save_and_leave_host_streams(command, monkeypatch, stage, error, want):
    c = command
    host_streams = (c.m.sys.stdout, c.m.sys.stderr)
    def fail(*args, **kwargs): raise error
    monkeypatch.setattr(c.out, stage, fail)
    assert c.m.main(c.argv) == 2
    assert ('save', c.output) in c.events
    assert bytes(c.err.data) == error_bytes(want)
    assert host_streams == (c.m.sys.stdout, c.m.sys.stderr)
    assert not c.out.closed and not c.err.closed


def test_stderr_failure_still_returns_two(command, monkeypatch):
    def fail(*args): raise KeyboardInterrupt('private')
    monkeypatch.setattr(command.err, 'flush', fail)
    assert command.m.main([]) == 2
    assert bytes(command.err.data) == error_bytes('INVALID_ARGUMENTS')


def test_receipt_budget_includes_lf_and_semantic_failure_does_not_print_success(command, monkeypatch):
    c = command
    wanted = expected_receipt(c, 'inspect')
    size = len((json.dumps(wanted, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8'))
    monkeypatch.setattr(c.m, '_OUTPUT_LIMIT', size - 1)
    assert c.m.main(['inspect', '--result-package', str(c.result_dir)]) == 2
    assert bytes(c.err.data) == error_bytes('RESOURCE_LIMIT')
    assert not c.out.data
    c.err.data.clear()
    monkeypatch.setattr(c.m, '_OUTPUT_LIMIT', size)
    assert c.m.main(['inspect', '--result-package', str(c.result_dir)]) == 0
    assert len(c.out.data) == size


def test_module_entrypoint_redirects_failed_owned_descriptors_only(command, monkeypatch):
    c = command
    events = []
    c.m.sys.stdout.fileno = lambda: 10
    c.m.sys.stderr.fileno = lambda: 11
    fake_os = SimpleNamespace(devnull='null', O_WRONLY=1,
        open=lambda path, mode: events.append(('open', path, mode)) or 99,
        dup2=lambda source, target: events.append(('dup', source, target)),
        close=lambda fd: events.append(('close', fd)))
    monkeypatch.setattr(c.m, 'os', fake_os)
    monkeypatch.setattr(c.m, 'main', lambda: 2)
    assert c.m._cli_entrypoint() == 2
    assert events == [('open', 'null', 1), ('dup', 99, 10), ('close', 99),
                      ('open', 'null', 1), ('dup', 99, 11), ('close', 99)]
    events.clear()
    monkeypatch.setattr(c.m, 'main', lambda: 0)
    assert c.m._cli_entrypoint() == 0
    assert not events


def test_run_h30_is_its_own_single_view_operation(tmp_path, monkeypatch):
    c = build_command(tmp_path, monkeypatch, 'h30_26')
    assert c.m.main(c.argv) == 0
    expected = dict(expected_receipt(c, 'run'), view='h30_26')
    assert json.loads(c.out.data) == expected
    assert c.events == [('raw', c.raw), ('prepared', c.prepared), ('pair',),
        ('fit', 'h30_26'), ('make',), ('save', c.output), ('stdout', 'write'), ('stdout', 'flush')]


@pytest.mark.parametrize('stage', ['fit', 'make'])
def test_run_cannot_save_a_valid_but_unrequested_upstream_view(command, monkeypatch, stage):
    c = command
    if stage == 'fit':
        monkeypatch.setattr(c.m, 'fit_release_iforest', lambda pair, *, view: hand_result(view='h30_26'))
    else:
        package = decode_release_if_result_package(reference_members(view='h30_26'))
        monkeypatch.setattr(c.m, 'make_release_if_result_package', lambda pair, result: package)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes('INVALID_RESULT')
    assert not c.out.data
    assert not any(event[0] == 'save' for event in c.events)


@pytest.mark.parametrize('condition', ['permission', 'reparse'])
def test_output_ancestor_access_and_reparse_fail_before_fit(command, monkeypatch, condition):
    c = command
    original = Path.lstat
    def lstat(path, *args, **kwargs):
        if path == c.output.parent:
            if condition == 'permission':
                raise PermissionError('private access details')
            return SimpleNamespace(st_file_attributes=0x400)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', lstat)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes('OUTPUT_ERROR' if condition == 'permission' else 'INVALID_PACKAGE_PATH')
    assert c.events == [('stderr', 'write'), ('stderr', 'flush')]


def test_paths_all_validate_original_spelling_before_business(command, monkeypatch):
    c = command
    seen = []
    original = c.m._lexical
    def lexical(value):
        seen.append(value)
        return original(value)
    monkeypatch.setattr(c.m, '_lexical', lexical)
    c.argv[-1] = '../not-normalized'
    assert c.m.main(c.argv) == 2
    assert seen == [str(c.raw), str(c.prepared), '../not-normalized']
    assert bytes(c.err.data) == error_bytes('INVALID_PACKAGE_PATH')
    assert c.events == [('stderr', 'write'), ('stderr', 'flush')]


def test_unknown_exception_with_valid_looking_code_is_not_trusted(command, monkeypatch):
    c = command
    error = RuntimeError('private')
    error.code = 'INVALID_PACKAGE'
    def fail(path): raise error
    monkeypatch.setattr(c.m, 'load_release_minute_package', fail)
    assert c.m.main(c.argv) == 2
    assert bytes(c.err.data) == error_bytes('INTERNAL_ERROR')
    assert not c.out.data
