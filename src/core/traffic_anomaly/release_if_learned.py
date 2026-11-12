"""One fresh retained estimator and explicit replay of its bounded numeric state.

These operations check numerical and declaration consistency. They neither
authenticate sources nor recover or prove a historical estimator execution.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import math
import sys
from typing import TYPE_CHECKING

from .release_if_learned_contract import (
    LEARNED_PACKAGE_PROFILE_ID, LEARNED_FIT_RUNTIME_ID,
    ReleaseIFLearnedError, ReleaseIFLearnedReference,
    ReleaseIFLearnedConfiguration, ReleaseIFLearnedContext,
    ReleaseIFLearnedPackage, encode_release_if_learned_package,
    _make_release_if_learned_package, _feature_columns, _population_sha256,
)

if TYPE_CHECKING:
    from .release_iforest import ReleaseIFConfiguration
    from .release_if_result_contract import ReleaseIFResultPackage
    from .release_model_inputs import ReleaseModelInputPair
    from .iforest_numeric_state import IForestNumericState


@dataclass(frozen=True, slots=True)
class ReleaseIFLearnedRun:
    result_package: ReleaseIFResultPackage
    learned_package: ReleaseIFLearnedPackage


@dataclass(frozen=True, slots=True)
class ReleaseIFLearnedReplayReport:
    profile_id: str
    scope: str
    learned_identity: ReleaseIFLearnedReference
    result_identity: ReleaseIFLearnedReference
    scored_count: int
    calibration_count: int
    score_replay: str
    calibration_replay: str
    prediction_replay: str
    source_authentication: str
    derivation_replay: str


def _need(condition, code):
    if not condition:
        raise ReleaseIFLearnedError(code) from None


def _unknown(error):
    if type(error) is ReleaseIFLearnedError:
        raise error from None
    raise ReleaseIFLearnedError('LEARNED_ERROR') from None


def _numerical():
    try:
        import numpy as np
        from . import release_iforest as old
        from . import release_if_result_contract as saved
        from .release_model_inputs import ReleaseModelInputPair
        return np, old, saved, ReleaseModelInputPair
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) in (ImportError, ModuleNotFoundError):
            raise ReleaseIFLearnedError('INCOMPATIBLE_RUNTIME') from None
        _unknown(error)


def _models():
    try:
        import joblib
        import sklearn
        from joblib.parallel import get_active_backend
        from joblib._parallel_backends import ThreadingBackend
        from sklearn.ensemble import IsolationForest
        from sklearn.tree import ExtraTreeRegressor
        from sklearn.tree._tree import Tree
        return (joblib, sklearn, get_active_backend, ThreadingBackend,
                IsolationForest, ExtraTreeRegressor, Tree)
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        raise ReleaseIFLearnedError('MODEL_UNAVAILABLE' if type(error) in
            (ImportError, ModuleNotFoundError) else 'MODEL_ERROR') from None


def _if_call(function, *args):
    from .release_iforest import ReleaseIFError
    try:
        return function(*args)
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is ReleaseIFError:
            mapping = {'INVALID_IF_ARGUMENTS': 'INVALID_LEARNED_ARGUMENTS',
                'INVALID_IF_INPUT': 'INPUT_BINDING_MISMATCH',
                'INVALID_IF_RESULT': 'INPUT_BINDING_MISMATCH'}
            preserved = ('RESOURCE_LIMIT', 'NO_TRAINING_NORMAL', 'NO_CALIBRATION_NORMAL',
                'INVALID_INPUT_NUMERIC', 'INVALID_MODEL_SCORES', 'MODEL_UNAVAILABLE', 'MODEL_ERROR')
            code = error.code
            raise ReleaseIFLearnedError(code if code in preserved else
                mapping.get(code, 'LEARNED_ERROR')) from None
        _unknown(error)


def _result_call(function, *args):
    from .release_if_result_contract import ReleaseIFResultPackageError
    try:
        return function(*args)
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is ReleaseIFResultPackageError:
            code = error.code
            mapping = {'INCOMPATIBLE_PACKAGE': 'INCOMPATIBLE_LEARNED_PACKAGE',
                'INVALID_PACKAGE_ARGUMENTS': 'INVALID_LEARNED_PACKAGE',
                'INVALID_PACKAGE': 'INVALID_LEARNED_PACKAGE',
                'INCONSISTENT_PACKAGE': 'INVALID_LEARNED_PACKAGE'}
            raise ReleaseIFLearnedError(code if code in ('RESOURCE_LIMIT',
                'INTEGRITY_MISMATCH', 'INPUT_BINDING_MISMATCH') else
                mapping.get(code, 'LEARNED_ERROR')) from None
        _unknown(error)


def _p1_call(function, *args, exporting=False):
    from .iforest_numeric_state import IForestNumericStateError
    try:
        return function(*args)
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is IForestNumericStateError:
            code = error.code
            if code == 'RESOURCE_LIMIT':
                raise ReleaseIFLearnedError(code) from None
            if exporting:
                mapped = 'INVALID_MODEL_STATE' if code in ('INVALID_STATE_ARGUMENTS',
                    'INVALID_STATE', 'INCOMPATIBLE_STATE') else 'LEARNED_ERROR'
            else:
                mapped = {'INCOMPATIBLE_RUNTIME': 'INCOMPATIBLE_RUNTIME',
                          'INVALID_MATRIX': 'INVALID_INPUT_NUMERIC'}.get(code, 'LEARNED_ERROR')
            raise ReleaseIFLearnedError(mapped) from None
        _unknown(error)


def _python_runtime():
    _need(sys.version_info[:2] == (3, 14), 'INCOMPATIBLE_RUNTIME')


def _serial(np, sklearn, get_active_backend, backend_type):
    backend, jobs = get_active_backend()
    _need(type(backend) is backend_type and type(jobs) is int and jobs == 1,
          'INCOMPATIBLE_RUNTIME')
    effective = backend.effective_n_jobs(1)
    working = sklearn.get_config()['working_memory']
    _need(type(effective) is int and effective == 1 and type(working) is int
          and working == 1024 and np.geterr()['under'] == 'ignore', 'INCOMPATIBLE_RUNTIME')


def _model_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception:
        raise ReleaseIFLearnedError('MODEL_ERROR') from None


def _parameters(configuration):
    return {name: getattr(configuration, name) for name in ('n_estimators',
        'max_samples', 'max_features', 'bootstrap', 'contamination', 'random_state', 'n_jobs')}


def _model_fields(value, names):
    try:
        return tuple(getattr(value, name) for name in names)
    except Exception as error:
        if type(error) is AttributeError:
            raise ReleaseIFLearnedError('INVALID_MODEL_STATE') from None
        raise


def _export_retained_model(model: object, configuration: ReleaseIFConfiguration) -> IForestNumericState:
    """Export only the retained fit branch's exact bounded estimator profile."""
    try:
        import numpy as np
        from .iforest_numeric_state import (
            IForestNumericNode, IForestNumericTree, IForestNumericState,
            NUMERIC_STATE_VERSION, NUMERIC_STATE_PROFILE_ID, NUMERIC_STATE_ALGORITHM_ID,
            encode_iforest_numeric_state,
        )
        _, _, _, _, IsolationForest, ExtraTreeRegressor, Tree = _models()
        code = 'INVALID_MODEL_STATE'
        _need(type(model) is IsolationForest, code)
        expected = dict(_parameters(configuration), warm_start=False, verbose=0)
        get_params, = _model_fields(model, ('get_params',))
        parameters = get_params(deep=False)
        _need(type(parameters) is dict and len(parameters) == 9
              and all(type(k) is str for k in parameters) and parameters.keys() == expected.keys(), code)
        _need(all(type(parameters[k]) is type(v) and parameters[k] == v
                  for k, v in expected.items()), code)
        width, m = configuration.input_width, configuration.max_samples
        (bootstrap_features, n_features, max_samples, private_samples, max_features,
         estimators, feature_maps) = _model_fields(model, ('bootstrap_features',
            'n_features_in_', 'max_samples_', '_max_samples', '_max_features',
            'estimators_', 'estimators_features_'))
        _need(bootstrap_features is False, code)
        for value, wanted in ((n_features, width), (max_samples, m),
                              (private_samples, m), (max_features, width)):
            _need(type(value) is int and value == wanted, code)
        _need(type(estimators) is list and type(feature_maps) is list, code)
        _need(len(estimators) == len(feature_maps) == 16, code)
        trees, observed_depths = [], []
        limit = (max(m, 2) - 1).bit_length()
        for estimator, feature_map in zip(estimators, feature_maps, strict=True):
            _need(type(estimator) is ExtraTreeRegressor, code)
            (n_features, max_features, fitted_features, max_depth, splitter, tree) = _model_fields(
                estimator, ('n_features_in_', 'max_features', 'max_features_', 'max_depth', 'splitter', 'tree_'))
            _need(type(n_features) is int and n_features == width
                and type(max_features) is int and max_features == 1
                and type(fitted_features) is int and fitted_features == 1
                and type(max_depth) is int and max_depth == limit
                and type(splitter) is str and splitter == 'random', code)
            _need(type(feature_map) is np.ndarray and feature_map.ndim == 1
                and feature_map.shape == (width,) and feature_map.dtype.kind == 'i'
                and feature_map.dtype.isnative, code)
            _need(tuple(int(v) for v in feature_map) == tuple(range(width)), code)
            _need(type(tree) is Tree, code)
            n_features, count, observed_depth = _model_fields(tree, ('n_features', 'node_count', 'max_depth'))
            _need(type(n_features) is int and n_features == width, code)
            _need(type(count) is int and 1 <= count <= min(63, 2 * m - 1), code)
            left, right, feature, threshold, samples = _model_fields(tree,
                ('children_left', 'children_right', 'feature', 'threshold', 'n_node_samples'))
            for array in (left, right, feature, samples):
                _need(type(array) is np.ndarray and array.ndim == 1 and array.shape == (count,)
                    and array.dtype == np.dtype(np.intp) and array.dtype.isnative, code)
            _need(type(threshold) is np.ndarray and threshold.ndim == 1
                and threshold.shape == (count,) and threshold.dtype == np.dtype('float64')
                and threshold.dtype.isnative and bool(np.isfinite(threshold).all()), code)
            nodes = []
            for index in range(count):
                l, r, f, n = (int(array[index]) for array in (left, right, feature, samples))
                t = float(threshold[index])
                if l == -1 or r == -1:
                    _need(l == r == -1 and f == -2 and t == -2., code)
                    nodes.append(IForestNumericNode(None, None, None, None, n))
                else:
                    _need(0 <= f < width, code)
                    nodes.append(IForestNumericNode(l, r, int(feature_map[f]), t, n))
            trees.append(IForestNumericTree(tuple(nodes)))
            observed_depths.append(observed_depth)
        state = IForestNumericState(NUMERIC_STATE_VERSION, NUMERIC_STATE_PROFILE_ID,
            NUMERIC_STATE_ALGORITHM_ID, width, tuple(range(width)), m, tuple(trees))
        # P1 alone validates topology, root/child sample counts and depth bounds.
        _p1_call(encode_iforest_numeric_state, state, exporting=True)
        for tree, observed in zip(state.trees, observed_depths, strict=True):
            pending, maximum = [(0, 0)], 0
            while pending:
                index, depth = pending.pop()
                maximum = max(maximum, depth)
                node = tree.nodes[index]
                if node.left is not None:
                    pending.extend(((node.left, depth + 1), (node.right, depth + 1)))
            _need(type(observed) is int and observed == maximum, code)
        return state
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        _unknown(error)


def _original_scores(np, returned, count):
    _need(type(returned) is np.ndarray and returned.ndim == 1 and returned.shape == (count,)
        and returned.dtype == np.dtype('float64') and returned.dtype.isnative,
        'INVALID_MODEL_SCORES')
    _need(bool(np.isfinite(returned).all()), 'INVALID_MODEL_SCORES')
    scores = tuple(-float(value) for value in returned)
    _need(all(math.isfinite(value) and 0. < value <= 1. for value in scores), 'INVALID_MODEL_SCORES')
    return scores


def _compare_scores(scores, original, count):
    _need(type(scores) is tuple and len(scores) == count, 'SCORE_MISMATCH')
    _need(all(type(value) is float and math.isfinite(value) and 0. < value <= 1.
              for value in scores), 'SCORE_MISMATCH')
    _need(all(a.hex() == b.hex() for a, b in zip(scores, original, strict=True)), 'SCORE_MISMATCH')


def _calibrate(np, scores, indices, *, replay):
    from .evaluation.calibration import calibrate
    code = 'CALIBRATION_MISMATCH' if replay else 'INVALID_MODEL_SCORES'
    try:
        with np.errstate(over='raise', invalid='raise'):
            threshold = calibrate([scores[i] for i in indices])
        _need(type(threshold) is float and math.isfinite(threshold), code)
        return threshold
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) in (ValueError, FloatingPointError, OverflowError):
            raise ReleaseIFLearnedError(code) from None
        _unknown(error)


def _reference(value):
    return ReleaseIFLearnedReference(value.profile_id, value.context_sha256,
                                    value.manifest_sha256, value.manifest_byte_count)


def _configuration(value):
    return ReleaseIFLearnedConfiguration(*(getattr(value, field.name)
        for field in fields(ReleaseIFLearnedConfiguration)))


def _population(result):
    return _population_sha256(minute_count=len(result.scored_mask),
        scored_mask=result.scored_mask, train_indices=result.train_indices,
        calibration_indices=result.calibration_indices,
        preprocessing_fit_indices=result.preprocessing_fit_indices)


def _semantics(pair, view, *, code):
    expected = _feature_columns(view)
    names = pair.configuration.feature_names
    _need(type(pair.configuration.numeric_rules_id) is str
        and pair.configuration.numeric_rules_id == 'c17-release-log1p-mad-input-rules-v1', code)
    _need(type(names) is tuple and len(names) == 13
        and all(type(name) is str for name in names), code)
    _need(tuple('current:' + name for name in names) == expected[:13], code)
    return expected


def fit_release_iforest_learned(pair: ReleaseModelInputPair, *, view: str) -> ReleaseIFLearnedRun:
    """Fit once, compare all common scores, then form the two in-memory packages."""
    try:
        _need(type(view) is str and view in ('current13', 'h30_26'), 'INVALID_LEARNED_ARGUMENTS')
        np, old, saved, pair_type = _numerical()
        _need(type(pair) is pair_type, 'INVALID_LEARNED_ARGUMENTS')
        inputs = _if_call(old._validated_inputs, pair, view)
        config = old._configuration(inputs.matrix.shape[1], len(inputs.train_indices))
        _python_runtime()
        _need(type(np.__version__) is str and np.__version__ == '2.5.4', 'INCOMPATIBLE_RUNTIME')
        joblib, sklearn, active, backend_type, IsolationForest, _, _ = _models()
        _need(type(sklearn.__version__) is str and sklearn.__version__ == '1.9.1'
            and type(joblib.__version__) is str and joblib.__version__ == '1.6.0', 'INCOMPATIBLE_RUNTIME')
        columns = _semantics(pair, view, code='INPUT_BINDING_MISMATCH')
        from .iforest_numeric_state import score_iforest_numeric_state
        with joblib.parallel_backend('threading', n_jobs=1), \
                sklearn.config_context(working_memory=1024), np.errstate(under='ignore'):
            _serial(np, sklearn, active, backend_type)
            model = _model_call(IsolationForest, **_parameters(config), warm_start=False, verbose=0)
            _need(type(model) is IsolationForest, 'INVALID_MODEL_STATE')
            _serial(np, sklearn, active, backend_type)
            _model_call(model.fit, inputs.matrix[list(inputs.train_indices)])
            _serial(np, sklearn, active, backend_type)
            returned = _model_call(model.score_samples, inputs.matrix[list(inputs.common_indices)])
            original = _original_scores(np, returned, len(inputs.common_indices))
            _serial(np, sklearn, active, backend_type)
            state = _export_retained_model(model, config)
            replayed = _p1_call(score_iforest_numeric_state, state,
                                inputs.matrix[list(inputs.common_indices)])
            _compare_scores(replayed, original, len(inputs.common_indices))
            full = [None] * len(inputs.matrix)
            for index, score in zip(inputs.common_indices, original, strict=True):
                full[index] = score
            mask = tuple(value is not None for value in full)
            threshold = _calibrate(np, full, inputs.calibration_indices, replay=False)
            predictions = tuple(value > threshold if ok else None for value, ok in zip(full, mask))
            result = old.ReleaseIFResult('c17-release-iforest-engineering-v1', view,
                pair.raw_identity, pair.prepared_identity, pair.configuration_sha256,
                tuple(full), predictions, mask, threshold, inputs.train_indices,
                inputs.calibration_indices, inputs.preprocessing_fit_indices, config)
            result_package = _result_call(saved.make_release_if_result_package, pair, result)
            context = ReleaseIFLearnedContext(LEARNED_PACKAGE_PROFILE_ID, view,
                _reference(pair.raw_identity), _reference(pair.prepared_identity),
                _reference(result_package.identity), pair.configuration_sha256,
                len(full), len(result.train_indices), len(result.calibration_indices),
                len(result.preprocessing_fit_indices), _population(result),
                pair.configuration.numeric_rules_id, columns, _configuration(config), LEARNED_FIT_RUNTIME_ID)
            learned = _make_release_if_learned_package(context, state)
            return ReleaseIFLearnedRun(result_package, learned)
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        _unknown(error)


def replay_release_iforest_learned(package: ReleaseIFLearnedPackage,
    pair: ReleaseModelInputPair, result_package: ReleaseIFResultPackage,
) -> ReleaseIFLearnedReplayReport:
    """Bind explicit supplied declarations and replay every common score once."""
    try:
        encode_release_if_learned_package(package)
        np, _, saved, pair_type = _numerical()
        _need(type(result_package) is saved.ReleaseIFResultPackage, 'INVALID_LEARNED_ARGUMENTS')
        _result_call(saved.encode_release_if_result_package, result_package)
        context = package.context
        _need(_reference(result_package.identity) == context.result_identity, 'INPUT_BINDING_MISMATCH')
        _need(type(pair) is pair_type, 'INVALID_LEARNED_ARGUMENTS')
        inputs = _result_call(saved._pair_inputs, pair, context.view)
        result = result_package.result
        _result_call(saved._bind, result_package.context, result, pair, inputs)
        columns = _semantics(pair, context.view, code='INPUT_BINDING_MISMATCH')
        comparisons = ((context.view, result.view),
            (context.raw_identity, _reference(pair.raw_identity)),
            (context.prepared_identity, _reference(pair.prepared_identity)),
            (context.result_identity, _reference(result_package.identity)),
            (context.configuration_sha256, pair.configuration_sha256),
            (context.minute_count, len(inputs.matrix)),
            (context.train_count, len(result.train_indices)),
            (context.calibration_count, len(result.calibration_indices)),
            (context.preprocessing_fit_count, len(result.preprocessing_fit_indices)),
            (context.model_configuration, _configuration(result.configuration)),
            (context.input_rules_id, pair.configuration.numeric_rules_id),
            (context.feature_columns, columns), (context.population_sha256, _population(result)),
            (package.state.max_samples, min(32, len(inputs.train_indices))))
        _need(all(actual == expected for actual, expected in comparisons), 'INPUT_BINDING_MISMATCH')
        _python_runtime()
        from .iforest_numeric_state import score_iforest_numeric_state
        scores = _p1_call(score_iforest_numeric_state, package.state,
                          inputs.matrix[list(inputs.common_indices)])
        common = set(inputs.common_indices)
        _need(all(ok == (i in common) and (ok or result.scores[i] is None
            and result.predictions[i] is None) for i, ok in enumerate(result.scored_mask)), 'SCORE_MISMATCH')
        _compare_scores(scores, tuple(result.scores[i] for i in inputs.common_indices), len(inputs.common_indices))
        full = [None] * len(inputs.matrix)
        for index, score in zip(inputs.common_indices, scores, strict=True):
            full[index] = score
        threshold = _calibrate(np, full, inputs.calibration_indices, replay=True)
        _need(threshold.hex() == result.threshold.hex(), 'CALIBRATION_MISMATCH')
        predictions = tuple(value > threshold if i in common else None for i, value in enumerate(full))
        _need(predictions == result.predictions, 'PREDICTION_MISMATCH')
        return ReleaseIFLearnedReplayReport(LEARNED_PACKAGE_PROFILE_ID,
            'EXPLICIT_INPUT_NUMERICAL_REPLAY_ONLY', package.identity, context.result_identity,
            len(inputs.common_indices), len(inputs.calibration_indices), 'MATCHED', 'MATCHED',
            'MATCHED', 'NOT_AUTHENTICATED', 'NOT_PERFORMED')
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        _unknown(error)
