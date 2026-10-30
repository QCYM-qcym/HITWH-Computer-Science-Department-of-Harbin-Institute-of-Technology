"""AE JSON persistence, lazy dependencies and bounded synthetic CLI checks."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from traffic_anomaly.candidate_cli import _run as numeric_run
from traffic_anomaly.candidate_record_cli import _run as records_run


SOURCE = Path(__file__).parents[1] / "fixtures" / "g13u-records-v1.json"
MODES = [("current_ae", None), ("history_ae", 15), ("history_ae", 30)]
COMMON_KEYS = {"schema_version", "run_id", "model_profile_id", "evidence_kind", "time_basis",
               "policy_status", "scope", "selected_policy", "score_direction", "value_space",
               "feature_names", "qualification_windows", "configuration", "configuration_sha256",
               "library_versions", "provenance", "preprocessing_state", "runtime"}


@pytest.fixture
def package(tmp_path):
    records, inputs = tmp_path / "records", tmp_path / "inputs"
    records_run(SOURCE, "P_U", records)
    numeric_run(records / "minute-fixture.json", inputs)
    return records, inputs


def read(path):
    return json.loads(path.read_text("utf-8"))


def digest(path):
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data)}


def snapshot(package):
    paths = [SOURCE, *(path for directory in package for path in directory.iterdir())]
    return {path: (path.stat().st_size, path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}


def run_cli(package, output, method="current_ae", window=None, run_id="toy-ae", extra=()):
    command = [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_ae_cli",
               "--records", str(package[0]), "--inputs", str(package[1]),
               "--source-fixture", str(SOURCE), "--run-id", run_id, "--output", str(output),
               "--method", method]
    if window is not None:
        command.extend(["--history-window", str(window)])
    return subprocess.run([*command, *extra], capture_output=True, text=True, encoding="utf-8")


def safe_error(result):
    assert result.returncode == 2 and result.stdout == ""
    value = json.loads(result.stderr)
    assert set(value) == {"error"} and re.fullmatch(r"[A-Z][A-Z0-9_]*", value["error"])
    assert "private" not in result.stderr and "Traceback" not in result.stderr
    return value["error"]


def install_stub_pipeline(monkeypatch):
    """Exercise the writer with explicit non-model doubles, before core is ready."""
    from traffic_anomaly import candidate_ae_cli
    from traffic_anomaly.candidate_evaluation import evaluate_candidate_predictions
    from traffic_anomaly.candidate_iforest import calibrate_candidate_scores

    calls = []

    def compute(payload, *, method, history_window=None):
        common = payload.common_valid
        current = np.full(len(common), np.nan)
        current[common] = np.linspace(.1, .9, int(common.sum()))
        history = np.full(len(common), np.nan)
        if method == "history_ae":
            history[common] = current[common] * 1.5
            scores = .5 * current + .5 * history
        else:
            scores = current.copy()
        threshold, alarms, calibration = calibrate_candidate_scores(scores, common, payload.calibration_normal)
        width = 13 if method == "current_ae" else 26
        configuration = dict(model_profile_id="c17-i1-g13u-ae-synthetic-v1", parameter_status="ENGINEERING_TOY_ONLY",
            method=method, input_width=width, history_window=history_window, architecture=[width, 8, 3, 8, width],
            parameter_count=288 if width == 13 else 509, activation="RELU_HIDDEN_LINEAR_OUTPUT", device="cpu",
            training_dtype="float32", score_dtype="float64", score_rule="FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT",
            epochs=5, batch_strategy="FULL_BATCH", shuffle=False, optimizer="Adam", learning_rate=.001,
            random_state=42, fit_scope="TRAIN_NORMAL_COMMON", calibration_scope="CALIBRATION_NORMAL_COMMON",
            quantile=.99, quantile_method="linear", alarm_comparison="STRICT_GREATER",
            preprocessing_fit_provenance="NOT_REESTIMATED")
        calls.append("compute")
        return SimpleNamespace(model=object(), scores=scores, score_valid=common.copy(), alarms=alarms,
            threshold=threshold, calibration=calibration, configuration=configuration,
            fit_indices=tuple(np.flatnonzero(payload.training_normal).tolist()),
            calibration_indices=tuple(np.flatnonzero(payload.calibration_normal).tolist()),
            evaluation=evaluate_candidate_predictions(labels=payload.labels, partitions=payload.partitions,
                score_valid=common, alarms=alarms, source_attack_label_present=payload.source_attack_label_present,
                score_origin_policy=payload.report["selected_policy"]),
            current_reconstruction_mse=current, history_deviation_reconstruction_mse=history,
            training_losses=(.5, .4, .3, .2, .1),
            runtime={"device": "cpu", "torch_num_threads": 1, "torch_num_interop_threads": 1})

    def encode(model, binding):
        assert set(binding) == COMMON_KEYS
        calls.append("encode")
        return {"schema_version": 1, "format": "candidate-ae-json-weights-v1", "binding": binding,
                "parameters": {"non_model_test_double": []}}

    def parse(data, expected):
        value = json.loads(data)
        assert value["binding"] == expected
        calls.append("parse")
        return value

    def rebuild(document, expected):
        assert document["binding"] == expected
        calls.append("rebuild")
        return object()

    monkeypatch.setattr(candidate_ae_cli, "compute_synthetic_candidate_ae", compute)
    monkeypatch.setattr(candidate_ae_cli, "encode_candidate_ae_weights", encode)
    monkeypatch.setattr(candidate_ae_cli, "parse_candidate_ae_weights", parse)
    monkeypatch.setattr(candidate_ae_cli, "rebuild_candidate_ae_from_json", rebuild)
    monkeypatch.setattr(candidate_ae_cli, "replay_candidate_ae", lambda *args: calls.append("replay"))
    monkeypatch.setattr(candidate_ae_cli, "_versions", lambda: {"python": "test", "numpy": np.__version__, "torch": "test"})
    return candidate_ae_cli, calls


def test_import_and_help_do_not_initialize_any_model_library():
    child = '''
import importlib
import importlib.abc
import sys
forbidden = {"torch", "sklearn", "joblib"}
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".",1)[0] in forbidden:
            raise AssertionError("model dependency forbidden during import/help")
sys.meta_path.insert(0,Block())
module=importlib.import_module("traffic_anomaly.candidate_ae_cli")
assert not forbidden.intersection(sys.modules)
module.main(["--help"])
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", child], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "--method" in result.stdout and "--history-window" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("method,window", MODES)
def test_stub_writer_binds_full_common_and_nulls_channels_without_core(package, tmp_path, monkeypatch, method, window):
    module, calls = install_stub_pipeline(monkeypatch)
    before = snapshot(package)
    output = tmp_path / "run"
    assert module.run_synthetic_candidate_ae(*package, SOURCE, "toy", output, method=method, history_window=window)["status"] == "COMPLETE"
    assert calls == ["compute", "encode", "parse", "rebuild", "replay"]
    assert {path.name for path in output.iterdir()} == {"weights.json", "model-state.json", "scores.json", "evaluation.json", "manifest.json"}
    docs = {name: read(output / name) for name in ("model-state.json", "scores.json", "evaluation.json", "manifest.json")}
    binding = read(output / "weights.json")["binding"]
    assert set(binding) == COMMON_KEYS
    for document in docs.values():
        assert {key: document[key] for key in COMMON_KEYS} == binding
        assert document["run_id"] == "toy" and document["scope"] == "ENGINEERING_TOY_ONLY"
        assert document["configuration"]["method"] == method
        assert document["configuration"]["history_window"] == window
        assert document["configuration"]["parameter_count"] == (288 if method == "current_ae" else 509)
    assert docs["model-state.json"]["weights"] == digest(output / "weights.json")
    assert len(docs["model-state.json"]["training_losses"]) == 5
    scores = docs["scores.json"]
    assert len(scores["scores"]) == len(scores["current_reconstruction_mse"]) == len(scores["history_deviation_reconstruction_mse"]) == 144
    for index, valid in enumerate(scores["score_valid"]):
        if not valid:
            assert all(scores[name][index] is None for name in ("scores", "alarms", "current_reconstruction_mse", "history_deviation_reconstruction_mse"))
        elif method == "current_ae":
            assert scores["history_deviation_reconstruction_mse"][index] is None
            assert scores["scores"][index] == scores["current_reconstruction_mse"][index]
        else:
            assert scores["scores"][index] == .5 * scores["current_reconstruction_mse"][index] + .5 * scores["history_deviation_reconstruction_mse"][index]
    assert scores["history_deviation_reconstruction_mse_status"] == ("NOT_APPLICABLE" if method == "current_ae" else "APPLICABLE")
    assert docs["evaluation.json"]["scores"] == digest(output / "scores.json")
    for name, entry in docs["manifest.json"]["artifacts"].items():
        assert entry == digest(output / name)
    assert snapshot(package) == before


@pytest.mark.parametrize("method,window", MODES)
def test_real_cli_modes_use_safe_json_weights_and_full_score_axis(package, tmp_path, method, window):
    output = tmp_path / "real-run"
    before = snapshot(package)
    result = run_cli(package, output, method, window)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"run_id": "toy-ae", "status": "COMPLETE", "evidence_kind": "SYNTHETIC_ONLY"}
    assert result.stderr == ""
    manifest = read(output / "manifest.json")
    assert manifest["status"] == "COMPLETE" and manifest["scope"] == "ENGINEERING_TOY_ONLY"
    assert set(manifest["library_versions"]) == {"python", "numpy", "torch"}
    assert read(output / "weights.json")["binding"] == {key: manifest[key] for key in COMMON_KEYS}
    assert set(read(output / "weights.json")["parameters"]) == {f"{layer}.{kind}" for layer in (0, 2, 4, 6) for kind in ("weight", "bias")}
    assert set(manifest["artifacts"]) == {"weights.json", "model-state.json", "scores.json", "evaluation.json"}
    for name, entry in manifest["artifacts"].items():
        assert entry == digest(output / name)
    scores = read(output / "scores.json")
    assert len(scores["scores"]) == 144 and sum(scores["score_valid"]) == 24
    assert scores["calibration"]["sample_count"] == 6
    assert (output / "weights.json").stat().st_size <= 1024 * 1024
    assert snapshot(package) == before


def test_real_execution_cannot_use_pickle_torch_serializers_or_other_model_libraries(package, tmp_path):
    output = tmp_path / "no-serializers"
    child = '''
import builtins
import importlib
import pickle
import sys
import torch
def forbidden(*args, **kwargs):
    raise AssertionError("executable model serialization forbidden")
pickle.load = pickle.loads = forbidden
torch.load = torch.save = forbidden
blocked = {"sklearn", "joblib"}
original_import = builtins.__import__
original_import_module = importlib.import_module
def guarded_import(name, *args, **kwargs):
    if name.split(".",1)[0] in blocked:
        raise AssertionError("unrelated model library import forbidden")
    return original_import(name, *args, **kwargs)
def guarded_import_module(name, *args, **kwargs):
    if name.split(".",1)[0] in blocked:
        raise AssertionError("unrelated model library import forbidden")
    return original_import_module(name, *args, **kwargs)
builtins.__import__ = guarded_import
importlib.import_module = guarded_import_module
module = importlib.import_module("traffic_anomaly.candidate_ae_cli")
status = module.main(["--records",sys.argv[1],"--inputs",sys.argv[2],"--source-fixture",sys.argv[3],
    "--run-id","safe-json-ae","--method","current_ae","--output",sys.argv[4]])
assert not blocked.intersection(sys.modules)
raise SystemExit(status)
'''
    before = snapshot(package)
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", child, str(package[0]), str(package[1]), str(SOURCE), str(output)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "COMPLETE"
    assert (output / "weights.json").exists() and not (output / "weights.bin").exists()
    assert snapshot(package) == before


@pytest.mark.parametrize("method,window", [("history_ae", None), ("current_ae", 15), ("current_ae", 30), ("history_ae", 16), ("other", None)])
def test_method_window_constraints_fail_before_model_execution(package, tmp_path, method, window):
    output = tmp_path / "run"
    assert safe_error(run_cli(package, output, method, window)) in {"INVALID_ARGUMENTS", "INVALID_METHOD_WINDOW"}
    assert not output.exists()


@pytest.mark.parametrize("extra", [("--checkpoint", "private-model"), ("--model", "private-model"), ("--resume",),
                                  ("--epochs", "99"), ("--device", "cuda"), ("--policy", "P_A")])
def test_external_models_and_tuning_arguments_do_not_exist(package, tmp_path, extra):
    output = tmp_path / "run"
    assert safe_error(run_cli(package, output, extra=extra)) == "INVALID_ARGUMENTS"
    assert not output.exists()


@pytest.mark.parametrize("run_id", ["", "../private", "bad space", "x" * 65, "é"])
def test_run_id_is_explicit_bounded_ascii(package, tmp_path, run_id):
    output = tmp_path / "run"
    assert safe_error(run_cli(package, output, run_id=run_id)) == "INVALID_RUN_ID"
    assert not output.exists()


def test_existing_output_and_its_manifest_are_untouched(package, tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    marker = output / "manifest.json"
    marker.write_text("existing manifest")
    assert safe_error(run_cli(package, output)) == "OUTPUT_EXISTS"
    assert marker.read_text() == "existing manifest"
    assert list(output.iterdir()) == [marker]


@pytest.mark.parametrize("alias_side", ["records", "output"])
def test_canonical_alias_cannot_nest_output_in_upstream(package, tmp_path, alias_side):
    from traffic_anomaly import candidate_ae_cli

    records = package[0]
    if alias_side == "records":
        records = records / ".." / "records"
        output = package[0] / "nested-run"
    else:
        alias = tmp_path / "alias"
        alias.mkdir()
        output = alias / ".." / "records" / "nested-run"
    with pytest.raises(ValueError) as error:
        candidate_ae_cli.run_synthetic_candidate_ae(records, package[1], SOURCE, "toy", output, method="current_ae")
    assert str(error.value) == "UNSAFE_OUTPUT"
    assert not (package[0] / "nested-run").exists()


def test_reparse_parent_is_rejected_before_resolution(package, tmp_path, monkeypatch):
    from traffic_anomaly import candidate_ae_cli

    parent = tmp_path / "unsafe-parent"
    parent.mkdir()
    original = Path.lstat

    def altered(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == parent:
            return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=getattr(value, "st_file_attributes", 0) | 1024)
        return value

    monkeypatch.setattr(Path, "lstat", altered)
    with pytest.raises(ValueError) as error:
        candidate_ae_cli.run_synthetic_candidate_ae(*package, SOURCE, "toy", parent / "run", method="current_ae")
    assert str(error.value) == "UNSAFE_OUTPUT"
    assert not (parent / "run").exists()


@pytest.mark.parametrize("limit", ["MAX_WEIGHTS_BYTES", "MAX_JSON_BYTES", "MAX_TOTAL_BYTES"])
def test_buffers_and_total_output_caps_preserve_partial_without_complete(package, tmp_path, monkeypatch, capsys, limit):
    module, _ = install_stub_pipeline(monkeypatch)
    monkeypatch.setattr(module, limit, 64)
    output = tmp_path / "run"
    assert module.main(["--records", str(package[0]), "--inputs", str(package[1]), "--source-fixture", str(SOURCE),
                        "--run-id", "toy", "--method", "current_ae", "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "RESOURCE_LIMIT"}
    assert output.is_dir() and not (output / "manifest.json").exists()


def test_write_time_cap_counts_real_memoryview_bytes():
    from traffic_anomaly import candidate_ae_cli

    buffer = candidate_ae_cli._BoundedBuffer(4)
    with pytest.raises(ValueError) as error:
        buffer.write(memoryview(bytearray(8)).cast("Q"))
    assert str(error.value) == "RESOURCE_LIMIT"
    assert buffer.getvalue() == b""


@pytest.mark.parametrize("fault", ["current_nonfinite", "history_nonfinite", "current_mode_history_value", "reduced_valid", "wrong_score_sum"])
def test_channel_result_contract_cannot_be_silently_nullified_or_reduced(package, tmp_path, monkeypatch, fault):
    module, _ = install_stub_pipeline(monkeypatch)
    original = module.compute_synthetic_candidate_ae

    def bad(payload, **kwargs):
        result = original(payload, **kwargs)
        index = np.flatnonzero(result.score_valid)[0]
        if fault == "current_nonfinite": result.current_reconstruction_mse[index] = np.inf
        elif fault == "history_nonfinite": result.history_deviation_reconstruction_mse[index] = np.inf
        elif fault == "current_mode_history_value": result.history_deviation_reconstruction_mse[index] = 1
        elif fault == "reduced_valid": result.score_valid[index] = False
        else: result.scores[index] += .01
        return result

    monkeypatch.setattr(module, "compute_synthetic_candidate_ae", bad)
    method, window = ("history_ae", 15) if fault == "history_nonfinite" else ("current_ae", None)
    output = tmp_path / "run"
    with pytest.raises(ValueError) as error:
        module.run_synthetic_candidate_ae(*package, SOURCE, "toy", output, method=method, history_window=window)
    assert str(error.value) == "INVALID_MODEL_RESULT"
    assert output.is_dir() and not (output / "manifest.json").exists()


def test_strict_parse_and_rebuild_failure_never_create_completion(package, tmp_path, monkeypatch):
    module, _ = install_stub_pipeline(monkeypatch)

    def reject(*args):
        raise ValueError("private malformed weights")

    monkeypatch.setattr(module, "parse_candidate_ae_weights", reject)
    output = tmp_path / "run"
    with pytest.raises(ValueError) as error:
        module.run_synthetic_candidate_ae(*package, SOURCE, "toy", output, method="current_ae")
    assert str(error.value) == "OUTPUT_ERROR"
    assert (output / "weights.json").exists() and not (output / "manifest.json").exists()


def test_failed_manifest_cleanup_never_deletes_a_preexisting_marker(package, tmp_path, monkeypatch, capsys):
    module, _ = install_stub_pipeline(monkeypatch)
    original = module.compute_synthetic_candidate_ae
    output = tmp_path / "run"

    def collision(payload, **kwargs):
        result = original(payload, **kwargs)
        (output / "manifest.json").write_text("someone else's manifest")
        return result

    monkeypatch.setattr(module, "compute_synthetic_candidate_ae", collision)
    assert module.main(["--records", str(package[0]), "--inputs", str(package[1]), "--source-fixture", str(SOURCE),
                        "--run-id", "toy", "--method", "current_ae", "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "OUTPUT_ERROR"}
    assert (output / "manifest.json").read_text() == "someone else's manifest"


def test_failed_own_manifest_is_removed_but_partial_weights_are_retained(package, tmp_path, monkeypatch, capsys):
    module, _ = install_stub_pipeline(monkeypatch)
    original_open = Path.open

    class FailManifest:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def write(self, data):
            self.stream.write(data)
            raise OSError("private manifest failure")

    def fail(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return FailManifest(stream) if path.name == "manifest.json" and args and "x" in args[0] else stream

    monkeypatch.setattr(Path, "open", fail)
    output = tmp_path / "run"
    assert module.main(["--records", str(package[0]), "--inputs", str(package[1]), "--source-fixture", str(SOURCE),
                        "--run-id", "toy", "--method", "current_ae", "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "OUTPUT_ERROR"}
    assert not (output / "manifest.json").exists()
    assert (output / "weights.json").exists() and (output / "scores.json").exists()


def test_input_payloads_read_once_and_preprocessor_never_refitted(package, tmp_path, monkeypatch):
    module, _ = install_stub_pipeline(monkeypatch)
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor

    expected = {SOURCE.resolve(), *(path.resolve() for directory in package for path in directory.iterdir())}
    opened = Counter()
    original_open = Path.open

    def track(path, *args, **kwargs):
        if path.resolve() in expected: opened[path.resolve()] += 1
        return original_open(path, *args, **kwargs)

    def forbidden(*args): raise AssertionError("preprocessing fit forbidden")

    monkeypatch.setattr(Path, "open", track)
    monkeypatch.setattr(CandidatePreprocessor, "fit", forbidden)
    module.run_synthetic_candidate_ae(*package, SOURCE, "toy", tmp_path / "run", method="current_ae")
    assert set(opened) == expected and all(value == 1 for value in opened.values())
