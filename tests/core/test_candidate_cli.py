"""The candidate entry point consumes bounded, explicit synthetic JSON only."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest


FIXTURE = Path(__file__).parents[1] / "fixtures" / "g13u-inputs-v1.json"


def run_cli(fixture, output, *extra):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "traffic_anomaly.candidate_cli", "--fixture",
         str(fixture), "--output", str(output), *extra],
        capture_output=True, text=True, encoding="utf-8",
    )


def write_fixture(tmp_path, value):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def fixture_value():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_is_hand_constructed_and_semantically_consistent():
    fixture = fixture_value()
    assert fixture["evidence_kind"] == "SYNTHETIC_ONLY"
    assert fixture["time_basis"] == "synthetic_source_clock"
    assert len(fixture["minutes"]) == 144
    assert len(fixture["normal_candidates"]) == 144
    assert not all(fixture["normal_candidates"][-36:])
    for partition in ("train", "validation", "calibration", "test"):
        assert sum(row["partition"] == partition for row in fixture["minutes"]) == 36
    for row in fixture["minutes"]:
        values = row["features"]
        assert sum(values[5:9]) == values[0]
        assert 0 <= values[12] <= values[0]
        assert values[10] <= values[11] <= values[9]


def test_cli_matches_shared_computation_and_reloads_preprocessing(tmp_path):
    from traffic_anomaly.candidate_inputs import (
        CandidateMinuteBatch, CandidatePreprocessor, G13U_FEATURE_NAMES,
        prepare_candidate_inputs,
    )

    fixture = fixture_value()
    assert fixture["feature_names"] == list(G13U_FEATURE_NAMES)
    rows = fixture["minutes"]
    raw = CandidateMinuteBatch(
        timestamps=np.array([r["timestamp"] for r in rows], dtype="datetime64[us]"),
        values=np.array([r["features"] for r in rows]),
        row_valid=np.array([r["valid"] for r in rows]),
        segment_ids=np.array([r["segment_id"] for r in rows]),
        partitions=np.array([r["partition"] for r in rows]),
    )
    expected = prepare_candidate_inputs(raw, np.array(fixture["normal_candidates"]), epsilon=fixture["epsilon"])
    output = tmp_path / "result"
    run = run_cli(FIXTURE, output)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == {"evidence_kind": "SYNTHETIC_ONLY", "status": "COMPLETE"}
    data = json.loads((output / "candidate-inputs.json").read_text())
    assert data["evidence_kind"] == "SYNTHETIC_ONLY"
    assert data["time_basis"] == "synthetic_source_clock"
    assert data["feature_names"] == list(G13U_FEATURE_NAMES)
    assert data["dimensions"] == {"current": 13, "joined": 26}
    assert data["normal_candidates"] == fixture["normal_candidates"]
    assert data["common_valid"] == expected.common_valid.tolist()
    assert data["training_normal"] == expected.training_normal.tolist()
    assert data["calibration_normal"] == expected.calibration_normal.tolist()
    assert data["test_normal"] == expected.test_normal.tolist()
    np.testing.assert_allclose(data["current_values"], expected.prepared.values)
    for window in (15, 30):
        history = data["histories"][str(window)]
        expected_history = expected.histories[window]
        assert history["valid"] == expected_history.valid.tolist()
        assert history["invalid_reason"] == list(expected_history.invalid_reason)
        for field in ("current", "residual", "joined"):
            exported = np.array(getattr(expected_history, field), dtype=object)
            exported[~np.isfinite(getattr(expected_history, field))] = None
            assert history[field] == exported.tolist()
        assert len(history["joined"][0]) == 26
    reloaded = CandidatePreprocessor.load(output / "preprocess.json").transform(raw)
    np.testing.assert_array_equal(reloaded.values, expected.prepared.values)
    for partition in ("train", "validation", "calibration", "test"):
        summary = data["partition_summary"][partition]
        assert summary["minute_count"] == 36
        assert summary["common_valid_count"] == 6
    assert data["partition_summary"]["test"]["test_normal_count"] == 6
    encoded = (output / "candidate-inputs.json").read_text()
    assert "null" in encoded and "NaN" not in encoded and "Infinity" not in encoded
    assert "scores" not in data and "metrics" not in data
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "COMPLETE"
    assert manifest["evidence_kind"] == "SYNTHETIC_ONLY"
    assert manifest["fixture"]["sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert manifest["fixture"]["byte_count"] == FIXTURE.stat().st_size
    config_bytes = json.dumps(manifest["configuration"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert manifest["configuration_sha256"] == hashlib.sha256(config_bytes).hexdigest()
    assert set(manifest["artifacts"]) == {"candidate-inputs.json", "preprocess.json"}
    for name, entry in manifest["artifacts"].items():
        payload = (output / name).read_bytes()
        assert entry == {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}
    for path in output.iterdir():
        assert str(tmp_path) not in path.read_text()


def test_cli_refuses_existing_output_without_modifying_it(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("unchanged")
    result = run_cli(FIXTURE, output)
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "OUTPUT_EXISTS"}
    assert marker.read_text() == "unchanged"
    assert list(output.iterdir()) == [marker]


def test_test_current_normal_mask_does_not_change_history(tmp_path):
    fixture = fixture_value()
    fixture["normal_candidates"][-1] = False
    output = tmp_path / "result"
    result = run_cli(write_fixture(tmp_path, fixture), output)
    assert result.returncode == 0, result.stderr
    data = json.loads((output / "candidate-inputs.json").read_text())
    assert data["common_valid"][-1] is True
    assert data["histories"]["30"]["valid"][-1] is True
    assert data["test_normal"][-1] is False
    assert data["partition_summary"]["test"]["test_normal_count"] == 5


@pytest.mark.parametrize("mutation", [
    lambda v: v.update(evidence_kind="REAL"),
    lambda v: v.update(time_basis="UTC"),
    lambda v: v.update(schema_version=True),
    lambda v: v.update(schema_version=2),
    lambda v: v.update(unknown="extra"),
    lambda v: v.pop("epsilon"),
    lambda v: v.update(epsilon=0),
    lambda v: v.update(epsilon=True),
    lambda v: v.update(epsilon=float("inf")),
    lambda v: v["feature_names"].reverse(),
    lambda v: v["feature_names"].append("label"),
    lambda v: v["normal_candidates"].pop(),
    lambda v: v["normal_candidates"].__setitem__(0, 1),
    lambda v: v["minutes"][0].update(label="BENIGN"),
    lambda v: v["minutes"][0].update(timestamp="2026-01-01T00:00:01"),
    lambda v: v["minutes"][0].update(timestamp="2026-01-01T00:00:00Z"),
    lambda v: v["minutes"][0].update(timestamp="2026-02-30T00:00:00"),
    lambda v: v["minutes"][0].update(valid=1),
    lambda v: v["minutes"][0].update(partition="holdout"),
    lambda v: v["minutes"][0].update(segment_id="private/path"),
    lambda v: v["minutes"][0]["features"].pop(),
    lambda v: v["minutes"][0]["features"].__setitem__(0, True),
    lambda v: v["minutes"][0]["features"].__setitem__(0, "1"),
    lambda v: v["minutes"][0]["features"].__setitem__(0, float("nan")),
    lambda v: v["minutes"][0]["features"].__setitem__(0, -1),
    lambda v: v["minutes"].__setitem__(1, copy.deepcopy(v["minutes"][0])),
    lambda v: v.update(minutes=[], normal_candidates=[]),
    lambda v: v.update(minutes=[v["minutes"][0]] * 10001, normal_candidates=[True] * 10001),
])
def test_cli_rejects_invalid_fixture_before_creating_output(tmp_path, mutation):
    value = fixture_value()
    mutation(value)
    output = tmp_path / "private-result"
    result = run_cli(write_fixture(tmp_path, value), output)
    assert result.returncode == 2
    assert json.loads(result.stderr)["error"] == "INVALID_FIXTURE"
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("content", [b"{} " + b" " * (1024 * 1024), b"{bad json}", b'{"schema_version":1,"schema_version":1}', b"[]"], ids=["oversize", "malformed", "duplicate", "array-root"])
def test_cli_rejects_oversized_malformed_or_duplicate_json(tmp_path, content):
    source = tmp_path / "private-input.json"
    source.write_bytes(content)
    output = tmp_path / "result"
    result = run_cli(source, output)
    assert result.returncode == 2
    assert json.loads(result.stderr)["error"] == "INVALID_FIXTURE"
    assert str(tmp_path) not in result.stderr
    assert not output.exists()


def test_cli_reports_safe_missing_input_and_argument_errors(tmp_path):
    result = run_cli(tmp_path / "private-missing.json", tmp_path / "out")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INPUT_UNAVAILABLE"}
    assert str(tmp_path) not in result.stderr
    result = run_cli(FIXTURE, tmp_path / "out", "--private-unknown")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_ARGUMENTS"}
    assert "private-unknown" not in result.stderr


def test_invalid_row_is_preserved_with_null_values_and_reset_history(tmp_path):
    fixture = fixture_value()
    fixture["minutes"][40]["valid"] = False
    output = tmp_path / "result"
    result = run_cli(write_fixture(tmp_path, fixture), output)
    assert result.returncode == 0, result.stderr
    data = json.loads((output / "candidate-inputs.json").read_text())
    assert len(data["timestamps"]) == 144
    assert data["row_valid"][40] is False
    assert data["current_values"][40] == [None] * 13
    assert data["histories"]["30"]["joined"][40] == [None] * 26
    assert data["histories"]["30"]["invalid_reason"][40] == "invalid_input"
    assert data["common_valid"][66] is False
    assert data["common_valid"][71] is True


def test_no_eligible_training_normal_input_fails_before_output(tmp_path):
    fixture = fixture_value()
    fixture["normal_candidates"][:36] = [False] * 36
    output = tmp_path / "result"
    result = run_cli(write_fixture(tmp_path, fixture), output)
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_FIXTURE"}
    assert not output.exists()


def test_csv_filename_is_not_an_input_adapter(tmp_path):
    source = tmp_path / "candidate.csv"
    source.write_bytes(FIXTURE.read_bytes())
    result = run_cli(source, tmp_path / "result")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {"error": "INVALID_FIXTURE"}


def test_failed_manifest_write_cannot_leave_a_complete_marker(tmp_path, monkeypatch, capsys):
    from traffic_anomaly import candidate_cli

    actual_dump = candidate_cli.json.dump

    def failed_dump(value, stream, **kwargs):
        if Path(stream.name).name == "manifest.json":
            stream.write('{"status":"COMPLETE"}')
            raise OSError("simulated final flush failure")
        return actual_dump(value, stream, **kwargs)

    monkeypatch.setattr(candidate_cli.json, "dump", failed_dump)
    output = tmp_path / "result"
    assert candidate_cli.main(["--fixture", str(FIXTURE), "--output", str(output)]) == 2
    assert not (output / "manifest.json").exists()
    assert json.loads(capsys.readouterr().err) == {"error": "OUTPUT_ERROR"}


def test_manifest_is_written_last_and_failed_write_has_no_completion_marker(tmp_path, monkeypatch, capsys):
    from traffic_anomaly import candidate_cli

    calls = []
    actual_write = candidate_cli._write_json

    def failing_write(path, value):
        calls.append(Path(path).name)
        if Path(path).name == "candidate-inputs.json":
            raise OSError("private path must stay private")
        return actual_write(path, value)

    monkeypatch.setattr(candidate_cli, "_write_json", failing_write)
    output = tmp_path / "failed-output"
    assert candidate_cli.main(["--fixture", str(FIXTURE), "--output", str(output)]) == 2
    assert not (output / "manifest.json").exists()
    assert "manifest.json" not in calls
    assert json.loads(capsys.readouterr().err) == {"error": "OUTPUT_ERROR"}
    monkeypatch.setattr(candidate_cli, "_write_json", lambda path, value: (calls.append(Path(path).name), actual_write(path, value))[1])
    assert candidate_cli.main(["--fixture", str(FIXTURE), "--output", str(tmp_path / "success")]) == 0
    assert calls[-1] == "manifest.json"
