"""Manual admission semantics: hand inputs and a closed non-model numeric boundary.

No real Torch/network/optimizer/forward/backward is permitted. Successful fits in
this class perform one real hand-score calibration each; that is manual NumPy
arithmetic, not actual model Q99 evidence. Cold-process proof is NOT_RUN.
"""
import builtins
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import importlib
import importlib.abc
import importlib.util
import math
import sys

import pytest


MODULE = 'traffic_anomaly.release_autoencoder'
COMMON55 = (*range(31, 48), *range(78, 88), *range(118, 128), *range(158, 176))
TRAIN17 = tuple(range(31, 48))
CAL4 = (124, 125, 126, 127)
PREPROCESS18 = tuple(range(30, 48))
ERROR_CODES = (
    'INVALID_AE_ARGUMENTS', 'INVALID_AE_INPUT', 'RESOURCE_LIMIT',
    'NO_TRAINING_NORMAL', 'NO_CALIBRATION_NORMAL', 'INVALID_INPUT_NUMERIC',
    'INCOMPATIBLE_RUNTIME', 'MODEL_UNAVAILABLE', 'MODEL_ERROR',
    'INVALID_MODEL_STATE', 'NONFINITE_TRAINING', 'INVALID_MODEL_SCORES',
    'RNG_RESTORATION_FAILED', 'AE_ERROR',
)


def _api():
    # Missing feature is a test failure, not a collection-time import error.
    if importlib.util.find_spec(MODULE) is None:
        pytest.fail('release_autoencoder public fit interface is not implemented')
    api = importlib.import_module(MODULE)
    assert callable(getattr(api, 'fit_release_autoencoder', None)), 'public fit interface is missing'
    return api


def _safe_error(api, code, call):
    with pytest.raises(api.ReleaseAEError) as caught:
        call()
    assert type(caught.value) is api.ReleaseAEError
    assert type(caught.value.code) is str and caught.value.code == code
    assert caught.value.args == (code,) and str(caught.value) == code
    assert caught.value.__suppress_context__ is True


def _set(values, index, value):
    return values[:index] + (value,) + values[index + 1:]


def _forged(value, **changes):
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


def _configuration(view):
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


def _exact_tree(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key in expected:
            _exact_tree(actual[key], expected[key])
    elif type(expected) in (tuple, list):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            _exact_tree(left, right)
    elif type(expected) is float:
        assert actual.hex() == expected.hex()
    else:
        assert actual == expected


def _numeric_double(api, monkeypatch, view, *, failure=None):
    """Replace only numerical/model execution; admission and calibration stay real.

    The private context yields common-axis channels/losses/runtime, never a pair,
    label sidecar or completed public result. Four equal calibration scores4 have
    hand-derived Q99=4 exactly; no expected quantile is computed by the product.
    """
    import numpy as np
    from traffic_anomaly.evaluation import calibration

    assert callable(getattr(api, '_numeric_operation', None)), 'closed numeric boundary is missing'
    seen = dict(events=[], values=[], configurations=[], selected=[], payloads=[])
    original_calibrate = calibration.calibrate

    def calibrate(scores, quantile=.99):
        seen['events'].append('calibrate')
        seen['selected'].append((tuple(float(value) for value in scores), quantile))
        return original_calibrate(scores, quantile)

    monkeypatch.setattr(calibration, 'calibrate', calibrate)

    @contextmanager
    def numeric(values, configuration):
        seen['events'].append('numeric-enter')
        seen['values'].append(values)
        seen['configurations'].append(configuration)
        if failure is not None:
            raise failure
        current = np.asarray([float(index % 7) for index in COMMON55], dtype=np.float64)
        history = np.full(55, np.nan, dtype=np.float64)
        if view == 'h30_26':
            history = current + 2.
        for position, index in enumerate(COMMON55):
            if index in CAL4:
                current[position] = 4. if view == 'current13' else 2.
                if view == 'h30_26':
                    history[position] = 6.
        scores = current.copy() if view == 'current13' else .5 * current + .5 * history
        payload = dict(scores=scores, current_reconstruction_mse=current,
            history_deviation_reconstruction_mse=history,
            training_losses=[.5, .4, .3, .2, .1],
            runtime=dict(python_version='3.14.0', numpy_version='2.5.4', torch_version='2.14.1+cpu',
                device='cpu', torch_num_threads=2, torch_num_interop_threads=3))
        seen['payloads'].append(payload)
        try:
            yield payload
        finally:
            seen['events'].append('numeric-exit')

    monkeypatch.setattr(api, '_numeric_operation', numeric)
    return seen


def _primitive_tree(value):
    if is_dataclass(value):
        assert value.__dataclass_params__.frozen and not hasattr(value, '__dict__')
        for field in fields(value):
            _primitive_tree(getattr(value, field.name))
    elif type(value) is tuple:
        for item in value:
            _primitive_tree(item)
    else:
        assert type(value) in (str, int, float, bool, type(None))
        if type(value) is float:
            assert math.isfinite(value)


class TestAdmission:
    @pytest.fixture(autouse=True)
    def _no_real_model_imports(self, monkeypatch):
        forbidden = {'torch', 'sklearn', 'joblib', 'tensorflow'}
        # A broader suite may have already used its independently authorized
        # model tests. Preserve those objects; this class grants no new imports.
        baseline_models = {name: module for name, module in sys.modules.items()
                           if name.split('.')[0] in forbidden}
        attempts = []
        original_import = builtins.__import__
        original_import_module = importlib.import_module

        def check(name):
            if name.split('.')[0] in forbidden:
                attempts.append(name)
                raise AssertionError('real model import is forbidden in manual admission tests')

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                check(fullname)

        def guarded(name, *args, **kwargs):
            check(name)
            return original_import(name, *args, **kwargs)

        def import_module(name, *args, **kwargs):
            check(name)
            return original_import_module(name, *args, **kwargs)

        with monkeypatch.context() as guard:
            guard.setattr(sys, 'meta_path', [Block(), *sys.meta_path])
            guard.setattr(builtins, '__import__', guarded)
            guard.setattr(importlib, 'import_module', import_module)
            yield
        assert attempts == []
        current_models = {name: module for name, module in sys.modules.items()
                          if name.split('.')[0] in forbidden}
        assert current_models.keys() == baseline_models.keys()
        assert all(current_models[name] is module for name, module in baseline_models.items())

    def test_module_import_is_in_process_stdlib_fenced_not_cold_process(self, monkeypatch):
        api = _api()
        attempts = []
        original_import = builtins.__import__
        original_import_module = importlib.import_module
        forbidden = {'numpy', 'torch', 'sklearn', 'scipy', 'joblib', 'tensorflow'}

        def check(name):
            if name.split('.')[0] in forbidden or name.startswith('traffic_anomaly.') and name != MODULE:
                attempts.append(name)
                raise AssertionError('numerical/product import during module import')

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                check(fullname)

        def guarded(name, *args, **kwargs):
            check(name)
            return original_import(name, *args, **kwargs)

        def import_module(name, *args, **kwargs):
            check(name)
            return original_import_module(name, *args, **kwargs)

        package = sys.modules['traffic_anomaly']
        with monkeypatch.context() as guard:
            guard.setattr(package, 'release_autoencoder', api)
            guard.delitem(sys.modules, MODULE)
            guard.setattr(sys, 'meta_path', [Block(), *sys.meta_path])
            guard.setattr(builtins, '__import__', guarded)
            guard.setattr(importlib, 'import_module', import_module)
            imported = importlib.import_module(MODULE)
            assert callable(imported.fit_release_autoencoder)
        assert attempts == []
        assert sys.modules[MODULE] is api

    @pytest.mark.parametrize('view', ['current13', 'h30_26'])
    def test_real_admission_strips_labels_and_preserves_all_hand_rows(self, monkeypatch, view):
        api = _api()
        import numpy as np
        from tests.core.release_if_result_cases import hand_pair
        from traffic_anomaly import release_iforest
        from traffic_anomaly import release_inputs

        pair = hand_pair()
        seen = _numeric_double(api, monkeypatch, view)
        admitted = []
        original = release_iforest._validated_inputs

        def admit(value, selected):
            admitted.append((value, selected))
            return original(value, selected)

        monkeypatch.setattr(release_iforest, '_validated_inputs', admit)
        external = []

        def forbidden(*args, **kwargs):
            external.append(True)
            raise AssertionError('preparation or derivation is forbidden')

        for name in ('prepare_release_inputs', 'verify_release_input_derivation', '_fit_state',
                     '_fit_statistics', '_transform', '_history'):
            monkeypatch.setattr(release_inputs, name, forbidden)
        result = api.fit_release_autoencoder(pair, view=view)
        assert admitted == [(pair, view)] and external == []
        assert seen['events'] == ['numeric-enter', 'calibrate', 'numeric-exit']
        assert seen['selected'] == [((4., 4., 4., 4.), .99)]
        values, = seen['values']
        assert tuple(field.name for field in fields(values)) == (
            'matrix', 'common_indices', 'train_indices', 'calibration_indices', 'preprocessing_fit_indices')
        assert values.common_indices == COMMON55 and values.train_indices == TRAIN17
        assert values.calibration_indices == CAL4 and values.preprocessing_fit_indices == PREPROCESS18
        width = 13 if view == 'current13' else 26
        assert type(values.matrix) is np.ndarray and values.matrix.dtype == np.dtype('float32')
        assert values.matrix.shape == (176, width) and values.matrix.flags.writeable is False
        expected = [[float(index) + column / 100 for column in range(13)] +
                    ([] if width == 13 else [-float(index) - column / 10 for column in range(13)])
                    for index in COMMON55]
        np.testing.assert_array_equal(values.matrix[list(COMMON55)], np.asarray(expected, dtype=np.float32))
        assert np.isnan(values.matrix[[i for i in range(176) if i not in COMMON55]]).all()
        _exact_tree(seen['configurations'][0], _configuration(view))
        assert result.raw_identity is pair.raw_identity and result.prepared_identity is pair.prepared_identity
        assert result.configuration_sha256 == pair.configuration_sha256
        assert result.train_indices == TRAIN17 and result.calibration_indices == CAL4
        assert result.preprocessing_fit_indices == PREPROCESS18 and result.scored_mask[30] is False
        assert result.profile_id == 'c17-release-ae-engineering-v1'
        assert result.scope == 'IN_MEMORY_ENGINEERING_NUMERICAL_RESULT_ONLY' and result.view == view
        assert type(result) is api.ReleaseAEResult and type(result.configuration) is api.ReleaseAEConfiguration
        assert type(result.calibration) is api.ReleaseAECalibration and type(result.runtime) is api.ReleaseAERuntime
        frozen_configuration = _configuration(view)
        frozen_configuration['architecture'] = tuple(frozen_configuration['architecture'])
        frozen_configuration['adam_betas'] = tuple(frozen_configuration['adam_betas'])
        _exact_tree({field.name: getattr(result.configuration, field.name) for field in fields(result.configuration)},
                    frozen_configuration)
        assert result.threshold.hex() == (4.).hex() and result.training_losses == (.5, .4, .3, .2, .1)
        assert (result.calibration.quantile, result.calibration.method, result.calibration.comparison,
                result.calibration.sample_count, result.calibration.equal_count, result.calibration.strictly_above_count) == (
                    .99, 'linear', 'STRICT_GREATER', 4, 4, 0)
        assert (result.runtime.python_version, result.runtime.numpy_version, result.runtime.torch_version,
                result.runtime.device, result.runtime.torch_num_threads, result.runtime.torch_num_interop_threads) == (
                    '3.14.0', '2.5.4', '2.14.1+cpu', 'cpu', 2, 3)
        from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
        columns = tuple('current:' + name for name in G13U_FEATURE_NAMES)
        if width == 26:
            columns += tuple('residual_h30:' + name for name in G13U_FEATURE_NAMES)
        assert result.feature_columns == columns
        assert all(type(vector) is tuple and len(vector) == 176 for vector in (
            result.scores, result.predictions, result.scored_mask,
            result.current_reconstruction_mse, result.history_deviation_reconstruction_mse))
        for index in range(176):
            assert type(result.scored_mask[index]) is bool
            if index not in COMMON55:
                assert result.scored_mask[index] is False
                assert result.scores[index] is result.predictions[index] is None
                assert result.current_reconstruction_mse[index] is result.history_deviation_reconstruction_mse[index] is None
            else:
                score = 4. if index in CAL4 else float(index % 7) + (1. if width == 26 else 0.)
                assert type(result.scores[index]) is float and result.scores[index].hex() == score.hex()
                assert type(result.predictions[index]) is bool and result.predictions[index] is (score > 4.)
                current = (4. if width == 13 else 2.) if index in CAL4 else float(index % 7)
                assert result.current_reconstruction_mse[index] == current
                historical = None if width == 13 else 6. if index in CAL4 else float(index % 7) + 2.
                assert result.history_deviation_reconstruction_mse[index] == historical
        _primitive_tree(result)

    @pytest.mark.parametrize('view', ['current13', 'h30_26'])
    def test_result_does_not_retain_mutable_numeric_payload_or_configuration(self, monkeypatch, view):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        seen = _numeric_double(api, monkeypatch, view)
        result = api.fit_release_autoencoder(hand_pair(), view=view)
        score = result.scores[31]
        payload = seen['payloads'][0]
        payload['scores'][:] = 999.
        payload['current_reconstruction_mse'][:] = 999.
        payload['runtime']['torch_num_threads'] = 64
        payload['training_losses'][0] = 999.
        seen['configurations'][0]['architecture'][0] = 999
        assert result.scores[31] == score and result.current_reconstruction_mse[31] == 3.
        assert result.training_losses == (.5, .4, .3, .2, .1) and result.runtime.torch_num_threads == 2
        assert result.configuration.architecture == ((13, 8, 3, 8, 13) if view == 'current13' else (26, 8, 3, 8, 26))
        assert result.configuration.adam_betas == (.9, .999)
        for holder, name in ((result, 'threshold'), (result.configuration, 'epochs'),
                             (result.calibration, 'sample_count'), (result.runtime, 'device')):
            with pytest.raises(FrozenInstanceError):
                setattr(holder, name, None)
        with pytest.raises(TypeError):
            result.scores[31] = 0.
        _primitive_tree(result)
        assert seen['selected'] == [((4., 4., 4., 4.), .99)]

    def test_legal_validation_test_label_changes_do_not_reach_numeric_operation(self, monkeypatch):
        api = _api()
        import numpy as np
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        kinds = _set(pair.labels.saved.label_kinds, 82, ('unknown',) * 3)
        kinds = _set(kinds, 160, ('attack',) * 3)
        stale = replace(pair, labels=replace(pair.labels, saved=replace(pair.labels.saved, label_kinds=kinds)))
        seen = _numeric_double(api, monkeypatch, 'current13')
        _safe_error(api, 'INVALID_AE_INPUT', lambda: api.fit_release_autoencoder(stale, view='current13'))
        assert seen['values'] == [] and seen['selected'] == []
        first = api.fit_release_autoencoder(pair, view='current13')
        second = api.fit_release_autoencoder(hand_pair(kinds=kinds), view='current13')
        assert first.scores == second.scores and first.predictions == second.predictions
        assert first.train_indices == second.train_indices == TRAIN17
        assert first.calibration_indices == second.calibration_indices == CAL4
        np.testing.assert_array_equal(seen['values'][0].matrix, seen['values'][1].matrix)
        assert seen['selected'] == [((4., 4., 4., 4.), .99)] * 2

    @pytest.mark.parametrize('bad_view', [None, True, 13, [], 'h15_26', 'current134', ''])
    def test_invalid_view_precedes_any_numerical_import(self, monkeypatch, bad_view):
        api = _api()
        attempts = []
        original = builtins.__import__
        original_import_module = importlib.import_module

        def check(name):
            if name == 'numpy' or name.startswith(('numpy.', 'traffic_anomaly.')):
                attempts.append(name)
                raise AssertionError('invalid view reached numerical admission')

        def guarded(name, *args, **kwargs):
            check(name)
            return original(name, *args, **kwargs)

        def import_module(name, *args, **kwargs):
            check(name)
            return original_import_module(name, *args, **kwargs)

        with monkeypatch.context() as guard:
            guard.setattr(builtins, '__import__', guarded)
            guard.setattr(importlib, 'import_module', import_module)
            _safe_error(api, 'INVALID_AE_ARGUMENTS', lambda: api.fit_release_autoencoder(object(), view=bad_view))
        assert attempts == []

    def test_string_subclass_view_is_not_a_native_view(self, monkeypatch):
        api = _api()
        class Text(str):
            pass
        _safe_error(api, 'INVALID_AE_ARGUMENTS', lambda: api.fit_release_autoencoder(object(), view=Text('current13')))

    @pytest.mark.parametrize('kind', ['object', 'dict', 'subclass', 'missing_slots'])
    def test_exact_pair_type_and_storage_are_admitted_before_numeric_work(self, monkeypatch, kind):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        seen = _numeric_double(api, monkeypatch, 'current13')
        if kind == 'object':
            bad = object()
        elif kind == 'dict':
            bad = {}
        elif kind == 'subclass':
            class Subclass(type(pair)):
                pass
            bad = object.__new__(Subclass)
        else:
            bad = object.__new__(type(pair))
        code = 'INVALID_AE_INPUT' if kind == 'missing_slots' else 'INVALID_AE_ARGUMENTS'
        _safe_error(api, code, lambda: api.fit_release_autoencoder(bad, view='current13'))
        assert seen['values'] == seen['selected'] == []

    @pytest.mark.parametrize('change', ['identity_bool', 'configuration_hash', 'joined_h15', 'joined_h30',
        'mask_bool', 'duplicate_indices', 'bool_index', 'out_of_range', 'role', 'width'])
    def test_saved_content_corruption_stops_before_numeric_operation(self, monkeypatch, change):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        if change == 'identity_bool':
            pair = replace(pair, raw_identity=_forged(pair.raw_identity, manifest_byte_count=True))
        elif change == 'configuration_hash':
            pair = replace(pair, configuration_sha256='f' * 64)
        elif change.startswith('joined_'):
            rows = getattr(pair, change)
            pair = replace(pair, **{change: _set(rows, 31, rows[31][13:] + rows[31][:13])})
        elif change == 'mask_bool':
            pair = replace(pair, prepared_minutes=replace(pair.prepared_minutes,
                common_valid=(0,) + pair.prepared_minutes.common_valid[1:]))
        elif change in ('duplicate_indices', 'bool_index', 'out_of_range'):
            indices = {'duplicate_indices': (31, 31), 'bool_index': (True,), 'out_of_range': (176,)}[change]
            pair = replace(pair, population=replace(pair.population, train_indices=indices))
        elif change == 'role':
            pair = replace(pair, roles=_set(pair.roles, 31, 'test'))
        else:
            pair = replace(pair, prepared_minutes=replace(pair.prepared_minutes,
                current_values=_set(pair.prepared_minutes.current_values, 31, (1.,) * 12)))
        seen = _numeric_double(api, monkeypatch, 'h30_26')
        _safe_error(api, 'INVALID_AE_INPUT', lambda: api.fit_release_autoencoder(pair, view='h30_26'))
        assert seen['values'] == seen['selected'] == []

    @pytest.mark.parametrize('kind', ['minutes', 'segments'])
    def test_resource_limits_precede_remaining_content_and_model_checks(self, monkeypatch, kind):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        if kind == 'minutes':
            pair = replace(pair, prepared_minutes=replace(pair.prepared_minutes,
                timestamps=(pair.prepared_minutes.timestamps[0],) * 10001))
        else:
            pair = replace(pair, segments=pair.segments * 2)
        seen = _numeric_double(api, monkeypatch, 'current13')
        _safe_error(api, 'RESOURCE_LIMIT', lambda: api.fit_release_autoencoder(pair, view='current13'))
        assert seen['values'] == seen['selected'] == []

    @pytest.mark.parametrize('view', ['current13', 'h30_26'])
    @pytest.mark.parametrize('index', [31, 124, 158])
    def test_float64_finite_float32_overflow_is_rejected_without_dropping_rows(self, monkeypatch, view, index):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        minutes = pair.prepared_minutes
        row = (1e39,) + minutes.current_values[index][1:]
        changes = {'joined_h' + str(history.window): _set(getattr(pair, 'joined_h' + str(history.window)),
                   index, row + history.residual[index]) for history in minutes.histories}
        pair = replace(pair, prepared_minutes=replace(minutes, current_values=_set(minutes.current_values, index, row)), **changes)
        seen = _numeric_double(api, monkeypatch, view)
        _safe_error(api, 'INVALID_INPUT_NUMERIC', lambda: api.fit_release_autoencoder(pair, view=view))
        assert seen['values'] == seen['selected'] == []

    @pytest.mark.parametrize('kind,code', [('train', 'NO_TRAINING_NORMAL'), ('calibration', 'NO_CALIBRATION_NORMAL'),
                                         ('both', 'NO_TRAINING_NORMAL')])
    def test_valid_empty_populations_have_stable_pre_model_precedence(self, monkeypatch, kind, code):
        api = _api()
        from tests.core.test_release_iforest import _case
        kinds = tuple(('attack',) * 3 if 88 <= index < 128 else ('normal',) * 3 for index in range(176))
        if kind == 'train':
            pair = _case(invalid_train=True, train=())
        elif kind == 'calibration':
            pair = _case(kinds=kinds, cal=())
        else:
            pair = _case(kinds=kinds, invalid_train=True, train=(), cal=())
        seen = _numeric_double(api, monkeypatch, 'current13')
        _safe_error(api, code, lambda: api.fit_release_autoencoder(pair, view='current13'))
        assert seen['values'] == seen['selected'] == []

    @pytest.mark.parametrize('source,target', [('INVALID_IF_ARGUMENTS', 'INVALID_AE_ARGUMENTS'),
        ('INVALID_IF_INPUT', 'INVALID_AE_INPUT'), ('RESOURCE_LIMIT', 'RESOURCE_LIMIT'),
        ('NO_TRAINING_NORMAL', 'NO_TRAINING_NORMAL'), ('NO_CALIBRATION_NORMAL', 'NO_CALIBRATION_NORMAL'),
        ('INVALID_INPUT_NUMERIC', 'INVALID_INPUT_NUMERIC'), ('MODEL_ERROR', 'AE_ERROR')])
    def test_exact_admission_owner_errors_map_only_the_stage_allowlist(self, monkeypatch, source, target):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        from traffic_anomaly import release_iforest
        pair = hand_pair()
        seen = _numeric_double(api, monkeypatch, 'current13')
        error = release_iforest.ReleaseIFError(source)

        def reject(*args):
            raise error

        monkeypatch.setattr(release_iforest, '_validated_inputs', reject)
        _safe_error(api, target, lambda: api.fit_release_autoencoder(pair, view='current13'))
        assert seen['values'] == seen['selected'] == []

    @pytest.mark.parametrize('kind', ['known', 'unknown', 'bool', 'subclass_value', 'getter_failure', 'foreign_subclass'])
    def test_owning_code_is_read_once_and_foreign_getters_are_not_inspected(self, monkeypatch, kind):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        from traffic_anomaly import release_iforest
        pair = hand_pair()
        seen = _numeric_double(api, monkeypatch, 'current13')
        reads = []
        class Text(str):
            pass
        if kind == 'foreign_subclass':
            class Foreign(release_iforest.ReleaseIFError):
                def __init__(self):
                    ValueError.__init__(self, 'DETAIL_SHOULD_NOT_ESCAPE')
                @property
                def code(self):
                    reads.append(True)
                    raise AssertionError('foreign getter inspected')
            error = Foreign()
        else:
            error = release_iforest.ReleaseIFError('INVALID_IF_INPUT')
            def code(self):
                reads.append(True)
                if kind == 'getter_failure':
                    raise ValueError('DETAIL_SHOULD_NOT_ESCAPE')
                return {'known': 'INVALID_IF_INPUT', 'unknown': 'UNDECLARED_CODE', 'bool': True,
                        'subclass_value': Text('INVALID_IF_INPUT')}[kind]
            monkeypatch.setattr(release_iforest.ReleaseIFError, 'code', property(code), raising=False)

        def reject(*args):
            raise error

        monkeypatch.setattr(release_iforest, '_validated_inputs', reject)
        _safe_error(api, 'INVALID_AE_INPUT' if kind == 'known' else 'AE_ERROR',
                    lambda: api.fit_release_autoencoder(pair, view='current13'))
        assert len(reads) == (0 if kind == 'foreign_subclass' else 1)
        assert seen['values'] == seen['selected'] == []

    @pytest.mark.parametrize('code', ['INCOMPATIBLE_RUNTIME', 'MODEL_UNAVAILABLE', 'INVALID_MODEL_STATE', 'INVALID_MODEL_SCORES'])
    def test_typed_numeric_entry_error_keeps_its_stage_code(self, monkeypatch, code):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        seen = _numeric_double(api, monkeypatch, 'current13', failure=api.ReleaseAEError(code))
        _safe_error(api, code, lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert seen['events'] == ['numeric-enter'] and seen['selected'] == []

    @pytest.mark.parametrize('error_type', [MemoryError, KeyboardInterrupt, SystemExit])
    def test_resource_and_received_interrupts_are_not_hidden_by_admission_mapping(self, monkeypatch, error_type):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        from traffic_anomaly import release_iforest
        pair = hand_pair()
        seen = _numeric_double(api, monkeypatch, 'current13')
        error = error_type('DETAIL_SHOULD_NOT_ESCAPE')
        def reject(*args):
            raise error
        monkeypatch.setattr(release_iforest, '_validated_inputs', reject)
        if error_type is MemoryError:
            _safe_error(api, 'RESOURCE_LIMIT', lambda: api.fit_release_autoencoder(pair, view='current13'))
        else:
            with pytest.raises(error_type) as caught:
                api.fit_release_autoencoder(pair, view='current13')
            assert caught.value is error
        assert seen['values'] == seen['selected'] == []

    def test_public_error_constructor_normalizes_only_unknown_or_non_native_codes(self):
        api = _api()
        for code in ERROR_CODES:
            error = api.ReleaseAEError(code)
            assert error.code == code and error.args == (code,)
        class Text(str):
            pass
        class Hostile:
            def __str__(self):
                raise AssertionError('unknown error argument was inspected')
        for value in ('DETAIL_SHOULD_NOT_ESCAPE', None, [], True, Text('MODEL_ERROR'), Hostile()):
            error = api.ReleaseAEError(value)
            assert error.code == 'AE_ERROR' and error.args == ('AE_ERROR',)


def _numerical_rig(api, monkeypatch, view='current13', *, fault=None, failures=None):
    """Closed scripted runtime, not Torch or a claim about trusted helper math.

    Exercise the new numerical orchestration, keeping its real admission,
    calibration and assembly. No model-root module is imported or injected.
    Future private seams are installed only on the new module under test.
    """
    import numpy as np
    from types import SimpleNamespace
    from traffic_anomaly import candidate_autoencoder as helpers
    from traffic_anomaly.evaluation import calibration

    failures = {} if failures is None else failures
    seen = dict(events=[], train=[], common=[], selected=[], built=[], checked=[],
                versions=('3.14.0', '2.5.4'), rng=['torch-before', 'numpy-before', 'python-before'])
    before = tuple(seen['rng'])

    def trip(stage):
        seen['events'].append(stage)
        if stage in failures:
            raise failures[stage]

    class Tensor:
        def __init__(self, data, *, dtype='float32', device='cpu'):
            self.data = np.asarray(data, dtype=np.float32)
            self.dtype = dtype
            self.device = SimpleNamespace(type=device)
            self.grad = None

        @property
        def shape(self):
            return self.data.shape

        def numel(self):
            return self.data.size

        def detach(self):
            return self

        def item(self):
            return float(self.data.item())

        def numpy(self):
            return self.data.copy()

        def clone(self):
            return Tensor(self.data.copy(), dtype=self.dtype, device=self.device.type)

        def __sub__(self, other):
            return Tensor(self.data - other.data)

        def __pow__(self, power):
            return Tensor(self.data ** power)

        def backward(self):
            trip('backward')
            for parameter in model.parameters():
                parameter.grad = Tensor(np.ones(parameter.shape, dtype=np.float32))
            parameter = model.parameters()[0]
            if fault == 'gradient_missing':
                parameter.grad = None
            elif fault == 'gradient_shape':
                parameter.grad = Tensor([1., 1.])
            elif fault == 'gradient_dtype':
                parameter.grad.dtype = 'float64'
            elif fault == 'gradient_device':
                parameter.grad.device.type = 'not-cpu'
            elif fault == 'gradient_nonfinite':
                parameter.grad.data[:] = np.nan

    class Model:
        def __init__(self):
            self.training = True
            self.steps = 0
            self._parameters = (Tensor([1.]), Tensor([2.]))

        def parameters(self):
            return self._parameters

        def train(self):
            trip('train-mode')
            self.training = True
            return self

        def eval(self):
            trip('eval-mode')
            self.training = False
            return self

        def __call__(self, tensor):
            if not self.training:
                trip('score-forward')
                return Tensor(np.zeros(tensor.shape, dtype=np.float32))
            trip('train-forward')
            seen['train'].append(tensor.data.copy())
            seen['rng'][:] = ['torch-work', 'numpy-work', 'python-work']
            recovered = Tensor(tensor.data + np.float32(self.steps + 1))
            if fault == 'output_type':
                return object()
            if fault == 'output_shape':
                return Tensor(recovered.data[:1])  # broadcastable, still forbidden
            if fault == 'output_dtype':
                recovered.dtype = 'float64'
            if fault == 'output_device':
                recovered.device.type = 'not-cpu'
            if fault == 'output_nonfinite':
                recovered.data[0, 0] = np.nan
            return recovered

    model = Model()

    class Optimizer:
        def __init__(self):
            self.state = {model.parameters()[0]: {'step': Tensor(0.)}}

        def zero_grad(self, *, set_to_none):
            assert set_to_none is True
            trip('zero-grad')
            for parameter in model.parameters():
                parameter.grad = None

        def step(self):
            trip('step')
            model.steps += 1
            if fault == 'parameter_nonfinite':
                model.parameters()[0].data[:] = np.nan
            if fault == 'state_nonfinite':
                self.state[model.parameters()[0]]['step'].data[...] = np.nan

    optimizer = Optimizer()

    class Adam:
        @staticmethod
        def _accelerator_graph_capture_health_check():
            raise AssertionError('the actual Adam health check must not run in this double')

    tensor_type = Tensor
    class Torch:
        Tensor = tensor_type
        float32 = 'float32'
        __version__ = '2.14.1+cpu'
        num_threads = 2
        interop_threads = 3
        optim = SimpleNamespace(Adam=Adam)
        nn = SimpleNamespace(Sequential=Model, Linear=lambda: None, ReLU=lambda: None)
        random = SimpleNamespace(get_rng_state=lambda: Tensor([1.]), set_rng_state=lambda state: None,
                                 default_generator=SimpleNamespace(manual_seed=lambda seed: None))

        @staticmethod
        @contextmanager
        def inference_mode(mode=True):
            yield

        @staticmethod
        @contextmanager
        def enable_grad():
            yield

        @staticmethod
        def from_numpy(array):
            trip('train-tensor')
            return Tensor(array.copy())

        @staticmethod
        def isfinite(tensor):
            return np.isfinite(tensor.data)

        @staticmethod
        def is_tensor(value):
            return type(value) is Tensor

        @staticmethod
        def mean(tensor):
            trip('loss')
            return Tensor(np.nan if fault == 'loss_nonfinite' else np.mean(tensor.data, dtype=np.float32))

        def get_num_threads(self):
            trip('intra-threads')
            return self.num_threads

        def get_num_interop_threads(self):
            trip('inter-threads')
            return self.interop_threads

        def __getattr__(self, name):
            if name in ('cuda', 'accelerator', 'manual_seed', 'set_num_threads', 'set_num_interop_threads'):
                raise AssertionError('accelerator/global RNG/thread mutation is forbidden')
            raise AttributeError(name)

    torch = Torch()

    def versions():
        trip('versions')
        return seen['versions']

    def load():
        trip('load-torch')
        return torch

    @contextmanager
    def scope(runtime):
        assert runtime is torch
        trip('scope-enter')
        saved = tuple(seen['rng'])
        seen['rng'][:] = ['torch-seeded', 'numpy-seeded', 'python-seeded']
        try:
            yield
        finally:
            trip('scope-exit')
            seen['rng'][:] = saved

    def build(width, *, model_profile_id):
        trip('build')
        seen['built'].append((width, model_profile_id))
        return model

    def check(network, configuration, runtime):
        assert network is model and runtime is torch
        trip('network-check')
        seen['checked'].append((configuration['input_width'], model.steps))
        if not all(np.isfinite(parameter.data).all() for parameter in model.parameters()):
            raise helpers.CandidateAEError('NONFINITE_AE_WEIGHTS')

    def cpu_optimizer(runtime, parameters):
        trip('optimizer')
        assert runtime is torch
        assert tuple(parameters) == model.parameters()
        return optimizer

    def score(network, matrix, method):
        trip('score-common')
        assert network is model
        assert method == ('current_ae' if view == 'current13' else 'history_ae')
        seen['common'].append(matrix.copy())
        network.eval()
        network(Tensor(matrix))  # exactly one separately labeled scripted score forward
        current = np.full(55, 4. if view == 'current13' else 2., dtype=np.float64)
        history = np.full(55, np.nan if view == 'current13' else 6., dtype=np.float64)
        current[0], current[1] = 1., 8. if view == 'current13' else 10.
        scores = current.copy() if view == 'current13' else .5 * current + .5 * history
        if fault == 'score_tuple':
            return [scores, current, history]
        if fault == 'score_length':
            return scores, current
        if fault == 'score_shape':
            scores = scores.reshape(55, 1)
        if fault == 'score_dtype':
            scores = scores.astype(np.float32)
        if fault == 'score_subclass':
            class ForeignArray(np.ndarray):
                pass
            scores = scores.view(ForeignArray)
        if fault == 'score_nan':
            scores[0] = np.nan
        if fault == 'score_negative':
            scores[0] = -1.
        if fault == 'score_inconsistent':
            scores[0] = 123.
        if fault == 'current_negative':
            current[0] = -1.
        if fault == 'history_invalid':
            history[0] = 0. if view == 'current13' else np.nan
        return scores, current, history

    original_calibrate = calibration.calibrate

    def calibrate(scores, quantile=.99):
        trip('calibrate')
        seen['selected'].append(tuple(float(value) for value in scores))
        if fault == 'threshold_nonfinite':
            return float('nan')
        if fault == 'threshold_type':
            return np.float64(4.)
        return original_calibrate(scores, quantile)

    for name, function in (
        ('_runtime_versions', versions), ('_load_torch', load), ('_cpu_scope', scope),
        ('_build_network', build), ('_cpu_optimizer', cpu_optimizer),
        ('_check_model', check), ('_score_common', score),
    ):
        monkeypatch.setattr(api, name, function, raising=False)
    monkeypatch.setattr(calibration, 'calibrate', calibrate)
    seen.update(torch=torch, model=model, optimizer=optimizer, Tensor=Tensor, before=before,
                failures=failures, helpers=helpers)
    return seen


class TestNumerical:
    # Reuse only the import fence fixture, without inheriting admission tests.
    _no_real_model_imports = TestAdmission._no_real_model_imports

    @pytest.mark.parametrize('view', ['current13', 'h30_26'])
    def test_five_updates_one_common_forward_and_public_assembly_inside_scope(self, monkeypatch, view):
        api = _api()
        import numpy as np
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        rig = _numerical_rig(api, monkeypatch, view)
        result = api.fit_release_autoencoder(pair, view=view)
        events = rig['events']
        work_names = {'scope-enter', 'build', 'network-check', 'optimizer', 'train-tensor', 'train-mode',
                      'zero-grad', 'train-forward', 'loss', 'backward', 'step', 'score-common',
                      'eval-mode', 'score-forward', 'calibrate', 'scope-exit'}
        expected = ['scope-enter', 'build', 'network-check', 'optimizer', 'train-tensor', 'train-mode']
        expected += ['zero-grad', 'train-forward', 'loss', 'backward', 'step', 'network-check'] * 5
        expected += ['score-common', 'eval-mode', 'score-forward', 'calibrate', 'scope-exit']
        assert [event for event in events if event in work_names] == expected
        assert events.index('versions') < events.index('load-torch') < events.index('scope-enter')
        assert events.count('intra-threads') == events.count('inter-threads') == 1
        assert rig['built'] == [(13 if view == 'current13' else 26, 'c17-i1-g13u-ae-synthetic-v1')]
        assert rig['checked'] == [(13 if view == 'current13' else 26, step) for step in range(6)]
        rows = pair.prepared_minutes.current_values if view == 'current13' else pair.joined_h30
        train = np.asarray([rows[index] for index in TRAIN17], dtype=np.float32)
        common = np.asarray([rows[index] for index in COMMON55], dtype=np.float32)
        assert len(rig['train']) == 5 and len(rig['common']) == 1
        for observed in rig['train']:
            np.testing.assert_array_equal(observed, train)
        np.testing.assert_array_equal(rig['common'][0], common)
        expected_losses = tuple(float(np.mean(((train + np.float32(delta)) - train) ** 2,
                                               dtype=np.float32)) for delta in range(1, 6))
        assert result.training_losses == expected_losses
        assert rig['selected'] == [(4., 4., 4., 4.)]
        assert result.threshold == 4. and result.calibration.equal_count == 4
        assert result.scores[31] == (1. if view == 'current13' else 3.5)
        assert result.scores[32] == 8. and result.predictions[32] is True
        assert result.predictions[31] is False and result.predictions[124] is False
        assert sum(value is None for value in result.scores) == 121
        assert result.history_deviation_reconstruction_mse[124] == (None if view == 'current13' else 6.)
        assert tuple(rig['rng']) == rig['before']
        _primitive_tree(result)

    @pytest.mark.parametrize('kind', ['python', 'numpy', 'torch', 'intra_bool', 'intra_zero', 'intra_large',
                                      'inter_bool', 'inter_zero', 'inter_large', 'adam_api', 'cpu_rng_api'])
    def test_runtime_incompatibility_precedes_scope_and_model(self, monkeypatch, kind):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch)
        if kind == 'python':
            rig['versions'] = ('3.13.9', '2.5.4')
        elif kind == 'numpy':
            rig['versions'] = ('3.14.0', '2.5.3')
        elif kind == 'torch':
            rig['torch'].__version__ = '2.14.0+cpu'
        elif kind.startswith(('intra_', 'inter_')):
            value = {'bool': True, 'zero': 0, 'large': 65}[kind.split('_')[1]]
            setattr(rig['torch'], 'num_threads' if kind.startswith('intra_') else 'interop_threads', value)
        elif kind == 'adam_api':
            rig['torch'].optim.Adam._accelerator_graph_capture_health_check = None
        else:
            rig['torch'].random.set_rng_state = None
        _safe_error(api, 'INCOMPATIBLE_RUNTIME', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert not {'scope-enter', 'build', 'optimizer', 'calibrate'} & set(rig['events'])
        assert tuple(rig['rng']) == rig['before']

    def test_torch_str_subclass_version_is_normalized_without_overloaded_comparison(self, monkeypatch):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch)
        class Version(str):
            def __eq__(self, other):
                raise AssertionError('trusted TorchVersion must first become plain str')
            def __ne__(self, other):
                raise AssertionError('trusted TorchVersion must first become plain str')
        rig['torch'].__version__ = Version('2.14.1+cpu')
        result = api.fit_release_autoencoder(hand_pair(), view='current13')
        assert type(result.runtime.torch_version) is str and result.runtime.torch_version == '2.14.1+cpu'
        assert rig['events'].count('build') == 1 and rig['selected'] == [(4., 4., 4., 4.)]

    def test_float64_helper_scores_are_not_narrowed_after_reconstruction(self, monkeypatch):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch)
        original = api._score_common
        # Script the trusted helper's separately widened (2**24 - 1)**2.
        # This proves consumer preservation, not execution of helper/model math.
        expected = 281474943156225.
        def score(*args):
            scores, current, history = original(*args)
            scores[:] = current[:] = expected
            return scores, current, history
        monkeypatch.setattr(api, '_score_common', score)
        result = api.fit_release_autoencoder(hand_pair(), view='current13')
        assert result.scores[31].hex() == result.threshold.hex() == expected.hex()
        assert all(result.predictions[index] is False for index in COMMON55)
        assert rig['events'].count('score-forward') == rig['events'].count('calibrate') == 1
        assert rig['selected'] == [(expected,) * 4] and tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('name,code', [('torch', 'MODEL_UNAVAILABLE'), ('unrelated_dependency', 'AE_ERROR')])
    def test_controlled_missing_dependency_is_classified_without_real_import(self, monkeypatch, name, code):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        error = ModuleNotFoundError('DETAIL_SHOULD_NOT_ESCAPE', name=name)
        rig = _numerical_rig(api, monkeypatch, failures={'load-torch': error})
        _safe_error(api, code, lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert 'build' not in rig['events'] and 'scope-enter' not in rig['events']

    @pytest.mark.parametrize('fault,code,last', [
        ('output_type', 'INVALID_MODEL_STATE', 'train-forward'),
        ('output_shape', 'INVALID_MODEL_STATE', 'train-forward'),
        ('output_dtype', 'INVALID_MODEL_STATE', 'train-forward'),
        ('output_device', 'INVALID_MODEL_STATE', 'train-forward'),
        ('output_nonfinite', 'NONFINITE_TRAINING', 'train-forward'),
        ('loss_nonfinite', 'NONFINITE_TRAINING', 'loss'),
        ('gradient_missing', 'INVALID_MODEL_STATE', 'backward'),
        ('gradient_shape', 'INVALID_MODEL_STATE', 'backward'),
        ('gradient_dtype', 'INVALID_MODEL_STATE', 'backward'),
        ('gradient_device', 'INVALID_MODEL_STATE', 'backward'),
        ('gradient_nonfinite', 'NONFINITE_TRAINING', 'backward'),
        ('parameter_nonfinite', 'NONFINITE_TRAINING', 'network-check'),
        ('state_nonfinite', 'NONFINITE_TRAINING', 'network-check'),
    ])
    def test_first_bad_training_value_stops_without_scoring(self, monkeypatch, fault, code, last):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch, fault=fault)
        _safe_error(api, code, lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert 'score-common' not in rig['events'] and 'calibrate' not in rig['events']
        assert [event for event in rig['events'] if event not in ('scope-exit',)][-1] == last
        assert rig['events'].count('train-forward') == 1
        assert rig['events'].count('step') == (1 if fault in ('parameter_nonfinite', 'state_nonfinite') else 0)
        assert tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('stage', ['build', 'network-check', 'optimizer', 'train-forward', 'loss', 'backward', 'step', 'score-common'])
    def test_ordinary_model_failure_is_finite_and_not_retried(self, monkeypatch, stage):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch, failures={stage: RuntimeError('DETAIL_SHOULD_NOT_ESCAPE')})
        _safe_error(api, 'MODEL_ERROR', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert rig['events'].count(stage) == 1 and rig['events'][-1] == 'scope-exit'
        assert 'calibrate' not in rig['events'] and tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('fault', ['score_tuple', 'score_length', 'score_shape', 'score_dtype', 'score_subclass',
                                       'score_nan', 'score_negative', 'score_inconsistent', 'current_negative', 'history_invalid'])
    @pytest.mark.parametrize('view', ['current13', 'h30_26'])
    def test_scorer_contract_rejects_before_public_calibration(self, monkeypatch, fault, view):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch, view, fault=fault)
        _safe_error(api, 'INVALID_MODEL_SCORES', lambda: api.fit_release_autoencoder(hand_pair(), view=view))
        assert rig['events'].count('score-common') == rig['events'].count('score-forward') == 1
        assert rig['events'].count('step') == 5 and 'calibrate' not in rig['events']
        assert tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('fault', ['threshold_nonfinite', 'threshold_type'])
    def test_bad_calibration_return_has_no_result_and_no_second_quantile(self, monkeypatch, fault):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch, fault=fault)
        _safe_error(api, 'INVALID_MODEL_SCORES', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert rig['events'].count('calibrate') == 1 and rig['selected'] == [(4., 4., 4., 4.)]
        assert rig['events'][-1] == 'scope-exit' and tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('boundary', ['scope-enter', 'scope-exit'])
    @pytest.mark.parametrize('error_type', [RuntimeError, MemoryError, KeyboardInterrupt, SystemExit])
    def test_received_boundary_error_never_becomes_success(self, monkeypatch, boundary, error_type):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        error = error_type('DETAIL_SHOULD_NOT_ESCAPE')
        rig = _numerical_rig(api, monkeypatch, failures={boundary: error})
        call = lambda: api.fit_release_autoencoder(hand_pair(), view='current13')
        if error_type in (KeyboardInterrupt, SystemExit):
            with pytest.raises(error_type) as caught:
                call()
            assert caught.value is error
        else:
            _safe_error(api, 'RESOURCE_LIMIT' if error_type is MemoryError else 'RNG_RESTORATION_FAILED', call)
        assert rig['events'].count(boundary) == 1
        assert rig['events'].count('calibrate') == (1 if boundary == 'scope-exit' else 0)
        if boundary == 'scope-enter':
            assert 'build' not in rig['events'] and tuple(rig['rng']) == rig['before']
        else:
            assert tuple(rig['rng']) != rig['before']  # failed restoration is uncertainty, not a restoration claim

    @pytest.mark.parametrize('stage', ['build', 'score-common', 'projection'])
    @pytest.mark.parametrize('kind', ['typed', 'interrupt', 'exit'])
    def test_first_observed_work_error_survives_later_cleanup_failure(self, monkeypatch, stage, kind):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        primary = (api.ReleaseAEError('INVALID_MODEL_STATE') if kind == 'typed' else
                   KeyboardInterrupt('PRIVATE') if kind == 'interrupt' else SystemExit('PRIVATE'))
        failures = {'scope-exit': RuntimeError('LATER_PRIVATE')}
        if stage != 'projection':
            failures[stage] = primary
        rig = _numerical_rig(api, monkeypatch, failures=failures)
        if stage == 'projection':
            def reject(*args):
                rig['events'].append('projection')
                raise primary
            monkeypatch.setattr(api, '_validate_result', reject)
        call = lambda: api.fit_release_autoencoder(hand_pair(), view='current13')
        if kind == 'typed':
            _safe_error(api, 'INVALID_MODEL_STATE', call)
        else:
            with pytest.raises(type(primary)) as caught:
                call()
            assert caught.value is primary
        assert rig['events'].count(stage) == 1 and rig['events'][-1] == 'scope-exit'
        assert rig['events'].count('calibrate') == (1 if stage == 'projection' else 0)
        assert tuple(rig['rng']) != rig['before']

    def test_helper_hidden_failure_is_not_recovered_from_exception_chain(self, monkeypatch):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch)
        def masked(width, *, model_profile_id):
            rig['events'].append('build')
            try:
                raise KeyboardInterrupt('HIDDEN_PRIVATE')
            finally:
                raise RuntimeError('ONLY_RECEIVED_PRIVATE')
        monkeypatch.setattr(api, '_build_network', masked)
        _safe_error(api, 'MODEL_ERROR', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert 'optimizer' not in rig['events'] and tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('change', ['profile_type', 'mask', 'score_type', 'loss_type', 'configuration_type', 'runtime_type'])
    def test_final_projection_is_revalidated_before_successful_scope_exit(self, monkeypatch, change):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch)
        original = api._validate_result
        def corrupt(result, *args):
            rig['events'].append('projection')
            if change == 'profile_type':
                class Text(str):
                    pass
                object.__setattr__(result, 'profile_id', Text(result.profile_id))
            elif change == 'mask':
                object.__setattr__(result, 'scored_mask', _set(result.scored_mask, 30, True))
            elif change == 'score_type':
                object.__setattr__(result, 'scores', _set(result.scores, 31, 1))
            elif change == 'loss_type':
                object.__setattr__(result, 'training_losses', list(result.training_losses))
            elif change == 'configuration_type':
                object.__setattr__(result.configuration, 'epochs', True)
            else:
                object.__setattr__(result.runtime, 'torch_num_threads', True)
            return original(result, *args)
        monkeypatch.setattr(api, '_validate_result', corrupt)
        _safe_error(api, 'AE_ERROR', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert rig['events'].count('calibrate') == rig['events'].count('projection') == 1
        assert rig['events'][-1] == 'scope-exit' and tuple(rig['rng']) == rig['before']

    def test_owned_wrappers_delegate_once_without_running_trusted_model_helpers(self, monkeypatch):
        api = _api()
        from traffic_anomaly import candidate_autoencoder as helpers
        from traffic_anomaly import candidate_ae_weights as weights
        required = ('_cpu_scope', '_build_network', '_cpu_optimizer', '_check_model', '_score_common')
        assert all(callable(getattr(api, name, None)) for name in required), 'new numerical helper seams are missing'
        objects = tuple(object() for _ in range(5))
        torch, network, matrix, configuration, parameters = objects
        calls = []
        def record(name, result):
            def invoke(*args, **kwargs):
                calls.append((name, args, kwargs))
                return result
            return invoke
        @contextmanager
        def cpu(runtime):
            calls.append(('enter', (runtime,), {}))
            try:
                yield
            finally:
                calls.append(('exit', (runtime,), {}))
        monkeypatch.setattr(helpers, '_cpu_execution', cpu)
        monkeypatch.setattr(weights, 'build_candidate_ae_network', record('build', network))
        monkeypatch.setattr(helpers, '_cpu_adam', record('optimizer', parameters))
        monkeypatch.setattr(helpers, '_check_network', record('check', None))
        widened = (281474943156225.,)  # (float64(float32(2**24)) - float64(float32(1)))**2
        monkeypatch.setattr(helpers, '_reconstruction_scores', record('score', widened))
        with api._cpu_scope(torch):
            assert api._build_network(13, model_profile_id='c17-i1-g13u-ae-synthetic-v1') is network
            assert api._cpu_optimizer(torch, parameters) is parameters
            api._check_model(network, configuration, torch)
            assert api._score_common(network, matrix, 'current_ae') is widened
        assert calls == [
            ('enter', (torch,), {}),
            ('build', (13,), {'model_profile_id': 'c17-i1-g13u-ae-synthetic-v1'}),
            ('optimizer', (torch, parameters), {}),
            ('check', (network, configuration, torch), {}),
            ('score', (network, matrix, 'current_ae'), {}),
            ('exit', (torch,), {}),
        ]

    @pytest.mark.parametrize('kind,code', [('numpy', 'INCOMPATIBLE_RUNTIME'), ('unrelated', 'AE_ERROR'),
        ('none', 'AE_ERROR'), ('hostile_name', 'AE_ERROR'), ('text_subclass', 'AE_ERROR'), ('foreign_error', 'AE_ERROR')])
    def test_admission_missing_module_classification_never_compares_foreign_name(self, monkeypatch, kind, code):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        reads, attempts = [], []
        class Hostile:
            def __eq__(self, other):
                reads.append('comparison')
                raise RuntimeError('PRIVATE_NAME_COMPARISON')
        class Text(str):
            def __eq__(self, other):
                reads.append('text-comparison')
                raise RuntimeError('PRIVATE_TEXT_COMPARISON')
        class Foreign(ModuleNotFoundError):
            @property
            def name(self):
                reads.append('foreign-getter')
                raise RuntimeError('PRIVATE_NAME_GETTER')
        if kind == 'foreign_error':
            error = Foreign('PRIVATE')
        else:
            name = {'numpy': 'numpy', 'unrelated': 'another_package', 'none': None,
                    'hostile_name': Hostile(), 'text_subclass': Text('numpy')}[kind]
            error = ModuleNotFoundError('PRIVATE', name=name)
        original_import = builtins.__import__
        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 1 and name == '' and 'release_iforest' in fromlist:
                attempts.append(True)
                raise error
            return original_import(name, globals, locals, fromlist, level)
        with monkeypatch.context() as guard:
            guard.setattr(builtins, '__import__', guarded)
            _safe_error(api, code, lambda: api.fit_release_autoencoder(pair, view='current13'))
        assert attempts == [True] and reads == []

    @pytest.mark.parametrize('error_type', [MemoryError, KeyboardInterrupt, SystemExit])
    def test_admission_import_resource_and_interrupts_remain_classified(self, monkeypatch, error_type):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        pair = hand_pair()
        error = error_type('PRIVATE')
        attempts = []
        original_import = builtins.__import__
        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 1 and name == '' and 'release_iforest' in fromlist:
                attempts.append(True)
                raise error
            return original_import(name, globals, locals, fromlist, level)
        with monkeypatch.context() as guard:
            guard.setattr(builtins, '__import__', guarded)
            if error_type is MemoryError:
                _safe_error(api, 'RESOURCE_LIMIT', lambda: api.fit_release_autoencoder(pair, view='current13'))
            else:
                with pytest.raises(error_type) as caught:
                    api.fit_release_autoencoder(pair, view='current13')
                assert caught.value is error
        assert attempts == [True]

    @pytest.mark.parametrize('stage,source,target', [
        ('network-check', 'INCOMPATIBLE_AE_NETWORK', 'INVALID_MODEL_STATE'),
        ('network-check', 'NONFINITE_AE_WEIGHTS', 'INVALID_MODEL_STATE'),
        ('optimizer', 'CPU_ONLY_AE_OPTIMIZER', 'INVALID_MODEL_STATE'),
        ('optimizer', 'UNSUPPORTED_TORCH_ADAM_API', 'INCOMPATIBLE_RUNTIME'),
        ('score-common', 'NONFINITE_AE_INPUT', 'INVALID_MODEL_SCORES'),
        ('score-common', 'NONFINITE_AE_OUTPUT', 'INVALID_MODEL_SCORES'),
        ('score-common', 'NONFINITE_AE_SCORE', 'INVALID_MODEL_SCORES'),
    ])
    def test_closed_helper_codes_are_mapped_by_model_stage(self, monkeypatch, stage, source, target):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        rig = _numerical_rig(api, monkeypatch)
        rig['failures'][stage] = rig['helpers'].CandidateAEError(source)
        _safe_error(api, target, lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert rig['events'].count(stage) == 1 and 'calibrate' not in rig['events']
        assert tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('kind', ['unknown', 'getter_failure', 'foreign_subclass'])
    def test_helper_error_codes_are_read_once_only_for_the_exact_owner(self, monkeypatch, kind):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        from traffic_anomaly import candidate_ae_weights as weights
        rig = _numerical_rig(api, monkeypatch)
        owner = weights.CandidateAEWeightsError
        reads = []
        if kind == 'foreign_subclass':
            class Foreign(owner):
                def __init__(self):
                    ValueError.__init__(self, 'PRIVATE')
                @property
                def code(self):
                    reads.append(True)
                    raise RuntimeError('PRIVATE_GETTER')
            error = Foreign()
        else:
            error = owner('UNDECLARED_CODE')
            def code(self):
                reads.append(True)
                if kind == 'getter_failure':
                    raise RuntimeError('PRIVATE_GETTER')
                return 'UNDECLARED_CODE'
            monkeypatch.setattr(owner, 'code', property(code), raising=False)
        rig['failures']['build'] = error
        _safe_error(api, 'AE_ERROR', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert reads == ([] if kind == 'foreign_subclass' else [True])
        assert rig['events'].count('build') == 1 and 'optimizer' not in rig['events']

    def test_builder_own_finite_failure_maps_to_model_error(self, monkeypatch):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        from traffic_anomaly import candidate_ae_weights as weights
        rig = _numerical_rig(api, monkeypatch, failures={'build': weights.CandidateAEWeightsError('MODEL_BUILD_ERROR')})
        _safe_error(api, 'MODEL_ERROR', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert rig['events'].count('build') == 1 and 'optimizer' not in rig['events']
        assert tuple(rig['rng']) == rig['before']

    @pytest.mark.parametrize('kind', ['none', 'hostile_name', 'text_subclass', 'foreign_error'])
    def test_torch_load_failure_does_not_inspect_nonnative_module_names(self, monkeypatch, kind):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        reads = []
        class Hostile:
            def __eq__(self, other):
                reads.append(True)
                raise RuntimeError('PRIVATE')
        class Text(str):
            def __eq__(self, other):
                reads.append(True)
                raise RuntimeError('PRIVATE')
        class Foreign(ModuleNotFoundError):
            @property
            def name(self):
                reads.append(True)
                raise RuntimeError('PRIVATE')
        error = (Foreign('PRIVATE') if kind == 'foreign_error' else ModuleNotFoundError('PRIVATE',
            name={'none': None, 'hostile_name': Hostile(), 'text_subclass': Text('torch')}[kind]))
        rig = _numerical_rig(api, monkeypatch, failures={'load-torch': error})
        _safe_error(api, 'AE_ERROR', lambda: api.fit_release_autoencoder(hand_pair(), view='current13'))
        assert reads == [] and rig['events'].count('load-torch') == 1
        assert 'scope-enter' not in rig['events'] and 'build' not in rig['events']

    @pytest.mark.parametrize('stage', ['configuration', 'entry', 'projection'])
    def test_foreign_exception_class_getter_is_not_an_error_classification_api(self, monkeypatch, stage):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        reads = []
        class Foreign(Exception):
            @property
            def __class__(self):
                reads.append(True)
                raise RuntimeError('PRIVATE_CLASS_GETTER')
        error = Foreign('PRIVATE')
        if stage == 'configuration':
            events = []
            def reject(*args):
                events.append('configuration')
                raise error
            monkeypatch.setattr(api, '_configuration', reject)
            rig = {'events': events}
        elif stage == 'entry':
            rig = _numeric_double(api, monkeypatch, 'current13', failure=error)
        else:
            rig = _numerical_rig(api, monkeypatch)
            def reject(*args):
                rig['events'].append('projection')
                raise error
            monkeypatch.setattr(api, '_validate_result', reject)
        expected = 'RNG_RESTORATION_FAILED' if stage == 'entry' else 'AE_ERROR'
        observed = (False, None, False, False)
        try:
            api.fit_release_autoencoder(hand_pair(), view='current13')
        except BaseException as actual:
            # Never hand a hostile exception/context to pytest's formatter.
            if type(actual) is api.ReleaseAEError:
                code = actual.code
                observed = (True, code if type(code) is str else None,
                            actual.args == (expected,), actual.__suppress_context__ is True)
        assert observed == (True, expected, True, True)
        assert reads == []
        event = {'configuration': 'configuration', 'entry': 'numeric-enter', 'projection': 'projection'}[stage]
        assert rig['events'].count(event) == 1

    @pytest.mark.parametrize('base', [MemoryError, KeyboardInterrupt, SystemExit])
    def test_real_resource_and_interrupt_subclasses_keep_their_actual_type_semantics(self, monkeypatch, base):
        api = _api()
        from tests.core.release_if_result_cases import hand_pair
        reads = []
        class RealSubclass(base):
            @property
            def __class__(self):
                reads.append(True)
                raise RuntimeError('PRIVATE_CLASS_GETTER')
        error = RealSubclass('PRIVATE')
        rig = _numerical_rig(api, monkeypatch, failures={'build': error})
        observed = (False, None, False, False, False, False)
        try:
            api.fit_release_autoencoder(hand_pair(), view='current13')
        except BaseException as actual:
            identity = actual is error and type(actual) is RealSubclass
            if type(actual) is api.ReleaseAEError:
                code = actual.code
                observed = (True, code if type(code) is str else None,
                            actual.args == ('RESOURCE_LIMIT',), actual.__suppress_context__ is True,
                            False, False)
            else:
                observed = (False, None, False, False, identity, type(actual) is RealSubclass)
        if base is MemoryError:
            assert observed == (True, 'RESOURCE_LIMIT', True, True, False, False)
        else:
            assert observed == (False, None, False, False, True, True)
        assert reads == [] and 'optimizer' not in rig['events']
        assert rig['events'].count('build') == 1 and tuple(rig['rng']) == rig['before']
