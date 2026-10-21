"""W0 contract acceptance; synthetic inputs only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/core"))


def contracts():
    assert importlib.util.find_spec("traffic_anomaly"), "core package is not implemented"
    from traffic_anomaly import contracts as c
    return c


def batch(width=134, names=None):
    return contracts().MinuteBatch(
        timestamps=np.array(["2026-01-01T00:00", "2026-01-01T00:01"], dtype="datetime64[ns]"),
        features=np.zeros((2, width), dtype=np.float32),
        feature_names=names or tuple(f"feature_{i:03}" for i in range(width)),
        row_valid=np.ones(2, dtype=bool), segment_ids=np.zeros(2, dtype=np.int64),
    )


def test_feature_width_and_label_separation():
    assert batch().features.shape == (2, 134)
    for width in (133, 135):
        with pytest.raises(ValueError):
            batch(width)
    for label in ("dos", "label_dos", "attack", "label", "spam"):
        names = list(batch().feature_names)
        names[0] = label
        with pytest.raises(ValueError):
            batch(names=tuple(names))


def test_duplicate_feature_names_and_label_axis_are_rejected():
    c = contracts()
    good = batch()
    names = list(good.feature_names)
    names[-1] = names[0]
    with pytest.raises(ValueError):
        batch(names=tuple(names))
    labels = {name: np.zeros(2, dtype=np.int64) for name in c.LABEL_NAMES}
    labels["dos"] = np.zeros(1, dtype=np.int64)
    with pytest.raises(ValueError):
        c.LabelBatch(good.timestamps, labels)


def test_model_compatibility_checks_order_method_and_saved_transform():
    c = contracts()
    assert hasattr(c, "validate_model_compatibility"), "W1 needs a shared compatibility check"
    fixture = json.loads((ROOT / "tests/fixtures/contracts-v1.json").read_text(encoding="utf-8"))
    metadata = c.ModelMetadata.model_validate(next(s["body"] for s in fixture["responses"] if s["schema"] == "ModelMetadata"))
    state = c.PreprocessState.model_validate(next(s["body"] for s in fixture["responses"] if s["schema"] == "PreprocessState"))
    config = c.RunConfig(dataset_id="synthetic-v1", split_id="split-v1", method="iforest")
    c.validate_model_compatibility(metadata, batch().feature_names, state, config)
    reordered = tuple(reversed(batch().feature_names))
    for names, saved, requested in ((reordered, state, config),
                                    (batch().feature_names, state.model_copy(update={"feature_names": reordered}), config),
                                    (batch().feature_names, state, config.model_copy(update={"method": "current_ae"}))):
        with pytest.raises(ValueError):
            c.validate_model_compatibility(metadata, names, saved, requested)
    for model, value in ((c.ModelMetadata, metadata.model_dump() | {"schema_version": "2.0"}),
                         (c.PreprocessState, state.model_dump() | {"version": "unknown"})):
        with pytest.raises(ValidationError):
            model.model_validate(value)


def test_openapi_embeds_schema_valid_request_and_error_examples():
    spec = yaml.safe_load((ROOT / "docs/design/openapi-v1.yaml").read_text(encoding="utf-8"))
    request = spec["paths"]["/api/v1/runs"]["post"]["requestBody"]["content"]["application/json"]
    assert "example" in request, "OpenAPI needs an executable synthetic request example"
    contracts().RunRequest.model_validate(request["example"])
    expected_codes = {"404": "NOT_FOUND", "409": "RUN_BUSY", "422": "VALIDATION_ERROR", "500": "EXECUTION_FAILED"}
    for path, operations in spec["paths"].items():
        for operation in operations.values():
            for status, response in operation["responses"].items():
                if status not in expected_codes:
                    continue
                media = response["content"]["application/json"]
                assert media.get("examples"), (path, status)
                for example in media["examples"].values():
                    c = contracts()
                    c.ErrorResponse.model_validate(example["value"])
                    schema = media["schema"] | {"components": spec["components"]}
                    Draft202012Validator(schema).validate(example["value"])
                if path == "/api/v1/runs":
                    assert next(iter(media["examples"].values()))["value"]["error"]["code"] == expected_codes[status]


def test_shared_fixture_has_separate_normal_attack_and_invalid_minutes():
    c = contracts()
    fixture = json.loads((ROOT / "tests/fixtures/contracts-v1.json").read_text(encoding="utf-8"))
    assert "core_sample" in fixture, "all worktrees need an aligned feature/label sample"
    raw = fixture["core_sample"]
    timestamps = np.array([value.removesuffix("Z") for value in raw["timestamps"]], dtype="datetime64[ns]")
    minutes = c.MinuteBatch(timestamps, np.array(raw["features"], dtype=np.float32), tuple(raw["feature_names"]),
                            np.array(raw["row_valid"], dtype=bool), np.array(raw["segment_ids"], dtype=np.int64))
    labels = c.LabelBatch(timestamps, {name: np.array(values, dtype=np.int64) for name, values in raw["labels"].items()})
    page = next(s["body"] for s in fixture["responses"] if s["schema"] == "SeriesPage" and s["body"]["total"] > 0)
    assert len(minutes.timestamps) == len(page["items"])
    normal = np.all(np.stack(list(labels.labels.values())) == 0, axis=0)
    assert any(normal[i] and point["valid"] and point["alarm"] is False for i, point in enumerate(page["items"]))
    assert any(normal[i] and point["alarm"] is True for i, point in enumerate(page["items"]))
    assert any(labels.labels["dos"][i] > 0 and point["valid"] and point["alarm"] is False for i, point in enumerate(page["items"]))
    assert any(not point["valid"] and point["score"] is None for point in page["items"])


def test_alarms_examples_contain_only_valid_alarm_minutes():
    spec = yaml.safe_load((ROOT / "docs/design/openapi-v1.yaml").read_text(encoding="utf-8"))
    media = spec["paths"]["/api/v1/runs/{run_id}/alarms"]["get"]["responses"]["200"]["content"]["application/json"]
    for example in media["examples"].values():
        page = example["value"]
        assert all(row["valid"] and row["alarm"] is True for row in page["items"])
        assert page["total"] == len(page["items"])
    populated = next(example["value"] for example in media["examples"].values() if example["value"]["total"] > 0)
    assert populated["total"] == 1
    assert populated["items"][0]["timestamp"] == "2026-01-01T00:02:00Z"


def test_time_axis_and_array_integrity():
    from dataclasses import replace
    good = batch()
    for changes in (
        {"timestamps": good.timestamps[::-1]},
        {"timestamps": np.repeat(good.timestamps[:1], 2)},
        {"features": good.features.astype(np.float64)},
        {"row_valid": np.ones(1, dtype=bool)},
        {"features": np.full((2, 134), np.nan, dtype=np.float32)},
    ):
        with pytest.raises(ValueError):
            replace(good, **changes)


def test_mock_sample_matches_api_schema():
    c = contracts()
    spec = yaml.safe_load((ROOT / "docs/design/openapi-v1.yaml").read_text(encoding="utf-8"))
    fixture = json.loads((ROOT / "tests/fixtures/contracts-v1.json").read_text(encoding="utf-8"))
    for sample in fixture["responses"]:
        schema = {"$ref": f"#/components/schemas/{sample['schema']}", "components": spec["components"]}
        Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(sample["body"])
        getattr(c, sample["schema"]).model_validate(sample["body"])
    assert fixture["evidence_kind"] == "SYNTHETIC_ONLY"
    rows = next(s["body"]["items"] for s in fixture["responses"] if s["schema"] == "SeriesPage")
    assert rows[0]["score"] is None and rows[0]["invalid_reason"] == "warmup"
    assert rows[1]["score"] == rows[1]["threshold"] and rows[1]["alarm"] is False


def test_invalid_api_values_are_rejected():
    c = contracts()
    valid = dict(timestamp="2026-01-01T00:00:00Z", score=1.0, threshold=1.0,
                 alarm=False, valid=True, invalid_reason=None, flow_count=None)
    for change in ({"score": float("nan")}, {"alarm": True}, {"valid": False},
                   {"timestamp": "2026-01-01T00:00:00"}, {"score": None}):
        with pytest.raises(ValidationError):
            c.SeriesPoint.model_validate(valid | change)
    for field, value in (("method", "usad"), ("dataset_id", "../private"), ("path", "secret")):
        request = dict(dataset_id="synthetic-v1", split_id="split-v1", method="iforest", config_id="smoke-v1")
        request[field] = value
        with pytest.raises(ValidationError):
            c.RunRequest.model_validate(request)


def test_labels_config_and_lifecycle():
    c = contracts()
    good = batch()
    c.LabelBatch(good.timestamps, {name: np.zeros(2, dtype=np.int64) for name in c.LABEL_NAMES})
    with pytest.raises(ValueError):
        c.LabelBatch(good.timestamps, {"dos": np.zeros(2)})
    for previous, following in (("queued", "running"), ("queued", "failed"),
                                ("running", "succeeded"), ("running", "failed")):
        assert c.can_transition(previous, following)
    assert not c.can_transition("succeeded", "running")
    config = c.RunConfig(dataset_id="synthetic-v1", split_id="split-v1", method="iforest")
    assert config.schema_version == "1.0"
    for change in ({"window_minutes": 0}, {"preprocess": {"epsilon": 0}}, {"seed": -1}):
        with pytest.raises(ValidationError):
            c.RunConfig.model_validate(config.model_dump() | change)


def test_contract_import_does_not_load_training_runtime():
    contracts()
    subprocess.run([sys.executable, "-c", "import traffic_anomaly.contracts; import sys; assert 'torch' not in sys.modules; assert 'sklearn' not in sys.modules"],
                   env=__import__("os").environ | {"PYTHONPATH": str(ROOT / "src/core")}, check=True)


def test_utc_calendar_and_task_seconds():
    c = contracts()
    with pytest.raises(ValidationError):
        c.TimeRange(start="2026-02-30T00:00:00Z", end="2026-03-02T00:00:00Z")
    with pytest.raises(ValidationError):
        c.SeriesPoint(timestamp="2026-02-30T00:00:00Z", score=1, threshold=1,
                      alarm=False, valid=True, invalid_reason=None, flow_count=None)
    config = dict(dataset_id="synthetic-v1", split_id="split-v1", method="iforest")
    assert c.RunStatus(run_id="synthetic-run", status="running", evidence_kind="SYNTHETIC_ONLY",
                       created_at="2026-01-01T00:00:01Z", started_at="2026-01-01T00:00:03Z",
                       finished_at=None, config=config, error=None)


def test_split_path_and_segment_boundaries():
    from dataclasses import replace
    c = contracts()
    good = batch()
    with pytest.raises(ValueError):
        replace(good, timestamps=np.array(["2026-01-01T00:00", "2026-01-01T00:02"], dtype="datetime64[ns]"))
    replace(good, timestamps=np.array(["2026-01-01T00:00", "2026-01-01T00:02"], dtype="datetime64[ns]"),
            segment_ids=np.array([0, 1], dtype=np.int64))
    for path in ("../secret", "/secret", "C:/secret", "run/../../secret", "run\\secret"):
        with pytest.raises(ValidationError):
            c.RunResult(run_id="synthetic-run", manifest_path=path, summary_path="summary.json", scores_path="scores.parquet")


def test_metric_zero_denominators_and_counts_are_consistent():
    c = contracts()
    fields = dict(tp=0, fp=0, tn=0, fn=0, precision=0.0, recall=0.0, f1=0.0, fpr=0.0, undefined_reasons=[])
    with pytest.raises(ValidationError):
        c.Metrics(**fields)
    c.Metrics(**(fields | dict(precision=None, recall=None, f1=None, fpr=None,
                              undefined_reasons=["precision", "recall", "f1", "fpr"])))
    with pytest.raises(ValidationError):
        c.Metrics(**(fields | dict(tp=1, fp=1, tn=1, fn=1, precision=0.9, recall=0.5, f1=0.5, fpr=0.5)))


def test_manifest_is_complete_and_consistent():
    c = contracts()
    fields = dict(run_id="synthetic-run", evidence_kind="SYNTHETIC_ONLY",
                  config=dict(dataset_id="synthetic-v1", split_id="split-v1", method="iforest"),
                  code_commit="a" * 40, dataset_version="manual-v1", feature_version="synthetic-v1",
                  split_version="v1", seed=42, dependency_lock_sha256="b" * 64,
                  files=[dict(path="scores.parquet", sha256="c" * 64)])
    with pytest.raises(ValidationError):
        c.Manifest(**fields)
    files = [dict(path=p, sha256="c" * 64) for p in (
        "summary.json", "scores.parquet", "metrics.json", "config.json", "channels.parquet",
        "model/metadata.json", "model/preprocess.json", "model/weights.bin")]
    c.Manifest(**(fields | dict(files=files)))
    with pytest.raises(ValidationError):
        c.Manifest(**(fields | dict(files=files, seed=43)))
    with pytest.raises(ValidationError):
        c.ArtifactFile(path="./manifest.json", sha256="c" * 64)


def test_openapi_time_parameters_use_minute_utc_schema():
    spec = yaml.safe_load((ROOT / "docs/design/openapi-v1.yaml").read_text(encoding="utf-8"))
    for path, operations in spec["paths"].items():
        for operation in operations.values():
            for parameter in operation.get("parameters", []):
                if parameter["name"] in ("start", "end", "timestamp"):
                    validator = Draft202012Validator(parameter["schema"], format_checker=Draft202012Validator.FORMAT_CHECKER)
                    assert validator.is_valid("2026-01-01T00:00:00Z")
                    assert not validator.is_valid("2026-01-01T00:00:01Z"), path
                    assert not validator.is_valid("2026-01-01T00:00:00+01:00"), path


def test_replay_artifact_types_exist_and_validate():
    c = contracts()
    assert hasattr(c, "RunSummary"), "saved summary must have a frozen shape"
    assert hasattr(c, "ChannelRow"), "saved channels must support detail replay"
    assert hasattr(c, "LabelRow"), "evaluation labels need a separate saved layout"
    c.ChannelRow(timestamp="2026-01-01T00:00:00Z", current=[0.0]*134,
                 history_residual=None, reconstruction_error_current=None, reconstruction_error_history=None)
    with pytest.raises(ValidationError):
        c.ChannelRow(timestamp="2026-01-01T00:00:00Z", current=[0.0]*133,
                     history_residual=None, reconstruction_error_current=None, reconstruction_error_history=None)


def test_saved_preprocessor_rejects_wrong_width_and_nonpositive_scale():
    c = contracts()
    assert hasattr(c, "PreprocessState"), "saved transform must have a frozen shape"
    fields = dict(feature_names=batch().feature_names, mean=[0.0]*134, scale=[1.0]*134, n_samples_seen=2)
    c.PreprocessState(**fields)
    for change in ({"scale": [0.0]*134}, {"mean": [0.0]*133}, {"n_samples_seen": 0}):
        with pytest.raises(ValidationError):
            c.PreprocessState(**(fields | change))


@pytest.mark.parametrize("case", ["lifecycle", "history", "high_load"])
def test_lifecycle_history_and_unavailable_reasons(case):
    from dataclasses import replace
    c = contracts()
    fixture = json.loads((ROOT / "tests/fixtures/contracts-v1.json").read_text(encoding="utf-8"))
    status = next(s["body"] for s in fixture["responses"] if s["schema"] == "RunStatus" and s["body"]["status"] == "running")
    if case == "lifecycle":
        with pytest.raises(ValidationError):
            c.RunStatus.model_validate(status | dict(started_at="2025-01-01T00:00:00Z"))
    evaluation = next(s["body"] for s in fixture["responses"] if s["schema"] == "Evaluation")
    if case == "high_load":
        with pytest.raises(ValidationError):
            c.Evaluation.model_validate(evaluation | dict(high_load_unavailable_reason=None))
    good = batch()
    history = c.HistoryBatch(good.timestamps, good.features, good.features, np.zeros(2, dtype=bool), ("warmup", "warmup"))
    if case == "history":
        with pytest.raises(ValueError):
            replace(history, invalid_reason=("arbitrary", "warmup"))
