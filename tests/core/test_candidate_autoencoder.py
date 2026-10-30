"""Synthetic candidate AE isolation, numerical precision and reload checks."""
from dataclasses import replace
from pathlib import Path
import random
import subprocess
import sys

import numpy as np
import pytest

from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts, _array_mapping
from traffic_anomaly.candidate_cli import _run as numeric_run
from traffic_anomaly.candidate_record_cli import _run as record_run


SOURCE = Path(__file__).parents[1] / 'fixtures' / 'g13u-records-v1.json'


@pytest.fixture
def snapshot(tmp_path):
    records, inputs = tmp_path / 'records', tmp_path / 'inputs'
    record_run(SOURCE, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    return load_verified_candidate_artifacts(records, inputs, source_fixture=SOURCE)


def compute(snapshot, **kwargs):
    from traffic_anomaly.candidate_autoencoder import compute_synthetic_candidate_ae
    return compute_synthetic_candidate_ae(snapshot, **kwargs)


def assert_safe_failure(callback):
    from traffic_anomaly.candidate_autoencoder import CandidateAEError
    with pytest.raises(CandidateAEError) as caught:
        callback()
    assert caught.value.code == str(caught.value)
    assert caught.value.code.replace('_', '').isupper()


def selected_matrix(snapshot, method, window):
    return (snapshot.current_values if method == 'current_ae'
            else snapshot.histories[window].joined)


@pytest.mark.parametrize('method,window,width,parameters', [
    ('current_ae', None, 13, 288), ('history_ae', 15, 26, 509), ('history_ae', 30, 26, 509),
])
def test_fixed_cpu_toy_ae_full_axis_channels_threshold_and_policy_evaluation(snapshot, method, window, width, parameters):
    import torch
    from traffic_anomaly.candidate_autoencoder import MODEL_PROFILE_ID
    result = compute(snapshot, method=method, history_window=window)
    cfg = result.configuration
    assert MODEL_PROFILE_ID == 'c17-i1-g13u-ae-synthetic-v1'
    assert cfg['model_profile_id'] == MODEL_PROFILE_ID
    assert cfg['parameter_status'] == 'ENGINEERING_TOY_ONLY'
    assert cfg['method'] == method and cfg['history_window'] == window
    assert cfg['input_width'] == width and cfg['architecture'] == [width, 8, 3, 8, width]
    assert cfg['parameter_count'] == parameters == sum(p.numel() for p in result.model.parameters())
    assert cfg['epochs'] == 5 and cfg['optimizer'] == 'Adam' and cfg['learning_rate'] == .001
    assert cfg['shuffle'] is False and cfg['batch_strategy'] == 'FULL_BATCH'
    assert cfg['training_dtype'] == 'float32' and cfg['score_dtype'] == 'float64'
    assert cfg['fit_scope'] == 'TRAIN_NORMAL_COMMON' and cfg['calibration_scope'] == 'CALIBRATION_NORMAL_COMMON'
    assert cfg['preprocessing_fit_provenance'] == 'NOT_REESTIMATED'
    assert len(result.training_losses) == 5 and all(np.isfinite(v) and v >= 0 for v in result.training_losses)
    assert all(p.device.type == 'cpu' and p.dtype == torch.float32 for p in result.model.parameters())
    assert result.runtime['device'] == 'cpu'
    assert np.array_equal(result.score_valid, snapshot.common_valid)
    assert result.fit_indices == tuple(np.flatnonzero(snapshot.training_normal))
    assert result.calibration_indices == tuple(np.flatnonzero(snapshot.calibration_normal))
    assert len(result.fit_indices) == len(result.calibration_indices) == 6
    assert not set(result.fit_indices) & set(result.calibration_indices)
    assert result.scores.dtype == np.float64 and result.current_reconstruction_mse.dtype == np.float64
    valid = result.score_valid
    assert np.isfinite(result.scores[valid]).all() and np.isnan(result.scores[~valid]).all()
    assert np.isnan(result.current_reconstruction_mse[~valid]).all()
    assert not result.alarms[~valid].any()
    matrix = selected_matrix(snapshot, method, window)[valid].astype(np.float32)
    with torch.inference_mode():
        recovered = result.model(torch.from_numpy(matrix)).numpy()
    squared = (matrix.astype(np.float64) - recovered.astype(np.float64)) ** 2
    current = squared[:, :13].mean(axis=1)
    assert np.array_equal(result.current_reconstruction_mse[valid], current)
    if width == 13:
        expected = current
        assert np.isnan(result.history_deviation_reconstruction_mse).all()
    else:
        historical = squared[:, 13:].mean(axis=1)
        expected = .5 * current + .5 * historical
        assert np.array_equal(result.history_deviation_reconstruction_mse[valid], historical)
        assert np.isnan(result.history_deviation_reconstruction_mse[~valid]).all()
    assert np.array_equal(result.scores[valid], expected)
    calibration = result.scores[list(result.calibration_indices)]
    assert result.threshold == float(np.quantile(calibration, .99, method='linear'))
    assert np.array_equal(result.alarms[valid], result.scores[valid] > result.threshold)
    assert result.calibration['sample_count'] == 6 and result.calibration['comparison'] == 'STRICT_GREATER'
    assert result.evaluation['evidence_kind'] == 'SYNTHETIC_ONLY'
    assert result.evaluation['policies']['P_U']['normal_minutes'] == 4
    assert result.evaluation['policies']['P_B']['normal_minutes'] == 5
    assert result.evaluation['policies']['P_A']['normal_minutes'] == 4
    for array in (result.scores, result.score_valid, result.alarms,
                  result.current_reconstruction_mse, result.history_deviation_reconstruction_mse):
        assert not array.flags.writeable


def test_train_forward_receives_only_fixed_full_batch_training_normal_common(snapshot, monkeypatch):
    import torch
    from traffic_anomaly import candidate_ae_weights
    original = candidate_ae_weights.build_candidate_ae_network
    seen = []
    def build(width):
        network = original(width)
        original_forward = network.forward
        def forward(x):
            if network.training:
                seen.append(x.detach().cpu().numpy().copy())
            return original_forward(x)
        network.forward = forward
        return network
    monkeypatch.setattr(candidate_ae_weights, 'build_candidate_ae_network', build)
    compute(snapshot, method='history_ae', history_window=15)
    expected = snapshot.histories[15].joined[snapshot.training_normal].astype(np.float32)
    assert len(seen) == 5
    assert all(np.array_equal(x, expected) for x in seen)


@pytest.mark.parametrize('caller_mode', ['grad', 'no_grad', 'inference'])
def test_rng_threads_and_caller_context_restored_for_success(snapshot, caller_mode):
    import torch
    mode = {'grad': torch.enable_grad, 'no_grad': torch.no_grad, 'inference': torch.inference_mode}[caller_mode]
    state = torch.random.get_rng_state().clone()
    numpy_state, python_state = np.random.get_state(), random.getstate()
    threads = torch.get_num_threads(), torch.get_num_interop_threads()
    with mode():
        caller_grad, caller_inference = torch.is_grad_enabled(), torch.is_inference_mode_enabled()
        compute(snapshot, method='current_ae')
        assert (torch.is_grad_enabled(), torch.is_inference_mode_enabled()) == (caller_grad, caller_inference)
    assert torch.equal(state, torch.random.get_rng_state())
    current_numpy = np.random.get_state()
    assert numpy_state[0] == current_numpy[0] and np.array_equal(numpy_state[1], current_numpy[1])
    assert numpy_state[2:] == current_numpy[2:] and python_state == random.getstate()
    assert threads == (torch.get_num_threads(), torch.get_num_interop_threads())


def test_repeated_same_seed_snapshot_has_same_parameters_losses_and_scores(snapshot):
    import torch
    a = compute(snapshot, method='current_ae')
    b = compute(snapshot, method='current_ae')
    assert a.training_losses == b.training_losses
    assert np.array_equal(a.scores, b.scores, equal_nan=True)
    assert all(torch.equal(x, y) for x, y in zip(a.model.parameters(), b.model.parameters()))


@pytest.mark.parametrize('method,window', [('unknown', None), ('current_ae', 15),
    ('history_ae', None), ('history_ae', 1), ('history_ae', True), ('history_ae', '15')])
def test_engineering_mode_and_window_must_be_explicit_compatible(snapshot, method, window):
    assert_safe_failure(lambda: compute(snapshot, method=method, history_window=window))


def test_requires_a_verified_source_replayed_snapshot(tmp_path):
    records, inputs = tmp_path / 'records', tmp_path / 'inputs'
    record_run(SOURCE, 'P_U', records)
    numeric_run(records / 'minute-fixture.json', inputs)
    internal_only = load_verified_candidate_artifacts(records, inputs)
    assert_safe_failure(lambda: compute(internal_only, method='current_ae'))
    assert_safe_failure(lambda: compute(object(), method='current_ae'))


def test_score_precision_squares_after_float64_promotion(snapshot):
    import torch
    from traffic_anomaly.candidate_autoencoder import _reconstruction_scores
    from traffic_anomaly.candidate_ae_weights import build_candidate_ae_network
    model = build_candidate_ae_network(13)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
    x = np.full((2, 13), 1e20, dtype=np.float32)
    score, current, historical = _reconstruction_scores(model, x, 'current_ae')
    expected = (x.astype(np.float64) ** 2).mean(axis=1)
    assert np.isfinite(score).all() and np.array_equal(score, expected)
    assert np.array_equal(current, expected) and np.isnan(historical).all()


@pytest.mark.parametrize('failure', ['forward', 'gradient', 'weights', 'optimizer_state'])
def test_nonfinite_training_stops_and_restores_rng(snapshot, monkeypatch, failure):
    import torch
    from traffic_anomaly import candidate_ae_weights
    original_build = candidate_ae_weights.build_candidate_ae_network
    original_step = torch.optim.Adam.step
    def build(width):
        network = original_build(width)
        if failure == 'forward':
            network[0].register_forward_hook(lambda module, args, output: output * float('inf'))
        if failure == 'gradient':
            next(network.parameters()).register_hook(lambda gradient: gradient * float('inf'))
        return network
    def step(optimizer, *args, **kwargs):
        result = original_step(optimizer, *args, **kwargs)
        parameter = optimizer.param_groups[0]['params'][0]
        if failure == 'weights':
            with torch.no_grad(): parameter.fill_(float('inf'))
        if failure == 'optimizer_state':
            optimizer.state[parameter]['exp_avg'].fill_(float('inf'))
        return result
    monkeypatch.setattr(candidate_ae_weights, 'build_candidate_ae_network', build)
    monkeypatch.setattr(torch.optim.Adam, 'step', step)
    before = torch.random.get_rng_state().clone()
    with torch.no_grad():
        assert_safe_failure(lambda: compute(snapshot, method='current_ae'))
        assert not torch.is_grad_enabled()
    assert torch.equal(before, torch.random.get_rng_state())


def test_safe_replay_does_not_train_and_rejects_changed_parameters_or_metadata(snapshot, monkeypatch):
    import torch
    from traffic_anomaly.candidate_autoencoder import replay_candidate_ae
    from traffic_anomaly.candidate_ae_weights import build_candidate_ae_network
    result = compute(snapshot, method='current_ae')
    reloaded = build_candidate_ae_network(13)
    with torch.no_grad():
        for saved, destination in zip(result.model.parameters(), reloaded.parameters()):
            destination.copy_(saved)
    def forbidden(*args, **kwargs): raise AssertionError('replay must not optimize')
    monkeypatch.setattr(torch.optim.Adam, 'step', forbidden)
    replay_candidate_ae(snapshot, result, reloaded)
    bad = replace(result, threshold=result.threshold + 1.)
    assert_safe_failure(lambda: replay_candidate_ae(snapshot, bad, reloaded))
    with torch.no_grad(): next(reloaded.parameters()).add_(1.)
    assert_safe_failure(lambda: replay_candidate_ae(snapshot, result, reloaded))


def test_default_float_dtype_does_not_change_explicit_float32_network(snapshot):
    import torch
    previous = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float64)
        result = compute(snapshot, method='current_ae')
        assert all(p.dtype == torch.float32 for p in result.model.parameters())
        assert torch.get_default_dtype() == torch.float64
    finally:
        torch.set_default_dtype(previous)


def test_import_is_lazy_without_model_dependencies():
    code = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('torch', 'sklearn', 'joblib'):
        raise AssertionError('unexpected model import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import traffic_anomaly.candidate_autoencoder
'''
    completed = subprocess.run([sys.executable, '-X', 'utf8', '-c', code],
        capture_output=True, text=True, encoding='utf-8')
    assert completed.returncode == 0, completed.stderr


def changed_arrays(snapshot, **changes):
    arrays = {key: snapshot._arrays[key] for key in snapshot._arrays}
    arrays.update(changes)
    return replace(snapshot, _arrays=_array_mapping(arrays))


@pytest.mark.parametrize('change', ['empty_train', 'empty_calibration', 'test_in_training', 'float32_overflow', 'loss_overflow'])
def test_invalid_qualifications_and_large_finite_input_fail_without_dropping_rows(snapshot, change):
    if change == 'empty_train':
        bad = changed_arrays(snapshot, training_normal=np.zeros(144, bool))
    elif change == 'empty_calibration':
        bad = changed_arrays(snapshot, calibration_normal=np.zeros(144, bool))
    elif change == 'test_in_training':
        mask = snapshot.training_normal.copy()
        mask[140] = True
        bad = changed_arrays(snapshot, training_normal=mask)
    else:
        values = snapshot.current_values.copy()
        if change == 'float32_overflow': values[140, 0] = 1e39
        else: values[snapshot.training_normal] = 1e20
        bad = changed_arrays(snapshot, current_values=values)
    assert_safe_failure(lambda: compute(bad, method='current_ae'))


def test_nontraining_values_do_not_change_training_parameters_or_loss(snapshot):
    import torch
    original = compute(snapshot, method='current_ae')
    values = snapshot.current_values.copy()
    values[snapshot.partitions != 'train'] += .25
    modified = compute(changed_arrays(snapshot, current_values=values), method='current_ae')
    assert original.fit_indices == modified.fit_indices and original.training_losses == modified.training_losses
    assert all(torch.equal(a, b) for a, b in zip(original.model.parameters(), modified.model.parameters()))


def test_no_preprocessing_fit_or_snapshot_file_reread(snapshot, monkeypatch):
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor
    def forbidden(*args, **kwargs): raise AssertionError('already verified snapshot must not be fit or reread')
    monkeypatch.setattr(CandidatePreprocessor, 'fit', forbidden)
    monkeypatch.setattr(Path, 'open', forbidden)
    assert compute(snapshot, method='current_ae').score_valid.sum() == 24


@pytest.mark.parametrize('change', ['joined_current', 'joined_history'])
def test_history_joined_layout_must_match_declared_current_and_residual(snapshot, change):
    original = snapshot.histories[15]
    arrays = {key: original._arrays[key] for key in original._arrays}
    joined = original.joined.copy()
    joined[140, 0 if change == 'joined_current' else 13] += 1.
    arrays['joined'] = joined
    histories = dict(snapshot.histories)
    histories[15] = replace(original, _arrays=_array_mapping(arrays))
    bad = replace(snapshot, histories=histories)
    assert_safe_failure(lambda: compute(bad, method='history_ae', history_window=15))


@pytest.mark.parametrize('change', ['integer_valid', 'runtime_device', 'runtime_bool_threads'])
def test_replay_rejects_forged_runtime_and_nonboolean_score_mask(snapshot, change):
    from traffic_anomaly.candidate_autoencoder import replay_candidate_ae
    result = compute(snapshot, method='current_ae')
    if change == 'integer_valid': bad = replace(result, score_valid=result.score_valid.astype(int))
    elif change == 'runtime_device': bad = replace(result, runtime={**result.runtime, 'device': 'cuda'})
    else: bad = replace(result, runtime={**result.runtime, 'torch_num_threads': True})
    assert_safe_failure(lambda: replay_candidate_ae(snapshot, bad, result.model))


def test_replay_checks_parameter_bits_including_signed_zero(snapshot, monkeypatch):
    import torch
    from traffic_anomaly import candidate_ae_weights
    from traffic_anomaly.candidate_autoencoder import replay_candidate_ae
    original_build = candidate_ae_weights.build_candidate_ae_network
    def zeros(width):
        model = original_build(width)
        with torch.no_grad():
            for parameter in model.parameters(): parameter.zero_()
        return model
    monkeypatch.setattr(candidate_ae_weights, 'build_candidate_ae_network', zeros)
    result = compute(snapshot, method='current_ae')
    reloaded = zeros(13)
    with torch.no_grad():
        for source, destination in zip(result.model.parameters(), reloaded.parameters()): destination.copy_(source)
    replay_candidate_ae(snapshot, result, reloaded)
    source = next(result.model.parameters())
    target = next(reloaded.parameters())
    assert source.flatten()[0].item() == 0.
    with torch.no_grad():
        target.flatten()[0] = 0. if np.signbit(source.detach().numpy().flat[0]) else -0.
    assert torch.equal(source, target) and source.detach().numpy().tobytes() != target.detach().numpy().tobytes()
    assert_safe_failure(lambda: replay_candidate_ae(snapshot, result, reloaded))


def test_default_meta_device_does_not_change_cpu_engine_or_caller_setting(snapshot):
    import torch
    with torch.device('meta'):
        result = compute(snapshot, method='current_ae')
        assert all(p.device.type == 'cpu' and p.dtype == torch.float32 for p in result.model.parameters())
        assert torch.empty(0).device.type == 'meta'


def test_actual_engine_does_not_query_accelerator_during_five_adam_steps(snapshot, monkeypatch):
    import torch
    original_healthcheck = torch.optim.Adam._accelerator_graph_capture_health_check
    def forbidden(*args, **kwargs): raise AssertionError('CPU engine must not query an accelerator')
    monkeypatch.setattr(torch.accelerator, 'current_accelerator', forbidden)
    result = compute(snapshot, method='current_ae')
    assert len(result.training_losses) == 5
    assert torch.optim.Adam._accelerator_graph_capture_health_check is original_healthcheck
    assert result.configuration['optimizer_cpu_guard'] == 'INSTANCE_LOCAL_HEALTH_CHECK_V1'


def test_missing_private_adam_healthcheck_api_fails_safe_without_accelerator_query(snapshot, monkeypatch):
    import torch
    from traffic_anomaly.candidate_autoencoder import CandidateAEError
    monkeypatch.setattr(torch.optim.Adam, '_accelerator_graph_capture_health_check', None)
    with pytest.raises(CandidateAEError) as caught:
        compute(snapshot, method='current_ae')
    assert caught.value.code == 'UNSUPPORTED_TORCH_ADAM_API'


@pytest.mark.parametrize('kind', ['meta_parameters', 'capturable'])
def test_cpu_optimizer_guard_rejects_non_cpu_or_capture_mode(kind):
    import torch
    from traffic_anomaly.candidate_autoencoder import _cpu_adam
    parameter = torch.nn.Parameter(torch.zeros(1, device='meta' if kind == 'meta_parameters' else 'cpu'))
    def attempt():
        optimizer = _cpu_adam(torch, [parameter])
        if kind == 'capturable':
            optimizer.param_groups[0]['capturable'] = True
            optimizer.step()
    assert_safe_failure(attempt)
