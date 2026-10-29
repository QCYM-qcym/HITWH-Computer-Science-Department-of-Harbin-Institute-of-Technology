"""Synthetic source-record adaptation remains separate from numeric fitting."""
import hashlib
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest


FIXTURE = Path(__file__).parents[1] / "fixtures" / "g13u-records-v1.json"
POLICIES = ("P_U", "P_B", "P_A")


def fixture_value():
    return json.loads(FIXTURE.read_text("utf-8"))


def write_fixture(tmp_path, value):
    path = tmp_path / "source-records.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_cli(fixture, output, policy="P_U", *extra):
    command = [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_record_cli",
               "--fixture", str(fixture), "--output", str(output)]
    if policy is not None:
        command.extend(["--policy", policy])
    return subprocess.run([*command, *extra], capture_output=True, text=True, encoding="utf-8")


def run_numeric(fixture, output):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_cli",
         "--fixture", str(fixture), "--output", str(output)],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_fixture_has_explicit_source_identity_and_unique_manual_records():
    fixture = fixture_value()
    assert fixture["evidence_kind"] == "SYNTHETIC_ONLY"
    assert fixture["time_basis"] == "synthetic_source_clock"
    assert len(fixture["minutes"]) == 144
    stamps = np.array([row["timestamp"] for row in fixture["minutes"]], dtype="datetime64[us]")
    assert np.all(np.diff(stamps) == np.timedelta64(1, "m"))
    for partition in ("train", "validation", "calibration", "test"):
        assert sum(row["partition"] == partition for row in fixture["minutes"]) == 36
    assert len(fixture["records"]) == len({row["record_key"] for row in fixture["records"]}) == 576
    assert {row["protocol"] for row in fixture["records"]} == {0, 1, 6, 17}
    assert {row["label"] for row in fixture["records"]} == {"BENIGN", "SSH-Patator - Attempted", "Portscan"}
    assert all(row["empty_label"] == "unknown" for row in fixture["minutes"])


@pytest.mark.parametrize("policy", POLICIES)
def test_cli_matches_adapter_and_exports_audit_only_bound_artifacts(tmp_path, policy):
    from traffic_anomaly.candidate_records import RECORD_PROFILE_ID, adapt_synthetic_records

    fixture = fixture_value()
    expected = adapt_synthetic_records(fixture["minutes"], fixture["records"])
    output = tmp_path / "adapter"
    result = run_cli(FIXTURE, output, policy)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"evidence_kind": "SYNTHETIC_ONLY", "status": "COMPLETE",
                                        "selected_policy": policy, "policy_status": "AUDIT_ONLY"}
    assert {path.name for path in output.iterdir()} == {"minute-fixture.json", "label-audit.json", "manifest.json"}
    minute_fixture = json.loads((output / "minute-fixture.json").read_text("utf-8"))
    assert minute_fixture == expected.to_fixture(policy, epsilon=fixture["epsilon"])
    audit = json.loads((output / "label-audit.json").read_text("utf-8"))
    assert audit["profile_id"] == RECORD_PROFILE_ID
    assert audit["evidence_kind"] == "SYNTHETIC_ONLY"
    assert audit["time_basis"] == "synthetic_source_clock"
    assert audit["selected_policy"] == policy and audit["policy_status"] == "AUDIT_ONLY"
    assert audit["audit"] == expected.audit
    assert audit["labels"] == {name: list(expected.labels[name]) for name in POLICIES}
    assert audit["normal_candidates"] == {name: expected.normal_candidates[name].tolist() for name in POLICIES}
    assert audit["labels"]["P_U"][139] == "unknown"
    assert audit["labels"]["P_B"][139] == "normal"
    assert audit["labels"]["P_A"][139] == "attack"
    assert all(audit["labels"][name][140] == "attack" for name in POLICIES)
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    assert manifest["profile_id"] == RECORD_PROFILE_ID
    assert manifest["status"] == "COMPLETE" and manifest["evidence_kind"] == "SYNTHETIC_ONLY"
    assert manifest["selected_policy"] == policy and manifest["policy_status"] == "AUDIT_ONLY"
    assert manifest["fixture"] == {"sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                                    "byte_count": FIXTURE.stat().st_size}
    assert manifest["configuration"]["selected_policy"] == policy
    assert manifest["configuration"]["policy_status"] == "AUDIT_ONLY"
    encoded_config = json.dumps(manifest["configuration"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert manifest["configuration_sha256"] == hashlib.sha256(encoded_config).hexdigest()
    assert set(manifest["artifacts"]) == {"minute-fixture.json", "label-audit.json"}
    for name, entry in manifest["artifacts"].items():
        payload = (output / name).read_bytes()
        assert entry == {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}
    for path in output.iterdir():
        content = path.read_text("utf-8")
        assert str(tmp_path) not in content
        assert "NaN" not in content and "Infinity" not in content
    assert "scores" not in audit and "metrics" not in audit


def test_exported_fixture_runs_numeric_cli_with_equivalent_thirteen_and_twenty_six_values(tmp_path):
    from traffic_anomaly.candidate_inputs import prepare_candidate_inputs
    from traffic_anomaly.candidate_records import adapt_synthetic_records

    fixture = fixture_value()
    adapted = adapt_synthetic_records(fixture["minutes"], fixture["records"])
    expected = prepare_candidate_inputs(adapted.batch, adapted.normal_candidates["P_U"], epsilon=fixture["epsilon"])
    assert run_cli(FIXTURE, tmp_path / "adapter", "P_U").returncode == 0
    numeric = tmp_path / "numeric"
    result = run_numeric(tmp_path / "adapter" / "minute-fixture.json", numeric)
    assert result.returncode == 0, result.stderr
    data = json.loads((numeric / "candidate-inputs.json").read_text("utf-8"))
    assert data["dimensions"] == {"current": 13, "joined": 26}
    np.testing.assert_allclose(data["current_values"], expected.prepared.values)
    for name in ("common_valid", "training_normal", "calibration_normal", "test_normal"):
        assert data[name] == getattr(expected, name).tolist()
    for window in (15, 30):
        exported = np.array(expected.histories[window].joined, dtype=object)
        exported[~np.isfinite(expected.histories[window].joined)] = None
        assert data["histories"][str(window)]["joined"] == exported.tolist()


def test_invalid_record_minute_exports_null_and_numeric_cli_keeps_it_invalid(tmp_path):
    fixture = fixture_value()
    fixture["records"][40 * 4]["protocol"] = 200
    source = write_fixture(tmp_path, fixture)
    adapter = tmp_path / "adapter"
    result = run_cli(source, adapter)
    assert result.returncode == 0, result.stderr
    minute_fixture = json.loads((adapter / "minute-fixture.json").read_text("utf-8"))
    assert minute_fixture["minutes"][40]["valid"] is False
    assert minute_fixture["minutes"][40]["features"] == [None] * 13
    result = run_numeric(adapter / "minute-fixture.json", tmp_path / "numeric")
    assert result.returncode == 0, result.stderr
    data = json.loads((tmp_path / "numeric" / "candidate-inputs.json").read_text("utf-8"))
    assert data["row_valid"][40] is False
    assert data["current_values"][40] == [None] * 13
    assert not any(data["common_valid"][40:71])
    assert data["common_valid"][71] is True


@pytest.mark.parametrize("policy", [None, "P_Z"])
def test_cli_requires_explicit_valid_policy(tmp_path, policy):
    result = run_cli(FIXTURE, tmp_path / "result", policy)
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_ARGUMENTS"}
    assert not (tmp_path / "result").exists()


def test_cli_rejects_export_larger_than_numeric_input_limit_before_creating_output(tmp_path):
    from traffic_anomaly.candidate_cli import MAX_FIXTURE_BYTES

    minutes = [{"timestamp": (datetime(2026, 1, 1) + timedelta(minutes=i)).isoformat(timespec="seconds"),
                "partition": "train", "segment_id": "s", "coverage": "confirmed_empty", "empty_label": "normal"}
               for i in range(4000)]
    fixture = {"schema_version": 1, "evidence_kind": "SYNTHETIC_ONLY",
               "time_basis": "synthetic_source_clock", "minutes": minutes,
               "records": [], "epsilon": 1e-6}
    source = tmp_path / "compact-source.json"
    source.write_text(json.dumps(fixture, separators=(",", ":")), encoding="utf-8")
    assert source.stat().st_size < MAX_FIXTURE_BYTES
    output = tmp_path / "incompatible-export"
    result = run_cli(source, output)
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_FIXTURE"}
    assert not output.exists()


def test_minute_fixture_size_check_matches_actual_writer_bytes_and_platform_newlines(tmp_path):
    from traffic_anomaly import candidate_record_cli

    value = {"z": [None, 1.25, True], "a": {"text": "synthetic-é"}}
    actual = tmp_path / "serialized.json"
    candidate_record_cli._write_json(actual, value)
    assert candidate_record_cli._minute_fixture_bytes(value) == actual.read_bytes()


def test_cli_refuses_existing_output_without_touching_it(tmp_path):
    output = tmp_path / "result"
    output.mkdir()
    marker = output / "marker.txt"
    marker.write_text("keep")
    result = run_cli(FIXTURE, output)
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "OUTPUT_EXISTS"}
    assert list(output.iterdir()) == [marker]
    assert marker.read_text() == "keep"


@pytest.mark.parametrize("mutation", [
    lambda v: v.update(evidence_kind="REAL"),
    lambda v: v.update(time_basis="UTC"),
    lambda v: v.update(schema_version=True),
    lambda v: v.update(schema_version=2),
    lambda v: v.update(extra="private"),
    lambda v: v.pop("epsilon"),
    lambda v: v.update(epsilon=0),
    lambda v: v.update(epsilon=True),
    lambda v: v.update(epsilon=float("inf")),
    lambda v: v.update(minutes=[]),
    lambda v: v.update(minutes=[v["minutes"][0]] * 10001),
    lambda v: v.update(records=[v["records"][0]] * 10001),
    lambda v: v.update(records={}),
    lambda v: v["minutes"][0].update(extra=True),
    lambda v: v["records"][0].update(extra=True),
    lambda v: v["records"][0].update(start="bad-time"),
    lambda v: v["records"][0].update(duration_us=-1),
    lambda v: v["records"][0].update(duration_us="1000"),
    lambda v: v["minutes"][0].update(timestamp="2026-01-01T00:00:00Z"),
])
def test_cli_rejects_invalid_fixture_before_creating_output(tmp_path, mutation):
    fixture = fixture_value()
    mutation(fixture)
    output = tmp_path / "result"
    result = run_cli(write_fixture(tmp_path, fixture), output)
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_FIXTURE"}
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("content", [b" " * (1024 * 1024 + 1), b"bad-json", b'{"schema_version":1,"schema_version":1}', b"[]", b'{"epsilon":NaN}'], ids=["oversize", "malformed", "duplicate", "array-root", "nonstandard-number"])
def test_cli_rejects_bounded_json_failures(tmp_path, content):
    source = tmp_path / "source.json"
    source.write_bytes(content)
    result = run_cli(source, tmp_path / "result")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_FIXTURE"}
    assert str(tmp_path) not in result.stderr
    assert not (tmp_path / "result").exists()


def test_cli_safe_missing_csv_unknown_argument_and_missing_parent_errors(tmp_path):
    result = run_cli(tmp_path / "private-missing.json", tmp_path / "result")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INPUT_UNAVAILABLE"}
    source = tmp_path / "source.csv"
    source.write_bytes(FIXTURE.read_bytes())
    result = run_cli(source, tmp_path / "result")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_FIXTURE"}
    result = run_cli(FIXTURE, tmp_path / "result", "P_U", "--private-unknown")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_ARGUMENTS"}
    assert "private-unknown" not in result.stderr
    result = run_cli(FIXTURE, tmp_path / "missing-parent" / "result")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "OUTPUT_ERROR"}
    assert str(tmp_path) not in result.stderr


def test_adapter_cli_never_fits_numeric_preprocessing(tmp_path, monkeypatch, capsys):
    from traffic_anomaly import candidate_record_cli
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor

    def forbidden(*args, **kwargs):
        raise AssertionError("record adaptation must not fit preprocessing")

    monkeypatch.setattr(CandidatePreprocessor, "fit", forbidden)
    assert candidate_record_cli.main(["--fixture", str(FIXTURE), "--policy", "P_U", "--output", str(tmp_path / "result")]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "COMPLETE"


def test_manifest_is_last_and_failed_artifact_write_has_no_completion_marker(tmp_path, monkeypatch, capsys):
    from traffic_anomaly import candidate_record_cli

    calls = []
    actual = candidate_record_cli._write_json

    def write(path, value):
        calls.append(path.name)
        if path.name == "label-audit.json":
            raise OSError("private path error")
        return actual(path, value)

    monkeypatch.setattr(candidate_record_cli, "_write_json", write)
    output = tmp_path / "failed"
    assert candidate_record_cli.main(["--fixture", str(FIXTURE), "--policy", "P_U", "--output", str(output)]) == 2
    assert "manifest.json" not in calls
    assert not (output / "manifest.json").exists()
    assert json.loads(capsys.readouterr().err) == {"error": "OUTPUT_ERROR"}
    monkeypatch.setattr(candidate_record_cli, "_write_json", lambda path, value: (calls.append(path.name), actual(path, value))[1])
    assert candidate_record_cli.main(["--fixture", str(FIXTURE), "--policy", "P_U", "--output", str(tmp_path / "success")]) == 0
    assert calls[-1] == "manifest.json"
