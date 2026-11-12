"""Controlled operation tests; these doubles do not establish sklearn provenance."""
from dataclasses import FrozenInstanceError, fields, replace
import importlib
import importlib.util
import math
from pathlib import Path
import subprocess
import sys
import builtins

import numpy as np
import pytest

from tests.core.release_if_result_cases import hand_pair

# Manual m17 leaf forest under P1's fixed repeated binary64 accumulation.
LEAF17 = float.fromhex('0x1.fffffffffffffp-2')

def operation():
    assert importlib.util.find_spec('traffic_anomaly.release_if_learned') is not None, (
        'the explicit retained-fit/replay operation is missing')
    return importlib.import_module('traffic_anomaly.release_if_learned')


def leaf_state(width=13, m=17):
    from traffic_anomaly.iforest_numeric_state import (
        IForestNumericNode, IForestNumericTree, IForestNumericState,
    )
    tree = IForestNumericTree((IForestNumericNode(None, None, None, None, m),))
    return IForestNumericState(1, 'iforest-numeric-state-v1',
        'iforest16-m32-f32route-f64path-numpy254-v1', width,
        tuple(range(width)), m, (tree,) * 16)


def controlled(monkeypatch, *, view='current13', returned=None):
    op = operation()
    import sklearn.ensemble
    calls = []

    class Estimator:
        def __init__(self, **kwargs):
            calls.append(('construct', self, kwargs))

        def fit(self, matrix):
            calls.append(('fit', self, matrix.copy()))
            return self

        def score_samples(self, matrix):
            calls.append(('score', self, matrix.copy()))
            return np.full(len(matrix), -LEAF17, dtype=np.float64) if returned is None else returned

    monkeypatch.setattr(sklearn.ensemble, 'IsolationForest', Estimator)

    def export(model, config):
        calls.append(('export', model, config))
        return leaf_state(config.input_width, config.max_samples)

    monkeypatch.setattr(op, '_export_retained_model', export)
    return op, hand_pair(), calls


def safe_error(op, code, action):
    with pytest.raises(op.ReleaseIFLearnedError) as caught:
        action()
    assert type(caught.value) is op.ReleaseIFLearnedError
    assert caught.value.code == code
    assert caught.value.args == (code,)
    assert str(caught.value) == code
    assert caught.value.__suppress_context__ is True


@pytest.mark.parametrize('view,width', [('current13', 13), ('h30_26', 26)])
def test_one_retained_instance_numeric_rows_and_authoritative_result(monkeypatch, view, width):
    op, pair, calls = controlled(monkeypatch, view=view)
    previous = np.geterr()
    with np.errstate(under='raise'):
        run = op.fit_release_iforest_learned(pair, view=view)
        assert np.geterr()['under'] == 'raise'
    assert np.geterr() == previous
    assert [row[0] for row in calls] == ['construct', 'fit', 'score', 'export']
    assert all(row[1] is calls[0][1] for row in calls)
    assert calls[0][2] == dict(n_estimators=16, max_samples=17, max_features=1.,
        bootstrap=False, contamination='auto', random_state=42, n_jobs=1,
        warm_start=False, verbose=0)
    assert calls[1][2].shape == (17, width)
    assert calls[2][2].shape == (55, width)
    assert calls[1][2].dtype == np.dtype('float32')
    expected_rows = pair.prepared_minutes.current_values if width == 13 else pair.joined_h30
    assert np.array_equal(calls[1][2], np.asarray([expected_rows[i] for i in range(31, 48)], np.float32))
    result = run.result_package.result
    assert result.scored_mask == pair.prepared_minutes.common_valid
    assert result.threshold.hex() == LEAF17.hex()
    assert all(score == LEAF17 and prediction is False if ok else score is prediction is None
        for score, prediction, ok in zip(result.scores, result.predictions, result.scored_mask))
    assert run.learned_package.context.train_count == 17
    assert run.learned_package.context.calibration_count == 4
    assert run.learned_package.context.preprocessing_fit_count == 18
    assert run.learned_package.context.result_identity.manifest_sha256 == run.result_package.identity.manifest_sha256
    assert tuple(f.name for f in fields(run)) == ('result_package', 'learned_package')
    with pytest.raises(FrozenInstanceError):
        run.result_package = None
    assert not hasattr(run, '__dict__')


def test_all_33_rows_enter_fit_even_when_sample_cap_is_32(monkeypatch):
    op, pair, calls = controlled(monkeypatch)
    from traffic_anomaly import release_iforest as old
    matrix = np.arange(35 * 13, dtype=np.float32).reshape(35, 13)
    matrix.setflags(write=False)
    values = old._NumericInputs(matrix, tuple(range(35)), tuple(range(33)), (33, 34), tuple(range(33)))
    monkeypatch.setattr(old, '_validated_inputs', lambda p, v: values)
    from traffic_anomaly import iforest_numeric_state as p1
    monkeypatch.setattr(p1, 'score_iforest_numeric_state', lambda s, m: (.5,) * 34 + (.6,))
    safe_error(op, 'SCORE_MISMATCH', lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert calls[0][2]['max_samples'] == 32
    assert calls[1][2].shape == (33, 13)
    assert np.array_equal(calls[1][2], matrix[:33])
    assert calls[3][2].max_samples == 32


@pytest.mark.parametrize('returned', [[], np.zeros((55, 1)), np.full(55, -.5, np.float32),
    np.full(55, -.5, dtype='>f8'), np.full(55, np.nan), np.zeros(55), np.full(55, -1.01)])
def test_invalid_original_return_never_reaches_export(monkeypatch, returned):
    op, pair, calls = controlled(monkeypatch, returned=returned)
    safe_error(op, 'INVALID_MODEL_SCORES', lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert [c[0] for c in calls] == ['construct', 'fit', 'score']


def test_last_common_ulp_difference_stops_before_result_formation(monkeypatch):
    op, pair, calls = controlled(monkeypatch)
    from traffic_anomaly import iforest_numeric_state as p1
    from traffic_anomaly import release_if_result_contract as result
    monkeypatch.setattr(p1, 'score_iforest_numeric_state', lambda s, m:
        (LEAF17,) * 54 + (math.nextafter(LEAF17, 1.),))
    monkeypatch.setattr(result, 'make_release_if_result_package', lambda *a: pytest.fail('formed result before score gate'))
    safe_error(op, 'SCORE_MISMATCH', lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert len(calls) == 4


@pytest.mark.parametrize('code', ['NO_TRAINING_NORMAL', 'NO_CALIBRATION_NORMAL', 'INVALID_INPUT_NUMERIC', 'RESOURCE_LIMIT'])
def test_input_codes_survive_without_model_calls(monkeypatch, code):
    op, pair, calls = controlled(monkeypatch)
    from traffic_anomaly import release_iforest as old
    def fail(*args):
        raise old.ReleaseIFError(code)
    monkeypatch.setattr(old, '_validated_inputs', fail)
    safe_error(op, code, lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert calls == []


def test_unknown_subclass_code_is_never_read_and_memory_wins(monkeypatch):
    op, pair, _ = controlled(monkeypatch)
    from traffic_anomaly import release_iforest as old
    class Hostile(old.ReleaseIFError):
        @property
        def code(self):
            pytest.fail('read foreign code')
    def fail(*args):
        raise Hostile.__new__(Hostile)
    monkeypatch.setattr(old, '_validated_inputs', fail)
    safe_error(op, 'LEARNED_ERROR', lambda: op.fit_release_iforest_learned(pair, view='current13'))
    monkeypatch.setattr(old, '_validated_inputs', lambda *a: (_ for _ in ()).throw(MemoryError()))
    safe_error(op, 'RESOURCE_LIMIT', lambda: op.fit_release_iforest_learned(pair, view='current13'))


def test_runtime_mismatch_and_model_failure_restore_context(monkeypatch):
    op, pair, calls = controlled(monkeypatch)
    import sklearn
    monkeypatch.setattr(sklearn, '__version__', '0.0')
    safe_error(op, 'INCOMPATIBLE_RUNTIME', lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert calls == []
    monkeypatch.undo()
    op, pair, calls = controlled(monkeypatch)
    import sklearn.ensemble
    estimator = sklearn.ensemble.IsolationForest
    def bad_fit(self, matrix):
        raise RuntimeError('private model detail')
    monkeypatch.setattr(estimator, 'fit', bad_fit)
    with np.errstate(under='raise'):
        safe_error(op, 'MODEL_ERROR', lambda: op.fit_release_iforest_learned(pair, view='current13'))
        assert np.geterr()['under'] == 'raise'


def test_serial_context_is_rechecked_between_constructor_and_fit(monkeypatch):
    op, pair, calls = controlled(monkeypatch)
    import sklearn.ensemble
    estimator = sklearn.ensemble.IsolationForest
    original = estimator.__init__
    def changed(self, **kwargs):
        original(self, **kwargs)
        np.seterr(under='raise')
    monkeypatch.setattr(estimator, '__init__', changed)
    safe_error(op, 'INCOMPATIBLE_RUNTIME', lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert [c[0] for c in calls] == ['construct']


@pytest.mark.parametrize('phase', ['numerical', 'model'])
@pytest.mark.parametrize('error_kind,code', [(ImportError, None), (RuntimeError, 'other')])
def test_dependency_failures_are_phase_specific(monkeypatch, phase, error_kind, code):
    op, pair, calls = controlled(monkeypatch)
    original = builtins.__import__
    root = 'numpy' if phase == 'numerical' else 'sklearn'
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] == root:
            raise error_kind('private dependency message')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    expected = ('INCOMPATIBLE_RUNTIME' if phase == 'numerical' else 'MODEL_UNAVAILABLE') if code is None else (
        'LEARNED_ERROR' if phase == 'numerical' else 'MODEL_ERROR')
    safe_error(op, expected, lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert calls == []


@pytest.mark.parametrize('target', ['python', 'numpy', 'joblib'])
def test_each_required_runtime_version_is_checked(monkeypatch, target):
    op, pair, calls = controlled(monkeypatch)
    if target == 'python':
        monkeypatch.setattr(sys, 'version_info', (3, 13))
    elif target == 'numpy':
        monkeypatch.setattr(np, '__version__', '2.5.3')
    else:
        import joblib
        monkeypatch.setattr(joblib, '__version__', '1.5.0')
    safe_error(op, 'INCOMPATIBLE_RUNTIME', lambda: op.fit_release_iforest_learned(pair, view='current13'))
    assert calls == []


@pytest.mark.parametrize('m', [1, 2])
def test_fit_small_training_and_single_calibration_strict_boundary(monkeypatch, m):
    op, _, calls = controlled(monkeypatch, returned=np.full(55, -.5))
    # Attack at 31+m truncates train eligibility; attack at 96 leaves just
    # calibration127's complete normal window. Preprocessing additionally sees30.
    kinds = tuple(('attack',) * 3 if i in (31 + m, 96) else ('normal',) * 3 for i in range(176))
    pair = hand_pair(kinds=kinds, train=tuple(range(31, 31 + m)),
        cal=(127,), fit=tuple(range(30, 31 + m)))
    run = op.fit_release_iforest_learned(pair, view='current13')
    assert calls[1][2].shape == (m, 13)
    assert run.learned_package.state.max_samples == m
    assert run.result_package.result.threshold == .5
    assert all(v is False if ok else v is None for v, ok in zip(
        run.result_package.result.predictions, run.result_package.result.scored_mask))


def test_replay_same_pair_one_bind_one_score_and_coherent_forgery(monkeypatch):
    op, pair, _ = controlled(monkeypatch)
    run = op.fit_release_iforest_learned(pair, view='current13')
    from traffic_anomaly import release_if_result_contract as old
    from traffic_anomaly import iforest_numeric_state as p1
    from traffic_anomaly import release_if_learned_contract as contract
    original_bind, original_score = old._bind, p1.score_iforest_numeric_state
    calls = []
    def bind(*args):
        calls.append('bind')
        return original_bind(*args)
    def score(*args):
        calls.append('score')
        return original_score(*args)
    monkeypatch.setattr(old, '_bind', bind)
    monkeypatch.setattr(p1, 'score_iforest_numeric_state', score)
    report = op.replay_release_iforest_learned(run.learned_package, pair, run.result_package)
    assert calls == ['bind', 'score']
    assert (report.scored_count, report.calibration_count) == (55, 4)
    assert report.score_replay == report.calibration_replay == report.prediction_replay == 'MATCHED'
    assert report.source_authentication == 'NOT_AUTHENTICATED'
    assert report.derivation_replay == 'NOT_PERFORMED'
    saved = run.result_package.result
    rewritten_scores = list(saved.scores)
    rewritten_scores[175] = .6
    rewritten_predictions = list(saved.predictions)
    rewritten_predictions[175] = True
    rewritten = old.make_release_if_result_package(pair, replace(saved,
        scores=tuple(rewritten_scores), predictions=tuple(rewritten_predictions)))
    ref = contract.ReleaseIFLearnedReference(*(getattr(rewritten.identity, f) for f in
        ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')))
    learned = contract._make_release_if_learned_package(
        replace(run.learned_package.context, result_identity=ref), run.learned_package.state)
    calls.clear()
    safe_error(op, 'SCORE_MISMATCH', lambda: op.replay_release_iforest_learned(learned, pair, rewritten))
    assert calls == ['bind', 'score']


def test_result_identity_precedes_pair_allocation(monkeypatch):
    op, pair, _ = controlled(monkeypatch)
    run = op.fit_release_iforest_learned(pair, view='current13')
    from traffic_anomaly import release_if_result_contract as old
    other = old.make_release_if_result_package(pair, replace(run.result_package.result,
        scores=tuple(.6 if ok else None for ok in run.result_package.result.scored_mask),
        threshold=.6))
    monkeypatch.setattr(old, '_pair_inputs', lambda *a: pytest.fail('allocated before identity'))
    safe_error(op, 'INPUT_BINDING_MISMATCH', lambda: op.replay_release_iforest_learned(run.learned_package, object(), other))


def test_replay_population_semantic_drift_precedes_score(monkeypatch):
    op, pair, _ = controlled(monkeypatch)
    run = op.fit_release_iforest_learned(pair, view='current13')
    from traffic_anomaly import release_if_learned_contract as contract
    from traffic_anomaly import iforest_numeric_state as p1
    context = replace(run.learned_package.context, population_sha256='f' * 64)
    learned = contract._make_release_if_learned_package(context, run.learned_package.state)
    monkeypatch.setattr(p1, 'score_iforest_numeric_state', lambda *a: pytest.fail('scored before population binding'))
    safe_error(op, 'INPUT_BINDING_MISMATCH', lambda: op.replay_release_iforest_learned(learned, pair, run.result_package))


def test_replay_independent_calibration_failure(monkeypatch):
    op, pair, _ = controlled(monkeypatch)
    run = op.fit_release_iforest_learned(pair, view='current13')
    from traffic_anomaly.evaluation import calibration
    original = calibration.calibrate
    # Existing result codec retains its imported helper; replay imports this one.
    seen = []
    def changed(values):
        seen.append(tuple(values))
        return math.nextafter(original(values), 1.)
    monkeypatch.setattr(calibration, 'calibrate', changed)
    safe_error(op, 'CALIBRATION_MISMATCH', lambda: op.replay_release_iforest_learned(run.learned_package, pair, run.result_package))
    assert seen == [(LEAF17,) * 4]


def test_replay_prediction_gate_with_controlled_saved_codec(monkeypatch):
    op, pair, _ = controlled(monkeypatch)
    run = op.fit_release_iforest_learned(pair, view='current13')
    from traffic_anomaly import release_if_result_contract as old
    wrong_predictions = list(run.result_package.result.predictions)
    wrong_predictions[175] = True
    corrupted = replace(run.result_package, result=replace(run.result_package.result,
        predictions=tuple(wrong_predictions)))
    # Real saved codec rejects this earlier; bypass only to exercise the later
    # independent prediction gate, never to claim a valid saved representation.
    monkeypatch.setattr(old, 'encode_release_if_result_package', lambda package: ())
    safe_error(op, 'PREDICTION_MISMATCH', lambda:
        op.replay_release_iforest_learned(run.learned_package, pair, corrupted))


def test_missing_slots_and_foreign_arguments_fail_safely(monkeypatch):
    op, pair, calls = controlled(monkeypatch)
    safe_error(op, 'INVALID_LEARNED_ARGUMENTS', lambda: op.fit_release_iforest_learned(object(), view='current13'))
    safe_error(op, 'INVALID_LEARNED_ARGUMENTS', lambda: op.fit_release_iforest_learned(pair, view='h15_26'))
    assert calls == []
    run = op.fit_release_iforest_learned(pair, view='current13')
    missing = object.__new__(type(run.learned_package))
    safe_error(op, 'INVALID_LEARNED_PACKAGE', lambda:
        op.replay_release_iforest_learned(missing, pair, run.result_package))
    safe_error(op, 'INVALID_LEARNED_ARGUMENTS', lambda:
        op.replay_release_iforest_learned(run.learned_package, pair, object()))
    missing_result = object.__new__(type(run.result_package))
    safe_error(op, 'INVALID_LEARNED_PACKAGE', lambda:
        op.replay_release_iforest_learned(run.learned_package, pair, missing_result))


def export_fixture(monkeypatch, m=2):
    op = operation()
    import sklearn.ensemble
    import sklearn.tree
    import sklearn.tree._tree
    class Tree:
        pass
    class Extra:
        pass
    class Model:
        def get_params(self, deep=False):
            return dict(n_estimators=16, max_samples=m, max_features=1., bootstrap=False,
                contamination='auto', random_state=42, n_jobs=1, warm_start=False, verbose=0)
    monkeypatch.setattr(sklearn.ensemble, 'IsolationForest', Model)
    monkeypatch.setattr(sklearn.tree, 'ExtraTreeRegressor', Extra)
    monkeypatch.setattr(sklearn.tree._tree, 'Tree', Tree)
    model = Model()
    model.bootstrap_features = False
    model.n_features_in_ = model._max_features = 13
    model.max_samples_ = model._max_samples = m
    tree = Tree()
    tree.n_features = 13
    tree.node_count = 1 if m == 1 else 3
    tree.max_depth = 0 if m == 1 else 1
    tree.children_left = np.array([-1] if m == 1 else [1, -1, -1], dtype=np.intp)
    tree.children_right = np.array([-1] if m == 1 else [2, -1, -1], dtype=np.intp)
    tree.feature = np.array([-2] if m == 1 else [12, -2, -2], dtype=np.intp)
    tree.threshold = np.array([-2.] if m == 1 else [-0., -2., -2.], dtype=np.float64)
    tree.n_node_samples = np.array([1] if m == 1 else [m, 1, m - 1], dtype=np.intp)
    estimator = Extra()
    estimator.n_features_in_ = 13
    estimator.max_features = estimator.max_features_ = 1
    estimator.max_depth = (max(m, 2) - 1).bit_length()
    estimator.splitter = 'random'
    estimator.tree_ = tree
    model.estimators_ = [estimator] * 16
    model.estimators_features_ = [np.arange(13, dtype=np.intp)] * 16
    from traffic_anomaly.release_iforest import _configuration
    return op, model, tree, _configuration(13, m)


@pytest.mark.parametrize('m', [1, 2, 32])
def test_export_native_leaf_quartet_and_noncontiguous_arrays(monkeypatch, m):
    op, model, tree, config = export_fixture(monkeypatch, m)
    for name in ('children_left', 'children_right', 'feature', 'threshold', 'n_node_samples'):
        original = getattr(tree, name)
        strided = np.empty(len(original) * 2, dtype=original.dtype)[::2]
        strided[:] = original
        setattr(tree, name, strided)
    state = op._export_retained_model(model, config)
    assert state.max_samples == m
    assert state.trees[0].nodes[-1].left is state.trees[0].nodes[-1].threshold is None
    if m != 1:
        assert state.trees[0].nodes[0].feature == 12
        assert state.trees[0].nodes[0].threshold.hex() == '-0x0.0p+0'


@pytest.mark.parametrize('defect', ['map', 'samples', 'threshold', 'leaf', 'root', 'depth', 'params'])
def test_export_rejects_profile_and_native_array_defects(monkeypatch, defect):
    op, model, tree, config = export_fixture(monkeypatch)
    if defect == 'map':
        model.estimators_features_[0] = np.arange(13, dtype=np.intp)[::-1]
    elif defect == 'samples':
        tree.n_node_samples = tree.n_node_samples.astype(np.float64)
    elif defect == 'threshold':
        tree.threshold = tree.threshold.astype('>f8')
    elif defect == 'leaf':
        tree.feature[-1] = 0
    elif defect == 'root':
        tree.n_node_samples[0] = 3
    elif defect == 'depth':
        tree.max_depth = 2
    else:
        model.get_params = lambda deep=False: dict(input_width=13)
    safe_error(op, 'INVALID_MODEL_STATE', lambda: op._export_retained_model(model, config))


def test_export_distinguishes_missing_field_from_unrelated_attribute_error(monkeypatch):
    op, model, tree, config = export_fixture(monkeypatch)
    original = tree.threshold
    del tree.threshold
    safe_error(op, 'INVALID_MODEL_STATE', lambda: op._export_retained_model(model, config))
    tree.threshold = original
    def unexpected(deep=False):
        raise AttributeError('private implementation detail')
    model.get_params = unexpected
    safe_error(op, 'LEARNED_ERROR', lambda: op._export_retained_model(model, config))


def test_operation_module_import_has_no_numeric_or_pickle_dependencies():
    operation()
    script = '''import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'numpy','sklearn','joblib','torch','pickle','cloudpickle'}:
        raise AssertionError(name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import traffic_anomaly.release_if_learned
print('PURE_IMPORT')
'''
    completed = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == 'PURE_IMPORT'


def test_cold_replay_bootstrap_then_strict_pickle_and_model_fences():
    operation()
    script = '''import builtins, sys, importlib
original = builtins.__import__
original_module = importlib.import_module
bootstrap_pickle = []
strict = False
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split('.')[0]
    if root in {'sklearn','joblib','torch','cloudpickle'} or strict and root == 'pickle':
        raise AssertionError('forbidden import ' + name)
    if root == 'pickle':
        bootstrap_pickle.append((globals or {}).get('__name__', ''))
    return original(name, globals, locals, fromlist, level)
def guarded_module(name, package=None):
    if name.split('.')[0] in {'sklearn','joblib','torch','cloudpickle','pickle'}:
        raise AssertionError('forbidden importlib ' + name)
    return original_module(name, package)
builtins.__import__ = guarded
importlib.import_module = guarded_module
import numpy as np
assert bootstrap_pickle and all(name.startswith('numpy.') for name in bootstrap_pickle)
from tests.core.release_if_result_cases import hand_pair
from traffic_anomaly import release_iforest as old
from traffic_anomaly import release_if_result_contract as saved
from traffic_anomaly import iforest_numeric_state as p1
from traffic_anomaly import release_if_learned_contract as c
from traffic_anomaly.release_if_learned import replay_release_iforest_learned
pair = hand_pair()
mask = pair.prepared_minutes.common_valid
v = float.fromhex('0x1.fffffffffffffp-2')
result = old.ReleaseIFResult('c17-release-iforest-engineering-v1', 'current13', pair.raw_identity,
    pair.prepared_identity, pair.configuration_sha256, tuple(v if ok else None for ok in mask),
    tuple(False if ok else None for ok in mask), mask, v, pair.population.train_indices,
    pair.population.calibration_indices, pair.population.preprocessing_fit_indices, old._configuration(13,17))
package = saved.make_release_if_result_package(pair,result)
def ref(value):
    return c.ReleaseIFLearnedReference(value.profile_id,value.context_sha256,value.manifest_sha256,value.manifest_byte_count)
node = p1.IForestNumericNode(None,None,None,None,17)
state = p1.IForestNumericState(1,'iforest-numeric-state-v1',
    'iforest16-m32-f32route-f64path-numpy254-v1',13,tuple(range(13)),17,
    (p1.IForestNumericTree((node,)),)*16)
context = c.ReleaseIFLearnedContext(c.LEARNED_PACKAGE_PROFILE_ID,'current13',ref(pair.raw_identity),
    ref(pair.prepared_identity),ref(package.identity),pair.configuration_sha256,176,17,4,18,
    c._population_sha256(minute_count=176,scored_mask=mask,train_indices=result.train_indices,
        calibration_indices=result.calibration_indices,preprocessing_fit_indices=result.preprocessing_fit_indices),
    pair.configuration.numeric_rules_id,c._feature_columns('current13'),
    c.ReleaseIFLearnedConfiguration(13,16,17,1.,False,'auto',42,1),c.LEARNED_FIT_RUNTIME_ID)
learned = c._make_release_if_learned_package(context,state)
def denied(*args, **kwargs):
    raise AssertionError('forbidden operation')
old.fit_release_iforest = old._compute = denied
import traffic_anomaly.release_inputs as inputs
for name in ('prepare_release_inputs','prepare_release_input_package','replay_release_inputs'):
    if hasattr(inputs,name):
        setattr(inputs,name,denied)
pickle_module = sys.modules['pickle']
assert pickle_module.__file__.endswith('pickle.py')
for name in ('load','loads','dump','dumps'):
    setattr(pickle_module,name,denied)
strict = True
report = replay_release_iforest_learned(learned,pair,package)
assert report.scored_count == 55 and report.score_replay == 'MATCHED'
assert not any(name.split('.')[0] in {'sklearn','joblib','torch','cloudpickle'} for name in sys.modules)
print('BOOTSTRAP_PICKLE=' + str(len(bootstrap_pickle)) + ';STRICT_REPLAY=55')
'''
    completed = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().endswith(';STRICT_REPLAY=55')
