"""Read-only stored-score consistency checks never deserialize IF models."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


SOURCE = Path(__file__).parents[1] / "fixtures" / "g13u-records-v1.json"


def make_run(tmp_path, policy="P_U"):
    from traffic_anomaly.candidate_cli import _run as numeric_run
    from traffic_anomaly.candidate_record_cli import _run as record_run
    from traffic_anomaly.candidate_if_cli import run_synthetic_candidate_if

    records, inputs, run = tmp_path / "records", tmp_path / "inputs", tmp_path / "toy-run"
    record_run(SOURCE, policy, records)
    numeric_run(records / "minute-fixture.json", inputs)
    run_synthetic_candidate_if(records, inputs, SOURCE, "batch5-toy", run)
    return run, records, inputs


def snapshot(tmp_path):
    paths = [SOURCE, *sorted(tmp_path.rglob("*"))]
    return {str(path): (path.is_dir(), path.stat().st_mtime_ns, path.stat().st_size,
                       None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}


def run_cli(paths, source=None, extra=()):
    run, records, inputs = paths
    command = [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_run_verify_cli",
               "--run", str(run), "--records", str(records), "--inputs", str(inputs)]
    if source is not None:
        command.extend(["--source-fixture", str(source)])
    return subprocess.run([*command, *extra], capture_output=True, text=True, encoding="utf-8")


def assert_safe_error(result, tmp_path):
    assert result.returncode == 2
    assert result.stdout == ""
    error = json.loads(result.stderr)
    assert set(error) == {"error"}
    assert re.fullmatch(r"[A-Z][A-Z0-9_]*", error["error"])
    assert str(tmp_path) not in result.stderr
    assert "private" not in result.stderr and "Traceback" not in result.stderr
    return error["error"]


@pytest.mark.parametrize("policy", ["P_U", "P_B", "P_A"])
@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
def test_cli_returns_full_core_report_without_writes_or_model_replay(tmp_path, policy, include_source):
    from traffic_anomaly.candidate_run_artifacts import verify_candidate_if_run

    paths = make_run(tmp_path, policy)
    source = SOURCE if include_source else None
    before = snapshot(tmp_path)
    expected = verify_candidate_if_run(*paths, source_fixture=source)
    result = run_cli(paths, source)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report == expected
    assert report["status"] == "VERIFIED"
    assert report["evidence_kind"] == "SYNTHETIC_ONLY"
    assert report["policy_status"] == "AUDIT_ONLY"
    assert report["checks"]["model_deserialization"] == "NOT_PERFORMED"
    assert report["checks"]["model_score_replay"] == "NOT_CHECKED"
    assert report["checks"]["source_replay"] == ("VERIFIED" if include_source else "NOT_PROVIDED")
    assert str(tmp_path) not in result.stdout
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
def test_clean_child_blocks_model_libraries_and_pickle_calls(tmp_path, include_source):
    paths = make_run(tmp_path)
    before = snapshot(tmp_path)
    child = '''
import importlib
import importlib.abc
import pickle
import sys

forbidden = {"sklearn", "joblib", "torch"}
assert not forbidden.intersection(sys.modules)
class BlockModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in forbidden:
            raise AssertionError("model library import forbidden during run verification")
sys.meta_path.insert(0, BlockModels())
def no_pickle(*args, **kwargs):
    raise AssertionError("model deserialization forbidden during run verification")
pickle.load = pickle.loads = no_pickle
module = importlib.import_module("traffic_anomaly.candidate_run_verify_cli")
arguments = ["--run", sys.argv[1], "--records", sys.argv[2], "--inputs", sys.argv[3]]
if len(sys.argv) == 5:
    arguments.extend(["--source-fixture", sys.argv[4]])
status = module.main(arguments)
assert not forbidden.intersection(sys.modules)
raise SystemExit(status)
'''
    arguments = [*(str(path) for path in paths)]
    if include_source:
        arguments.append(str(SOURCE))
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", child, *arguments],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report["checks"]["model_deserialization"] == "NOT_PERFORMED"
    assert report["checks"]["model_score_replay"] == "NOT_CHECKED"
    assert snapshot(tmp_path) == before


def test_relocated_run_and_upstream_directories_remain_verifiable(tmp_path):
    paths = make_run(tmp_path)
    archive = tmp_path / "moved"
    archive.mkdir()
    moved = tuple(archive / name for name in ("run-artifacts", "record-artifacts", "input-artifacts"))
    for old, new in zip(paths, moved):
        old.rename(new)
    before = snapshot(tmp_path)
    result = run_cli(moved, SOURCE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "VERIFIED"
    assert snapshot(tmp_path) == before
    assert not any(path.exists() for path in paths)


@pytest.mark.parametrize("filename", ["manifest.json", "model-state.json", "weights.bin", "scores.json", "evaluation.json"])
def test_tampered_run_artifacts_are_rejected_safely_without_repair(tmp_path, filename):
    from traffic_anomaly.candidate_run_artifacts import CandidateRunArtifactError, verify_candidate_if_run

    paths = make_run(tmp_path)
    (paths[0] / filename).write_bytes(b'{"private":"untrusted file contents"}')
    before = snapshot(tmp_path)
    with pytest.raises(CandidateRunArtifactError) as expected:
        verify_candidate_if_run(*paths)
    result = run_cli(paths)
    assert assert_safe_error(result, tmp_path) == expected.value.code
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("run_id", ["../private-run", "changed-valid-id", True])
def test_run_id_tampering_is_rejected_without_echo(tmp_path, run_id):
    from traffic_anomaly.candidate_run_artifacts import CandidateRunArtifactError, verify_candidate_if_run

    paths = make_run(tmp_path)
    manifest = paths[0] / "manifest.json"
    value = json.loads(manifest.read_text("utf-8"))
    value["run_id"] = run_id
    manifest.write_text(json.dumps(value), encoding="utf-8")
    before = snapshot(tmp_path)
    with pytest.raises(CandidateRunArtifactError) as expected:
        verify_candidate_if_run(*paths)
    assert assert_safe_error(run_cli(paths), tmp_path) == expected.value.code
    assert snapshot(tmp_path) == before


def test_overflowing_stored_calibration_scores_emit_only_safe_json(tmp_path):
    original_run, records, inputs = make_run(tmp_path)
    run = tmp_path / "extreme-score-copy"
    shutil.copytree(original_run, run)
    state = json.loads((run / "model-state.json").read_text("utf-8"))
    indices = state["calibration_indices"]
    assert len(indices) == 6
    score_path = run / "scores.json"
    scores = json.loads(score_path.read_text("utf-8"))
    for index, value in zip(indices, [-1e308] * 5 + [1e308]):
        scores["scores"][index] = value
    score_path.write_text(json.dumps(scores, allow_nan=False), encoding="utf-8")

    def identity(path):
        payload = path.read_bytes()
        return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}

    evaluation_path = run / "evaluation.json"
    evaluation = json.loads(evaluation_path.read_text("utf-8"))
    evaluation["scores"] = identity(score_path)
    evaluation_path.write_text(json.dumps(evaluation, allow_nan=False), encoding="utf-8")
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    for name in ("scores.json", "evaluation.json"):
        manifest["artifacts"][name] = identity(run / name)
    manifest_path.write_text(json.dumps(manifest, allow_nan=False), encoding="utf-8")
    before = snapshot(tmp_path)
    result = run_cli((run, records, inputs), SOURCE)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "RuntimeWarning" not in result.stderr, result.stderr
    assert json.loads(result.stderr) == {"error": "REPLAY_MISMATCH"}
    assert str(tmp_path) not in result.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("index", [0, 1, 2])
def test_missing_run_or_upstream_directory_is_safe_and_readonly(tmp_path, index):
    from traffic_anomaly.candidate_run_artifacts import CandidateRunArtifactError, verify_candidate_if_run

    paths = list(make_run(tmp_path))
    paths[index] = tmp_path / "private-missing-directory"
    before = snapshot(tmp_path)
    with pytest.raises(CandidateRunArtifactError) as expected:
        verify_candidate_if_run(*paths)
    assert assert_safe_error(run_cli(paths), tmp_path) == expected.value.code
    assert snapshot(tmp_path) == before


def test_missing_source_fixture_is_safe_and_readonly(tmp_path):
    from traffic_anomaly.candidate_run_artifacts import CandidateRunArtifactError, verify_candidate_if_run

    paths = make_run(tmp_path)
    source = tmp_path / "private-missing-source.json"
    before = snapshot(tmp_path)
    with pytest.raises(CandidateRunArtifactError) as expected:
        verify_candidate_if_run(*paths, source_fixture=source)
    assert assert_safe_error(run_cli(paths, source), tmp_path) == expected.value.code
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("extra", [("--model", "private-model.bin"), ("--resume",),
                                  ("--policy", "P_A"), ("--output", "private-output"),
                                  ("--threshold", "0"), ("--run-id", "private-run")])
def test_cli_rejects_model_resume_output_and_other_unavailable_flags(tmp_path, extra):
    paths = make_run(tmp_path)
    before = snapshot(tmp_path)
    assert assert_safe_error(run_cli(paths, extra=extra), tmp_path) == "INVALID_ARGUMENTS"
    assert snapshot(tmp_path) == before


def test_cli_missing_required_arguments_are_safe():
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_run_verify_cli"],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "INVALID_ARGUMENTS"}
