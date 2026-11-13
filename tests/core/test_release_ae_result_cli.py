"""Inspect-only tests: collection is stdlib/pytest, no model fixture.

Hand constructors are imported
only inside named cases. Mock-loader packages use public immutable holders,
not a codec or a fabricated input pair. Only the moved-hand-load test delegates
to real saved-score calibration: one four-value call per view. No cold/native
closed-pipe claim follows from these in-process tests.
"""
import builtins
from dataclasses import asdict
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


MODULE = 'traffic_anomaly.release_ae_result_cli'
CONTRACT = 'traffic_anomaly.release_ae_result_contract'
DISK = 'traffic_anomaly.release_ae_result_package'
VIEWS = ('current13', 'h30_26')
LIBRARY_CODES = (
    'INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE',
    'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE',
    'INVALID_PACKAGE_PATH', 'INPUT_UNAVAILABLE', 'OUTPUT_EXISTS',
    'PACKAGE_CHANGED', 'OUTPUT_ERROR', 'INPUT_BINDING_MISMATCH',
    'NUMERICAL_DEPENDENCY_UNAVAILABLE', 'INCOMPATIBLE_RUNTIME', 'PACKAGE_ERROR',
)
CHECKS = dict(byte_integrity='MATCHED', structure='MATCHED', saved_score_q99='MATCHED',
    input_declaration_binding='MATCHED', input_pair_binding='NOT_PERFORMED',
    derivation_replay='NOT_PERFORMED', source_authentication='NOT_AUTHENTICATED',
    model_execution='NOT_AUTHENTICATED')
SUCCESS_KEYS = (
    'schema_version', 'profile_id', 'command', 'status', 'result_identity', 'view',
    'input_references', 'configuration_sha256', 'segments', 'counts', 'feature_columns',
    'model_configuration', 'runtime_declarations', 'threshold', 'training_losses',
    'calibration', 'score_ranges', 'checks', 'operations',
)


def _api():
    if importlib.util.find_spec(MODULE) is None:
        pytest.fail('release_ae_result_cli inspect is not implemented')
    api = importlib.import_module(MODULE)
    assert callable(getattr(api, 'main', None)), 'public inspect main is missing'
    assert callable(getattr(api, '_cli_entrypoint', None)), 'module-main entrypoint is missing'
    return api


def _fence(monkeypatch, denied):
    attempts = []
    original, dynamic = builtins.__import__, importlib.import_module

    def check(name):
        if denied(name):
            attempts.append(name)
            raise AssertionError('import outside the declared inspect test boundary')

    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            check(fullname)

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        full = name
        if level and globals and globals.get('__package__'):
            full = importlib.util.resolve_name('.' * level + name, globals['__package__'])
        check(full)
        for part in fromlist or ():
            if type(part) is str and part != '*':
                check(full + '.' + part)
        return original(name, globals, locals, fromlist, level)

    def guarded_dynamic(name, package=None):
        full = importlib.util.resolve_name(name, package) if name.startswith('.') else name
        check(full)
        return dynamic(name, package)

    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(importlib, 'import_module', guarded_dynamic)
    monkeypatch.setattr(sys, 'meta_path', [Fence(), *sys.meta_path])
    return attempts


@pytest.fixture(autouse=True)
def _no_new_models(monkeypatch):
    roots = {'torch', 'sklearn', 'joblib', 'tensorflow', 'tf', 'jax', 'jaxlib',
             'cloudpickle', 'keras', 'xgboost', 'lightgbm', 'catboost', 'onnxruntime'}
    products = ('traffic_anomaly.release_iforest', 'traffic_anomaly.release_if_learned',
                'traffic_anomaly.release_model_inputs', 'traffic_anomaly.candidate_autoencoder',
                'traffic_anomaly.candidate_ae_weights')
    before = {name: module for name, module in sys.modules.items() if name.split('.')[0] in roots}
    with monkeypatch.context() as patch:
        attempts = _fence(patch, lambda name: name.split('.')[0] in roots
            or any(name == p or name.startswith(p + '.') for p in products))
        yield
    assert attempts == []
    after = {name: module for name, module in sys.modules.items() if name.split('.')[0] in roots}
    assert before.keys() == after.keys()
    assert all(after[name] is module for name, module in before.items())


def _canonical(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def _error_bytes(code):
    return _canonical(dict(status='ERROR', code=code))


def _exact(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key in expected:
            _exact(actual[key], expected[key])
    elif type(expected) in (list, tuple):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            _exact(left, right)
    elif type(expected) is float:
        assert actual.hex() == expected.hex()
    else:
        assert actual == expected


class Binary:
    def __init__(self, events, name, mode='ok'):
        self.data, self.events, self.name, self.mode = bytearray(), events, name, mode

    def write(self, payload):
        self.events.append((self.name, 'write', bytes(payload)))
        if self.mode in ('raise', 'memory', 'interrupt', 'system'):
            error = {'raise': OSError, 'memory': MemoryError,
                     'interrupt': KeyboardInterrupt, 'system': SystemExit}[self.mode]
            raise error('private write diagnostic')
        self.data.extend(payload[:-1] if self.mode == 'short' else payload)
        if self.mode == 'short': return len(payload) - 1
        if self.mode == 'none': return None
        if self.mode == 'bool': return True
        if self.mode == 'float': return float(len(payload))
        if self.mode == 'int-subclass':
            class Count(int): pass
            return Count(len(payload))
        return len(payload)

    def flush(self):
        self.events.append((self.name, 'flush'))
        if self.mode.startswith('flush-'):
            error = {'flush-raise': OSError, 'flush-memory': MemoryError,
                     'flush-interrupt': KeyboardInterrupt, 'flush-system': SystemExit}[self.mode]
            raise error('private flush diagnostic')


class Stream:
    def __init__(self, binary):
        self.buffer = binary
        self.text_attempts = []

    def write(self, text):
        self.text_attempts.append(text)
        raise AssertionError('text output fallback is forbidden')


def _streams(cli, monkeypatch, *, out_mode='ok', err_mode='ok'):
    events = []
    out, err = Binary(events, 'stdout', out_mode), Binary(events, 'stderr', err_mode)
    stdout, stderr = Stream(out), Stream(err)
    host = SimpleNamespace(argv=['program'], stdout=stdout, stderr=stderr)
    monkeypatch.setattr(cli, 'sys', host)
    return SimpleNamespace(out=out, err=err, stdout=stdout, stderr=stderr, host=host, events=events)


def _run(cli, argv, *, expected_exception=None):
    # No exception object or its context is returned to pytest's formatter.
    record = dict(returned=False, status=None, escaped=False, expected_identity=False)
    try:
        value = cli.main(argv)
        record.update(returned=True, status=value if type(value) is int else None)
    except BaseException as error:
        record.update(escaped=True, expected_identity=error is expected_exception)
    return record


def _returned(status):
    return dict(returned=True, status=status, escaped=False, expected_identity=False)


def _hand_package(view):
    # Only public data holders; no make/encode/decode/load, hence no Q99 here.
    h = importlib.import_module('tests.core.test_release_ae_result_contract')
    contract = importlib.import_module(CONTRACT)
    result, declarations = h.hand_native(contract, view)
    context_values = h.hand_context(view)
    context_values.update(raw_identity=declarations.raw_identity,
        prepared_identity=declarations.prepared_identity, segments=declarations.segments)
    context = contract.ReleaseAEResultContext(**context_values)
    members = h.reference_members(view)
    identity = contract.ReleaseAEResultIdentity(profile_id=h.PACKAGE_PROFILE,
        context_sha256=hashlib.sha256(h.canonical(h.hand_context(view))).hexdigest(),
        manifest_sha256=hashlib.sha256(members['manifest.json']).hexdigest(),
        manifest_byte_count=len(members['manifest.json']))
    report = contract.ReleaseAEResultLoadReport(profile_id=h.LOAD_PROFILE,
        scope='SAVED_AE_RESULT_INTERNAL_CONSISTENCY_ONLY', **CHECKS)
    package = contract.ReleaseAEResultPackage(identity=identity, context=context,
                                             result=result, load_report=report)
    return h, contract, package


def _expected(h, package, view):
    p, context = h.hand_projection(view), h.hand_context(view)
    low = -0.0
    return dict(schema_version=1, profile_id='c17-release-ae-result-cli-v1', command='inspect',
        status='INTERNAL_CONSISTENCY_CHECKED', result_identity=asdict(package.identity), view=view,
        input_references=dict(raw=p['raw_identity'], prepared=p['prepared_identity']),
        configuration_sha256=p['configuration_sha256'], segments=context['segments'],
        counts=dict(total=68, scored=7, training=3, calibration=4, preprocessing_fit=4),
        feature_columns=p['feature_columns'], model_configuration=p['configuration'],
        runtime_declarations=p['runtime'], threshold=4.0, training_losses=p['training_losses'],
        calibration=p['calibration'], score_ranges=dict(
            scores=dict(count=7, min=low, max=8.0),
            current_reconstruction_mse=dict(count=7, min=low, max=8.0 if view == 'current13' else 6.0),
            history_deviation_reconstruction_mse=(dict(count=0, min=None, max=None)
                if view == 'current13' else dict(count=7, min=low, max=10.0))),
        checks=dict(CHECKS), operations=dict(model_fit_calls=0, model_forward_calls=0,
            saved_score_q99_checks=1, upstream_package_loads=0))


def _mock_command(cli, tmp_path, monkeypatch, view='current13'):
    h, contract, package = _hand_package(view)
    disk = importlib.import_module(DISK)
    path, calls = tmp_path / 'saved-hand', []
    streams = _streams(cli, monkeypatch)

    def load(value):
        assert type(value) in (str, type(path))
        assert Path(value) == path
        calls.append(value)
        streams.events.append(('load', str(value)))
        return package

    monkeypatch.setattr(disk, 'load_release_ae_result_package', load)
    # A just-loaded formatter must not nest another public codec validation.
    forbidden_calls = []
    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        raise AssertionError('summary nested a public codec stage')
    for name in ('decode_release_ae_result_projection', 'make_release_ae_result_package',
                 'encode_release_ae_result_package', 'decode_release_ae_result_package'):
        monkeypatch.setattr(contract, name, forbidden)
    return SimpleNamespace(h=h, contract=contract, package=package, disk=disk, path=path,
        calls=calls, streams=streams, forbidden_calls=forbidden_calls,
        argv=['inspect', '--result-package', str(path)])


def _assert_error(streams, code):
    assert bytes(streams.err.data) == _error_bytes(code)
    assert len(streams.err.data) <= 1024
    assert not streams.out.data
    assert streams.stdout.text_attempts == streams.stderr.text_attempts == []
    assert sum(event[:2] == ('stderr', 'flush') for event in streams.events) == 1


class TestInspectCLI:
    @pytest.mark.parametrize('view', VIEWS)
    @pytest.mark.parametrize('form', ('split', 'equals', 'tuple', 'argv-none'))
    def test_exact_summary_from_one_just_loaded_hand_holder_without_extra_codec(self, tmp_path, monkeypatch, view, form):
        cli = _api()
        c = _mock_command(cli, tmp_path, monkeypatch, view)
        argv = c.argv
        if form == 'equals': argv = ['inspect', '--result-package=' + str(c.path)]
        elif form == 'tuple': argv = tuple(argv)
        elif form == 'argv-none': c.streams.host.argv = ['program', *argv]; argv = None
        before = dict(vars(cli))
        result = _run(cli, argv)
        after = dict(vars(cli))
        assert after.keys() == before.keys()
        assert all(after[name] is value for name, value in before.items())
        assert result == _returned(0)
        actual = json.loads(c.streams.out.data)
        expected = _expected(c.h, c.package, view)
        assert set(actual) == set(SUCCESS_KEYS) and len(actual) == 19
        _exact(actual, expected)
        assert bytes(c.streams.out.data) == _canonical(expected)
        assert len(c.streams.out.data) <= 65536 and not c.streams.err.data
        assert len(c.calls) == 1 and c.forbidden_calls == []
        assert [event[:2] for event in c.streams.events] == [
            ('load', str(c.path)), ('stdout', 'write'), ('stdout', 'flush')]
        assert c.streams.stdout.text_attempts == c.streams.stderr.text_attempts == []

    @pytest.mark.parametrize('view', VIEWS)
    def test_moved_hand_package_real_loader_one_saved_q99_no_producer(self, tmp_path, monkeypatch, view):
        cli = _api()
        h = importlib.import_module('tests.core.test_release_ae_result_contract')
        contract, disk = importlib.import_module(CONTRACT), importlib.import_module(DISK)
        selected = h._calibration_spy(contract, monkeypatch)
        source, moved = tmp_path / 'hand-original', tmp_path / 'hand-moved'
        source.mkdir()
        members = h.reference_members(view)
        for name, payload in members.items(): (source / name).write_bytes(payload)
        source.rename(moved)
        calls, loaded = [], []
        original = disk.load_release_ae_result_package
        def load(path):
            calls.append(path)
            streams.events.append(('load', str(path)))
            package = original(path)
            loaded.append(package)
            return package
        monkeypatch.setattr(disk, 'load_release_ae_result_package', load)
        streams = _streams(cli, monkeypatch)
        assert _run(cli, ['inspect', '--result-package', str(moved)]) == _returned(0)
        assert len(calls) == len(loaded) == 1
        assert selected == [((4., 4., 4., 4.), .99)]
        _exact(json.loads(streams.out.data), _expected(h, loaded[0], view))
        assert bytes(streams.out.data) == _canonical(_expected(h, loaded[0], view))
        assert [event[:2] for event in streams.events] == [
            ('load', str(moved)), ('stdout', 'write'), ('stdout', 'flush')]
        assert not streams.err.data and not source.exists()
        assert {p.name: p.read_bytes() for p in moved.iterdir()} == members

    @pytest.mark.parametrize('option', ('-h', '--help'))
    def test_standalone_help_before_all_data_imports(self, monkeypatch, option):
        cli = _api()
        streams = _streams(cli, monkeypatch)
        with monkeypatch.context() as patch:
            attempts = _fence(patch, lambda n: n.split('.')[0] == 'numpy'
                or (n.startswith('traffic_anomaly.') and n != MODULE))
            result = _run(cli, [option])
        assert result == _returned(0) and attempts == []
        text = bytes(streams.out.data).decode('utf-8')
        assert 'inspect --result-package' in text
        assert text.endswith('\n') and not text.endswith('\n\n')
        assert not streams.err.data and len(streams.out.data) <= 65536
        assert streams.stdout.text_attempts == []

    @pytest.mark.parametrize('argv', (
        [], ['inspect'], ['fit'], ['pack'], ['verify'], ['replay'], ['@response'],
        ['--help', 'inspect'], ['--help', '--help'], ['-h', '--help'], ['--help=1'],
        ['inspect', '--result-pack', 'x'], ['inspect', '--result-package'],
        ['inspect', '--result-package='], ['inspect', '--result-package', ''],
        ['inspect', '--result-package', '--help'], ['inspect', '--result-package', '-bad'],
        ['inspect', '--result-package=@file'], ['inspect', '--result-package', '@file'],
        ['inspect', '--result-package=x', '--result-package=y'],
        ['inspect', '--result-package=x', '--result-package', 'y'],
        ['inspect', '--result-package=x', '--raw-package=y'],
        ['inspect', '--result-package=x', 'extra'], ['inspect', '--result-package=x', '--'],
        ['inspect', '--result-package=x', '-h'], ['inspect', '--result-package=x', '@file'],
        ['inspect', '--result-package', None], [None],
    ), ids=lambda argv: 'syntax-' + str(len(argv)))
    def test_invalid_syntax_is_finite_before_data_dependencies(self, monkeypatch, argv):
        cli = _api()
        streams = _streams(cli, monkeypatch)
        with monkeypatch.context() as patch:
            attempts = _fence(patch, lambda n: n.split('.')[0] == 'numpy'
                or (n.startswith('traffic_anomaly.') and n != MODULE))
            result = _run(cli, argv)
        assert result == _returned(2) and attempts == []
        _assert_error(streams, 'INVALID_ARGUMENTS')

    @pytest.mark.parametrize('kind', ('string', 'bytes', 'integer', 'generator', 'list-subclass', 'tuple-subclass', 'str-subclass'))
    def test_argv_admission_never_coerces_foreign_container_or_strings(self, monkeypatch, kind):
        cli = _api()
        streams, touched = _streams(cli, monkeypatch), []
        class ForeignList(list):
            def __iter__(self): touched.append('iter'); raise AssertionError('FOREIGN_ITERATOR')
        class ForeignTuple(tuple):
            def __iter__(self): touched.append('iter'); raise AssertionError('FOREIGN_ITERATOR')
        class ForeignString(str):
            def __eq__(self, other): touched.append('eq'); raise AssertionError('FOREIGN_EQUALITY')
            __hash__ = str.__hash__
        values = dict(string='--help', bytes=b'--help', integer=3,
            generator=(x for x in ('--help',)), **{'list-subclass': ForeignList(['--help']),
            'tuple-subclass': ForeignTuple(['--help']), 'str-subclass': [ForeignString('--help')]})
        assert _run(cli, values[kind]) == _returned(2)
        assert touched == []
        _assert_error(streams, 'INVALID_ARGUMENTS')

    @pytest.mark.parametrize('code', LIBRARY_CODES)
    def test_exact_library_error_code_has_minimal_canonical_terminal_line(self, tmp_path, monkeypatch, code):
        cli = _api()
        c = _mock_command(cli, tmp_path, monkeypatch)
        error = c.contract.ReleaseAEResultPackageError(code)
        def fail(path): raise error
        monkeypatch.setattr(c.disk, 'load_release_ae_result_package', fail)
        assert _run(cli, c.argv) == _returned(2)
        _assert_error(c.streams, code)

    @pytest.mark.parametrize('kind', ('ordinary', 'hostile', 'foreign-module-name'))
    def test_foreign_exception_never_exposes_getters_or_private_diagnostic(self, tmp_path, monkeypatch, kind):
        cli = _api()
        c, reads = _mock_command(cli, tmp_path, monkeypatch), []
        class Foreign(ValueError):
            @property
            def __class__(self): reads.append('class'); raise RuntimeError('private class')
            @property
            def code(self): reads.append('code'); raise KeyboardInterrupt('private code')
        class ForeignModule(ModuleNotFoundError):
            @property
            def name(self): reads.append('name'); raise MemoryError('private name')
        error = (ValueError('private ordinary') if kind == 'ordinary' else
                 ForeignModule('private module') if kind == 'foreign-module-name' else Foreign('private foreign'))
        def fail(path): raise error
        monkeypatch.setattr(c.disk, 'load_release_ae_result_package', fail)
        assert _run(cli, c.argv) == _returned(2)
        assert reads == []
        _assert_error(c.streams, 'CLI_ERROR')

    @pytest.mark.parametrize('kind,expected', (
        ('known', 'INPUT_UNAVAILABLE'), ('unknown', 'CLI_ERROR'), ('bool', 'CLI_ERROR'),
        ('str-subclass', 'CLI_ERROR'), ('raise', 'CLI_ERROR'),
        ('memory', 'RESOURCE_LIMIT'), ('interrupt', 'INTERRUPTED'), ('system', None),
    ))
    def test_owned_code_getter_read_once_protected_without_assertion_side_read(self, tmp_path, monkeypatch, kind, expected):
        cli = _api()
        c, reads = _mock_command(cli, tmp_path, monkeypatch), []
        error = c.contract.ReleaseAEResultPackageError('INPUT_UNAVAILABLE')
        terminal = SystemExit('private getter exit')
        class Text(str): pass
        def code(self):
            reads.append('code')
            if kind == 'raise': raise RuntimeError('private getter')
            if kind == 'memory': raise MemoryError('private getter')
            if kind == 'interrupt': raise KeyboardInterrupt('private getter')
            if kind == 'system': raise terminal
            return {'known': 'INPUT_UNAVAILABLE', 'unknown': 'NOT_A_PUBLIC_CODE',
                    'bool': True, 'str-subclass': Text('INPUT_UNAVAILABLE')}[kind]
        owner = c.contract.ReleaseAEResultPackageError
        original_getattribute = owner.__getattribute__
        def primary_only(self, name):
            if self is error and name == 'code':
                return code(self)
            return original_getattribute(self, name)
        monkeypatch.setattr(owner, '__getattribute__', primary_only)
        def fail(path): raise error
        monkeypatch.setattr(c.disk, 'load_release_ae_result_package', fail)
        result = _run(cli, c.argv, expected_exception=terminal)
        snapshot = tuple(reads)  # Library-owned accesses only; never inspect error.code here.
        assert snapshot == ('code',)
        if expected is None:
            assert result == dict(returned=False, status=None, escaped=True, expected_identity=True)
            assert not c.streams.out.data and not c.streams.err.data
        else:
            assert result == _returned(2)
            _assert_error(c.streams, expected)

    @pytest.mark.parametrize('kind', ('memory', 'interrupt', 'system'))
    def test_real_resource_interrupt_subclass_uses_actual_type_and_preserves_system_identity(self, tmp_path, monkeypatch, kind):
        cli = _api()
        c, reads = _mock_command(cli, tmp_path, monkeypatch), []
        base = {'memory': MemoryError, 'interrupt': KeyboardInterrupt, 'system': SystemExit}[kind]
        class Resource(base):
            @property
            def __class__(self): reads.append('class'); raise RuntimeError('private class')
            @property
            def code(self): reads.append('code'); raise RuntimeError('private code')
        error = Resource('private resource')
        def fail(path): raise error
        monkeypatch.setattr(c.disk, 'load_release_ae_result_package', fail)
        result = _run(cli, c.argv, expected_exception=error)
        assert reads == []
        if kind == 'system':
            assert result == dict(returned=False, status=None, escaped=True, expected_identity=True)
            assert not c.streams.out.data and not c.streams.err.data
        else:
            assert result == _returned(2)
            _assert_error(c.streams, 'RESOURCE_LIMIT' if kind == 'memory' else 'INTERRUPTED')

    @pytest.mark.parametrize('mode,code', (
        ('short', 'OUTPUT_ERROR'), ('none', 'OUTPUT_ERROR'), ('bool', 'OUTPUT_ERROR'),
        ('float', 'OUTPUT_ERROR'), ('int-subclass', 'OUTPUT_ERROR'), ('raise', 'OUTPUT_ERROR'),
        ('flush-raise', 'OUTPUT_ERROR'), ('memory', 'RESOURCE_LIMIT'),
        ('flush-memory', 'RESOURCE_LIMIT'), ('interrupt', 'INTERRUPTED'), ('flush-interrupt', 'INTERRUPTED'),
    ))
    def test_stdout_bad_counts_write_or_flush_never_return_success_or_retry(self, tmp_path, monkeypatch, mode, code):
        cli = _api()
        c = _mock_command(cli, tmp_path, monkeypatch)
        c.streams.out.mode = mode
        assert _run(cli, c.argv) == _returned(2)
        assert bytes(c.streams.err.data) == _error_bytes(code)
        assert len(c.calls) == 1 and c.forbidden_calls == []
        assert sum(event[:2] == ('stdout', 'write') for event in c.streams.events) == 1
        assert c.streams.stdout.text_attempts == c.streams.stderr.text_attempts == []

    @pytest.mark.parametrize('stage', ('write', 'flush'))
    def test_operation_system_exit_from_stdout_propagates_same_object(self, tmp_path, monkeypatch, stage):
        cli = _api()
        c = _mock_command(cli, tmp_path, monkeypatch)
        terminal = SystemExit('private stdout exit')
        def fail(*args): raise terminal
        monkeypatch.setattr(c.streams.out, stage, fail)
        assert _run(cli, c.argv, expected_exception=terminal) == dict(
            returned=False, status=None, escaped=True, expected_identity=True)
        assert not c.streams.err.data and len(c.calls) == 1

    @pytest.mark.parametrize('kind', ('absent', 'raise', 'memory', 'interrupt'))
    def test_missing_or_failed_stdout_buffer_has_no_text_fallback(self, tmp_path, monkeypatch, kind):
        cli = _api()
        c = _mock_command(cli, tmp_path, monkeypatch)
        touched = []
        class Missing:
            def write(self, value): touched.append('text'); raise AssertionError('TEXT_FALLBACK')
        class Raising(Missing):
            @property
            def buffer(self):
                touched.append('buffer')
                raise {'raise': RuntimeError, 'memory': MemoryError,
                       'interrupt': KeyboardInterrupt}[kind]('private buffer')
        c.streams.host.stdout = Missing() if kind == 'absent' else Raising()
        assert _run(cli, c.argv) == _returned(2)
        expected = {'absent': 'OUTPUT_ERROR', 'raise': 'OUTPUT_ERROR',
                    'memory': 'RESOURCE_LIMIT', 'interrupt': 'INTERRUPTED'}[kind]
        assert bytes(c.streams.err.data) == _error_bytes(expected)
        assert 'text' not in touched and len(c.calls) == 1

    @pytest.mark.parametrize('mode', ('short', 'none', 'float', 'int-subclass', 'raise',
        'memory', 'interrupt', 'system', 'flush-raise', 'flush-memory', 'flush-interrupt', 'flush-system'))
    def test_secondary_stderr_failure_cannot_replace_selected_primary_or_retry(self, tmp_path, monkeypatch, mode):
        cli = _api()
        c = _mock_command(cli, tmp_path, monkeypatch)
        c.streams.err.mode = mode
        error = c.contract.ReleaseAEResultPackageError('INPUT_UNAVAILABLE')
        def fail(path): raise error
        monkeypatch.setattr(c.disk, 'load_release_ae_result_package', fail)
        assert _run(cli, c.argv) == _returned(2)
        writes = [event[2] for event in c.streams.events if event[:2] == ('stderr', 'write')]
        assert writes == [_error_bytes('INPUT_UNAVAILABLE')]
        assert sum(event[:2] == ('stderr', 'flush') for event in c.streams.events) <= 1
        if mode.startswith('flush-'):
            assert sum(event[:2] == ('stderr', 'flush') for event in c.streams.events) == 1
        assert not c.streams.out.data
        assert c.streams.stdout.text_attempts == c.streams.stderr.text_attempts == []

    def test_missing_stderr_buffer_remains_finite_after_primary_error(self, tmp_path, monkeypatch):
        cli = _api()
        c = _mock_command(cli, tmp_path, monkeypatch)
        text_attempts = []
        class Missing:
            def write(self, text): text_attempts.append(text); raise RuntimeError('private fallback')
        c.streams.host.stderr = Missing()
        error = c.contract.ReleaseAEResultPackageError('INPUT_UNAVAILABLE')
        def fail(path): raise error
        monkeypatch.setattr(c.disk, 'load_release_ae_result_package', fail)
        assert _run(cli, c.argv) == _returned(2)
        assert text_attempts == [] and not c.streams.out.data

    @pytest.mark.parametrize('kind', ('foreign', 'dict', 'missing-slot'))
    def test_formatter_rejects_nonholder_or_incomplete_loader_value_without_foreign_getters(self, tmp_path, monkeypatch, kind):
        cli = _api()
        c, touched = _mock_command(cli, tmp_path, monkeypatch), []
        class Foreign:
            @property
            def __class__(self): touched.append('class'); raise RuntimeError('private class')
            @property
            def identity(self): touched.append('identity'); raise RuntimeError('private identity')
        values = {'foreign': Foreign(), 'dict': {},
                  'missing-slot': object.__new__(c.contract.ReleaseAEResultPackage)}
        monkeypatch.setattr(c.disk, 'load_release_ae_result_package', lambda path: values[kind])
        assert _run(cli, c.argv) == _returned(2)
        assert touched == []
        _assert_error(c.streams, 'CLI_ERROR')

    def test_inprocess_reload_is_stdlib_only_not_a_cold_or_native_proof(self, monkeypatch):
        cli = _api()
        with monkeypatch.context() as patch:
            attempts = _fence(patch, lambda n: n.split('.')[0] == 'numpy'
                or (n.startswith('traffic_anomaly.') and n != MODULE))
            assert importlib.reload(cli) is cli
        assert attempts == []
        # Actual buffered shutdown120/closed-pipe behavior is NOT_RUN here.
