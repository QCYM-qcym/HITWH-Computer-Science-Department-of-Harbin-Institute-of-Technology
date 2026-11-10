"""Actual artificial package I/O through the public result CLI; no estimator.

Only fixture setup prepares artificial inputs. Read-only commands run under
guards; run replaces the existing numerical boundary with handwritten scores.
No production codec or Q99 algorithm is reproduced here.
"""
import builtins
from contextlib import contextmanager
from dataclasses import asdict
import importlib
import json
import shutil
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from traffic_anomaly import release_if_result_contract as contract
from traffic_anomaly import release_if_result_package as result_io
from traffic_anomaly import release_iforest as forest
from traffic_anomaly import release_input_package as prepared_io
from traffic_anomaly import release_inputs as preparation
from traffic_anomaly import release_minute_package as raw_io
from traffic_anomaly.release_model_inputs import pair_release_model_inputs

# Reuse test-only bounded artificial input construction through the existing
# tests.core package. No sys.path edits or global integration conftest needed.
from tests.core.release_input_cases import make_config, make_upstream


THRESHOLD = 2.9699999999999998
TRAIN = tuple(range(31, 48))
CALIBRATION = (124, 125, 126, 127)
PREPROCESSING = tuple(range(31, 48))
SCORED = (*range(31, 48), *range(78, 88), *range(118, 128), *range(158, 176))
PRIVATE = 'private-output-flush-sentinel'


def api():
    try:
        return importlib.import_module('traffic_anomaly.release_if_result_cli')
    except ModuleNotFoundError as exc:
        if exc.name == 'traffic_anomaly.release_if_result_cli':
            pytest.fail('public saved-result run/inspect/verify CLI is not implemented')
        raise


def hand_scores():
    values = [None] * 176
    for index in SCORED:
        values[index] = 0.0
    values[31] = -0.0
    values[124:128] = [0.0, 1.0, 2.0, 3.0]
    values[158] = 4.0
    return tuple(values)


def hand_result(pair, view):
    scores = hand_scores()
    return forest.ReleaseIFResult('c17-release-iforest-engineering-v1', view,
        pair.raw_identity, pair.prepared_identity, pair.configuration_sha256,
        scores, tuple(None if score is None else score > THRESHOLD for score in scores),
        tuple(index in SCORED for index in range(176)), THRESHOLD,
        TRAIN, CALIBRATION, PREPROCESSING,
        forest.ReleaseIFConfiguration(13 if view == 'current13' else 26,
            16, 17, 1.0, False, 'auto', 42, 1))


def disk_inputs(root, *, continuous=False):
    """Bind real loader identities after saving each actual artificial package."""
    root.mkdir()
    upstream = make_upstream(invalid_indices=(0,), continuous=continuous,
                             label_overrides={93: ('attack',) * 3})
    raw_dir, prepared_dir = root / 'raw', root / 'prepared'
    raw_io.save_release_minute_package(upstream.minutes, upstream.segments, raw_dir)
    raw = raw_io.load_release_minute_package(raw_dir)
    saved = preparation.prepare_release_inputs(raw, make_config())
    prepared_io.save_release_input_package(saved, prepared_dir)
    prepared = prepared_io.load_release_input_package(prepared_dir)
    pair = pair_release_model_inputs(raw, prepared)
    assert pair.raw_identity == raw.identity and pair.prepared_identity == prepared.identity
    assert pair.population.train_indices == TRAIN
    assert pair.population.calibration_indices == CALIBRATION
    assert pair.population.preprocessing_fit_indices == PREPROCESSING
    assert tuple(i for i, scored in enumerate(pair.prepared_minutes.common_valid) if scored) == SCORED
    assert pair.prepared_minutes.common_valid[30] is False
    return SimpleNamespace(raw_dir=raw_dir, prepared_dir=prepared_dir, pair=pair)


def disk_result(root, view='current13'):
    inputs = disk_inputs(root / 'inputs')
    result = hand_result(inputs.pair, view)
    package = contract.make_release_if_result_package(inputs.pair, result)
    directory = root / 'saved-result'
    identity = result_io.save_release_if_result_package(package, directory)
    assert identity == package.identity
    assert result_io.load_release_if_result_package(directory) == package
    return inputs, package, directory


def snapshot(*directories):
    return {(str(directory), path.name): path.read_bytes()
            for directory in directories for path in directory.iterdir()}


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def receipt(package, command):
    return dict(version=1, command=command,
        status={'run': 'SAVED', 'inspect': 'INTERNAL_CONSISTENCY_CHECKED', 'verify': 'INPUT_BINDING_MATCHED'}[command],
        result_identity=asdict(package.identity), view=package.context.view, threshold=THRESHOLD,
        configuration_sha256=package.context.configuration_sha256,
        input_references=dict(raw=asdict(package.context.raw_identity), prepared=asdict(package.context.prepared_identity)),
        counts=dict(total=176, scored=55, training=17, calibration=4, preprocessing_fit=17),
        checks=dict(internal_consistency='MATCHED', saved_score_q99='MATCHED',
            input_pair_binding='NOT_PERFORMED' if command == 'inspect' else 'MATCHED',
            source_authentication='NOT_AUTHENTICATED', model_execution='NOT_AUTHENTICATED'),
        operations=dict(model_fit_score='PERFORMED' if command == 'run' else 'NOT_PERFORMED'))


@contextmanager
def readonly_guard(monkeypatch, cli, *, result_only=False):
    attempts, saved_q99 = [], []
    calibrate = contract.calibrate
    original_import = builtins.__import__
    def forbidden(*args, **kwargs):
        attempts.append('model/preparation/replay')
        raise AssertionError('read-only command entered forbidden execution')
    def import_guard(name, *args, **kwargs):
        if name.split('.')[0] in ('sklearn', 'torch', 'joblib'):
            return forbidden()
        return original_import(name, *args, **kwargs)
    def q99(values, *args, **kwargs):
        saved_q99.append(tuple(values))
        return calibrate(values, *args, **kwargs)
    with monkeypatch.context() as guarded:
        for name in ('fit_release_iforest', '_compute'):
            guarded.setattr(forest, name, forbidden)
        for name in ('prepare_release_inputs', 'verify_release_input_derivation',
                     '_fit_state', '_fit_statistics', '_transform', '_history'):
            guarded.setattr(preparation, name, forbidden)
        if hasattr(cli, 'fit_release_iforest'):
            guarded.setattr(cli, 'fit_release_iforest', forbidden)
        if result_only:
            for module, name in ((raw_io, 'load_release_minute_package'),
                                 (prepared_io, 'load_release_input_package')):
                guarded.setattr(module, name, forbidden)
                if hasattr(cli, name):
                    guarded.setattr(cli, name, forbidden)
        guarded.setattr(builtins, '__import__', import_guard)
        guarded.setattr(contract, 'calibrate', q99)
        yield saved_q99
    assert attempts == []


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_moved_result_inspect_and_real_input_verify_are_readonly(tmp_path, monkeypatch, capfdbinary, view):
    inputs, package, directory = disk_result(tmp_path, view)
    moved = tmp_path / 'independently-moved-result'
    directory.rename(moved)
    before = snapshot(inputs.raw_dir, inputs.prepared_dir, moved)
    cli = api()
    with readonly_guard(monkeypatch, cli, result_only=True) as inspect_q99:
        assert cli.main(['inspect', '--result-package', str(moved)]) == 0
    out, err = capfdbinary.readouterr()
    assert err == b'' and out == canonical(receipt(package, 'inspect'))
    assert inspect_q99 and all(values == (0.0, 1.0, 2.0, 3.0) for values in inspect_q99)
    with readonly_guard(monkeypatch, cli) as verify_q99:
        assert cli.main(['verify', '--result-package', str(moved), '--raw-package', str(inputs.raw_dir),
                         '--prepared-package', str(inputs.prepared_dir)]) == 0
    out, err = capfdbinary.readouterr()
    assert err == b'' and out == canonical(receipt(package, 'verify'))
    assert verify_q99 and all(values == (0.0, 1.0, 2.0, 3.0) for values in verify_q99)
    assert snapshot(inputs.raw_dir, inputs.prepared_dir, moved) == before


def test_verify_rejects_another_legitimate_disk_pair_but_inspect_still_succeeds(tmp_path, monkeypatch, capfdbinary):
    inputs, package, directory = disk_result(tmp_path)
    other = disk_inputs(tmp_path / 'another-legitimate-pair', continuous=True)
    assert other.pair.raw_identity != inputs.pair.raw_identity
    assert other.pair.prepared_identity != inputs.pair.prepared_identity
    before = snapshot(inputs.raw_dir, inputs.prepared_dir, other.raw_dir, other.prepared_dir, directory)
    cli = api()
    with readonly_guard(monkeypatch, cli):
        assert cli.main(['verify', '--result-package', str(directory), '--raw-package', str(other.raw_dir),
                         '--prepared-package', str(other.prepared_dir)]) == 2
    out, err = capfdbinary.readouterr()
    assert out == b'' and err == b'{"error":"INPUT_BINDING_MISMATCH"}\n'
    with readonly_guard(monkeypatch, cli, result_only=True):
        assert cli.main(['inspect', '--result-package', str(directory)]) == 0
    out, err = capfdbinary.readouterr()
    assert err == b'' and out == canonical(receipt(package, 'inspect'))
    assert snapshot(inputs.raw_dir, inputs.prepared_dir, other.raw_dir, other.prepared_dir, directory) == before


def test_bad_result_member_preserves_integrity_error_and_all_disk_bytes(tmp_path, monkeypatch, capfdbinary):
    inputs, _, directory = disk_result(tmp_path)
    broken = tmp_path / 'broken-result'
    shutil.copytree(directory, broken)
    member = broken / 'result.json'
    member.write_bytes(member.read_bytes() + b' ')
    before = snapshot(inputs.raw_dir, inputs.prepared_dir, directory, broken)
    cli = api()
    with readonly_guard(monkeypatch, cli, result_only=True):
        assert cli.main(['inspect', '--result-package', str(broken)]) == 2
    out, err = capfdbinary.readouterr()
    assert out == b'' and err == b'{"error":"INTEGRITY_MISMATCH"}\n'
    assert snapshot(inputs.raw_dir, inputs.prepared_dir, directory, broken) == before


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_run_flush_failure_retains_actual_loadable_and_inspectable_package(tmp_path, monkeypatch, capfdbinary, view):
    inputs = disk_inputs(tmp_path / 'inputs')
    before = snapshot(inputs.raw_dir, inputs.prepared_dir)
    output = tmp_path / 'result-after-output-failure'
    cli = api()
    calls, written = [], []
    def hand_compute(values, configuration):
        # This is the only substitute boundary: handwritten numeric output,
        # not an estimator execution or an alternate persistence implementation.
        calls.append((values, configuration))
        assert values.matrix.shape == (176, 13 if view == 'current13' else 26)
        assert values.common_indices == SCORED
        assert values.train_indices == TRAIN and values.calibration_indices == CALIBRATION
        assert values.preprocessing_fit_indices == PREPROCESSING
        assert configuration == forest.ReleaseIFConfiguration(13 if view == 'current13' else 26,
            16, 17, 1.0, False, 'auto', 42, 1)
        return np.array([np.nan if value is None else value for value in hand_scores()]), THRESHOLD
    class FlushFailure:
        def write(self, payload):
            written.append(payload)
            return len(payload)
        def flush(self):
            raise OSError(PRIVATE)
    with monkeypatch.context() as running:
        running.setattr(forest, '_compute', hand_compute)
        running.setattr(cli, 'sys', SimpleNamespace(stdout=SimpleNamespace(buffer=FlushFailure()),
                                                   stderr=sys.stderr, argv=sys.argv))
        assert cli.main(['run', '--raw-package', str(inputs.raw_dir),
            '--prepared-package', str(inputs.prepared_dir), '--view', view, '--output', str(output)]) == 2
    out, err = capfdbinary.readouterr()
    assert out == b'' and err == b'{"error":"OUTPUT_ERROR"}\n' and len(calls) == 1
    loaded = result_io.load_release_if_result_package(output)
    expected_result = hand_result(inputs.pair, view)
    assert loaded.result == expected_result
    assert len(written) == 1 and written[0] == canonical(receipt(loaded, 'run'))
    assert snapshot(inputs.raw_dir, inputs.prepared_dir) == before
    saved_bytes = snapshot(output)
    with readonly_guard(monkeypatch, cli, result_only=True):
        assert cli.main(['inspect', '--result-package', str(output)]) == 0
    out, err = capfdbinary.readouterr()
    assert err == b'' and out == canonical(receipt(loaded, 'inspect'))
    assert snapshot(output) == saved_bytes
