"""Verified payloads are immutable snapshots with one physical read per file."""
from collections import Counter
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, is_dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from traffic_anomaly.candidate_cli import _run as numeric_run
from traffic_anomaly.candidate_record_cli import _run as record_run


SOURCE = Path(__file__).parents[1] / "fixtures" / "g13u-records-v1.json"


def make_package(tmp_path, policy="P_U", source=SOURCE):
    records, inputs = tmp_path / "records", tmp_path / "inputs"
    record_run(source, policy, records)
    numeric_run(records / "minute-fixture.json", inputs)
    return records, inputs


def read(path):
    return json.loads(path.read_text("utf-8"))


def digest(path):
    payload = path.read_bytes()
    return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}


def plain(value):
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [plain(item) for item in value]
    return value


def assert_deep_json_immutable(value):
    if isinstance(value, Mapping):
        assert not isinstance(value, dict)
        if value:
            key = next(iter(value))
            with pytest.raises(TypeError):
                value[key] = value[key]
        for item in value.values():
            assert_deep_json_immutable(item)
    elif isinstance(value, tuple):
        if value:
            with pytest.raises(TypeError):
                value[0] = value[0]
        for item in value:
            assert_deep_json_immutable(item)
    else:
        assert value is None or type(value) in (str, bool, int, float)


def snapshot_arrays(payload):
    names = ("timestamps", "segment_ids", "partitions", "current_values", "row_valid",
             "raw_values", "raw_valid", "common_valid", "training_normal",
             "calibration_normal", "test_normal", "source_attack_label_present")
    arrays = [(name, getattr(payload, name)) for name in names]
    for policy, values in payload.normal_candidates.items():
        arrays.append(("normal_candidates." + policy, values))
    for window, history in payload.histories.items():
        for name in ("current", "residual", "joined", "valid"):
            arrays.append((f"histories.{window}.{name}", getattr(history, name)))
    return arrays


def assert_bytes_backed_immutable(array):
    assert isinstance(array, np.ndarray)
    assert not array.flags.writeable
    with pytest.raises(ValueError):
        array.flat[0] = array.flat[0]
    with pytest.raises(ValueError):
        array.setflags(write=True)
    storage = array
    while isinstance(storage, np.ndarray):
        storage = storage.base
    while isinstance(storage, memoryview):
        assert storage.readonly
        storage = storage.obj
    assert isinstance(storage, bytes)


@pytest.mark.parametrize("policy", ["P_U", "P_B", "P_A"])
@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
def test_snapshot_has_verified_typed_payload_and_exact_provenance(tmp_path, policy, include_source):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts
    from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES

    records, inputs = make_package(tmp_path, policy)
    minute = read(records / "minute-fixture.json")
    numeric = read(inputs / "candidate-inputs.json")
    label_audit = read(records / "label-audit.json")
    state = read(inputs / "preprocess.json")
    payload = load_verified_candidate_artifacts(records, inputs, source_fixture=SOURCE if include_source else None)
    assert payload.report["status"] == "VERIFIED"
    assert payload.report["selected_policy"] == policy
    assert payload.report["checks"]["source_replay"] == ("VERIFIED" if include_source else "NOT_PROVIDED")
    assert payload.report["checks"]["fit_parameters"] == "NOT_REESTIMATED"
    assert payload.value_space == "prepared"
    assert payload.feature_names == G13U_FEATURE_NAMES and isinstance(payload.feature_names, tuple)
    assert is_dataclass(payload) and payload.__dataclass_params__.frozen
    with pytest.raises(FrozenInstanceError):
        payload.value_space = "raw"
    expected_provenance = {
        "record_manifest": digest(records / "manifest.json"),
        "input_manifest": digest(inputs / "manifest.json"),
        "source_fixture": digest(SOURCE),
        "minute_fixture": digest(records / "minute-fixture.json"),
        "preprocess": digest(inputs / "preprocess.json"),
    }
    assert plain(payload.provenance) == expected_provenance
    assert plain(payload.preprocessing_state) == state
    np.testing.assert_array_equal(payload.timestamps, np.array([r["timestamp"] for r in minute["minutes"]], dtype="datetime64[us]"))
    assert payload.timestamps.dtype == np.dtype("datetime64[us]")
    np.testing.assert_array_equal(payload.segment_ids, [r["segment_id"] for r in minute["minutes"]])
    np.testing.assert_array_equal(payload.partitions, [r["partition"] for r in minute["minutes"]])
    np.testing.assert_allclose(payload.current_values, np.array(numeric["current_values"], dtype=float), equal_nan=True)
    np.testing.assert_allclose(payload.raw_values, np.array([r["features"] for r in minute["minutes"]], dtype=float), equal_nan=True)
    assert payload.current_values.dtype == payload.raw_values.dtype == np.dtype("float64")
    assert payload.row_valid.dtype == payload.raw_valid.dtype == np.dtype(bool)
    np.testing.assert_array_equal(payload.row_valid, numeric["row_valid"])
    np.testing.assert_array_equal(payload.raw_valid, [r["valid"] for r in minute["minutes"]])
    for name in ("common_valid", "training_normal", "calibration_normal", "test_normal"):
        values = getattr(payload, name)
        assert values.dtype == np.dtype(bool)
        np.testing.assert_array_equal(values, numeric[name])
    assert set(payload.histories) == {15, 30}
    for window, history in payload.histories.items():
        expected = numeric["histories"][str(window)]
        for name in ("current", "residual", "joined"):
            assert getattr(history, name).dtype == np.dtype("float64")
            np.testing.assert_allclose(getattr(history, name), np.array(expected[name], dtype=float), equal_nan=True)
        assert history.valid.dtype == np.dtype(bool)
        np.testing.assert_array_equal(history.valid, expected["valid"])
        assert history.invalid_reason == tuple(expected["invalid_reason"])
    assert set(payload.labels) == set(payload.normal_candidates) == {"P_U", "P_B", "P_A"}
    for name in payload.labels:
        assert payload.labels[name] == tuple(label_audit["labels"][name])
        assert payload.normal_candidates[name].dtype == np.dtype(bool)
        np.testing.assert_array_equal(payload.normal_candidates[name], label_audit["normal_candidates"][name])
    assert payload.source_attack_label_present.dtype == np.dtype(bool)
    np.testing.assert_array_equal(payload.source_attack_label_present,
        [row["source_attack_label_present"] for row in label_audit["audit"]["minute_reports"]])


def test_snapshot_is_deeply_immutable_and_exported_report_is_independent(tmp_path):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

    payload = load_verified_candidate_artifacts(*make_package(tmp_path), source_fixture=SOURCE)
    for value in (payload.report, payload.provenance, payload.preprocessing_state):
        assert_deep_json_immutable(value)
    for value in (payload.histories, payload.labels, payload.normal_candidates):
        assert isinstance(value, Mapping)
        key = next(iter(value))
        with pytest.raises(TypeError):
            value[key] = value[key]
    for name, array in snapshot_arrays(payload):
        try:
            assert_bytes_backed_immutable(array)
        except AssertionError as error:
            raise AssertionError(f"mutable payload array: {name}") from error
    original = payload.report_dict()
    exported = payload.report_dict()
    assert json.loads(json.dumps(exported, allow_nan=False)) == original
    assert exported == plain(payload.report)
    exported["status"] = "changed"
    exported["checks"]["source_replay"] = "changed"
    exported["partition_summary"]["train"]["common_valid_count"] = -1
    exported["windows"].append(99)
    assert payload.report_dict() == original


def test_snapshot_storage_objects_expose_no_mutable_instance_dictionary(tmp_path):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

    payload = load_verified_candidate_artifacts(*make_package(tmp_path), source_fixture=SOURCE)
    # Access private buffers only here to reject the direct __dict__ bypass.
    objects = (payload, payload.histories[30], payload.normal_candidates,
               payload.normal_candidates._buffers["P_U"])
    exposed = [type(value).__name__ for value in objects
               if isinstance(getattr(value, "__dict__", None), dict)]
    assert not exposed, f"mutable instance dictionaries exposed by {exposed}"


@pytest.mark.filterwarnings("ignore:Setting the (shape|dtype|strides) on a NumPy array has been deprecated.*:DeprecationWarning")
def test_local_view_metadata_edits_cannot_change_snapshot_arrays(tmp_path):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

    payload = load_verified_candidate_artifacts(*make_package(tmp_path), source_fixture=SOURCE)
    originals = [(name, array.copy(), array.shape, array.dtype, array.strides)
                 for name, array in snapshot_arrays(payload)]
    for name, original, shape, dtype, strides in originals:
        local = dict(snapshot_arrays(payload))[name]
        local.shape = (1, local.size)
        fresh = dict(snapshot_arrays(payload))[name]
        assert (fresh.shape, fresh.dtype, fresh.strides) == (shape, dtype, strides)
        np.testing.assert_array_equal(fresh, original)
        local = dict(snapshot_arrays(payload))[name]
        local.dtype = np.dtype("uint8") if dtype.itemsize > 1 else np.dtype("int8")
        fresh = dict(snapshot_arrays(payload))[name]
        assert (fresh.shape, fresh.dtype, fresh.strides) == (shape, dtype, strides)
        np.testing.assert_array_equal(fresh, original)
        local = dict(snapshot_arrays(payload))[name]
        local.strides = (0,) * local.ndim
        fresh = dict(snapshot_arrays(payload))[name]
        assert (fresh.shape, fresh.dtype, fresh.strides) == (shape, dtype, strides)
        np.testing.assert_array_equal(fresh, original)


def test_snapshot_preserves_actual_artifact_values_within_verification_tolerance(tmp_path):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

    records, inputs = make_package(tmp_path)
    current_path = inputs / "candidate-inputs.json"
    current = read(current_path)
    current["current_values"][0][0] += 5e-13
    current["histories"]["30"]["joined"][30][0] += 4e-13
    current_path.write_text(json.dumps(current, allow_nan=False), encoding="utf-8")
    manifest_path = inputs / "manifest.json"
    manifest = read(manifest_path)
    manifest["artifacts"]["candidate-inputs.json"] = digest(current_path)
    manifest_path.write_text(json.dumps(manifest, allow_nan=False), encoding="utf-8")
    payload = load_verified_candidate_artifacts(records, inputs)
    assert payload.current_values[0, 0] == current["current_values"][0][0]
    assert payload.histories[30].joined[30, 0] == current["histories"]["30"]["joined"][30][0]
    assert payload.provenance["input_manifest"]["sha256"] == digest(manifest_path)["sha256"]


@pytest.mark.parametrize("include_source", [False, True], ids=["without-source", "with-source"])
@pytest.mark.parametrize("api", ["load_verified_candidate_artifacts", "verify_candidate_artifacts"])
def test_each_file_is_opened_once_and_neither_api_fits_or_prepares(tmp_path, monkeypatch, include_source, api):
    from traffic_anomaly import candidate_artifacts, candidate_cli, candidate_inputs

    records, inputs = make_package(tmp_path)
    expected = {path.resolve() for directory in (records, inputs) for path in directory.iterdir()}
    if include_source:
        expected.add(SOURCE.resolve())
    opened = Counter()
    actual_open = Path.open

    def open_once(path, *args, **kwargs):
        opened[path.resolve()] += 1
        return actual_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("verified loading must not fit or call prepare_candidate_inputs")

    monkeypatch.setattr(Path, "open", open_once)
    monkeypatch.setattr(candidate_inputs.CandidatePreprocessor, "fit", forbidden)
    monkeypatch.setattr(candidate_inputs, "prepare_candidate_inputs", forbidden)
    monkeypatch.setattr(candidate_cli, "prepare_candidate_inputs", forbidden)
    if hasattr(candidate_artifacts, "prepare_candidate_inputs"):
        monkeypatch.setattr(candidate_artifacts, "prepare_candidate_inputs", forbidden)
    result = getattr(candidate_artifacts, api)(records, inputs, source_fixture=SOURCE if include_source else None)
    report = result.report_dict() if api.startswith("load_") else result
    assert report["status"] == "VERIFIED"
    assert set(opened) == expected
    assert all(count == 1 for count in opened.values())


def test_loaded_snapshot_survives_mutation_and_relocation_of_original_files(tmp_path):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

    source = tmp_path / "local-source.json"
    source.write_bytes(SOURCE.read_bytes())
    records, inputs = make_package(tmp_path, source=source)
    payload = load_verified_candidate_artifacts(records, inputs, source_fixture=source)
    arrays = [(name, array.copy()) for name, array in snapshot_arrays(payload)]
    report = payload.report_dict()
    provenance = plain(payload.provenance)
    state = plain(payload.preprocessing_state)
    labels = dict(payload.labels)
    (inputs / "candidate-inputs.json").write_text("{}", encoding="utf-8")
    (inputs / "preprocess.json").write_text("{}", encoding="utf-8")
    (records / "label-audit.json").write_text("{}", encoding="utf-8")
    source.write_text("{}", encoding="utf-8")
    records.rename(tmp_path / "moved-records")
    inputs.rename(tmp_path / "moved-inputs")
    source.rename(tmp_path / "moved-source.json")
    assert payload.report_dict() == report
    assert plain(payload.provenance) == provenance
    assert plain(payload.preprocessing_state) == state
    assert dict(payload.labels) == labels
    for (name, current), (original_name, original) in zip(snapshot_arrays(payload), arrays):
        assert name == original_name
        np.testing.assert_array_equal(current, original)


def test_invalid_rows_and_history_nulls_keep_typed_masks_in_snapshot(tmp_path):
    from traffic_anomaly.candidate_artifacts import load_verified_candidate_artifacts

    source = tmp_path / "invalid-row-source.json"
    value = read(SOURCE)
    value["records"][40 * 4]["protocol"] = 200
    source.write_text(json.dumps(value), encoding="utf-8")
    payload = load_verified_candidate_artifacts(*make_package(tmp_path, source=source), source_fixture=source)
    assert not payload.raw_valid[40] and not payload.row_valid[40]
    assert np.isnan(payload.raw_values[40]).all() and np.isnan(payload.current_values[40]).all()
    assert not payload.common_valid[40:71].any() and payload.common_valid[71]
    assert payload.histories[30].invalid_reason[40] == "invalid_input"
    for name, array in snapshot_arrays(payload):
        assert_bytes_backed_immutable(array)


@pytest.mark.parametrize("relative", ["records/manifest.json", "records/minute-fixture.json", "records/label-audit.json",
                                       "inputs/manifest.json", "inputs/preprocess.json", "inputs/candidate-inputs.json"])
def test_loader_preserves_existing_verifier_error_rejection(tmp_path, relative):
    from traffic_anomaly.candidate_artifacts import (
        CandidateArtifactError, load_verified_candidate_artifacts, verify_candidate_artifacts,
    )

    records, inputs = make_package(tmp_path)
    (tmp_path / relative).write_text('{"untrusted":"private-content"}', encoding="utf-8")
    with pytest.raises(CandidateArtifactError) as existing:
        verify_candidate_artifacts(records, inputs)
    with pytest.raises(CandidateArtifactError) as loaded:
        load_verified_candidate_artifacts(records, inputs)
    assert loaded.value.code == existing.value.code
    assert str(loaded.value) == loaded.value.code
    assert "private-content" not in str(loaded.value) and str(tmp_path) not in str(loaded.value)
