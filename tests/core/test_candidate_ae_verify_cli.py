"""AE stored-artifact verification remains isolated from model execution."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import numpy as np
import pytest


SOURCE = Path(__file__).parents[1] / "fixtures" / "g13u-records-v1.json"
MODES = [("current_ae", None), ("history_ae", 15), ("history_ae", 30)]


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    """Synthetic training is setup only; validation below runs independently."""
    from traffic_anomaly.candidate_cli import _run as numeric_run
    from traffic_anomaly.candidate_record_cli import _run as record_run
    from traffic_anomaly.candidate_ae_cli import run_synthetic_candidate_ae

    root = tmp_path_factory.mktemp("ae-verify-setup")
    records, inputs = root / "records", root / "inputs"
    record_run(SOURCE, "P_U", records)
    numeric_run(records / "minute-fixture.json", inputs)
    runs = {}
    for index, (method, window) in enumerate(MODES):
        run = root / f"ae-{index}"
        run_synthetic_candidate_ae(records, inputs, SOURCE, f"batch7-ae-{index}", run,
                                   method=method, history_window=window)
        runs[(method, window)] = run
    return records, inputs, runs


def copy_package(prepared, tmp_path, mode=MODES[0]):
    records, inputs, runs = prepared
    result = tmp_path / "run", tmp_path / "records", tmp_path / "inputs"
    for source, target in zip((runs[mode], records, inputs), result):
        shutil.copytree(source, target)
    return result


def read(path):
    return json.loads(path.read_text("utf-8"))


def write(path, value, target_size=None):
    payload = json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if target_size is not None:
        assert len(payload) <= target_size
        payload += b" " * (target_size - len(payload))
    path.write_bytes(payload)


def identity(path):
    payload = path.read_bytes()
    return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}


def reseal(run):
    state = read(run / "model-state.json")
    state["weights"] = identity(run / "weights.json")
    write(run / "model-state.json", state)
    evaluation = read(run / "evaluation.json")
    evaluation["scores"] = identity(run / "scores.json")
    write(run / "evaluation.json", evaluation)
    manifest = read(run / "manifest.json")
    manifest["artifacts"] = {name: identity(run / name) for name in
                             ("weights.json", "model-state.json", "scores.json", "evaluation.json")}
    write(run / "manifest.json", manifest)


def snapshot(root):
    paths = [SOURCE, *sorted(root.rglob("*"))]
    return {str(path): (path.is_dir(), path.stat().st_size, path.stat().st_mtime_ns,
                       None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}


def run_cli(paths, source=None, extra=()):
    run, records, inputs = paths
    command = [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_ae_verify_cli",
               "--run", str(run), "--records", str(records), "--inputs", str(inputs)]
    if source is not None:
        command.extend(["--source-fixture", str(source)])
    return subprocess.run([*command, *extra], capture_output=True, text=True, encoding="utf-8")


def safe_error(result, root):
    assert result.returncode == 2 and result.stdout == ""
    error = json.loads(result.stderr)
    assert set(error) == {"error"} and re.fullmatch(r"[A-Z][A-Z0-9_]*", error["error"])
    assert str(root) not in result.stderr and "private" not in result.stderr
    assert "RuntimeWarning" not in result.stderr and "Traceback" not in result.stderr
    return error["error"]


@pytest.mark.parametrize("method,window", MODES)
@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
def test_cli_reports_exact_stored_scope_for_three_modes(prepared, tmp_path, method, window, include_source):
    from traffic_anomaly.candidate_ae_run_artifacts import verify_candidate_ae_run

    paths = copy_package(prepared, tmp_path, (method, window))
    before = snapshot(tmp_path)
    source = SOURCE if include_source else None
    expected = verify_candidate_ae_run(*paths, source_fixture=source)
    result = run_cli(paths, source)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report == expected
    assert report["verifier_profile_id"] == "c17-i1-g13u-ae-run-verifier-v1"
    assert report["status"] == "VERIFIED" and report["scope"] == "STORED_ARTIFACT_CONSISTENCY_ONLY"
    assert report["evidence_kind"] == "SYNTHETIC_ONLY" and report["policy_status"] == "AUDIT_ONLY"
    assert report["method"] == method and report["history_window"] == window
    for key, value in {"source_replay": "VERIFIED" if include_source else "NOT_PROVIDED",
        "model_deserialization": "NOT_PERFORMED", "network_reconstruction": "NOT_PERFORMED",
        "model_score_replay": "NOT_CHECKED", "training_execution": "NOT_CHECKED",
        "training_loss_replay": "NOT_CHECKED", "model_origin": "NOT_AUTHENTICATED"}.items():
        assert report["checks"][key] == value
    assert str(tmp_path) not in result.stdout
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
def test_clean_child_forbids_actual_model_import_and_all_execution_helpers(prepared, tmp_path, include_source):
    paths = copy_package(prepared, tmp_path)
    before = snapshot(tmp_path)
    child = '''
import builtins
import importlib
import pickle
import sys
blocked = {"torch", "sklearn", "joblib"}
assert not blocked.intersection(sys.modules)
original_import, original_import_module = builtins.__import__, importlib.import_module
def guarded_import(name,*args,**kwargs):
    if name.split(".",1)[0] in blocked:
        raise AssertionError("model import forbidden during verification")
    return original_import(name,*args,**kwargs)
def guarded_import_module(name,*args,**kwargs):
    if name.split(".",1)[0] in blocked:
        raise AssertionError("model import forbidden during verification")
    return original_import_module(name,*args,**kwargs)
builtins.__import__, importlib.import_module = guarded_import, guarded_import_module
def forbid(label):
    def reject(*args,**kwargs): raise AssertionError(label)
    return reject
pickle.load, pickle.loads = forbid("pickle load forbidden"), forbid("pickle loads forbidden")
engine = importlib.import_module("traffic_anomaly.candidate_autoencoder")
weights = importlib.import_module("traffic_anomaly.candidate_ae_weights")
for name in ("compute_synthetic_candidate_ae","replay_candidate_ae"):
    setattr(engine,name,forbid(name))
for name in ("encode_candidate_ae_weights","rebuild_candidate_ae_from_json"):
    setattr(weights,name,forbid(name))
module=importlib.import_module("traffic_anomaly.candidate_ae_verify_cli")
arguments=["--run",sys.argv[1],"--records",sys.argv[2],"--inputs",sys.argv[3]]
if len(sys.argv)==5: arguments.extend(["--source-fixture",sys.argv[4]])
status=module.main(arguments)
assert not blocked.intersection(sys.modules)
raise SystemExit(status)
'''
    args = [str(path) for path in paths]
    if include_source:
        args.append(str(SOURCE))
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", child, *args],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["checks"]["network_reconstruction"] == "NOT_PERFORMED"
    assert snapshot(tmp_path) == before


def test_moved_packages_remain_verifiable(prepared, tmp_path):
    paths = copy_package(prepared, tmp_path, MODES[2])
    folder = tmp_path / "relocated"
    folder.mkdir()
    moved = tuple(folder / name for name in ("ae-run", "source-records", "numeric-inputs"))
    for old, new in zip(paths, moved):
        old.rename(new)
    before = snapshot(tmp_path)
    result = run_cli(moved, SOURCE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "VERIFIED"
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("filename", ["manifest.json", "weights.json", "model-state.json", "scores.json", "evaluation.json"])
def test_bad_json_artifacts_reject_safely_without_repair(prepared, tmp_path, filename):
    from traffic_anomaly.candidate_ae_run_artifacts import CandidateAERunArtifactError, verify_candidate_ae_run

    paths = copy_package(prepared, tmp_path)
    (paths[0] / filename).write_bytes(b'{"private":"untrusted contents"}')
    before = snapshot(tmp_path)
    with pytest.raises(CandidateAERunArtifactError) as expected:
        verify_candidate_ae_run(*paths)
    assert safe_error(run_cli(paths), tmp_path) == expected.value.code
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("field,value", [("run_id", "../private-run"), ("model_profile_id", "production-profile"),
                                        ("runtime", {"device": "cuda"}), ("unexpected", "private")])
def test_untrusted_metadata_is_not_echoed(prepared, tmp_path, field, value):
    paths = copy_package(prepared, tmp_path)
    manifest = read(paths[0] / "manifest.json")
    manifest[field] = value
    write(paths[0] / "manifest.json", manifest)
    before = snapshot(tmp_path)
    safe_error(run_cli(paths, SOURCE), tmp_path)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("mutation", [
    lambda value: value["timestamps"].__setitem__(0, "2000-01-01T00:00:00"),
    lambda value: value["scores"].pop(),
    lambda value: value["score_valid"].__setitem__(0, 1),
    lambda value: value["history_invalid_reason"]["30"].__setitem__(0, "private-reason"),
])
def test_resealed_axis_and_masks_cannot_override_upstream(prepared, tmp_path, mutation):
    paths = copy_package(prepared, tmp_path)
    scores = read(paths[0] / "scores.json")
    mutation(scores)
    write(paths[0] / "scores.json", scores)
    reseal(paths[0])
    before = snapshot(tmp_path)
    safe_error(run_cli(paths, SOURCE), tmp_path)
    assert snapshot(tmp_path) == before


def test_weights_limit_checks_actual_physical_bytes(prepared, tmp_path):
    paths = copy_package(prepared, tmp_path)
    weights = paths[0] / "weights.json"
    write(weights, read(weights), target_size=1024 * 1024 + 1)
    reseal(paths[0])
    before = snapshot(tmp_path)
    assert safe_error(run_cli(paths), tmp_path) == "RESOURCE_LIMIT"
    assert snapshot(tmp_path) == before


def test_total_budget_is_rejected_with_each_file_legal_and_all_hashes_resealed(prepared, tmp_path):
    paths = copy_package(prepared, tmp_path)
    run = paths[0]
    target_size = 11 * 1024 * 1024
    write(run / "scores.json", read(run / "scores.json"), target_size)
    evaluation = read(run / "evaluation.json")
    evaluation["scores"] = identity(run / "scores.json")
    write(run / "evaluation.json", evaluation, target_size)
    write(run / "model-state.json", read(run / "model-state.json"), target_size)
    manifest = read(run / "manifest.json")
    manifest["artifacts"] = {name: identity(run / name) for name in
                             ("weights.json", "model-state.json", "scores.json", "evaluation.json")}
    write(run / "manifest.json", manifest)
    assert all(path.stat().st_size <= (1024 * 1024 if path.name == "weights.json" else 16 * 1024 * 1024) for path in run.iterdir())
    assert sum(path.stat().st_size for path in run.iterdir()) > 32 * 1024 * 1024
    before = snapshot(tmp_path)
    assert safe_error(run_cli(paths), tmp_path) == "RESOURCE_LIMIT"
    assert snapshot(tmp_path) == before


def test_valid_resealed_weight_change_does_not_claim_model_replay(prepared, tmp_path):
    paths = copy_package(prepared, tmp_path)
    weights = read(paths[0] / "weights.json")
    tensor = next(iter(weights["parameters"].values()))
    tensor["values"][0] = float(np.float32(tensor["values"][0]) + np.float32(.125))
    write(paths[0] / "weights.json", weights)
    reseal(paths[0])
    before = snapshot(tmp_path)
    result = run_cli(paths, SOURCE)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["checks"]["weights_json_structure"] == "VERIFIED"
    assert report["checks"]["model_score_replay"] == "NOT_CHECKED"
    assert report["checks"]["model_origin"] == "NOT_AUTHENTICATED"
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("index", [0, 1, 2])
def test_missing_directories_are_safe_without_creating_them(prepared, tmp_path, index):
    paths = list(copy_package(prepared, tmp_path))
    paths[index] = tmp_path / "private-missing-directory"
    before = snapshot(tmp_path)
    safe_error(run_cli(paths), tmp_path)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("extra", [("--model", "private-model"), ("--resume",), ("--repair",), ("--output", "private-report"),
                                  ("--device", "cpu"), ("--method", "current_ae"), ("--threshold", "0")])
def test_no_model_repair_or_write_flags_exist(prepared, tmp_path, extra):
    paths = copy_package(prepared, tmp_path)
    before = snapshot(tmp_path)
    assert safe_error(run_cli(paths, extra=extra), tmp_path) == "INVALID_ARGUMENTS"
    assert snapshot(tmp_path) == before


def test_missing_arguments_use_safe_json():
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_ae_verify_cli"],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2 and result.stdout == ""
    assert json.loads(result.stderr) == {"error": "INVALID_ARGUMENTS"}
