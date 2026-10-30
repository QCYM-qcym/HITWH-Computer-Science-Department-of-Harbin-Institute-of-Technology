"""CPU toy AE execution for verified synthetic 13/26D candidate snapshots.

Imports no training runtime until execution. Files and executable model loaders
are deliberately absent; JSON construction belongs to candidate_ae_weights.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import math
import random

import numpy as np

from .candidate_artifacts import VerifiedCandidateArtifacts, _same
from .candidate_evaluation import evaluate_candidate_predictions
from .candidate_inputs import CandidateMinuteBatch, G13U_FEATURE_NAMES, MAX_MINUTES, _eligible
from .candidate_records import POLICIES
from .evaluation.calibration import calibrate


MODEL_PROFILE_ID = 'c17-i1-g13u-ae-synthetic-v1'


class CandidateAEError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code='INVALID_AE_INPUT'):
    if not condition:
        raise CandidateAEError(code)


def _readonly(values):
    array = np.asarray(values)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


def _configuration(method, history_window):
    _require(isinstance(method, str) and method in ('current_ae', 'history_ae'))
    _require(history_window is None if method == 'current_ae'
             else type(history_window) is int and history_window in (15, 30))
    width = 13 if method == 'current_ae' else 26
    return dict(model_profile_id=MODEL_PROFILE_ID, parameter_status='ENGINEERING_TOY_ONLY',
        method=method, input_width=width, history_window=history_window,
        architecture=[width, 8, 3, 8, width], parameter_count=288 if width == 13 else 509,
        activation='RELU_HIDDEN_LINEAR_OUTPUT', device='cpu', training_dtype='float32',
        score_dtype='float64', score_rule='FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT',
        epochs=5, batch_strategy='FULL_BATCH', shuffle=False, optimizer='Adam',
        optimizer_cpu_guard='INSTANCE_LOCAL_HEALTH_CHECK_V1',
        optimizer_healthcheck_api='_accelerator_graph_capture_health_check',
        learning_rate=.001, adam_betas=[.9, .999], adam_epsilon=1e-8,
        weight_decay=0., amsgrad=False, random_state=42,
        fit_scope='TRAIN_NORMAL_COMMON', calibration_scope='CALIBRATION_NORMAL_COMMON',
        quantile=.99, quantile_method='linear', alarm_comparison='STRICT_GREATER',
        preprocessing_fit_provenance='NOT_REESTIMATED')


def _mask(values, n):
    values = np.asarray(values)
    _require(values.shape == (n,) and values.dtype == np.dtype(bool))
    return values


def _inputs(snapshot, configuration):
    _require(isinstance(snapshot, VerifiedCandidateArtifacts))
    report = snapshot.report
    _require(report.get('status') == 'VERIFIED' and report.get('evidence_kind') == 'SYNTHETIC_ONLY'
             and report.get('policy_status') == 'AUDIT_ONLY'
             and report.get('time_basis') == 'synthetic_source_clock'
             and report.get('selected_policy') in POLICIES
             and report.get('checks', {}).get('source_replay') == 'VERIFIED'
             and report.get('checks', {}).get('fit_parameters') == 'NOT_REESTIMATED'
             and snapshot.feature_names == G13U_FEATURE_NAMES and snapshot.value_space == 'prepared')
    n = len(snapshot.timestamps)
    _require(1 <= n <= MAX_MINUTES)
    valid, common = _mask(snapshot.row_valid, n), _mask(snapshot.common_valid, n)
    train, calibration = _mask(snapshot.training_normal, n), _mask(snapshot.calibration_normal, n)
    _mask(snapshot.source_attack_label_present, n)
    for policy in POLICIES:
        labels = snapshot.labels[policy]
        _require(len(labels) == n and all(value in ('normal', 'attack', 'unknown') for value in labels))
        _require(np.array_equal(_mask(snapshot.normal_candidates[policy], n),
                                [value == 'normal' for value in labels]))
    h15, h30 = (_mask(snapshot.histories[h].valid, n) for h in (15, 30))
    _require(np.array_equal(common, h15 & h30) and not (common & ~valid).any())
    batch = CandidateMinuteBatch(snapshot.timestamps, snapshot.current_values, valid,
        snapshot.segment_ids, snapshot.partitions, value_space='prepared')
    normal = snapshot.normal_candidates[report['selected_policy']]
    all_normal = _eligible(batch, 30, normal) & common
    _require(np.array_equal(train, all_normal & (batch.partitions == 'train'))
             and np.array_equal(calibration, all_normal & (batch.partitions == 'calibration')))
    _require(train.any(), 'NO_TRAINING_NORMAL')
    _require(calibration.any(), 'NO_CALIBRATION_NORMAL')
    if configuration['method'] == 'current_ae':
        matrix = batch.values
    else:
        history = snapshot.histories[configuration['history_window']]
        _require(history.current.shape == history.residual.shape == (n, 13)
                 and np.array_equal(history.current, batch.values, equal_nan=True)
                 and np.isfinite(history.residual[history.valid]).all()
                 and np.isnan(history.residual[~history.valid]).all())
        expected = np.concatenate((history.current, history.residual), axis=1)
        expected[~history.valid] = np.nan
        _require(np.array_equal(history.joined, expected, equal_nan=True), 'INCOMPATIBLE_AE_HISTORY_LAYOUT')
        matrix = history.joined
    _require(matrix.shape == (n, configuration['input_width']) and np.isfinite(matrix[common]).all())
    with np.errstate(over='ignore', invalid='ignore'):
        converted = matrix.astype(np.float32)
    _require(np.isfinite(converted[common]).all(), 'NONFINITE_AE_INPUT')
    return batch, converted, common, train, calibration


@contextmanager
def _cpu_execution(torch):
    # fork_rng and torch.manual_seed query or seed accelerator modules. Only
    # save/seed/restore the CPU generator; do not alter thread/backend settings.
    numpy_state, python_state = np.random.get_state(), random.getstate()
    with torch.inference_mode(False), torch.enable_grad():
        saved = torch.random.get_rng_state().clone()
        try:
            torch.random.default_generator.manual_seed(42)
            yield
        finally:
            torch.random.set_rng_state(saved)
            np.random.set_state(numpy_state)
            random.setstate(python_state)


def _check_network(network, configuration, torch):
    width = configuration['input_width']
    _require(type(network) is torch.nn.Sequential and len(network) == 7, 'INCOMPATIBLE_AE_NETWORK')
    widths = [width, 8, 3, 8, width]
    for index, (left, right) in enumerate(zip(widths, widths[1:])):
        layer = network[index * 2]
        _require(type(layer) is torch.nn.Linear and layer.in_features == left
                 and layer.out_features == right and layer.bias is not None, 'INCOMPATIBLE_AE_NETWORK')
        if index < 3:
            _require(type(network[index * 2 + 1]) is torch.nn.ReLU, 'INCOMPATIBLE_AE_NETWORK')
    parameters = tuple(network.parameters())
    _require(sum(p.numel() for p in parameters) == configuration['parameter_count'], 'INCOMPATIBLE_AE_NETWORK')
    _require(all(p.device.type == 'cpu' and p.dtype == torch.float32
                 and bool(torch.isfinite(p).all()) for p in parameters), 'NONFINITE_AE_WEIGHTS')


def _cpu_adam(torch, parameters):
    """Keep Adam's update formula while replacing only its device-query hook.

    The pinned torch version queries accelerator availability in Adam.step's
    graph-capture health check even for CPU tensors. This local subclass instead
    verifies that capture is disabled and all parameters/gradients/state are CPU.
    It neither patches the global optimizer class nor supports accelerator use.
    """
    _require(callable(getattr(torch.optim.Adam, '_accelerator_graph_capture_health_check', None)),
             'UNSUPPORTED_TORCH_ADAM_API')
    parameters = tuple(parameters)
    _require(parameters and all(p.device.type == 'cpu' for p in parameters), 'CPU_ONLY_AE_OPTIMIZER')

    class CPUOnlyAdam(torch.optim.Adam):
        def _accelerator_graph_capture_health_check(self):
            _require(all(group.get('capturable') is False
                         and all(p.device.type == 'cpu' and (p.grad is None or p.grad.device.type == 'cpu')
                                 for p in group['params'])
                         for group in self.param_groups), 'CPU_ONLY_AE_OPTIMIZER')
            _require(all(not torch.is_tensor(value) or value.device.type == 'cpu'
                         for state in self.state.values() for value in state.values()), 'CPU_ONLY_AE_OPTIMIZER')

    return CPUOnlyAdam(parameters, lr=.001, betas=(.9, .999), eps=1e-8,
                       weight_decay=0., amsgrad=False, capturable=False)


def _reconstruction_scores(network, matrix, method):
    """Score the actual float32 input/output after promotion to float64."""
    import torch
    _require(method in ('current_ae', 'history_ae'))
    width = 13 if method == 'current_ae' else 26
    _require(isinstance(matrix, np.ndarray) and matrix.dtype == np.float32
             and matrix.ndim == 2 and matrix.shape[1] == width and np.isfinite(matrix).all(), 'NONFINITE_AE_INPUT')
    network.eval()
    with torch.inference_mode():
        output = network(torch.from_numpy(np.array(matrix, copy=True)))
        _require(output.device.type == 'cpu' and output.dtype == torch.float32
                 and tuple(output.shape) == matrix.shape and bool(torch.isfinite(output).all()), 'NONFINITE_AE_OUTPUT')
        recovered = output.numpy().astype(np.float64)
    with np.errstate(over='ignore', invalid='ignore'):
        error = (matrix.astype(np.float64) - recovered) ** 2
        current = error[:, :13].mean(axis=1, dtype=np.float64)
        historical = (error[:, 13:].mean(axis=1, dtype=np.float64) if width == 26
                      else np.full(len(matrix), np.nan))
        score = .5 * current + .5 * historical if width == 26 else current.copy()
    _require(np.isfinite(error).all() and np.isfinite(current).all()
             and np.isfinite(score).all() and (width == 13 or np.isfinite(historical).all()), 'NONFINITE_AE_SCORE')
    return score, current, historical


def _calibrate(scores, valid, mask):
    _require(mask.any() and not (mask & ~valid).any(), 'NO_CALIBRATION_NORMAL')
    _require(np.isfinite(scores[valid]).all() and np.isnan(scores[~valid]).all(), 'NONFINITE_AE_SCORE')
    selected = scores[mask]
    threshold = calibrate(selected)
    _require(math.isfinite(threshold), 'NONFINITE_AE_SCORE')
    alarms = np.zeros(len(scores), bool)
    alarms[valid] = scores[valid] > threshold
    metadata = dict(sample_count=len(selected), quantile=.99, method='linear', comparison='STRICT_GREATER',
        order_position_zero_based=(len(selected)-1)*.99,
        strictly_above_count=int((selected > threshold).sum()), equal_count=int((selected == threshold).sum()))
    return threshold, _readonly(alarms), metadata


@dataclass(frozen=True, slots=True)
class CandidateAEResult:
    model: object
    scores: np.ndarray
    score_valid: np.ndarray
    alarms: np.ndarray
    threshold: float
    calibration: dict
    evaluation: dict
    configuration: dict
    fit_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    current_reconstruction_mse: np.ndarray
    history_deviation_reconstruction_mse: np.ndarray
    training_losses: tuple[float, ...]
    runtime: dict


def _evaluation(snapshot, batch, common, alarms):
    return evaluate_candidate_predictions(labels=snapshot.labels, partitions=batch.partitions,
        score_valid=common, alarms=alarms, source_attack_label_present=snapshot.source_attack_label_present,
        score_origin_policy=snapshot.report['selected_policy'])


def compute_synthetic_candidate_ae(snapshot, *, method, history_window=None):
    """Run five fixed full-batch CPU updates; never opens paths or fits preprocessing."""
    try:
        configuration = _configuration(method, history_window)
        batch, matrix, common, train, calibration = _inputs(snapshot, configuration)
        import torch
        from .candidate_ae_weights import build_candidate_ae_network
        with _cpu_execution(torch):
            model = build_candidate_ae_network(configuration['input_width'])
            _check_network(model, configuration, torch)
            tensor = torch.from_numpy(np.array(matrix[train], copy=True))
            optimizer = _cpu_adam(torch, model.parameters())
            losses = []
            model.train()
            for _ in range(5):
                optimizer.zero_grad(set_to_none=True)
                recovered = model(tensor)
                _require(bool(torch.isfinite(recovered).all()), 'NONFINITE_AE_OUTPUT')
                loss = torch.mean((recovered - tensor) ** 2)
                _require(bool(torch.isfinite(loss)), 'NONFINITE_AE_LOSS')
                losses.append(float(loss.detach().item()))
                loss.backward()
                _require(all(p.grad is not None and bool(torch.isfinite(p.grad).all())
                             for p in model.parameters()), 'NONFINITE_AE_GRADIENT')
                optimizer.step()
                _check_network(model, configuration, torch)
                _require(all(not torch.is_tensor(v) or bool(torch.isfinite(v).all())
                             for state in optimizer.state.values() for v in state.values()), 'NONFINITE_AE_OPTIMIZER')
            observed = _reconstruction_scores(model, matrix[common], method)
            axes = [np.full(len(batch.timestamps), np.nan) for _ in range(3)]
            for axis, values in zip(axes, observed):
                axis[common] = values
            scores, current, historical = axes
            threshold, alarms, calibration_meta = _calibrate(scores, common, calibration)
            evaluation = _evaluation(snapshot, batch, common, alarms)
            runtime = dict(device='cpu', torch_num_threads=torch.get_num_threads(),
                           torch_num_interop_threads=torch.get_num_interop_threads())
            return CandidateAEResult(model, _readonly(scores), _readonly(common), alarms,
                threshold, calibration_meta, evaluation, configuration,
                tuple(np.flatnonzero(train).tolist()), tuple(np.flatnonzero(calibration).tolist()),
                _readonly(current), _readonly(historical), tuple(losses), runtime)
    except CandidateAEError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, RuntimeError) as exc:
        raise CandidateAEError('AE_EXECUTION_ERROR') from exc


def replay_candidate_ae(snapshot, result, network):
    """Check an already JSON-rebuilt network without fitting or loading files."""
    try:
        _require(isinstance(result, CandidateAEResult), 'AE_REPLAY_MISMATCH')
        configuration = _configuration(result.configuration['method'], result.configuration['history_window'])
        _require(_same(result.configuration, configuration), 'AE_REPLAY_MISMATCH')
        batch, matrix, common, train, calibration = _inputs(snapshot, configuration)
        import torch
        with _cpu_execution(torch):
            _check_network(network, configuration, torch)
            _check_network(result.model, configuration, torch)
            _require(all(a.detach().numpy().tobytes() == b.detach().numpy().tobytes()
                         for a, b in zip(network.parameters(), result.model.parameters())), 'AE_REPLAY_MISMATCH')
            expected_runtime = dict(device='cpu', torch_num_threads=torch.get_num_threads(),
                                    torch_num_interop_threads=torch.get_num_interop_threads())
            _require(_same(result.runtime, expected_runtime)
                     and isinstance(result.score_valid, np.ndarray)
                     and result.score_valid.dtype == np.dtype(bool)
                     and np.array_equal(result.score_valid, common)
                     and result.fit_indices == tuple(np.flatnonzero(train).tolist())
                     and result.calibration_indices == tuple(np.flatnonzero(calibration).tolist()), 'AE_REPLAY_MISMATCH')
            observed = _reconstruction_scores(network, matrix[common], configuration['method'])
            for stored, values in zip((result.scores, result.current_reconstruction_mse,
                                       result.history_deviation_reconstruction_mse), observed):
                _require(stored.shape == common.shape and stored.dtype == np.float64
                         and np.isnan(stored[~common]).all()
                         and np.array_equal(stored[common], values, equal_nan=True), 'AE_REPLAY_MISMATCH')
            threshold, alarms, metadata = _calibrate(result.scores, common, calibration)
            _require(type(result.threshold) is float and result.threshold == threshold
                     and result.alarms.dtype == np.dtype(bool) and np.array_equal(result.alarms, alarms)
                     and _same(result.calibration, metadata)
                     and _same(result.evaluation, _evaluation(snapshot, batch, common, alarms))
                     and len(result.training_losses) == 5
                     and all(type(v) is float and math.isfinite(v) and v >= 0 for v in result.training_losses), 'AE_REPLAY_MISMATCH')
    except CandidateAEError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, RuntimeError) as exc:
        raise CandidateAEError('AE_REPLAY_MISMATCH') from exc
