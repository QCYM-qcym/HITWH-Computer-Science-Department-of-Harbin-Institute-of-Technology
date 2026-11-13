"""Hand data-only AE storage checks; no fit, preparation or model runtime.

Collection imports stdlib/pytest only. Every named case acquires the missing
feature lazily, so the initial RED is a test failure rather than collection2.
Successful numerical checks use the real calibrator on hand values, never a
model. This file does not claim a cold-process or native output observation.
"""
import builtins
from dataclasses import asdict, fields, FrozenInstanceError, is_dataclass, replace
from datetime import datetime, timedelta
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import math
import sys

import pytest


MODULE = 'traffic_anomaly.release_ae_result_contract'
PACKAGE_PROFILE = 'c17-release-ae-result-package-v1'
RESULT_PROFILE = 'c17-release-ae-engineering-v1'
RESULT_SCOPE = 'IN_MEMORY_ENGINEERING_NUMERICAL_RESULT_ONLY'
LOAD_PROFILE = 'c17-release-ae-result-load-report-v1'
VIEWS = ('current13', 'h30_26')
MEMBERS = ('result.json', 'manifest.json', 'COMPLETE.json')
LIMITS = (2097152, 65536, 4096)
COMMON = (31, 32, 33, 64, 65, 66, 67)
TRAIN = (31, 32, 33)
CAL = (64, 65, 66, 67)
PREPROCESS = (30, 31, 32, 33)
G13 = (
    'completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s',
    'duration_median_s', 'duration_p95_s', 'no_backward_packet_source_record_count',
)
RESULT_KEYS = (
    'profile_id', 'scope', 'view', 'raw_identity', 'prepared_identity',
    'configuration_sha256', 'feature_columns', 'scores', 'predictions',
    'scored_mask', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse',
    'threshold', 'train_indices', 'calibration_indices', 'preprocessing_fit_indices',
    'training_losses', 'configuration', 'calibration', 'runtime',
)
CONTEXT_KEYS = (
    'profile_id', 'result_profile_id', 'view', 'raw_identity', 'prepared_identity',
    'configuration_sha256', 'source_schema_id', 'source_authentication',
    'time_basis', 'policy_status', 'audit_fit_policy', 'segments',
    'minute_count', 'score_direction',
)
CODES = (
    'INVALID_PACKAGE_ARGUMENTS', 'INVALID_PACKAGE', 'INCOMPATIBLE_PACKAGE',
    'RESOURCE_LIMIT', 'INTEGRITY_MISMATCH', 'INCONSISTENT_PACKAGE',
    'INVALID_PACKAGE_PATH', 'INPUT_UNAVAILABLE', 'OUTPUT_EXISTS',
    'PACKAGE_CHANGED', 'OUTPUT_ERROR', 'INPUT_BINDING_MISMATCH',
    'NUMERICAL_DEPENDENCY_UNAVAILABLE', 'INCOMPATIBLE_RUNTIME', 'PACKAGE_ERROR',
)


def _api():
    if importlib.util.find_spec(MODULE) is None:
        pytest.fail('release_ae_result_contract public codec is not implemented')
    api = importlib.import_module(MODULE)
    for name in ('decode_release_ae_result_projection', 'make_release_ae_result_package',
                 'encode_release_ae_result_package', 'decode_release_ae_result_package'):
        assert callable(getattr(api, name, None)), 'public AE result codec is missing'
    return api


@pytest.fixture(autouse=True)
def _no_new_models(monkeypatch):
    roots = {'torch', 'sklearn', 'joblib', 'tensorflow'}
    blocked_product = ('traffic_anomaly.release_iforest', 'traffic_anomaly.release_model_inputs',
                       'traffic_anomaly.candidate_autoencoder', 'traffic_anomaly.candidate_ae_weights')
    baseline = {n: m for n, m in sys.modules.items() if n.split('.')[0] in roots}
    attempts = []
    old_import, old_dynamic = builtins.__import__, importlib.import_module

    def check(name):
        if (name.split('.')[0] in roots
                or any(name == p or name.startswith(p + '.') for p in blocked_product)):
            attempts.append(name)
            raise AssertionError('model/input-admission import is outside this hand codec scope')

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
        return old_import(name, globals, locals, fromlist, level)

    def dynamic(name, package=None):
        full = importlib.util.resolve_name(name, package) if name.startswith('.') else name
        check(full)
        return old_dynamic(name, package)

    with monkeypatch.context() as guard:
        guard.setattr(sys, 'meta_path', [Fence(), *sys.meta_path])
        guard.setattr(builtins, '__import__', guarded)
        guard.setattr(importlib, 'import_module', dynamic)
        yield
    assert attempts == []
    current = {n: m for n, m in sys.modules.items() if n.split('.')[0] in roots}
    assert current.keys() == baseline.keys()
    assert all(current[n] is m for n, m in baseline.items())


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def _ref(profile, first, second, count):
    return dict(profile_id=profile, context_sha256=first * 64,
                manifest_sha256=second * 64, manifest_byte_count=count)


def hand_configuration(view):
    """Literal accepted default, independent of the product profile resolver."""
    width = 13 if view == 'current13' else 26
    return dict(model_profile_id='c17-i1-g13u-ae-synthetic-v1', parameter_status='ENGINEERING_TOY_ONLY',
        method='current_ae' if width == 13 else 'history_ae', input_width=width,
        history_window=None if width == 13 else 30, architecture=[width, 8, 3, 8, width],
        parameter_count=288 if width == 13 else 509, activation='RELU_HIDDEN_LINEAR_OUTPUT',
        device='cpu', training_dtype='float32', score_dtype='float64',
        score_rule='FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT', epochs=5, batch_strategy='FULL_BATCH',
        shuffle=False, optimizer='Adam', optimizer_cpu_guard='INSTANCE_LOCAL_HEALTH_CHECK_V1',
        optimizer_healthcheck_api='_accelerator_graph_capture_health_check', learning_rate=.001,
        adam_betas=[.9, .999], adam_epsilon=1e-8, weight_decay=0., amsgrad=False,
        random_state=42, fit_scope='TRAIN_NORMAL_COMMON', calibration_scope='CALIBRATION_NORMAL_COMMON',
        quantile=.99, quantile_method='linear', alarm_comparison='STRICT_GREATER',
        preprocessing_fit_provenance='NOT_REESTIMATED')


def hand_projection(view='current13'):
    """N68, seven scored rows, three training/four equal calibration values4."""
    scores, current, history, mask, predictions = ([None] * 68 for _ in range(5))
    mask[:] = [False] * 68
    for i, score, low, high in zip(COMMON, (-0., 4., 8., 4., 4., 4., 4.),
                                  (-0., 2., 6., 2., 2., 2., 2.),
                                  (-0., 6., 10., 6., 6., 6., 6.)):
        scores[i] = score
        current[i] = score if view == 'current13' else low
        history[i] = None if view == 'current13' else high
        mask[i] = True
        predictions[i] = i == 33
    return dict(profile_id=RESULT_PROFILE, scope=RESULT_SCOPE, view=view,
        raw_identity=_ref('c17-release-minute-package-v1', 'a', 'b', 101),
        prepared_identity=_ref('c17-release-prepared-input-package-v1', 'c', 'd', 202),
        configuration_sha256='e' * 64,
        feature_columns=['current:' + n for n in G13] + (
            ['residual_h30:' + n for n in G13] if view == 'h30_26' else []),
        scores=scores, predictions=predictions, scored_mask=mask,
        current_reconstruction_mse=current, history_deviation_reconstruction_mse=history,
        threshold=4., train_indices=list(TRAIN), calibration_indices=list(CAL),
        preprocessing_fit_indices=list(PREPROCESS), training_losses=[.5, .4, .3, .2, .1],
        configuration=hand_configuration(view),
        calibration=dict(quantile=.99, method='linear', comparison='STRICT_GREATER',
                         sample_count=4, equal_count=4, strictly_above_count=0),
        runtime=dict(python_version='3.14.0', numpy_version='2.5.4', torch_version='2.14.1+cpu',
                     device='cpu', torch_num_threads=2, torch_num_interop_threads=3))


def hand_context(view='current13'):
    p = hand_projection(view)
    return dict(profile_id=PACKAGE_PROFILE, result_profile_id=RESULT_PROFILE, view=view,
        raw_identity=p['raw_identity'], prepared_identity=p['prepared_identity'],
        configuration_sha256=p['configuration_sha256'], source_schema_id='c17-release-91-v1',
        source_authentication='NOT_AUTHENTICATED', time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',
        policy_status='AUDIT_ONLY', audit_fit_policy='P_U', minute_count=68,
        score_direction='HIGHER_IS_MORE_ANOMALOUS', segments=[
            dict(ordinal=0, id='train', role='train', start='2026-01-01T00:00:00', end='2026-01-01T00:34:00'),
            dict(ordinal=1, id='cal', role='calibration', start='2026-01-01T02:00:00', end='2026-01-01T02:34:00')])


def reference_members(view='current13', *, projection=None, context=None):
    """Hand-built envelopes; no product encoder or validator supplies the oracle."""
    projection = hand_projection(view) if projection is None else projection
    context = hand_context(view) if context is None else context
    digest = hashlib.sha256(canonical(context)).hexdigest()
    result = canonical(dict(schema_version=1, profile_id=PACKAGE_PROFILE,
                            context_sha256=digest, result=projection))
    manifest = canonical(dict(schema_version=1, profile_id=PACKAGE_PROFILE,
        context_sha256=digest, context=context,
        members={'result.json': dict(byte_count=len(result), sha256=hashlib.sha256(result).hexdigest())}))
    complete = canonical(dict(schema_version=1, profile_id=PACKAGE_PROFILE, status='COMPLETE',
        manifest=dict(byte_count=len(manifest), sha256=hashlib.sha256(manifest).hexdigest())))
    return dict(zip(MEMBERS, (result, manifest, complete)))


def reseal(view='current13', *, result_change=None, context_change=None):
    p, c = hand_projection(view), hand_context(view)
    if result_change:
        result_change(p)
    if context_change:
        context_change(c)
    return reference_members(view, projection=p, context=c)


def replace_member_bytes(members, name, payload):
    """Bind malformed target bytes honestly so its parser, not a stale SHA, fails."""
    changed = dict(members)
    changed[name] = payload
    if name == 'result.json':
        manifest = json.loads(changed['manifest.json'])
        manifest['members']['result.json'] = dict(byte_count=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        changed['manifest.json'] = canonical(manifest)
    if name != 'COMPLETE.json':
        manifest_bytes = changed['manifest.json']
        complete = json.loads(changed['COMPLETE.json'])
        complete['manifest'] = dict(byte_count=len(manifest_bytes), sha256=hashlib.sha256(manifest_bytes).hexdigest())
        changed['COMPLETE.json'] = canonical(complete)
    return changed


def hand_native(api, view='current13', *, projection=None, context=None):
    # These imports occur only during a named test, never collection. Their data
    # types are used without any fit/admission/preparation/pair construction.
    from traffic_anomaly.release_autoencoder import (
        ReleaseAEResult, ReleaseAEConfiguration, ReleaseAECalibration, ReleaseAERuntime)
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackageIdentity
    from traffic_anomaly.release_inputs import ReleaseInputIdentity
    from traffic_anomaly._release_minutes import ReleaseSegment
    p = hand_projection(view) if projection is None else projection
    c = hand_context(view) if context is None else context
    raw, prepared = ReleaseMinutePackageIdentity(**p['raw_identity']), ReleaseInputIdentity(**p['prepared_identity'])
    config = dict(p['configuration'])
    config['architecture'], config['adam_betas'] = tuple(config['architecture']), tuple(config['adam_betas'])
    values = dict(p, raw_identity=raw, prepared_identity=prepared,
                  configuration=ReleaseAEConfiguration(**config),
                  calibration=ReleaseAECalibration(**p['calibration']), runtime=ReleaseAERuntime(**p['runtime']))
    for name in ('feature_columns', 'scores', 'predictions', 'scored_mask', 'current_reconstruction_mse',
                 'history_deviation_reconstruction_mse', 'train_indices', 'calibration_indices',
                 'preprocessing_fit_indices', 'training_losses'):
        values[name] = tuple(values[name])
    declarations = {k: c[k] for k in ('configuration_sha256', 'source_schema_id', 'source_authentication',
                    'time_basis', 'policy_status', 'audit_fit_policy', 'minute_count')}
    declarations.update(raw_identity=ReleaseMinutePackageIdentity(**c['raw_identity']),
        prepared_identity=ReleaseInputIdentity(**c['prepared_identity']),
        segments=tuple(ReleaseSegment(s['id'], s['role'], datetime.fromisoformat(s['start']),
                                     datetime.fromisoformat(s['end'])) for s in c['segments']))
    return ReleaseAEResult(**values), api.ReleaseAEResultDeclarations(**declarations)


def _exact(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key in expected:
            _exact(actual[key], expected[key])
    elif type(expected) in (list, tuple):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            _exact(a, b)
    elif type(expected) is float:
        assert actual.hex() == expected.hex()
    else:
        assert actual == expected


def _wire(value):
    if is_dataclass(value):
        return {f.name: _wire(getattr(value, f.name)) for f in fields(value)}
    if type(value) is tuple:
        return [_wire(v) for v in value]
    return value


def _error(api, code, call):
    """Only native records escape except; foreign contexts never reach pytest."""
    record = (False, None, False, False)
    try:
        call()
    except BaseException as error:
        if type(error) is api.ReleaseAEResultPackageError:
            try:
                found = error.code
                args = error.args
                record = (True, found if type(found) is str else None,
                          type(args) is tuple and args == (code,), error.__suppress_context__ is True)
            except BaseException:
                record = (True, None, False, False)
    assert record == (True, code, True, True)


def _calibration_spy(api, monkeypatch):
    from traffic_anomaly.evaluation import calibration
    original = calibration.calibrate
    rows = []

    def calibrate(scores, quantile=.99):
        rows.append((tuple(float(v) for v in scores), quantile))
        return original(scores, quantile)

    monkeypatch.setattr(calibration, 'calibrate', calibrate)
    for name, value in tuple(vars(api).items()):
        if value is original:
            monkeypatch.setattr(api, name, calibrate)
    return rows


def _no_numerical_stage(api, monkeypatch):
    calls = []

    def forbidden():
        calls.append('dependencies')
        raise AssertionError('structural/context failure must precede dependency/Q99 stage')

    monkeypatch.setattr(api, '_dependencies', forbidden)
    return calls


class TestContract:
    @pytest.mark.parametrize('view', VIEWS)
    def test_hand_native_and_rebuilt_projection_have_exact_full_content(self, view, monkeypatch):
        api = _api()
        result, declarations = hand_native(api, view)
        selected = _calibration_spy(api, monkeypatch)
        rebuilt = api.decode_release_ae_result_projection(canonical(hand_projection(view)))
        assert selected == [((4., 4., 4., 4.), .99)]
        _exact(_wire(rebuilt), hand_projection(view))
        assert rebuilt is not result and rebuilt.raw_identity is not result.raw_identity
        selected.clear()
        package = api.make_release_ae_result_package(result, declarations)
        assert selected == [((4., 4., 4., 4.), .99)]
        assert len(fields(package.context)) == 14
        assert len(fields(package.result)) == 20 and len(fields(package.result.configuration)) == 30
        assert len(fields(declarations)) == 10
        assert set(_wire(rebuilt)) == set(RESULT_KEYS)
        assert set(json.loads(reference_members(view)['manifest.json'])['context']) == set(CONTEXT_KEYS)
        assert package.result.preprocessing_fit_indices == PREPROCESS
        assert package.result.scored_mask[30] is False
        assert package.result.threshold.hex() == '0x1.0000000000000p+2'
        assert package.result.scores[31].hex() == '-0x0.0p+0'
        assert package.result.predictions[32] is False and package.result.predictions[33] is True
        assert sum(package.result.scored_mask) == 7
        assert sum(v is None for v in package.result.scores) == 61
        if view == 'current13':
            assert package.result.history_deviation_reconstruction_mse == (None,) * 68
        else:
            assert package.result.current_reconstruction_mse[32] == 2.
            assert package.result.history_deviation_reconstruction_mse[32] == 6.

    @pytest.mark.parametrize('view', VIEWS)
    def test_four_public_successes_each_revalidate_once_and_match_hand_member_bytes(self, view, monkeypatch):
        api = _api()
        result, declarations = hand_native(api, view)
        selected = _calibration_spy(api, monkeypatch)
        projected = api.decode_release_ae_result_projection(canonical(hand_projection(view)))
        assert selected == [((4., 4., 4., 4.), .99)]
        selected.clear()
        package = api.make_release_ae_result_package(projected, declarations)
        assert selected == [((4., 4., 4., 4.), .99)]
        selected.clear()
        encoded = api.encode_release_ae_result_package(package)
        assert type(encoded) is tuple and tuple(n for n, _ in encoded) == MEMBERS
        assert dict(encoded) == reference_members(view)
        assert selected == [((4., 4., 4., 4.), .99)]
        selected.clear()
        loaded = api.decode_release_ae_result_package(reference_members(view))
        assert selected == [((4., 4., 4., 4.), .99)]
        _exact(_wire(loaded.result), hand_projection(view))
        expected_manifest = reference_members(view)['manifest.json']
        assert loaded.identity.manifest_sha256 == hashlib.sha256(expected_manifest).hexdigest()
        assert loaded.identity.manifest_byte_count == len(expected_manifest)
        assert loaded.identity.context_sha256 == hashlib.sha256(canonical(hand_context(view))).hexdigest()
        assert loaded.identity.profile_id == PACKAGE_PROFILE
        assert loaded.result is not projected and loaded.context is not package.context

    def test_load_report_is_limited_internal_identity_and_all_new_holders_are_immutable(self):
        api = _api()
        result, declarations = hand_native(api)
        package = api.make_release_ae_result_package(result, declarations)
        assert asdict(package.load_report) == dict(profile_id=LOAD_PROFILE,
            scope='SAVED_AE_RESULT_INTERNAL_CONSISTENCY_ONLY', byte_integrity='MATCHED',
            structure='MATCHED', saved_score_q99='MATCHED', input_declaration_binding='MATCHED',
            input_pair_binding='NOT_PERFORMED', derivation_replay='NOT_PERFORMED',
            source_authentication='NOT_AUTHENTICATED', model_execution='NOT_AUTHENTICATED')
        for value, name in ((declarations, 'minute_count'), (package, 'result'),
                            (package.identity, 'manifest_sha256'), (package.context, 'view'),
                            (package.load_report, 'scope'), (package.result, 'threshold')):
            assert not hasattr(value, '__dict__')
            with pytest.raises(FrozenInstanceError):
                setattr(value, name, None)
        assert type(package.context.segments) is tuple and type(package.result.scores) is tuple

    def test_package_revalidates_forged_identity_and_report_instead_of_trusting_holder(self, monkeypatch):
        api = _api()
        result, declarations = hand_native(api)
        package = api.make_release_ae_result_package(result, declarations)
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INTEGRITY_MISMATCH', lambda: api.encode_release_ae_result_package(
            replace(package, identity=replace(package.identity, manifest_sha256='f' * 64))))
        _error(api, 'INCONSISTENT_PACKAGE', lambda: api.encode_release_ae_result_package(
            replace(package, load_report=replace(package.load_report, model_execution='MATCHED'))))
        _error(api, 'INVALID_PACKAGE', lambda: api.encode_release_ae_result_package(
            replace(package, identity=asdict(package.identity))))
        assert calls == []

    @pytest.mark.parametrize('view', VIEWS)
    def test_projection_has_no_role_clock_or_reset_certificate_but_package_must_bind_it(self, view, monkeypatch):
        api = _api()
        p = hand_projection(view)
        # Move one training scored row to local0 while preserving every local
        # vector/index relationship and calibration scores. Projection can admit
        # this declaration; the context must reject its H30 reset for both views.
        for key in ('scores', 'predictions', 'scored_mask', 'current_reconstruction_mse',
                    'history_deviation_reconstruction_mse'):
            p[key][0], p[key][31] = p[key][31], p[key][0]
        p['train_indices'] = [0, 32, 33]
        p['preprocessing_fit_indices'] = [0, 30, 32, 33]
        selected = _calibration_spy(api, monkeypatch)
        result = api.decode_release_ae_result_projection(canonical(p))
        assert selected == [((4., 4., 4., 4.), .99)]
        _, declarations = hand_native(api, view)
        called = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INCONSISTENT_PACKAGE', lambda: api.make_release_ae_result_package(result, declarations))
        _error(api, 'INCONSISTENT_PACKAGE', lambda: api.decode_release_ae_result_package(
            reference_members(view, projection=p)))
        assert called == []

    @pytest.mark.parametrize('view', VIEWS)
    def test_wall_clock_gap_and_segment_shift_are_declarations_not_replay(self, view):
        api = _api()
        result, declarations = hand_native(api, view)
        segments = tuple(replace(s, start=s.start + timedelta(days=10),
                                 end=s.end + timedelta(days=10)) for s in declarations.segments)
        package = api.make_release_ae_result_package(result, replace(declarations, segments=segments))
        assert package.context.segments == segments
        assert package.result.scored_mask == result.scored_mask
        assert package.load_report.derivation_replay == 'NOT_PERFORMED'

    @pytest.mark.parametrize('view', VIEWS)
    @pytest.mark.parametrize('entry', ('make', 'encode', 'decode'))
    def test_all_contextual_entries_enforce_segment_reset_for_both_views(self, view, entry, monkeypatch):
        api = _api()
        result, declarations = hand_native(api, view)
        package = api.make_release_ae_result_package(result, declarations) if entry == 'encode' else None
        # Keep N68, but make the first segment35 and second33. Calibration64
        # now has local index29 and must fail even for current13.
        c = hand_context(view)
        c['segments'][0]['end'] = '2026-01-01T00:35:00'
        c['segments'][1]['end'] = '2026-01-01T02:33:00'
        _, bad_declarations = hand_native(api, view, context=c)
        calls = _no_numerical_stage(api, monkeypatch)
        if entry == 'make':
            call = lambda: api.make_release_ae_result_package(result, bad_declarations)
        elif entry == 'encode':
            bad_context = replace(package.context, segments=bad_declarations.segments)
            # Rebind the declared identity too, so stale SHA cannot conceal a
            # missing reset/role check in the encoder.
            members = reference_members(view, context=c)
            manifest = members['manifest.json']
            bad_identity = replace(package.identity,
                context_sha256=hashlib.sha256(canonical(c)).hexdigest(),
                manifest_sha256=hashlib.sha256(manifest).hexdigest(), manifest_byte_count=len(manifest))
            call = lambda: api.encode_release_ae_result_package(replace(
                package, context=bad_context, identity=bad_identity))
        else:
            call = lambda: api.decode_release_ae_result_package(reference_members(view, context=c))
        _error(api, 'INCONSISTENT_PACKAGE', call)
        assert calls == []

    @pytest.mark.parametrize('view', VIEWS)
    @pytest.mark.parametrize('index', (0, 29))
    def test_unscored_train_preprocessing_warmup_prefix_is_preserved(self, view, index, monkeypatch):
        api = _api()
        result, declarations = hand_native(api, view)
        warmup = replace(result, preprocessing_fit_indices=(index, *PREPROCESS))
        selected = _calibration_spy(api, monkeypatch)
        package = api.make_release_ae_result_package(warmup, declarations)
        assert package.result.preprocessing_fit_indices == (index, *PREPROCESS)
        assert package.result.scored_mask[index] is False
        assert package.result.scored_mask[30] is False
        assert package.result.train_indices == TRAIN
        assert selected == [((4., 4., 4., 4.), .99)]

    @pytest.mark.parametrize('entry', ('native', 'resealed'))
    def test_huge_legal_year_span_rejects_before_expansion_dependencies_or_q99(self, entry, monkeypatch):
        api = _api()
        c = hand_context()
        c['segments'] = [dict(ordinal=0, id='huge', role='train',
                             start='0001-01-01T00:00:00', end='9999-01-01T00:00:00')]
        result, declarations = hand_native(api, context=c)
        attempts = _no_numerical_stage(api, monkeypatch)
        expansions = []

        def no_expand(*args, **kwargs):
            expansions.append('expanded')
            raise AssertionError('huge date spans must not be traversed')

        monkeypatch.setattr(api, '_expand_axis', no_expand)
        call = (lambda: api.make_release_ae_result_package(result, declarations)) if entry == 'native' else (
            lambda: api.decode_release_ae_result_package(reference_members(context=c)))
        _error(api, 'RESOURCE_LIMIT', call)
        assert expansions == [] and attempts == []

    @pytest.mark.parametrize(('durations', 'expected'), [
        ((10001,), 'RESOURCE_LIMIT'), ((5000, 5001), 'RESOURCE_LIMIT'),
        ((34, 35), 'INCONSISTENT_PACKAGE'), ((33, 34), 'INCONSISTENT_PACKAGE'),
    ])
    def test_all_duration_totals_precede_any_axis_expansion(self, durations, expected, monkeypatch):
        api = _api()
        c = hand_context()
        start = datetime(2026, 1, 1)
        c['segments'] = []
        for i, minutes in enumerate(durations):
            end = start + timedelta(minutes=minutes)
            c['segments'].append(dict(ordinal=i, id='s' + str(i), role='train' if i == 0 else 'calibration',
                start=start.isoformat(timespec='seconds'), end=end.isoformat(timespec='seconds')))
            start = end
        attempts = _no_numerical_stage(api, monkeypatch)
        expansions = []
        monkeypatch.setattr(api, '_expand_axis', lambda *a, **k: expansions.append('expanded'))
        _error(api, expected, lambda: api.decode_release_ae_result_package(reference_members(context=c)))
        assert attempts == [] and expansions == []

    def test_exact_10000_duration_is_admitted_without_off_by_one_resource_failure(self):
        api = _api()
        p, c = hand_projection(), hand_context()
        extra = 10000 - 68
        for key in ('scores', 'predictions', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse'):
            p[key].extend([None] * extra)
        p['scored_mask'].extend([False] * extra)
        c['minute_count'] = 10000
        c['segments'][1]['end'] = '2026-01-08T00:06:00'  # 9966min after Jan1 02:00; +34=10000.
        package = api.decode_release_ae_result_package(reference_members(projection=p, context=c))
        assert len(package.result.scores) == 10000 and sum(package.result.scored_mask) == 7

    def test_vector_n_over_cap_rejects_before_axis_or_dependencies(self, monkeypatch):
        api = _api()
        p = hand_projection()
        for name in ('scores', 'predictions', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse'):
            p[name].extend([None] * (10001 - 68))
        p['scored_mask'].extend([False] * (10001 - 68))
        calls = _no_numerical_stage(api, monkeypatch)
        expansions = []
        monkeypatch.setattr(api, '_expand_axis', lambda *a, **k: expansions.append('expanded'))
        _error(api, 'RESOURCE_LIMIT', lambda: api.decode_release_ae_result_projection(canonical(p)))
        assert calls == [] and expansions == []

    @pytest.mark.parametrize(('change', 'code'), [
        (lambda p: p.update(extra=None), 'INVALID_PACKAGE'),
        (lambda p: p.pop('runtime'), 'INVALID_PACKAGE'),
        (lambda p: p.update(profile_id='unknown'), 'INCOMPATIBLE_PACKAGE'),
        (lambda p: p.update(scope='AUTHENTICATED'), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(view='h15_26'), 'INCOMPATIBLE_PACKAGE'),
        (lambda p: p.update(threshold=4), 'INVALID_PACKAGE'),
        (lambda p: p['scored_mask'].__setitem__(31, 1), 'INVALID_PACKAGE'),
        (lambda p: p['scores'].__setitem__(31, False), 'INVALID_PACKAGE'),
        (lambda p: p['scores'].__setitem__(31, -1.), 'INVALID_PACKAGE'),
        (lambda p: p['scores'].__setitem__(31, None), 'INCONSISTENT_PACKAGE'),
        (lambda p: p['scores'].__setitem__(0, 0.), 'INCONSISTENT_PACKAGE'),
        (lambda p: p['current_reconstruction_mse'].__setitem__(0, 0.), 'INCONSISTENT_PACKAGE'),
        (lambda p: p['history_deviation_reconstruction_mse'].__setitem__(31, 0.), 'INCONSISTENT_PACKAGE'),
        (lambda p: p['predictions'].__setitem__(31, 0), 'INVALID_PACKAGE'),
        (lambda p: p['predictions'].__setitem__(32, True), 'INCONSISTENT_PACKAGE'),
        (lambda p: p['predictions'].__setitem__(33, False), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(train_indices=[]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(calibration_indices=[]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(train_indices=[31, 31]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(train_indices=[32, 31]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(train_indices=[True]), 'INVALID_PACKAGE'),
        (lambda p: p.update(train_indices=[31.]), 'INVALID_PACKAGE'),
        (lambda p: p.update(train_indices=[-1]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(train_indices=[68]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(train_indices=[30]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(calibration_indices=[31, 64, 65, 66]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(preprocessing_fit_indices=[30, 31, 32]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(scores=p['scores'][:-1]), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(training_losses=[.5] * 4), 'INCONSISTENT_PACKAGE'),
        (lambda p: p.update(training_losses=[.5] * 6), 'INCONSISTENT_PACKAGE'),
        (lambda p: p['training_losses'].__setitem__(0, -.1), 'INVALID_PACKAGE'),
        (lambda p: p['feature_columns'].reverse(), 'INCONSISTENT_PACKAGE'),
        (lambda p: p['raw_identity'].update(manifest_byte_count=True), 'INVALID_PACKAGE'),
        (lambda p: p['raw_identity'].update(manifest_byte_count=65537), 'RESOURCE_LIMIT'),
        (lambda p: p.update(configuration_sha256='G' * 64), 'INVALID_PACKAGE'),
    ])
    def test_projection_native_types_and_local_semantics(self, change, code, monkeypatch):
        api = _api()
        p = hand_projection()
        change(p)
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, code, lambda: api.decode_release_ae_result_projection(canonical(p)))
        assert calls == []

    @pytest.mark.parametrize(('change', 'code'), [
        (lambda c: c.update(extra=None), 'INVALID_PACKAGE'),
        (lambda c: c.update(profile_id='wrong'), 'INCOMPATIBLE_PACKAGE'),
        (lambda c: c.update(result_profile_id='wrong'), 'INCOMPATIBLE_PACKAGE'),
        (lambda c: c.update(source_schema_id='invented'), 'INCOMPATIBLE_PACKAGE'),
        (lambda c: c.update(source_authentication='AUTHENTICATED'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c.update(time_basis='UTC'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c.update(policy_status='PRODUCTION'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c.update(audit_fit_policy='P_X'), 'INVALID_PACKAGE'),
        (lambda c: c.update(score_direction='NEGATIVE_SCORE_SAMPLES'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c.update(minute_count=True), 'INVALID_PACKAGE'),
        (lambda c: c.update(minute_count=67), 'INCONSISTENT_PACKAGE'),
        (lambda c: c.update(minute_count=10001), 'RESOURCE_LIMIT'),
        (lambda c: c['segments'][0].update(ordinal=True), 'INVALID_PACKAGE'),
        (lambda c: c['segments'][0].update(ordinal=1), 'INCONSISTENT_PACKAGE'),
        (lambda c: c['segments'][0].update(id=''), 'INVALID_PACKAGE'),
        (lambda c: c['segments'][0].update(id='x' * 129), 'RESOURCE_LIMIT'),
        (lambda c: c['segments'][0].update(id='x\x7f'), 'INVALID_PACKAGE'),
        (lambda c: c['segments'][1].update(id='train'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c['segments'][0].update(role='calibration'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c['segments'][1].update(role='train'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c['segments'][0].update(start='2026-02-30T00:00:00'), 'INVALID_PACKAGE'),
        (lambda c: c['segments'][0].update(start='2026-01-01T00:00:01'), 'INVALID_PACKAGE'),
        (lambda c: c['segments'][0].update(start='2026-01-01T00:00:00+00:00'), 'INVALID_PACKAGE'),
        (lambda c: c['segments'][0].update(end='2026-01-01T00:00:00'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c['segments'][1].update(start='2026-01-01T00:33:00'), 'INCONSISTENT_PACKAGE'),
        (lambda c: c.update(segments=[]), 'INCONSISTENT_PACKAGE'),
        (lambda c: c.update(segments=c['segments'] * 4), 'RESOURCE_LIMIT'),
    ])
    def test_resealed_context_rejects_before_numerical_dependency(self, change, code, monkeypatch):
        api = _api()
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, code, lambda: api.decode_release_ae_result_package(reseal(context_change=change)))
        assert calls == []

    @pytest.mark.parametrize('field', ('raw_identity', 'prepared_identity', 'configuration_sha256'))
    def test_result_context_reference_binding_cannot_be_resealed_away(self, field, monkeypatch):
        api = _api()
        def change(c):
            if field == 'configuration_sha256':
                c[field] = 'f' * 64
            else:
                c[field]['manifest_sha256'] = 'f' * 64
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INPUT_BINDING_MISMATCH', lambda: api.decode_release_ae_result_package(
            reseal(context_change=change)))
        assert calls == []

    @pytest.mark.parametrize(('field', 'value', 'code'), [
        ('epochs', 4, 'INCONSISTENT_PACKAGE'), ('epochs', True, 'INVALID_PACKAGE'),
        ('parameter_count', 492, 'INCONSISTENT_PACKAGE'), ('history_window', 15, 'INCONSISTENT_PACKAGE'),
        ('shuffle', 0, 'INVALID_PACKAGE'), ('architecture', [13, 14, 3, 14, 13], 'INCONSISTENT_PACKAGE'),
        ('learning_rate', .01, 'INCONSISTENT_PACKAGE'), ('learning_rate', 1, 'INVALID_PACKAGE'),
        ('weight_decay', -0., 'INCONSISTENT_PACKAGE'), ('preprocessing_fit_provenance', 'REFIT', 'INCONSISTENT_PACKAGE'),
    ])
    def test_full_profile_types_and_float_bits_are_prescribed(self, field, value, code, monkeypatch):
        api = _api()
        p = hand_projection()
        p['configuration'][field] = value
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, code, lambda: api.decode_release_ae_result_package(reference_members(projection=p)))
        assert calls == []

    @pytest.mark.parametrize(('field', 'value', 'code'), [
        ('python_version', '3.13.9', 'INCONSISTENT_PACKAGE'),
        ('numpy_version', '2.5.3', 'INCONSISTENT_PACKAGE'),
        ('torch_version', '2.14.1+cu128', 'INCONSISTENT_PACKAGE'),
        ('device', 'cuda', 'INCONSISTENT_PACKAGE'),
        ('torch_num_threads', True, 'INVALID_PACKAGE'),
        ('torch_num_threads', 0, 'INVALID_PACKAGE'),
        ('torch_num_interop_threads', 65, 'RESOURCE_LIMIT'),
    ])
    def test_saved_runtime_is_checked_as_data_without_loading_torch(self, field, value, code, monkeypatch):
        api = _api()
        p = hand_projection()
        p['runtime'][field] = value
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, code, lambda: api.decode_release_ae_result_projection(canonical(p)))
        assert calls == []

    @pytest.mark.parametrize('view', VIEWS)
    @pytest.mark.parametrize('channel', ('current_reconstruction_mse', 'history_deviation_reconstruction_mse'))
    def test_channel_inconsistency_is_not_hidden_by_valid_scores_and_sha(self, view, channel, monkeypatch):
        api = _api()
        p = hand_projection(view)
        p[channel][32] = 3.
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INCONSISTENT_PACKAGE', lambda: api.decode_release_ae_result_package(
            reference_members(view, projection=p)))
        assert calls == []

    def test_h30_equal_weight_rule_does_not_overflow_by_adding_channels_first(self):
        api = _api()
        p = hand_projection('h30_26')
        # Both half-products and their sum are finite. Adding the channels
        # before halving would overflow and reject this valid stored result.
        for key in ('scores', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse'):
            p[key][33] = 1.7e308
        package = api.decode_release_ae_result_package(reference_members('h30_26', projection=p))
        assert package.result.scores[33].hex() == (1.7e308).hex()
        assert package.result.predictions[33] is True

    @pytest.mark.parametrize('field', ('scores', 'current_reconstruction_mse', 'training_losses'))
    @pytest.mark.parametrize('value', (math.nan, math.inf, -math.inf))
    def test_native_nonfinite_values_reject_without_json_coercion(self, field, value, monkeypatch):
        api = _api()
        result, declarations = hand_native(api)
        index = 0 if field == 'training_losses' else 31
        values = getattr(result, field)
        bad = replace(result, **{field: values[:index] + (value,) + values[index + 1:]})
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INVALID_PACKAGE', lambda: api.make_release_ae_result_package(bad, declarations))
        assert calls == []

    @pytest.mark.parametrize('value', (math.nan, math.inf, -math.inf))
    def test_h30_native_nonfinite_history_is_rejected(self, value, monkeypatch):
        api = _api()
        result, declarations = hand_native(api, 'h30_26')
        values = result.history_deviation_reconstruction_mse
        bad = replace(result, history_deviation_reconstruction_mse=values[:31] + (value,) + values[32:])
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INVALID_PACKAGE', lambda: api.make_release_ae_result_package(bad, declarations))
        assert calls == []

    @pytest.mark.parametrize('threshold', (4.000000000000001, 4.000000000000002))
    def test_resealed_threshold_must_match_own_q99_bits(self, threshold, monkeypatch):
        api = _api()
        selected = _calibration_spy(api, monkeypatch)
        def change(p):
            p['threshold'] = threshold
            p['calibration']['equal_count'] = 0
        _error(api, 'INCONSISTENT_PACKAGE', lambda: api.decode_release_ae_result_package(reseal(
            result_change=change)))
        # Both wrong thresholds leave every stored strict prediction unchanged;
        # only recomputing this result's own Q99 can expose the wrong bits.
        assert selected == [((4., 4., 4., 4.), .99)]

    @pytest.mark.parametrize(('field', 'value'), [('sample_count', 3), ('equal_count', 3),
        ('strictly_above_count', 1), ('quantile', .95), ('method', 'nearest'), ('comparison', 'GREATER_EQUAL')])
    def test_calibration_declaration_is_not_a_trusted_certificate(self, field, value, monkeypatch):
        api = _api()
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INCONSISTENT_PACKAGE', lambda: api.decode_release_ae_result_package(reseal(
            result_change=lambda p: p['calibration'].update({field: value}))))
        assert calls == []

    @pytest.mark.parametrize('view', VIEWS)
    @pytest.mark.parametrize('singleton', (False, True))
    def test_equal_zero_and_singleton_calibration_preserve_strict_prediction_semantics(self, view, singleton):
        api = _api()
        p = hand_projection(view)
        p['threshold'] = 0.
        p['calibration_indices'] = [64] if singleton else list(CAL)
        for i in CAL:
            p['scores'][i] = 0.
            p['current_reconstruction_mse'][i] = 0.
            if view == 'h30_26':
                p['history_deviation_reconstruction_mse'][i] = 0.
        p['predictions'] = [None if s is None else s > 0. for s in p['scores']]
        p['calibration'].update(sample_count=1 if singleton else 4,
                                equal_count=1 if singleton else 4, strictly_above_count=0)
        loaded = api.decode_release_ae_result_package(reference_members(view, projection=p))
        assert loaded.result.threshold.hex() == '0x0.0p+0'
        assert loaded.result.predictions[31] is False
        assert loaded.result.predictions[33] is True

    @pytest.mark.parametrize('value', (math.nan, math.inf, -math.inf, -1., 4, True))
    def test_closed_bad_calibrator_return_is_finite_failure_not_model_work(self, value, monkeypatch):
        api = _api()
        import numpy as np
        selected = []
        def bad(scores, quantile=.99):
            selected.append((tuple(float(v) for v in scores), quantile))
            return value
        monkeypatch.setattr(api, '_dependencies', lambda: (np, bad))
        _error(api, 'INCONSISTENT_PACKAGE', lambda: api.decode_release_ae_result_projection(canonical(hand_projection())))
        assert selected == [((4., 4., 4., 4.), .99)]

    @pytest.mark.parametrize('member', MEMBERS)
    def test_duplicate_noncanonical_and_wrong_envelope_json_reject(self, member):
        api = _api()
        members = reference_members()
        payload = members[member]
        duplicate = payload.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1')
        members = replace_member_bytes(members, member, duplicate)
        _error(api, 'INVALID_PACKAGE', lambda: api.decode_release_ae_result_package(members))

    @pytest.mark.parametrize('style', ('no_lf', 'extra_lf', 'spaces', 'unsorted'))
    def test_valid_projection_requires_canonical_bytes_not_just_equal_decoded_values(self, style, monkeypatch):
        api = _api()
        p = hand_projection()
        payload = canonical(p)
        if style == 'no_lf':
            payload = payload[:-1]
        elif style == 'extra_lf':
            payload += b'\n'
        elif style == 'spaces':
            payload = (json.dumps(p, sort_keys=True, separators=(', ', ': ')) + '\n').encode()
        else:
            payload = (json.dumps(p, separators=(',', ':')) + '\n').encode()
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INVALID_PACKAGE', lambda: api.decode_release_ae_result_projection(payload))
        assert calls == []

    @pytest.mark.parametrize('member', MEMBERS)
    @pytest.mark.parametrize(('field', 'value', 'code'), [('schema_version', True, 'INVALID_PACKAGE'),
        ('schema_version', 2, 'INCOMPATIBLE_PACKAGE'), ('profile_id', 'wrong', 'INCOMPATIBLE_PACKAGE'),
        ('extra', None, 'INVALID_PACKAGE')])
    def test_resealed_member_envelopes_have_fixed_keys_native_version_and_profile(self, member, field, value, code):
        api = _api()
        members = reference_members()
        envelope = json.loads(members[member])
        envelope[field] = value
        members = replace_member_bytes(members, member, canonical(envelope))
        _error(api, code, lambda: api.decode_release_ae_result_package(members))

    @pytest.mark.parametrize('payload', [b'{}', b'{}\n\n', b'\xef\xbb\xbf{}\n', b'\xff\n',
        b'{"a":NaN}\n', b'{"a":Infinity}\n', b'{"a":1e999}\n', b'{"a":123456789}\n',
        b'{"a":0.123456789012345678901234567890123}\n', b'[' * 17 + b'0' + b']' * 17 + b'\n'])
    def test_projection_json_lexical_failures_are_finite(self, payload, monkeypatch):
        api = _api()
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INVALID_PACKAGE', lambda: api.decode_release_ae_result_projection(payload))
        assert calls == []

    @pytest.mark.parametrize('field', ('threshold', 'runtime', 'configuration'))
    def test_duplicate_keys_inside_projection_are_rejected_before_dependencies(self, field, monkeypatch):
        api = _api()
        payload = canonical(hand_projection())
        if field == 'threshold':
            payload = payload.replace(b'"threshold":4.0', b'"threshold":4.0,"threshold":4.0')
        elif field == 'runtime':
            payload = payload.replace(b'"torch_num_threads":2', b'"torch_num_threads":2,"torch_num_threads":2')
        else:
            payload = payload.replace(b'"epochs":5', b'"epochs":5,"epochs":5')
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INVALID_PACKAGE', lambda: api.decode_release_ae_result_projection(payload))
        assert calls == []

    def test_decoded_string_budget_precedes_field_semantics_and_numerical_work(self, monkeypatch):
        api = _api()
        p = hand_projection()
        p['runtime']['python_version'] = 'x' * 257
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'RESOURCE_LIMIT', lambda: api.decode_release_ae_result_projection(canonical(p)))
        assert calls == []

    def test_quoted_brackets_escapes_and_unicode_segment_ids_do_not_change_depth(self):
        api = _api()
        context = hand_context()
        context['segments'][0]['id'] = '引号"\\[[]]合法'
        package = api.decode_release_ae_result_package(reference_members(context=context))
        assert package.context.segments[0].id == '引号"\\[[]]合法'

    @pytest.mark.parametrize('entry', ('projection', *MEMBERS))
    def test_byte_caps_precede_json_parsing_and_numerical_work(self, entry, monkeypatch):
        api = _api()
        calls = _no_numerical_stage(api, monkeypatch)
        limit = 2097152 if entry == 'projection' else LIMITS[MEMBERS.index(entry)]
        payload = b'x' * (limit + 1)
        if entry == 'projection':
            call = lambda: api.decode_release_ae_result_projection(payload)
        else:
            members = reference_members()
            members[entry] = payload
            call = lambda: api.decode_release_ae_result_package(members)
        _error(api, 'RESOURCE_LIMIT', call)
        assert calls == []

    @pytest.mark.parametrize('argument', (None, [], {}, bytearray(b'{}\n'), memoryview(b'{}\n')))
    def test_projection_requires_exact_bytes(self, argument):
        api = _api()
        _error(api, 'INVALID_PACKAGE_ARGUMENTS', lambda: api.decode_release_ae_result_projection(argument))

    def test_exact_containers_strings_and_holders_reject_foreign_coercion(self, monkeypatch):
        api = _api()
        result, declarations = hand_native(api)
        touched = []
        class Foreign:
            def __str__(self):
                touched.append('str')
                raise RuntimeError('private text')
            def __iter__(self):
                touched.append('iter')
                raise RuntimeError('private iterator')
            @property
            def __class__(self):
                touched.append('__class__')
                raise RuntimeError('private class')
        class Text(str):
            pass
        class Sequence(tuple):
            pass
        calls = _no_numerical_stage(api, monkeypatch)
        for bad in (Foreign(), asdict(result)):
            _error(api, 'INVALID_PACKAGE', lambda: api.make_release_ae_result_package(bad, declarations))
        for bad in (replace(result, view=Text('current13')), replace(result, train_indices=Sequence(TRAIN)),
                    replace(result, configuration_sha256=Foreign())):
            _error(api, 'INVALID_PACKAGE', lambda: api.make_release_ae_result_package(bad, declarations))
        _error(api, 'INVALID_PACKAGE', lambda: api.make_release_ae_result_package(result, Foreign()))
        assert touched == [] and calls == []

    def test_missing_native_slots_reject_before_foreign_getters_or_q99(self, monkeypatch):
        api = _api()
        result, declarations = hand_native(api)
        incomplete = object.__new__(type(result))
        for f in fields(result):
            if f.name != 'runtime':
                object.__setattr__(incomplete, f.name, getattr(result, f.name))
        calls = _no_numerical_stage(api, monkeypatch)
        _error(api, 'INVALID_PACKAGE', lambda: api.make_release_ae_result_package(incomplete, declarations))
        assert calls == []

    @pytest.mark.parametrize('argument', (None, [], {}, {'other': b'{}\n'}))
    def test_member_inventory_arguments_are_exact(self, argument):
        api = _api()
        _error(api, 'INVALID_PACKAGE_ARGUMENTS', lambda: api.decode_release_ae_result_package(argument))

    @pytest.mark.parametrize('member', MEMBERS)
    def test_member_payload_types_and_unknown_members_are_rejected(self, member):
        api = _api()
        members = reference_members()
        members[member] = bytearray(members[member])
        _error(api, 'INVALID_PACKAGE_ARGUMENTS', lambda: api.decode_release_ae_result_package(members))
        members = reference_members()
        members['extra.json'] = b'{}\n'
        _error(api, 'INVALID_PACKAGE_ARGUMENTS', lambda: api.decode_release_ae_result_package(members))

    def test_actual_member_bytes_are_hashed_and_not_silently_resealed(self):
        api = _api()
        members = reference_members()
        members['result.json'] = members['result.json'].replace(b'"threshold":4.0', b'"threshold":5.0')
        _error(api, 'INTEGRITY_MISMATCH', lambda: api.decode_release_ae_result_package(members))

    @pytest.mark.parametrize('code', CODES)
    def test_error_constructor_owns_a_finite_native_code_without_external_text(self, code):
        api = _api()
        error = api.ReleaseAEResultPackageError(code)
        assert type(error.code) is str and error.code == code
        assert error.args == (code,) and str(error) == code

    def test_unknown_error_constructor_never_coerces_foreign_or_string_subclass(self):
        api = _api()
        touched = []
        class Text(str):
            def __eq__(self, other):
                touched.append('eq')
                raise RuntimeError('private comparison')
            __hash__ = str.__hash__
        class Foreign:
            def __str__(self):
                touched.append('str')
                raise RuntimeError('private text')
        for value in (None, [], True, 'PRIVATE', Text('RESOURCE_LIMIT'), Foreign()):
            error = api.ReleaseAEResultPackageError(value)
            assert error.code == 'PACKAGE_ERROR' and error.args == ('PACKAGE_ERROR',)
        assert touched == []

    @pytest.mark.parametrize(('name', 'code'), [('numpy', 'NUMERICAL_DEPENDENCY_UNAVAILABLE'),
        ('unrelated', 'PACKAGE_ERROR'), (None, 'PACKAGE_ERROR')])
    def test_exact_missing_numpy_name_is_classified_without_real_missing_import(self, name, code, monkeypatch):
        api = _api()
        failure = ModuleNotFoundError('private dependency', name=name)
        def missing():
            raise failure
        monkeypatch.setattr(api, '_dependencies', missing)
        _error(api, code, lambda: api.decode_release_ae_result_projection(canonical(hand_projection())))

    def test_hostile_missing_module_name_is_not_compared_or_coerced(self, monkeypatch):
        api = _api()
        touched = []
        class Name:
            def __eq__(self, other):
                touched.append('eq')
                raise RuntimeError('private equality')
            def __str__(self):
                touched.append('str')
                raise RuntimeError('private string')
        failure = ModuleNotFoundError('private dependency', name=Name())
        def missing():
            raise failure
        monkeypatch.setattr(api, '_dependencies', missing)
        _error(api, 'PACKAGE_ERROR', lambda: api.decode_release_ae_result_projection(canonical(hand_projection())))
        assert touched == []

    def test_missing_module_subclass_name_getter_is_not_read(self, monkeypatch):
        api = _api()
        touched = []
        class ForeignMissing(ModuleNotFoundError):
            @property
            def name(self):
                touched.append('name')
                raise RuntimeError('private missing name')
            @name.setter
            def name(self, value):
                pass
        primary = ForeignMissing('private dependency')
        def failing():
            raise primary
        monkeypatch.setattr(api, '_dependencies', failing)
        _error(api, 'PACKAGE_ERROR', lambda: api.decode_release_ae_result_projection(canonical(hand_projection())))
        assert touched == []

    def test_wrong_current_numpy_version_rejects_before_saved_q99(self, monkeypatch):
        api = _api()
        import numpy as np
        selected = _calibration_spy(api, monkeypatch)
        monkeypatch.setattr(np, '__version__', '2.5.3')
        _error(api, 'INCOMPATIBLE_RUNTIME', lambda: api.decode_release_ae_result_projection(canonical(hand_projection())))
        assert selected == []

    def test_foreign_exception_class_and_code_getters_are_never_inspected(self, monkeypatch):
        api = _api()
        touched = []
        class Foreign(Exception):
            @property
            def __class__(self):
                touched.append('__class__')
                raise RuntimeError('private class lookup')
            @property
            def code(self):
                touched.append('code')
                raise RuntimeError('private code lookup')
        def failing():
            raise Foreign('private message')
        monkeypatch.setattr(api, '_dependencies', failing)
        _error(api, 'PACKAGE_ERROR', lambda: api.decode_release_ae_result_projection(canonical(hand_projection())))
        assert touched == []

    @pytest.mark.parametrize('kind', ('memory', 'keyboard', 'exit'))
    def test_real_resource_and_interrupt_subclasses_keep_type_based_semantics(self, kind, monkeypatch):
        api = _api()
        base = {'memory': MemoryError, 'keyboard': KeyboardInterrupt, 'exit': SystemExit}[kind]
        class Actual(base):
            @property
            def __class__(self):
                raise RuntimeError('actual classification must use type inheritance')
        primary = Actual('private received failure')
        def failing():
            raise primary
        monkeypatch.setattr(api, '_dependencies', failing)
        call = lambda: api.decode_release_ae_result_projection(canonical(hand_projection()))
        if kind == 'memory':
            _error(api, 'RESOURCE_LIMIT', call)
        else:
            same = False
            try:
                call()
            except BaseException as received:
                same = received is primary
            assert same is True

    def test_exact_owned_error_code_is_read_once_and_unknown_or_subclass_is_sanitized(self, monkeypatch):
        api = _api()
        owner = api.ReleaseAEResultPackageError
        reads = []
        original_getattribute = owner.__getattribute__
        def observe(self, name):
            if name == 'code':
                reads.append('code')
            return original_getattribute(self, name)
        primary = owner('INCOMPATIBLE_RUNTIME')
        def failing():
            raise primary
        monkeypatch.setattr(api, '_dependencies', failing)
        # Attribute only reads performed during the public call. A safe same
        # owner may be rethrown, so snapshot before inspecting received.code.
        def primary_only(self, name):
            if self is primary:
                return observe(self, name)
            return original_getattribute(self, name)
        monkeypatch.setattr(owner, '__getattribute__', primary_only)
        library_reads = None
        record = (False, None, False, False)
        try:
            api.decode_release_ae_result_projection(canonical(hand_projection()))
        except BaseException as received:
            library_reads = tuple(reads)
            if type(received) is owner:
                try:
                    code, args = received.code, received.args
                    record = (True, code if type(code) is str else None,
                              type(args) is tuple and args == ('INCOMPATIBLE_RUNTIME',),
                              received.__suppress_context__ is True)
                except BaseException:
                    record = (True, None, False, False)
        assert library_reads == ('code',)
        assert record == (True, 'INCOMPATIBLE_RUNTIME', True, True)
        class Child(owner):
            @property
            def code(self):
                raise RuntimeError('subclass code must not be read')
            @code.setter
            def code(self, value):
                pass
        primary_child = Child('RESOURCE_LIMIT')
        def child_failure():
            raise primary_child
        monkeypatch.setattr(api, '_dependencies', child_failure)
        _error(api, 'PACKAGE_ERROR', lambda: api.decode_release_ae_result_projection(canonical(hand_projection())))

    @pytest.mark.parametrize('kind', ('ordinary', 'memory', 'keyboard', 'exit'))
    def test_owning_code_getter_failure_is_protected_and_read_only_once(self, kind, monkeypatch):
        api = _api()
        owner = api.ReleaseAEResultPackageError
        primary = owner('OUTPUT_ERROR')
        failure = {'ordinary': RuntimeError, 'memory': MemoryError,
                   'keyboard': KeyboardInterrupt, 'exit': SystemExit}[kind]('private getter')
        original = owner.__getattribute__
        reads = []
        def guarded(self, name):
            if self is primary and name == 'code':
                reads.append('code')
                raise failure
            return original(self, name)
        def failing():
            raise primary
        monkeypatch.setattr(owner, '__getattribute__', guarded)
        monkeypatch.setattr(api, '_dependencies', failing)
        call = lambda: api.decode_release_ae_result_projection(canonical(hand_projection()))
        if kind in ('ordinary', 'memory'):
            _error(api, 'PACKAGE_ERROR' if kind == 'ordinary' else 'RESOURCE_LIMIT', call)
        else:
            same = False
            try:
                call()
            except BaseException as received:
                same = received is failure
            assert same is True
        assert reads == ['code']

    def test_pure_success_never_calls_producer_input_admission_preparation_or_files(self, monkeypatch):
        api = _api()
        result, declarations = hand_native(api)
        from traffic_anomaly import release_autoencoder, release_inputs
        attempts = []
        def forbidden(*args, **kwargs):
            attempts.append('execution')
            raise AssertionError('codec cannot execute producer/preparation or open source files')
        for name in ('fit_release_autoencoder', '_admit', '_numeric_operation', '_build_network', '_load_torch'):
            monkeypatch.setattr(release_autoencoder, name, forbidden)
        for name in ('prepare_release_inputs', '_fit_state', '_fit_statistics', '_transform',
                     '_history', 'verify_release_input_derivation'):
            monkeypatch.setattr(release_inputs, name, forbidden)
        # Warm only the explicitly permitted numerical dependency before file
        # denial; no producer/model object is constructed for this preparation.
        from traffic_anomaly.evaluation import calibration
        monkeypatch.setattr(builtins, 'open', forbidden)
        package = api.make_release_ae_result_package(result, declarations)
        loaded = api.decode_release_ae_result_package(dict(api.encode_release_ae_result_package(package)))
        _exact(_wire(loaded.result), hand_projection())
        assert attempts == []

    def test_module_reload_is_in_process_stdlib_fenced_not_cold_process(self, monkeypatch):
        api = _api()
        old_import, old_dynamic = builtins.__import__, importlib.import_module
        attempts = []
        def check(name):
            if name.split('.')[0] in {'numpy', 'torch', 'sklearn', 'joblib'} or (
                    name.startswith('traffic_anomaly.') and name != MODULE):
                attempts.append(name)
                raise AssertionError('contract import must remain stdlib only')
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
            return old_import(name, globals, locals, fromlist, level)
        def dynamic(name, package=None):
            full = importlib.util.resolve_name(name, package) if name.startswith('.') else name
            check(full)
            return old_dynamic(name, package)
        product_before = {n: m for n, m in sys.modules.items() if n.startswith('traffic_anomaly.')}
        with monkeypatch.context() as guard:
            guard.setattr(sys, 'meta_path', [Fence(), *sys.meta_path])
            guard.setattr(builtins, '__import__', guarded)
            guard.setattr(importlib, 'import_module', dynamic)
            assert importlib.reload(api) is api
        product_after = {n: m for n, m in sys.modules.items() if n.startswith('traffic_anomaly.')}
        assert product_after.keys() == product_before.keys()
        assert all(product_after[n] is m for n, m in product_before.items())
        assert attempts == []
