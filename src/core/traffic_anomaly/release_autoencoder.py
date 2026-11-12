"""Fixed in-memory release AE interface; no source authentication or replay.

Only standard-library declarations run at import. Numerical execution is serial
and belongs to the private context boundary, never to caller-supplied adapters.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .release_minute_contract import ReleaseMinutePackageIdentity
    from .release_inputs import ReleaseInputIdentity
    from .release_model_inputs import ReleaseModelInputPair


_PROFILE = 'c17-release-ae-engineering-v1'
_SCOPE = 'IN_MEMORY_ENGINEERING_NUMERICAL_RESULT_ONLY'
_CODES = frozenset((
    'INVALID_AE_ARGUMENTS', 'INVALID_AE_INPUT', 'RESOURCE_LIMIT',
    'NO_TRAINING_NORMAL', 'NO_CALIBRATION_NORMAL', 'INVALID_INPUT_NUMERIC',
    'INCOMPATIBLE_RUNTIME', 'MODEL_UNAVAILABLE', 'MODEL_ERROR',
    'INVALID_MODEL_STATE', 'NONFINITE_TRAINING', 'INVALID_MODEL_SCORES',
    'RNG_RESTORATION_FAILED', 'AE_ERROR',
))
_ADMISSION_CODES = {
    'INVALID_IF_ARGUMENTS': 'INVALID_AE_ARGUMENTS',
    'INVALID_IF_INPUT': 'INVALID_AE_INPUT',
    'RESOURCE_LIMIT': 'RESOURCE_LIMIT',
    'NO_TRAINING_NORMAL': 'NO_TRAINING_NORMAL',
    'NO_CALIBRATION_NORMAL': 'NO_CALIBRATION_NORMAL',
    'INVALID_INPUT_NUMERIC': 'INVALID_INPUT_NUMERIC',
}


class ReleaseAEError(ValueError):
    """An exact finite code; never include dependency or input diagnostics."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in _CODES else 'AE_ERROR'
        super().__init__(self.code)


def _need(condition, code='AE_ERROR'):
    if not condition:
        raise ReleaseAEError(code) from None


def _owned_code(error, owner, allowed):
    if type(error) is not owner:
        return None
    try:
        code = error.code
    except (KeyboardInterrupt, SystemExit):
        raise
    except MemoryError:
        raise ReleaseAEError('RESOURCE_LIMIT') from None
    except Exception:
        return None
    return code if type(code) is str and code in allowed else None


def _raise_safe(error, fallback='AE_ERROR'):
    error_type = type(error)
    if issubclass(error_type, (KeyboardInterrupt, SystemExit)):
        raise error from None
    if issubclass(error_type, MemoryError):
        raise ReleaseAEError('RESOURCE_LIMIT') from None
    if error_type is ReleaseAEError:
        code = _owned_code(error, ReleaseAEError, _CODES)
        raise ReleaseAEError(code if code is not None else 'AE_ERROR') from None
    if issubclass(error_type, ReleaseAEError):
        raise ReleaseAEError('AE_ERROR') from None
    raise ReleaseAEError(fallback) from None


def _missing_module(error, root, code):
    if type(error) is not ModuleNotFoundError:
        return 'AE_ERROR'
    try:
        name = error.name
    except BaseException as failure:
        _raise_safe(failure)
    return code if type(name) is str and name == root else 'AE_ERROR'


def _admit(pair, view):
    try:
        from . import release_iforest
    except ModuleNotFoundError as error:
        raise ReleaseAEError(_missing_module(error, 'numpy', 'INCOMPATIBLE_RUNTIME')) from None
    except Exception as error:
        _raise_safe(error)
    try:
        return release_iforest._validated_inputs(pair, view)
    except (KeyboardInterrupt, SystemExit):
        raise
    except MemoryError:
        raise ReleaseAEError('RESOURCE_LIMIT') from None
    except Exception as error:
        code = _owned_code(error, release_iforest.ReleaseIFError, _ADMISSION_CODES)
        raise ReleaseAEError(_ADMISSION_CODES.get(code, 'AE_ERROR')) from None


@dataclass(frozen=True, slots=True)
class ReleaseAEConfiguration:
    model_profile_id: str
    parameter_status: str
    method: str
    input_width: int
    history_window: int | None
    architecture: tuple[int, ...]
    parameter_count: int
    activation: str
    device: str
    training_dtype: str
    score_dtype: str
    score_rule: str
    epochs: int
    batch_strategy: str
    shuffle: bool
    optimizer: str
    optimizer_cpu_guard: str
    optimizer_healthcheck_api: str
    learning_rate: float
    adam_betas: tuple[float, float]
    adam_epsilon: float
    weight_decay: float
    amsgrad: bool
    random_state: int
    fit_scope: str
    calibration_scope: str
    quantile: float
    quantile_method: str
    alarm_comparison: str
    preprocessing_fit_provenance: str


@dataclass(frozen=True, slots=True)
class ReleaseAECalibration:
    quantile: float
    method: str
    comparison: str
    sample_count: int
    equal_count: int
    strictly_above_count: int


@dataclass(frozen=True, slots=True)
class ReleaseAERuntime:
    python_version: str
    numpy_version: str
    torch_version: str
    device: str
    torch_num_threads: int
    torch_num_interop_threads: int


@dataclass(frozen=True, slots=True)
class ReleaseAEResult:
    profile_id: str
    scope: str
    view: str
    raw_identity: ReleaseMinutePackageIdentity
    prepared_identity: ReleaseInputIdentity
    configuration_sha256: str
    feature_columns: tuple[str, ...]
    scores: tuple[float | None, ...]
    predictions: tuple[bool | None, ...]
    scored_mask: tuple[bool, ...]
    current_reconstruction_mse: tuple[float | None, ...]
    history_deviation_reconstruction_mse: tuple[float | None, ...]
    threshold: float
    train_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    preprocessing_fit_indices: tuple[int, ...]
    training_losses: tuple[float, ...]
    configuration: ReleaseAEConfiguration
    calibration: ReleaseAECalibration
    runtime: ReleaseAERuntime


def _prescribed_configuration(view):
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


def _configuration(view):
    from .candidate_ae_profiles import (
        MODEL_PROFILE_ID, resolve_candidate_ae_configuration, strict_configuration_equal,
    )
    expected = _prescribed_configuration(view)
    resolved = resolve_candidate_ae_configuration(expected['method'], expected['history_window'],
                                                 model_profile_id=MODEL_PROFILE_ID)
    _need(strict_configuration_equal(resolved, expected), 'INCOMPATIBLE_RUNTIME')
    copied = dict(resolved)
    copied['architecture'] = tuple(resolved['architecture'])
    copied['adam_betas'] = tuple(resolved['adam_betas'])
    return resolved, ReleaseAEConfiguration(**copied)


def _runtime_versions():
    import sys
    import numpy as np
    return sys.version.split()[0], np.__version__


def _load_torch():
    import torch
    return torch


def _cpu_scope(torch):
    from .candidate_autoencoder import _cpu_execution
    return _cpu_execution(torch)


def _build_network(width, *, model_profile_id):
    from .candidate_ae_weights import build_candidate_ae_network
    return build_candidate_ae_network(width, model_profile_id=model_profile_id)


def _cpu_optimizer(torch, parameters):
    from .candidate_autoencoder import _cpu_adam
    return _cpu_adam(torch, parameters)


def _check_model(network, configuration, torch):
    from .candidate_autoencoder import _check_network
    return _check_network(network, configuration, torch)


def _score_common(network, matrix, method):
    from .candidate_autoencoder import _reconstruction_scores
    return _reconstruction_scores(network, matrix, method)


def _execution_runtime():
    try:
        versions = _runtime_versions()
    except ModuleNotFoundError as error:
        raise ReleaseAEError(_missing_module(error, 'numpy', 'INCOMPATIBLE_RUNTIME')) from None
    except BaseException as error:
        _raise_safe(error)
    _need(type(versions) is tuple and len(versions) == 2
          and all(type(value) is str for value in versions), 'INCOMPATIBLE_RUNTIME')
    python_version, numpy_version = versions
    parts = python_version.split('.')
    _need(len(parts) == 3 and parts[:2] == ['3', '14'] and parts[2].isascii()
          and parts[2].isdigit() and numpy_version == '2.5.4', 'INCOMPATIBLE_RUNTIME')
    try:
        torch = _load_torch()
    except ModuleNotFoundError as error:
        raise ReleaseAEError(_missing_module(error, 'torch', 'MODEL_UNAVAILABLE')) from None
    except BaseException as error:
        _raise_safe(error)
    try:
        # The pinned trusted module exposes TorchVersion(str); compare only the
        # normalized builtin string, never its overloaded comparison operators.
        torch_version = str(torch.__version__)
        _need(type(torch_version) is str and torch_version == '2.14.1+cpu', 'INCOMPATIBLE_RUNTIME')
        required = (torch.Tensor, torch.from_numpy, torch.mean, torch.isfinite, torch.is_tensor,
                    torch.inference_mode, torch.enable_grad, torch.get_num_threads,
                    torch.get_num_interop_threads, torch.random.get_rng_state,
                    torch.random.set_rng_state, torch.random.default_generator.manual_seed,
                    torch.nn.Sequential, torch.nn.Linear, torch.nn.ReLU, torch.optim.Adam,
                    getattr(torch.optim.Adam, '_accelerator_graph_capture_health_check', None))
        _need(all(callable(value) for value in required) and issubclass(type(torch.Tensor), type)
              and getattr(torch, 'float32', None) is not None, 'INCOMPATIBLE_RUNTIME')
        runtime = dict(python_version=python_version, numpy_version=numpy_version,
            torch_version=torch_version, device='cpu', torch_num_threads=torch.get_num_threads(),
            torch_num_interop_threads=torch.get_num_interop_threads())
        _runtime(runtime, 'INCOMPATIBLE_RUNTIME')
    except BaseException as error:
        _raise_safe(error, 'INCOMPATIBLE_RUNTIME')
    return torch, runtime


def _raise_model(error, stage):
    """Only closed helper owners may supply codes, with a stage allowlist."""
    error_type = type(error)
    if issubclass(error_type, (KeyboardInterrupt, SystemExit, MemoryError)) or error_type is ReleaseAEError:
        _raise_safe(error)
    from .candidate_autoencoder import CandidateAEError
    from .candidate_ae_weights import CandidateAEWeightsError
    if error_type is CandidateAEWeightsError:
        mapping = {'MODEL_BUILD_ERROR': 'MODEL_ERROR'} if stage == 'construction' else {}
        code = _owned_code(error, CandidateAEWeightsError, mapping)
        raise ReleaseAEError(mapping.get(code, 'AE_ERROR')) from None
    if error_type is CandidateAEError:
        mapping = {}
        if stage in ('network', 'updated'):
            mapping = {'INCOMPATIBLE_AE_NETWORK': 'INVALID_MODEL_STATE',
                'NONFINITE_AE_WEIGHTS': 'NONFINITE_TRAINING' if stage == 'updated' else 'INVALID_MODEL_STATE'}
        elif stage == 'optimizer':
            mapping = {'CPU_ONLY_AE_OPTIMIZER': 'INVALID_MODEL_STATE',
                       'UNSUPPORTED_TORCH_ADAM_API': 'INCOMPATIBLE_RUNTIME'}
        elif stage == 'training':
            mapping = {'CPU_ONLY_AE_OPTIMIZER': 'INVALID_MODEL_STATE'}
        elif stage == 'score':
            mapping = dict.fromkeys(('NONFINITE_AE_INPUT', 'NONFINITE_AE_OUTPUT', 'NONFINITE_AE_SCORE'),
                                    'INVALID_MODEL_SCORES')
        code = _owned_code(error, CandidateAEError, mapping)
        raise ReleaseAEError(mapping.get(code, 'AE_ERROR')) from None
    if issubclass(error_type, (CandidateAEError, CandidateAEWeightsError, ReleaseAEError)):
        raise ReleaseAEError('AE_ERROR') from None
    _raise_safe(error, 'MODEL_ERROR')


def _training_tensor(value, torch, shape, *, exact=False):
    # Parameters are nn.Parameter subclasses; recovered/train/loss values are
    # native Tensor. torch.Size is normalized without requiring a tuple type.
    _need((type(value) is torch.Tensor if exact else issubclass(type(value), torch.Tensor)),
          'INVALID_MODEL_STATE')
    _need(value.device.type == 'cpu' and value.dtype == torch.float32
          and tuple(value.shape) == tuple(shape), 'INVALID_MODEL_STATE')
    _need(bool(torch.isfinite(value).all()), 'NONFINITE_TRAINING')


@contextmanager
def _numeric_operation(values, configuration):
    """One fixed model, five updates and one complete-common reconstruction.

    The CPU context also encloses public calibration and immutable assembly.
    Preserve errors actually observed here; unchanged helper internals may hide
    earlier errors or fail before completing all sequential RNG restorations.
    """
    import numpy as np
    torch, runtime = _execution_runtime()
    primary = None
    stage = 'construction'
    try:
        with _cpu_scope(torch):
            try:
                model = _build_network(configuration['input_width'],
                                       model_profile_id=configuration['model_profile_id'])
                stage = 'network'
                _check_model(model, configuration, torch)
                parameters = tuple(model.parameters())
                _need(bool(parameters), 'INVALID_MODEL_STATE')
                stage = 'optimizer'
                optimizer = _cpu_optimizer(torch, parameters)
                stage = 'training'
                train = np.array(values.matrix[list(values.train_indices)], copy=True)
                tensor = torch.from_numpy(train)
                _training_tensor(tensor, torch, train.shape, exact=True)
                losses = []
                model.train()
                # Mirrors the accepted candidate loop's update order only;
                # snapshot, evaluation, persistence and replay are not copied.
                for _ in range(5):
                    stage = 'training'
                    optimizer.zero_grad(set_to_none=True)
                    recovered = model(tensor)
                    _training_tensor(recovered, torch, tensor.shape, exact=True)
                    loss = torch.mean((recovered - tensor) ** 2)
                    _training_tensor(loss, torch, (), exact=True)
                    observed_loss = float(loss.detach().item())
                    _need(_finite_float(observed_loss), 'NONFINITE_TRAINING')
                    losses.append(observed_loss)
                    loss.backward()
                    for parameter in parameters:
                        _need(parameter.grad is not None, 'INVALID_MODEL_STATE')
                        _training_tensor(parameter.grad, torch, parameter.shape)
                    optimizer.step()
                    stage = 'updated'
                    _check_model(model, configuration, torch)
                    for state in optimizer.state.values():
                        for value in state.values():
                            if torch.is_tensor(value):
                                _need(value.device.type == 'cpu', 'INVALID_MODEL_STATE')
                                _need(bool(torch.isfinite(value).all()), 'NONFINITE_TRAINING')
                stage = 'score'
                observed = _score_common(model, values.matrix[list(values.common_indices)],
                                         configuration['method'])
                _need(type(observed) is tuple and len(observed) == 3, 'INVALID_MODEL_SCORES')
                scores, current, history = observed
                stage = 'public'
                yield dict(scores=scores, current_reconstruction_mse=current,
                    history_deviation_reconstruction_mse=history,
                    training_losses=tuple(losses), runtime=runtime)
            except BaseException as error:
                primary = error
                raise
    except BaseException as error:
        if primary is None:
            _raise_safe(error, 'RNG_RESTORATION_FAILED')
        if stage == 'public':
            # The public orchestration owns body conversion. Do not read the
            # same owning code a second time or replace its received primary.
            raise primary from None
        _raise_model(primary, stage)
    if primary is not None:
        if stage == 'public':
            raise primary from None
        _raise_model(primary, stage)


def _runtime(payload, code='AE_ERROR'):
    _need(type(payload) is dict and payload.keys() == {field.name for field in fields(ReleaseAERuntime)}, code)
    for name in ('python_version', 'numpy_version', 'torch_version', 'device'):
        _need(type(payload[name]) is str, code)
    version = payload['python_version'].split('.')
    _need(len(version) == 3 and version[:2] == ['3', '14'] and version[2].isascii()
          and version[2].isdigit(), code)
    _need(payload['numpy_version'] == '2.5.4' and payload['torch_version'] == '2.14.1+cpu'
          and payload['device'] == 'cpu', code)
    for name in ('torch_num_threads', 'torch_num_interop_threads'):
        _need(type(payload[name]) is int and 1 <= payload[name] <= 64, code)
    return ReleaseAERuntime(**payload)


def _finite_float(value):
    return type(value) is float and math.isfinite(value) and value >= 0.


def _assemble(pair, view, values, configuration, payload):
    import numpy as np
    from .candidate_inputs import G13U_FEATURE_NAMES
    from .evaluation.calibration import calibrate

    names = {'scores', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse',
             'training_losses', 'runtime'}
    _need(type(payload) is dict and payload.keys() == names, 'INVALID_MODEL_SCORES')
    scores, current, history = (payload[name] for name in
        ('scores', 'current_reconstruction_mse', 'history_deviation_reconstruction_mse'))
    for vector in (scores, current, history):
        _need(type(vector) is np.ndarray and vector.dtype == np.dtype('float64')
              and vector.shape == (len(values.common_indices),), 'INVALID_MODEL_SCORES')
    _need(bool(np.isfinite(scores).all() and np.isfinite(current).all()
               and (scores >= 0.).all() and (current >= 0.).all()), 'INVALID_MODEL_SCORES')
    if view == 'current13':
        _need(bool(np.isnan(history).all() and np.array_equal(scores, current)), 'INVALID_MODEL_SCORES')
    else:
        with np.errstate(over='ignore', invalid='ignore'):
            combined = .5 * current + .5 * history
        _need(bool(np.isfinite(history).all() and (history >= 0.).all()
                   and np.array_equal(scores, combined)), 'INVALID_MODEL_SCORES')
    losses = payload['training_losses']
    _need(type(losses) in (list, tuple) and len(losses) == 5
          and all(_finite_float(loss) for loss in losses), 'NONFINITE_TRAINING')
    runtime = _runtime(payload['runtime'])
    n = len(values.matrix)
    full_scores, full_current, full_history = ([None] * n for _ in range(3))
    for position, index in enumerate(values.common_indices):
        full_scores[index] = float(scores[position])
        full_current[index] = float(current[position])
        if view == 'h30_26':
            full_history[index] = float(history[position])
    selected = np.asarray([full_scores[index] for index in values.calibration_indices], dtype=np.float64)
    try:
        threshold = calibrate(selected)
    except Exception as error:
        _raise_safe(error, 'INVALID_MODEL_SCORES')
    _need(_finite_float(threshold), 'INVALID_MODEL_SCORES')
    common = set(values.common_indices)
    mask = tuple(index in common for index in range(n))
    columns = tuple('current:' + name for name in G13U_FEATURE_NAMES)
    if view == 'h30_26':
        columns += tuple('residual_h30:' + name for name in G13U_FEATURE_NAMES)
    result = ReleaseAEResult(_PROFILE, _SCOPE, view, pair.raw_identity, pair.prepared_identity,
        pair.configuration_sha256, columns, tuple(full_scores),
        tuple(score > threshold if score is not None else None for score in full_scores), mask,
        tuple(full_current), tuple(full_history), threshold, values.train_indices,
        values.calibration_indices, values.preprocessing_fit_indices, tuple(losses), configuration,
        ReleaseAECalibration(.99, 'linear', 'STRICT_GREATER', len(selected),
            sum(float(score) == threshold for score in selected),
            sum(float(score) > threshold for score in selected)), runtime)
    _validate_result(result, pair, values, configuration, columns)
    return result


def _validate_result(result, pair, values, configuration, columns):
    """Check the final primitive projection without any fit/forward/Q99/read."""
    _need(type(result) is ReleaseAEResult and type(result.profile_id) is str
          and result.profile_id == _PROFILE and type(result.scope) is str
          and result.scope == _SCOPE and type(result.view) is str
          and result.view in ('current13', 'h30_26'))
    _need(result.raw_identity is pair.raw_identity and result.prepared_identity is pair.prepared_identity
          and type(result.configuration_sha256) is str
          and result.configuration_sha256 == pair.configuration_sha256)
    _need(type(result.configuration) is ReleaseAEConfiguration and result.configuration == configuration)
    _need(type(result.feature_columns) is tuple and result.feature_columns == columns
          and all(type(name) is str for name in result.feature_columns))
    for field in fields(configuration):
        actual = getattr(configuration, field.name)
        expected = _prescribed_configuration(result.view)[field.name]
        if type(expected) is list:
            expected = tuple(expected)
        _need(type(actual) is type(expected) and actual == expected)
        if type(actual) is tuple:
            _need(all(type(a) is type(b) and a == b for a, b in zip(actual, expected)))
    n = len(values.matrix)
    for vector in (result.scores, result.predictions, result.scored_mask,
                   result.current_reconstruction_mse, result.history_deviation_reconstruction_mse):
        _need(type(vector) is tuple and len(vector) == n)
    _need(_finite_float(result.threshold))
    common = set(values.common_indices)
    for index, (score, prediction, ok, current, history) in enumerate(zip(
            result.scores, result.predictions, result.scored_mask,
            result.current_reconstruction_mse, result.history_deviation_reconstruction_mse)):
        _need(type(ok) is bool and ok is (index in common))
        if ok:
            _need(_finite_float(score) and _finite_float(current) and type(prediction) is bool
                  and prediction is (score > result.threshold))
            if result.view == 'current13':
                _need(history is None and score == current)
            else:
                _need(_finite_float(history) and score == .5 * current + .5 * history)
        else:
            _need(score is prediction is current is history is None)
    for name in ('train_indices', 'calibration_indices', 'preprocessing_fit_indices'):
        indices = getattr(result, name)
        _need(type(indices) is tuple and indices == getattr(values, name)
              and all(type(index) is int and 0 <= index < n for index in indices)
              and all(a < b for a, b in zip(indices, indices[1:])))
    _need(bool(result.train_indices) and bool(result.calibration_indices)
          and not set(result.train_indices) & set(result.calibration_indices)
          and set(result.train_indices) <= set(result.preprocessing_fit_indices)
          and set(result.train_indices + result.calibration_indices) <= common)
    _need(type(result.training_losses) is tuple and len(result.training_losses) == 5
          and all(_finite_float(loss) for loss in result.training_losses))
    calibration = result.calibration
    _need(type(calibration) is ReleaseAECalibration and type(calibration.quantile) is float
          and calibration.quantile == .99 and type(calibration.method) is str
          and calibration.method == 'linear' and type(calibration.comparison) is str
          and calibration.comparison == 'STRICT_GREATER')
    selected = tuple(result.scores[index] for index in result.calibration_indices)
    for name, expected in (('sample_count', len(selected)),
                           ('equal_count', sum(score == result.threshold for score in selected)),
                           ('strictly_above_count', sum(score > result.threshold for score in selected))):
        _need(type(getattr(calibration, name)) is int and getattr(calibration, name) == expected)
    _need(type(result.runtime) is ReleaseAERuntime)
    _runtime({field.name: getattr(result.runtime, field.name) for field in fields(ReleaseAERuntime)})


def fit_release_autoencoder(pair: ReleaseModelInputPair, *, view: str) -> ReleaseAEResult:
    """Admit saved inputs and fit fixed CPU settings, returning immutable values.

    Public calibration and assembly remain inside the numeric CPU context. The
    first error actually received by this orchestration survives later cleanup;
    errors hidden inside unchanged helpers cannot be recovered here.
    """
    _need(type(view) is str and view in ('current13', 'h30_26'), 'INVALID_AE_ARGUMENTS')
    values = _admit(pair, view)
    try:
        configuration, frozen_configuration = _configuration(view)
    except Exception as error:
        _raise_safe(error)
    primary = None
    try:
        with _numeric_operation(values, configuration) as payload:
            try:
                result = _assemble(pair, view, values, frozen_configuration, payload)
            except BaseException as error:
                primary = error
                raise
    except BaseException as error:
        _raise_safe(primary if primary is not None else error,
                    'AE_ERROR' if primary is not None else 'RNG_RESTORATION_FAILED')
    if primary is not None:
        _raise_safe(primary)
    return result
