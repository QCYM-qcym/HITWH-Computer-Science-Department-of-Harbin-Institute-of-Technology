"""The comparison CLI only prints verified shared-data qualification context."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from tests.core.test_candidate_ae_verify_cli import SOURCE, prepared


@pytest.fixture(scope="module")
def comparison_packages(prepared, tmp_path_factory):
    """Reuse the existing three-AE setup; add one IF on exactly that upstream."""
    from traffic_anomaly.candidate_if_cli import run_synthetic_candidate_if

    records, inputs, ae_runs = prepared
    root = tmp_path_factory.mktemp("comparison-cli-setup")
    if_run = root / "iforest"
    run_synthetic_candidate_if(records, inputs, SOURCE, "batch8-if", if_run)
    runs = [("iforest", if_run), ("autoencoder", ae_runs[("current_ae", None)]),
            ("autoencoder", ae_runs[("history_ae", 15)]), ("autoencoder", ae_runs[("history_ae", 30)])]
    return records, inputs, runs


def copied(comparison_packages, tmp_path):
    records, inputs, runs = comparison_packages
    copied_records, copied_inputs = tmp_path / "records", tmp_path / "inputs"
    shutil.copytree(records, copied_records)
    shutil.copytree(inputs, copied_inputs)
    copied_runs = []
    for index, (family, directory) in enumerate(runs):
        target = tmp_path / f"model-{index}"
        shutil.copytree(directory, target)
        copied_runs.append((family, target))
    return copied_records, copied_inputs, copied_runs


def snapshot(root):
    paths = [SOURCE, *sorted(root.rglob("*"))]
    return {str(path): (path.is_dir(), path.stat().st_size, path.stat().st_mtime_ns,
                       None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}


def run_cli(records, inputs, runs, source=None, extra=()):
    command = [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_compare_cli",
               "--records", str(records), "--inputs", str(inputs)]
    if source is not None:
        command.extend(["--source-fixture", str(source)])
    for family, directory in runs:
        command.extend(["--if-run" if family == "iforest" else "--ae-run", str(directory)])
    return subprocess.run([*command, *extra], capture_output=True, text=True, encoding="utf-8")


def safe_error(result, root=None):
    assert result.returncode == 2 and result.stdout == ""
    error = json.loads(result.stderr)
    assert set(error) == {"error"} and re.fullmatch(r"[A-Z][A-Z0-9_]*", error["error"])
    assert "private" not in result.stderr and "Traceback" not in result.stderr and "RuntimeWarning" not in result.stderr
    if root is not None:
        assert str(root) not in result.stderr
    return error["error"]


@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
def test_cli_prints_entire_four_slot_core_report_and_does_not_write(comparison_packages, tmp_path, include_source):
    from traffic_anomaly.candidate_comparison import CandidateComparisonRun, compare_candidate_runs

    records, inputs, runs = copied(comparison_packages, tmp_path)
    source = SOURCE if include_source else None
    before = snapshot(tmp_path)
    expected = compare_candidate_runs([CandidateComparisonRun(family, path) for family, path in runs],
                                      records, inputs, source_fixture=source)
    result = run_cli(records, inputs, list(reversed(runs)), source)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report == expected
    assert report["status"] == "DATA_QUALIFICATION_ALIGNED"
    assert report["scope"] == "SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY"
    assert report["shared_context"]["source_replay"] == ("VERIFIED" if include_source else "NOT_PROVIDED")
    assert report["included_slots"] == ["iforest_current13", "current_ae13", "history_ae26_h15", "history_ae26_h30"]
    assert report["missing_slots"] == []
    assert report["limitations"]["capacity_control"] == "NOT_COMPARABLE"
    assert report["limitations"]["history_causal_attribution"] == "NOT_COMPARABLE"
    assert report["limitations"]["ranking"] == "NOT_PERFORMED"
    assert str(tmp_path) not in result.stdout
    assert snapshot(tmp_path) == before


def test_cli_allows_two_history_slots_without_if_or_automatic_window_choice(comparison_packages, tmp_path):
    records, inputs, runs = copied(comparison_packages, tmp_path)
    before = snapshot(tmp_path)
    result = run_cli(records, inputs, runs[2:], SOURCE)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["included_slots"] == ["history_ae26_h15", "history_ae26_h30"]
    assert report["missing_slots"] == ["iforest_current13", "current_ae13"]
    assert not {"winner", "best_window", "rank", "p_value", "normalized_score"}.intersection(report)
    assert snapshot(tmp_path) == before


def test_clean_child_comparison_forbids_model_imports_and_execution(comparison_packages, tmp_path):
    records, inputs, runs = copied(comparison_packages, tmp_path)
    before = snapshot(tmp_path)
    child = '''
import builtins
import importlib
import pickle
import sys
blocked={"torch","sklearn","joblib"}
assert not blocked.intersection(sys.modules)
original_import,original_module=builtins.__import__,importlib.import_module
def guarded_import(name,*args,**kwargs):
    if name.split(".",1)[0] in blocked: raise AssertionError("model import forbidden")
    return original_import(name,*args,**kwargs)
def guarded_module(name,*args,**kwargs):
    if name.split(".",1)[0] in blocked: raise AssertionError("model import forbidden")
    return original_module(name,*args,**kwargs)
builtins.__import__,importlib.import_module=guarded_import,guarded_module
def forbid(label):
    def fail(*args,**kwargs): raise AssertionError(label)
    return fail
pickle.load,pickle.loads=forbid("pickle load"),forbid("pickle loads")
for module_name, names in [
    ("candidate_iforest",("compute_synthetic_candidate_if","replay_saved_candidate_if")),
    ("candidate_autoencoder",("compute_synthetic_candidate_ae","replay_candidate_ae")),
    ("candidate_ae_weights",("encode_candidate_ae_weights","rebuild_candidate_ae_from_json"))]:
    module=importlib.import_module("traffic_anomaly."+module_name)
    for name in names: setattr(module,name,forbid(name))
module=importlib.import_module("traffic_anomaly.candidate_compare_cli")
args=["--records",sys.argv[1],"--inputs",sys.argv[2],"--source-fixture",sys.argv[3],"--if-run",sys.argv[4]]
for path in sys.argv[5:]: args.extend(["--ae-run",path])
status=module.main(args)
assert not blocked.intersection(sys.modules)
raise SystemExit(status)
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", child, str(records), str(inputs), str(SOURCE),
                             *(str(path) for _, path in runs)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "DATA_QUALIFICATION_ALIGNED"
    assert snapshot(tmp_path) == before


def test_relocated_packages_compare_without_original_paths(comparison_packages, tmp_path):
    records, inputs, runs = copied(comparison_packages, tmp_path)
    moved = tmp_path / "moved"
    moved.mkdir()
    moved_records, moved_inputs = moved / "records", moved / "inputs"
    records.rename(moved_records)
    inputs.rename(moved_inputs)
    moved_runs = []
    for index, (family, path) in enumerate(runs):
        target = moved / f"run-{index}"
        path.rename(target)
        moved_runs.append((family, target))
    before = snapshot(tmp_path)
    result = run_cli(moved_records, moved_inputs, moved_runs)
    assert result.returncode == 0, result.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_one_invalid_run_fails_whole_comparison_without_partial_report(comparison_packages, tmp_path, index):
    from traffic_anomaly.candidate_comparison import CandidateComparisonError, CandidateComparisonRun, compare_candidate_runs

    records, inputs, runs = copied(comparison_packages, tmp_path)
    (runs[index][1] / "scores.json").write_bytes(b'{"private":"tampered scores"}')
    before = snapshot(tmp_path)
    with pytest.raises(CandidateComparisonError) as expected:
        compare_candidate_runs([CandidateComparisonRun(family, path) for family, path in runs], records, inputs)
    assert safe_error(run_cli(records, inputs, runs), tmp_path) == expected.value.code
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("target", ["records", "inputs", "source"])
def test_missing_shared_inputs_are_safe_and_readonly(comparison_packages, tmp_path, target):
    records, inputs, runs = copied(comparison_packages, tmp_path)
    source = SOURCE
    if target == "records": records = tmp_path / "private-records"
    elif target == "inputs": inputs = tmp_path / "private-inputs"
    else: source = tmp_path / "private-source.json"
    before = snapshot(tmp_path)
    safe_error(run_cli(records, inputs, runs, source), tmp_path)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("if_count,ae_count", [(0, 0), (1, 0), (0, 1), (2, 0), (2, 2), (0, 4), (1, 4)])
def test_family_and_total_counts_reject_before_opening_run_paths(tmp_path, if_count, ae_count):
    runs = [("iforest", tmp_path / f"private-if-{i}") for i in range(if_count)]
    runs += [("autoencoder", tmp_path / f"private-ae-{i}") for i in range(ae_count)]
    before = snapshot(tmp_path)
    assert safe_error(run_cli(tmp_path / "private-records", tmp_path / "private-inputs", runs), tmp_path) == "INVALID_ARGUMENTS"
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("extra", [("--model", "private-model"), ("--output", "private-output"), ("--resume",),
                                  ("--repair",), ("--normalize",), ("--select-best",), ("--metric", "f1"),
                                  ("--p-value", "0.05"), ("--threshold", "0"), ("--window", "15")])
def test_no_model_write_ranking_or_tuning_options_exist(comparison_packages, tmp_path, extra):
    records, inputs, runs = copied(comparison_packages, tmp_path)
    before = snapshot(tmp_path)
    assert safe_error(run_cli(records, inputs, runs, extra=extra), tmp_path) == "INVALID_ARGUMENTS"
    assert snapshot(tmp_path) == before


def test_missing_required_arguments_are_safe():
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_compare_cli"],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2 and result.stdout == ""
    assert json.loads(result.stderr) == {"error": "INVALID_ARGUMENTS"}
