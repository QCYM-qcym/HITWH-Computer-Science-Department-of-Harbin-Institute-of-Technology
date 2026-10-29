"""Read-only CLI checks for the synthetic adapter/numeric artifact chain."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


FIXTURE = Path(__file__).parents[1] / "fixtures" / "g13u-records-v1.json"


def make_chain(tmp_path, policy="P_U"):
    from traffic_anomaly.candidate_cli import _run as build_inputs
    from traffic_anomaly.candidate_record_cli import _run as adapt_records

    records, inputs = tmp_path / "records", tmp_path / "inputs"
    adapt_records(FIXTURE, policy, records)
    build_inputs(records / "minute-fixture.json", inputs)
    return records, inputs


def run_cli(records, inputs, source=None, *extra):
    command = [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_verify_cli",
               "--records", str(records), "--inputs", str(inputs)]
    if source is not None:
        command.extend(["--source-fixture", str(source)])
    return subprocess.run([*command, *extra], capture_output=True, text=True, encoding="utf-8")


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        stat = path.stat()
        result[str(path.relative_to(root))] = (
            path.is_dir(), stat.st_size, stat.st_mtime_ns,
            None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return result


def source_snapshot():
    stat = FIXTURE.stat()
    return stat.st_size, stat.st_mtime_ns, hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def assert_safe_error(result, tmp_path):
    assert result.returncode == 2
    assert result.stdout == ""
    error = json.loads(result.stderr)
    assert set(error) == {"error"}
    assert re.fullmatch(r"[A-Z][A-Z0-9_]*", error["error"])
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    return error["error"]


@pytest.mark.parametrize("policy", ["P_U", "P_B", "P_A"])
@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
def test_cli_emits_complete_core_report_for_each_policy_without_writing(tmp_path, policy, include_source):
    from traffic_anomaly.candidate_artifacts import verify_candidate_artifacts

    records, inputs = make_chain(tmp_path, policy)
    source = FIXTURE if include_source else None
    before = snapshot(tmp_path), source_snapshot()
    expected = verify_candidate_artifacts(records, inputs, source_fixture=source)
    result = run_cli(records, inputs, source)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report == expected
    assert report["status"] == "VERIFIED"
    assert report["evidence_kind"] == "SYNTHETIC_ONLY"
    assert report["selected_policy"] == policy
    assert report["policy_status"] == "AUDIT_ONLY"
    assert report["checks"]["source_replay"] == ("VERIFIED" if include_source else "NOT_PROVIDED")
    assert report["checks"]["fit_parameters"] == "NOT_REESTIMATED"
    assert str(tmp_path) not in result.stdout
    assert (snapshot(tmp_path), source_snapshot()) == before


def test_cli_verifies_relocated_artifact_directories_without_original_paths(tmp_path):
    records, inputs = make_chain(tmp_path)
    archive = tmp_path / "relocated"
    archive.mkdir()
    moved_records, moved_inputs = archive / "adapter-artifacts", archive / "numeric-artifacts"
    records.rename(moved_records)
    inputs.rename(moved_inputs)
    before = snapshot(tmp_path)
    result = run_cli(moved_records, moved_inputs, FIXTURE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "VERIFIED"
    assert snapshot(tmp_path) == before
    assert not records.exists() and not inputs.exists()


@pytest.mark.parametrize("target", ["records", "inputs", "source"])
def test_cli_rejects_missing_inputs_with_core_error_and_no_side_effects(tmp_path, target):
    from traffic_anomaly.candidate_artifacts import CandidateArtifactError, verify_candidate_artifacts

    records, inputs = make_chain(tmp_path)
    source = FIXTURE
    if target == "records":
        records = tmp_path / "private-missing-records"
    elif target == "inputs":
        inputs = tmp_path / "private-missing-inputs"
    else:
        source = tmp_path / "private-missing-source.json"
    before = snapshot(tmp_path)
    with pytest.raises(CandidateArtifactError) as error:
        verify_candidate_artifacts(records, inputs, source_fixture=source)
    result = run_cli(records, inputs, source)
    assert assert_safe_error(result, tmp_path) == error.value.code
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("relative", [
    "records/manifest.json", "records/minute-fixture.json", "records/label-audit.json",
    "inputs/manifest.json", "inputs/preprocess.json", "inputs/candidate-inputs.json",
])
def test_cli_rejects_tampered_files_without_repair_or_private_diagnostics(tmp_path, relative):
    from traffic_anomaly.candidate_artifacts import CandidateArtifactError, verify_candidate_artifacts

    records, inputs = make_chain(tmp_path)
    target = tmp_path / relative
    target.write_bytes(b'{"private_error_path":"must_not_be_echoed"}')
    before = snapshot(tmp_path)
    with pytest.raises(CandidateArtifactError) as error:
        verify_candidate_artifacts(records, inputs)
    result = run_cli(records, inputs)
    assert assert_safe_error(result, tmp_path) == error.value.code
    assert "must_not_be_echoed" not in result.stderr
    assert snapshot(tmp_path) == before


def test_cli_rejects_changed_source_fixture_without_writing(tmp_path):
    from traffic_anomaly.candidate_artifacts import CandidateArtifactError, verify_candidate_artifacts

    records, inputs = make_chain(tmp_path)
    source = tmp_path / "private-source.json"
    value = json.loads(FIXTURE.read_text("utf-8"))
    value["records"][0]["fwd_packets"] += 1
    source.write_text(json.dumps(value), encoding="utf-8")
    before = snapshot(tmp_path)
    with pytest.raises(CandidateArtifactError) as error:
        verify_candidate_artifacts(records, inputs, source_fixture=source)
    result = run_cli(records, inputs, source)
    assert assert_safe_error(result, tmp_path) == error.value.code
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("arguments", [[], ["--records", "private-path"],
    ["--records", "private-path", "--inputs", "other-private", "--unknown-private"],
    ["--records", "private-path", "--inputs", "other-private", "--source-fixture"],
])
def test_cli_uses_safe_invalid_argument_error(arguments):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_verify_cli", *arguments],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "INVALID_ARGUMENTS"}
    assert "private" not in result.stderr


def test_cli_verification_cannot_fit_preprocessor(tmp_path, monkeypatch, capsys):
    from traffic_anomaly import candidate_verify_cli
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor

    records, inputs = make_chain(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("verification must not fit")

    monkeypatch.setattr(CandidatePreprocessor, "fit", forbidden)
    before = snapshot(tmp_path), source_snapshot()
    assert candidate_verify_cli.main(["--records", str(records), "--inputs", str(inputs), "--source-fixture", str(FIXTURE)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["checks"]["fit_parameters"] == "NOT_REESTIMATED"
    assert (snapshot(tmp_path), source_snapshot()) == before
