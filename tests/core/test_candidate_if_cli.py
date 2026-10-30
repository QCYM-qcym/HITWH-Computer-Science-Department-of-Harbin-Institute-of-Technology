"""Bounded synthetic-only IF persistence; upstream artifacts remain read-only."""
from collections import Counter
import hashlib
import io
import json
import pickle
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


@pytest.fixture
def package(tmp_path):
    records, inputs = tmp_path / "records", tmp_path / "inputs"
    records_run(SOURCE, "P_U", records)
    numeric_run(records / "minute-fixture.json", inputs)
    return records, inputs


def read(path):
    return json.loads(path.read_text("utf-8"))


def digest(path):
    payload = path.read_bytes()
    return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}


def snapshot(package):
    paths = [SOURCE, *(path for directory in package for path in directory.iterdir())]
    return {path: (path.stat().st_mtime_ns, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}


def run_cli(package, output, run_id="synthetic-if-v1", extra=(), source=SOURCE):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_if_cli",
         "--records", str(package[0]), "--inputs", str(package[1]),
         "--source-fixture", str(source), "--run-id", run_id, "--output", str(output), *extra],
        capture_output=True, text=True, encoding="utf-8",
    )


def safe_error(result):
    assert result.returncode == 2
    assert result.stdout == ""
    error = json.loads(result.stderr)
    assert set(error) == {"error"} and re.fullmatch(r"[A-Z][A-Z0-9_]*", error["error"])
    assert "Traceback" not in result.stderr and "private" not in result.stderr
    return error["error"]


def test_cli_persists_complete_toy_run_with_consistent_scores_and_bound_hashes(package, tmp_path):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
    from traffic_anomaly.candidate_iforest import MODEL_PROFILE_ID, compute_synthetic_candidate_if

    upstream = snapshot(package)
    verified = load_verified_candidate_artifacts(*package, source_fixture=SOURCE)
    expected = compute_synthetic_candidate_if(verified)
    output = tmp_path / "toy-if"
    result = run_cli(package, output)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"run_id": "synthetic-if-v1", "status": "COMPLETE", "evidence_kind": "SYNTHETIC_ONLY"}
    assert {path.name for path in output.iterdir()} == {"model-state.json", "weights.bin", "scores.json", "evaluation.json", "manifest.json"}
    documents = {name: read(output / name) for name in ("model-state.json", "scores.json", "evaluation.json", "manifest.json")}
    for document in documents.values():
        assert document["schema_version"] == 1
        assert document["run_id"] == "synthetic-if-v1"
        assert document["model_profile_id"] == MODEL_PROFILE_ID
        assert document["evidence_kind"] == "SYNTHETIC_ONLY"
        assert document["policy_status"] == "AUDIT_ONLY"
        assert document["scope"] == "ENGINEERING_TOY_ONLY"
        assert document["selected_policy"] == "P_U"
        assert document["score_direction"] == "HIGHER_IS_MORE_ANOMALOUS"
        assert document["feature_names"] == list(verified.feature_names)
        assert document["qualification_windows"] == [15, 30]
        assert document["configuration"] == expected.configuration
        assert set(document["library_versions"]) == {"python", "numpy", "scikit_learn", "joblib"}
        assert all(isinstance(value, str) and value for value in document["library_versions"].values())
        assert set(document["provenance"]) == {"record_manifest", "input_manifest", "source_fixture", "minute_fixture", "preprocess"}
        assert document["provenance"]["source_fixture"] == digest(SOURCE)
        assert document["preprocessing_state"]["feature_names"] == list(verified.feature_names)
        assert str(tmp_path) not in json.dumps(document)
    model = documents["model-state.json"]
    assert model["fit_indices"] == list(expected.fit_indices)
    assert model["calibration_indices"] == list(expected.calibration_indices)
    assert model["weights"] == digest(output / "weights.bin")
    scores = documents["scores.json"]
    assert len(scores["timestamps"]) == len(verified.timestamps) == 144
    assert scores["score_valid"] == expected.score_valid.tolist()
    assert scores["threshold"] == expected.threshold
    assert scores["calibration"] == expected.calibration
    for index, valid in enumerate(expected.score_valid):
        assert scores["scores"][index] == (expected.scores[index] if valid else None)
        assert scores["alarms"][index] == (bool(expected.alarms[index]) if valid else None)
    for window in (15, 30):
        assert scores["history_invalid_reason"][str(window)] == list(verified.histories[window].invalid_reason)
    evaluation = documents["evaluation.json"]
    assert evaluation["evaluation"] == expected.evaluation
    assert evaluation["scores"] == digest(output / "scores.json")
    assert evaluation["threshold"] == scores["threshold"]
    manifest = documents["manifest.json"]
    assert manifest["status"] == "COMPLETE"
    assert set(manifest["artifacts"]) == {"model-state.json", "weights.bin", "scores.json", "evaluation.json"}
    for name, identity in manifest["artifacts"].items():
        assert identity == digest(output / name)
    assert sum(path.stat().st_size for path in output.iterdir()) <= 32 * 1024 * 1024
    assert (output / "weights.bin").stat().st_size <= 8 * 1024 * 1024
    assert snapshot(package) == upstream


@pytest.mark.parametrize("run_id", ["", "../private", "bad space", "bad.dot", "é", "x" * 65])
def test_cli_rejects_invalid_run_ids_without_output(package, tmp_path, run_id):
    output = tmp_path / "output"
    assert safe_error(run_cli(package, output, run_id)) == "INVALID_RUN_ID"
    assert not output.exists()


@pytest.mark.parametrize("extra", [("--model", "private-model.bin"), ("--resume",), ("--policy", "P_B"),
                                  ("--n-estimators", "999"), ("--window", "30"), ("--threshold", "0")])
def test_cli_has_no_external_model_resume_policy_or_parameter_arguments(package, tmp_path, extra):
    output = tmp_path / "output"
    assert safe_error(run_cli(package, output, extra=extra)) == "INVALID_ARGUMENTS"
    assert not output.exists()


def test_cli_requires_source_fixture_and_run_id(package, tmp_path):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_if_cli",
         "--records", str(package[0]), "--inputs", str(package[1]), "--output", str(tmp_path / "output")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert safe_error(result) == "INVALID_ARGUMENTS"
    assert not (tmp_path / "output").exists()


def test_existing_output_is_untouched(package, tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    marker = output / "manifest.json"
    marker.write_text("existing unrelated manifest")
    assert safe_error(run_cli(package, output)) == "OUTPUT_EXISTS"
    assert marker.read_text() == "existing unrelated manifest"
    assert list(output.iterdir()) == [marker]


@pytest.mark.parametrize("target", ["records", "inputs", "source", "ancestor"])
def test_output_cannot_overlap_any_input_or_source(package, tmp_path, target):
    from traffic_anomaly import candidate_if_cli

    output = {"records": package[0] / "nested-run", "inputs": package[1] / "nested-run",
              "source": SOURCE, "ancestor": tmp_path}[target]
    before = snapshot(package)
    with pytest.raises(ValueError) as error:
        candidate_if_cli.run_synthetic_candidate_if(*package, SOURCE, "toy", output)
    assert getattr(error.value, "code", str(error.value)) == "UNSAFE_OUTPUT"
    assert snapshot(package) == before


def test_dotdot_output_cannot_hide_nesting_inside_upstream_directory(package, tmp_path):
    from traffic_anomaly import candidate_if_cli

    alias = tmp_path / "alias"
    alias.mkdir()
    output = alias / ".." / "records" / "nested-output"
    with pytest.raises(ValueError) as error:
        candidate_if_cli.run_synthetic_candidate_if(*package, SOURCE, "toy", output)
    assert getattr(error.value, "code", str(error.value)) == "UNSAFE_OUTPUT"
    assert not (package[0] / "nested-output").exists()


def test_records_dotdot_alias_cannot_allow_output_inside_actual_upstream(package):
    aliased = (package[0] / ".." / "records", package[1])
    output = package[0] / "nested-output"
    assert safe_error(run_cli(aliased, output)) == "UNSAFE_OUTPUT"
    assert not output.exists()


def test_score_export_requires_exact_common_axis_not_a_reduced_subset(package):
    from traffic_anomaly import candidate_if_cli
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

    payload = load_verified_candidate_artifacts(*package, source_fixture=SOURCE)
    result = candidate_if_cli.compute_synthetic_candidate_if(payload)
    valid, scores, alarms = result.score_valid.copy(), result.scores.copy(), result.alarms.copy()
    index = np.flatnonzero(valid)[0]
    valid[index], scores[index], alarms[index] = False, np.nan, False
    reduced = SimpleNamespace(scores=scores, score_valid=valid, alarms=alarms,
                              threshold=result.threshold, calibration=result.calibration)
    with pytest.raises(ValueError) as error:
        candidate_if_cli._score_document(payload, reduced, {})
    assert getattr(error.value, "code", str(error.value)) == "INVALID_MODEL_RESULT"


def test_reparse_output_ancestor_is_refused(package, tmp_path, monkeypatch):
    from traffic_anomaly import candidate_if_cli

    parent = tmp_path / "unsafe-parent"
    parent.mkdir()
    actual_lstat = Path.lstat

    def reparse(path, *args, **kwargs):
        info = actual_lstat(path, *args, **kwargs)
        if path == parent:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=getattr(info, "st_file_attributes", 0) | 1024)
        return info

    monkeypatch.setattr(Path, "lstat", reparse)
    with pytest.raises(ValueError) as error:
        candidate_if_cli.run_synthetic_candidate_if(*package, SOURCE, "toy", parent / "run")
    assert getattr(error.value, "code", str(error.value)) == "UNSAFE_OUTPUT"
    assert not (parent / "run").exists()


def test_verifies_and_reserves_before_compute_without_rereading_or_fitting_preprocessing(package, tmp_path, monkeypatch):
    from traffic_anomaly import candidate_if_cli
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor

    output = tmp_path / "output"
    watched = {SOURCE.resolve(), *(path.resolve() for directory in package for path in directory.iterdir())}
    opened = Counter()
    actual_open = Path.open
    actual_compute = candidate_if_cli.compute_synthetic_candidate_if

    def open_spy(path, *args, **kwargs):
        if path.resolve() in watched:
            opened[path.resolve()] += 1
        return actual_open(path, *args, **kwargs)

    def compute(payload):
        assert output.is_dir()
        assert payload.report["checks"]["source_replay"] == "VERIFIED"
        return actual_compute(payload)

    def forbidden(*args, **kwargs):
        raise AssertionError("IF CLI must not fit preprocessing")

    monkeypatch.setattr(Path, "open", open_spy)
    monkeypatch.setattr(CandidatePreprocessor, "fit", forbidden)
    monkeypatch.setattr(candidate_if_cli, "compute_synthetic_candidate_if", compute)
    result = candidate_if_cli.run_synthetic_candidate_if(*package, SOURCE, "toy", output)
    assert result["status"] == "COMPLETE"
    assert set(opened) == watched and all(value == 1 for value in opened.values())


def test_bad_source_is_rejected_before_reserving_output_or_computing(package, tmp_path, monkeypatch):
    from traffic_anomaly import candidate_if_cli

    source = tmp_path / "private-source.json"
    source.write_text("{}", encoding="utf-8")
    output = tmp_path / "output"

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid source must not reach IF compute")

    monkeypatch.setattr(candidate_if_cli, "compute_synthetic_candidate_if", forbidden)
    with pytest.raises(ValueError):
        candidate_if_cli.run_synthetic_candidate_if(*package, source, "toy", output)
    assert not output.exists()


def test_joblib_only_loads_same_newly_serialized_bytes_and_replay_is_required(package, tmp_path, monkeypatch):
    from traffic_anomaly import candidate_if_cli

    actual_load = candidate_if_cli.joblib.load
    actual_replay = candidate_if_cli.replay_saved_candidate_if
    seen = []

    def load(buffer, *args, **kwargs):
        assert isinstance(buffer, io.BytesIO)
        seen.append(buffer.getvalue())
        assert seen[-1] == (tmp_path / "output" / "weights.bin").read_bytes()
        return actual_load(buffer, *args, **kwargs)

    def replay(payload, result, model):
        seen.append("replayed")
        return actual_replay(payload, result, model)

    monkeypatch.setattr(candidate_if_cli.joblib, "load", load)
    monkeypatch.setattr(candidate_if_cli, "replay_saved_candidate_if", replay)
    candidate_if_cli.run_synthetic_candidate_if(*package, SOURCE, "toy", tmp_path / "output")
    assert len(seen) == 2 and seen[-1] == "replayed"


def test_reload_failure_keeps_partial_artifacts_without_completion(package, tmp_path, monkeypatch):
    from traffic_anomaly import candidate_if_cli

    def fail(*args, **kwargs):
        raise ValueError("private internal model detail")

    monkeypatch.setattr(candidate_if_cli.joblib, "load", fail)
    output = tmp_path / "output"
    assert candidate_if_cli.main(["--records", str(package[0]), "--inputs", str(package[1]),
        "--source-fixture", str(SOURCE), "--run-id", "toy", "--output", str(output)]) == 2
    assert output.is_dir() and (output / "weights.bin").exists()
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize("error_type", [pickle.UnpicklingError, AttributeError, ImportError, KeyError, IndexError])
def test_joblib_standard_reload_errors_are_safe_and_keep_partial_artifacts(package, tmp_path, monkeypatch, capsys, error_type):
    from traffic_anomaly import candidate_if_cli

    def fail(*args, **kwargs):
        raise error_type("private-reload-detail")

    monkeypatch.setattr(candidate_if_cli.joblib, "load", fail)
    output = tmp_path / "output"
    assert candidate_if_cli.main(["--records", str(package[0]), "--inputs", str(package[1]),
        "--source-fixture", str(SOURCE), "--run-id", "toy", "--output", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {"error": "RELOAD_FAILED"}
    assert "private-reload-detail" not in captured.err and "Traceback" not in captured.err
    assert output.is_dir() and (output / "weights.bin").exists()
    assert not (output / "manifest.json").exists()


def test_bounded_buffer_refuses_growth_before_allocating_over_cap():
    from traffic_anomaly import candidate_if_cli

    buffer = candidate_if_cli._BoundedBuffer(8)
    buffer.write(b"12345678")
    with pytest.raises(ValueError) as error:
        buffer.write(b"9")
    assert str(error.value) == "RESOURCE_LIMIT"
    assert buffer.getvalue() == b"12345678"


def test_bounded_buffer_counts_typed_memoryview_nbytes_before_write():
    from traffic_anomaly import candidate_if_cli

    buffer = candidate_if_cli._BoundedBuffer(4)
    typed = memoryview(bytearray(8)).cast("Q")
    assert len(typed) == 1 and typed.nbytes == 8
    with pytest.raises(ValueError) as error:
        buffer.write(typed)
    assert str(error.value) == "RESOURCE_LIMIT"
    assert buffer.getvalue() == b""


@pytest.mark.parametrize("limit", ["MAX_MODEL_BYTES", "MAX_JSON_BYTES", "MAX_TOTAL_BYTES"])
def test_output_limits_keep_partial_directory_without_manifest(package, tmp_path, monkeypatch, capsys, limit):
    from traffic_anomaly import candidate_if_cli

    monkeypatch.setattr(candidate_if_cli, limit, 64)
    output = tmp_path / "output"
    assert candidate_if_cli.main(["--records", str(package[0]), "--inputs", str(package[1]),
        "--source-fixture", str(SOURCE), "--run-id", "toy", "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "RESOURCE_LIMIT"}
    assert output.is_dir() and not (output / "manifest.json").exists()


def test_failed_manifest_is_cleaned_only_after_own_exclusive_create(package, tmp_path, monkeypatch, capsys):
    from traffic_anomaly import candidate_if_cli

    actual_open = Path.open

    class FailingWriter:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def write(self, payload):
            self.stream.write(payload)
            raise OSError("private flush error")

    def failing(path, *args, **kwargs):
        stream = actual_open(path, *args, **kwargs)
        return FailingWriter(stream) if path.name == "manifest.json" and args and "x" in args[0] else stream

    monkeypatch.setattr(Path, "open", failing)
    output = tmp_path / "output"
    assert candidate_if_cli.main(["--records", str(package[0]), "--inputs", str(package[1]),
        "--source-fixture", str(SOURCE), "--run-id", "toy", "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err) == {"error": "OUTPUT_ERROR"}
    assert not (output / "manifest.json").exists()
    assert (output / "weights.bin").exists()


def test_manifest_collision_does_not_delete_someone_elses_file(package, tmp_path, monkeypatch, capsys):
    from traffic_anomaly import candidate_if_cli

    actual_compute = candidate_if_cli.compute_synthetic_candidate_if
    output = tmp_path / "output"

    def compute(payload):
        result = actual_compute(payload)
        (output / "manifest.json").write_text("someone else's manifest", encoding="utf-8")
        return result

    monkeypatch.setattr(candidate_if_cli, "compute_synthetic_candidate_if", compute)
    assert candidate_if_cli.main(["--records", str(package[0]), "--inputs", str(package[1]),
        "--source-fixture", str(SOURCE), "--run-id", "toy", "--output", str(output)]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "OUTPUT_ERROR"
    assert (output / "manifest.json").read_text() == "someone else's manifest"
