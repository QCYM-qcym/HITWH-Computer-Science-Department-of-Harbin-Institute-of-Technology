"""Bounded synthetic G13U input development; no CSV, model or score adapter."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

from .candidate_inputs import (
    CandidateMinuteBatch, CandidatePreprocessor, G13U_FEATURE_NAMES,
    MAX_MINUTES, PARTITIONS, PROFILE_ID, prepare_candidate_inputs,
)


MAX_FIXTURE_BYTES = 1024 * 1024
EVIDENCE_KIND = "SYNTHETIC_ONLY"
TIME_BASIS = "synthetic_source_clock"
_TOP_FIELDS = {"schema_version", "evidence_kind", "time_basis", "feature_names",
               "minutes", "normal_candidates", "epsilon"}
_ROW_FIELDS = {"timestamp", "features", "valid", "segment_id", "partition"}
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::00)?\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


class _SafeError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _SafeError("INVALID_ARGUMENTS")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonstandard_json_number")


def _number(value, *, positive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def _read_fixture(path):
    try:
        if path.suffix.lower() != ".json":
            raise _SafeError("INVALID_FIXTURE")
        if not path.is_file():
            raise _SafeError("INPUT_UNAVAILABLE")
        if path.stat().st_size > MAX_FIXTURE_BYTES:
            raise _SafeError("INVALID_FIXTURE")
        with path.open("rb") as stream:
            payload = stream.read(MAX_FIXTURE_BYTES + 1)
    except OSError as exc:
        raise _SafeError("INPUT_UNAVAILABLE") from exc
    if len(payload) > MAX_FIXTURE_BYTES:
        raise _SafeError("INVALID_FIXTURE")
    try:
        fixture = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        if (not isinstance(fixture, dict) or set(fixture) != _TOP_FIELDS
                or type(fixture["schema_version"]) is not int or fixture["schema_version"] != 1
                or fixture["evidence_kind"] != EVIDENCE_KIND
                or fixture["time_basis"] != TIME_BASIS
                or fixture["feature_names"] != list(G13U_FEATURE_NAMES)
                or not _number(fixture["epsilon"], positive=True)):
            raise ValueError("invalid_fixture_contract")
        rows, normal = fixture["minutes"], fixture["normal_candidates"]
        if (not isinstance(rows, list) or not 1 <= len(rows) <= MAX_MINUTES
                or not isinstance(normal, list) or len(normal) != len(rows)
                or any(type(value) is not bool for value in normal)):
            raise ValueError("invalid_fixture_rows")
        for row in rows:
            if (not isinstance(row, dict) or set(row) != _ROW_FIELDS
                    or type(row["valid"]) is not bool
                    or not isinstance(row["timestamp"], str)
                    or not _TIMESTAMP.fullmatch(row["timestamp"])
                    or not isinstance(row["segment_id"], str)
                    or not _SEGMENT.fullmatch(row["segment_id"])
                    or row["partition"] not in PARTITIONS
                    or not isinstance(row["features"], list) or len(row["features"]) != 13
                    or any(not _number(value) for value in row["features"])):
                raise ValueError("invalid_fixture_minute")
            datetime.fromisoformat(row["timestamp"])
        batch = CandidateMinuteBatch(
            timestamps=np.array([row["timestamp"] for row in rows], dtype="datetime64[us]"),
            values=np.array([row["features"] for row in rows], dtype=np.float64),
            row_valid=np.array([row["valid"] for row in rows], dtype=bool),
            segment_ids=np.array([row["segment_id"] for row in rows]),
            partitions=np.array([row["partition"] for row in rows]),
        )
        normal_mask = np.array(normal, dtype=bool)
        prepared = prepare_candidate_inputs(batch, normal_mask, epsilon=fixture["epsilon"])
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise _SafeError("INVALID_FIXTURE") from exc
    return payload, fixture, batch, prepared


def _json_value(value):
    """Preserve the full axis and explicitly export unavailable numerics as null."""
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist())
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    return value


def _candidate_document(fixture, batch, result):
    summary = {}
    for partition in PARTITIONS:
        selected = batch.partitions == partition
        summary[partition] = {
            "minute_count": int(selected.sum()),
            "input_valid_count": int((selected & result.prepared.row_valid).sum()),
            "common_valid_count": int((selected & result.common_valid).sum()),
            "training_normal_count": int((selected & result.training_normal).sum()),
            "calibration_normal_count": int((selected & result.calibration_normal).sum()),
            "test_normal_count": int((selected & result.test_normal).sum()),
            "window_valid_counts": {str(window): int((selected & history.valid).sum())
                                    for window, history in result.histories.items()},
        }
    return _json_value({
        "schema_version": 1, "profile_id": PROFILE_ID,
        "evidence_kind": EVIDENCE_KIND, "time_basis": TIME_BASIS,
        "value_space": result.prepared.value_space,
        "feature_names": list(G13U_FEATURE_NAMES),
        "dimensions": {"current": 13, "joined": 26},
        "windows": [15, 30], "epsilon": fixture["epsilon"],
        "timestamps": [str(stamp) for stamp in batch.timestamps],
        "segment_ids": batch.segment_ids, "partitions": batch.partitions,
        "row_valid": result.prepared.row_valid,
        "normal_candidates": fixture["normal_candidates"],
        "current_values": result.prepared.values,
        "histories": {str(window): {"current": history.current,
                                    "residual": history.residual,
                                    "joined": history.joined,
                                    "valid": history.valid,
                                    "invalid_reason": history.invalid_reason}
                      for window, history in result.histories.items()},
        "common_valid": result.common_valid, "training_normal": result.training_normal,
        "calibration_normal": result.calibration_normal, "test_normal": result.test_normal,
        "partition_summary": summary,
    })


def _write_json(path, value):
    created = False
    try:
        with path.open("x", encoding="utf-8") as stream:
            created = True
            json.dump(value, stream, allow_nan=False, sort_keys=True, indent=2)
            stream.write("\n")
    except (OSError, ValueError, TypeError, OverflowError):
        # Remove only a file this call created; a failed final write is not complete.
        if created:
            path.unlink(missing_ok=True)
        raise


def _digest(payload):
    return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}


def _run(fixture_path, output):
    payload, fixture, raw, result = _read_fixture(fixture_path)
    document = _candidate_document(fixture, raw, result)
    configuration = {
        "profile_id": PROFILE_ID, "feature_names": list(G13U_FEATURE_NAMES),
        "windows": [15, 30], "epsilon": fixture["epsilon"],
        "evidence_kind": EVIDENCE_KIND, "time_basis": TIME_BASIS,
        "transform": "log1p_standard_ddof0", "fit_partition": "train",
        "fit_eligibility": "current_and_previous_30_normal",
    }
    configuration_bytes = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise _SafeError("OUTPUT_EXISTS") from exc
    except OSError as exc:
        raise _SafeError("OUTPUT_ERROR") from exc
    try:
        state_path = output / "preprocess.json"
        result.preprocessor.save(state_path)
        reloaded = CandidatePreprocessor.load(state_path).transform(raw)
        if (not np.array_equal(reloaded.values, result.prepared.values, equal_nan=True)
                or not np.array_equal(reloaded.row_valid, result.prepared.row_valid)):
            raise ValueError("reload_mismatch")
        _write_json(output / "candidate-inputs.json", document)
        artifacts = {name: _digest((output / name).read_bytes())
                     for name in ("candidate-inputs.json", "preprocess.json")}
        # The completion marker is created only after both artifacts and reload checks.
        _write_json(output / "manifest.json", {
            "schema_version": 1, "profile_id": PROFILE_ID,
            "status": "COMPLETE", "evidence_kind": EVIDENCE_KIND,
            "time_basis": TIME_BASIS, "fixture": _digest(payload),
            "configuration": configuration,
            "configuration_sha256": hashlib.sha256(configuration_bytes).hexdigest(),
            "artifacts": artifacts,
        })
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        raise _SafeError("OUTPUT_ERROR") from exc


def main(argv=None):
    parser = _Parser(description="Synthetic-only G13U candidate input computation")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        _run(args.fixture, args.output)
    except _SafeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"evidence_kind": EVIDENCE_KIND, "status": "COMPLETE"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
