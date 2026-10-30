"""Bounded engineering-toy IF run from verified synthetic snapshots only."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import io
import json
import math
from pathlib import Path
import pickle
import platform
import re
import stat
import sys

import joblib
import numpy as np
import sklearn

from .candidate_artifacts import CandidateArtifactError, load_verified_candidate_artifacts
from .candidate_cli import _Parser, _SafeError
from .candidate_iforest import (
    CandidateIFError, MODEL_PROFILE_ID, compute_synthetic_candidate_if,
    replay_saved_candidate_if,
)


MAX_MODEL_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class _CLIError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _BoundedBuffer(io.BytesIO):
    """Refuse a write before BytesIO can allocate beyond the configured cap."""
    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def write(self, value):
        if self.tell() + memoryview(value).nbytes > self.limit:
            raise _CLIError("RESOURCE_LIMIT")
        return super().write(value)

    def truncate(self, size=None):
        if (self.tell() if size is None else size) > self.limit:
            raise _CLIError("RESOURCE_LIMIT")
        return super().truncate(size)


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def _identity(payload):
    return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_count": len(payload)}


def _json_bytes(value):
    with _BoundedBuffer(MAX_JSON_BYTES) as payload:
        with io.TextIOWrapper(payload, encoding="utf-8") as stream:
            json.dump(value, stream, allow_nan=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            return payload.getvalue()


def _ordinary_output_parent(path):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024
            or not stat.S_ISDIR(info.st_mode)):
        raise _CLIError("UNSAFE_OUTPUT")


def _check_output(records, inputs, source, output):
    # Check lexical ancestors before resolution, which would hide symlinks/junctions.
    paths = tuple(path.absolute() for path in (records, inputs, source, output))
    output_info = None
    for index, path in enumerate(paths):
        for parent in reversed(path.parents):
            _ordinary_output_parent(parent)
        try:
            info = path.lstat()
        except FileNotFoundError:
            if index != 3:
                raise CandidateArtifactError("INPUT_UNAVAILABLE")
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise _CLIError("UNSAFE_OUTPUT")
        if index == 3:
            output_info = info
    records, inputs, source = (path.resolve(strict=True) for path in paths[:3])
    output = paths[3].resolve(strict=False)
    for value in (records, inputs, source):
        if output.is_relative_to(value) or value.is_relative_to(output):
            raise _CLIError("UNSAFE_OUTPUT")
    if output_info is not None:
        raise _CLIError("OUTPUT_EXISTS")
    return records, inputs, source, output


def _write_payload(path, payload, *, manifest=False):
    created = False
    try:
        with path.open("xb") as stream:
            created = True
            if stream.write(payload) != len(payload):
                raise OSError("incomplete_output_write")
    except BaseException:
        # Only the failed completion marker created by this call may be removed.
        if manifest and created:
            path.unlink(missing_ok=True)
        raise


def _read_own_payload(path, expected, limit):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 1024 or info.st_size > limit):
        raise _CLIError("OUTPUT_ERROR")
    with path.open("rb") as stream:
        actual = stream.read(limit + 1)
    if actual != expected:
        raise _CLIError("OUTPUT_ERROR")
    return actual


def _versions():
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scikit_learn": sklearn.__version__, "joblib": joblib.__version__}


def _common(snapshot, result, run_id):
    configuration = _plain(result.configuration)
    encoded = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {
        "schema_version": 1, "run_id": run_id, "model_profile_id": MODEL_PROFILE_ID,
        "evidence_kind": "SYNTHETIC_ONLY", "time_basis": "synthetic_source_clock",
        "policy_status": "AUDIT_ONLY", "scope": "ENGINEERING_TOY_ONLY",
        "selected_policy": snapshot.report["selected_policy"],
        "score_direction": "HIGHER_IS_MORE_ANOMALOUS", "value_space": "prepared",
        "feature_names": list(snapshot.feature_names), "qualification_windows": [15, 30],
        "configuration": configuration, "configuration_sha256": hashlib.sha256(encoded).hexdigest(),
        "library_versions": _versions(), "provenance": _plain(snapshot.provenance),
        "preprocessing_state": _plain(snapshot.preprocessing_state),
    }


def _score_document(snapshot, result, common):
    n = len(snapshot.timestamps)
    scores, valid, alarms = np.asarray(result.scores), np.asarray(result.score_valid), np.asarray(result.alarms)
    if (scores.shape != (n,) or valid.shape != (n,) or alarms.shape != (n,)
            or valid.dtype != np.dtype(bool) or alarms.dtype != np.dtype(bool)
            or not np.isfinite(scores[valid]).all() or not np.isnan(scores[~valid]).all()
            or alarms[~valid].any() or not np.array_equal(valid, snapshot.common_valid)
            or not math.isfinite(result.threshold)):
        raise _CLIError("INVALID_MODEL_RESULT")
    return {
        **common, "timestamps": [str(value) for value in snapshot.timestamps],
        "segment_ids": snapshot.segment_ids.tolist(), "partitions": snapshot.partitions.tolist(),
        "current_input_valid": snapshot.row_valid.tolist(), "common_valid": snapshot.common_valid.tolist(),
        "score_valid": valid.tolist(),
        "scores": [float(value) if keep else None for value, keep in zip(scores, valid)],
        "alarms": [bool(value) if keep else None for value, keep in zip(alarms, valid)],
        "history_invalid_reason": {str(window): list(history.invalid_reason)
                                   for window, history in snapshot.histories.items()},
        "threshold": float(result.threshold), "calibration": _plain(result.calibration),
    }


def run_synthetic_candidate_if(records, inputs, source_fixture, run_id, output):
    """Reserve a fresh directory and persist only this invocation's toy model."""
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise _CLIError("INVALID_RUN_ID")
    records, inputs, source, output = map(Path, (records, inputs, source_fixture, output))
    try:
        records, inputs, source, output = _check_output(records, inputs, source, output)
        snapshot = load_verified_candidate_artifacts(records, inputs, source_fixture=source)
        if (snapshot.report["checks"]["source_replay"] != "VERIFIED"
                or snapshot.report["evidence_kind"] != "SYNTHETIC_ONLY"):
            raise _CLIError("SOURCE_NOT_VERIFIED")
        try:
            output.mkdir()
        except FileExistsError as exc:
            raise _CLIError("OUTPUT_EXISTS") from exc
        for parent in output.absolute().parents:
            _ordinary_output_parent(parent)
        _ordinary_output_parent(output)
        result = compute_synthetic_candidate_if(snapshot)
        common = _common(snapshot, result, run_id)
        score_document = _score_document(snapshot, result, common)
        with _BoundedBuffer(MAX_MODEL_BYTES) as buffer:
            joblib.dump(result.model, buffer)
            weights = buffer.getvalue()
        model_document = {
            **common, "model_type": "sklearn.ensemble.IsolationForest", "weights": _identity(weights),
            "fit_indices": list(result.fit_indices), "calibration_indices": list(result.calibration_indices),
        }
        used = 0
        artifacts = {}

        def persist(name, payload, limit, *, manifest=False):
            nonlocal used
            if len(payload) > limit or used + len(payload) > MAX_TOTAL_BYTES:
                raise _CLIError("RESOURCE_LIMIT")
            used += len(payload)
            path = output / name
            _write_payload(path, payload, manifest=manifest)
            if not manifest:
                return _read_own_payload(path, payload, limit)
            return payload

        model_bytes = _json_bytes(model_document)
        artifacts["model-state.json"] = _identity(persist("model-state.json", model_bytes, MAX_JSON_BYTES))
        saved_weights = persist("weights.bin", weights, MAX_MODEL_BYTES)
        artifacts["weights.bin"] = _identity(saved_weights)
        try:
            reloaded_model = joblib.load(io.BytesIO(saved_weights))
        except (ValueError, TypeError, OSError, RuntimeError, EOFError, pickle.UnpicklingError,
                AttributeError, ImportError, KeyError, IndexError) as exc:
            raise _CLIError("RELOAD_FAILED") from exc
        replay_saved_candidate_if(snapshot, result, reloaded_model)
        score_bytes = persist("scores.json", _json_bytes(score_document), MAX_JSON_BYTES)
        artifacts["scores.json"] = _identity(score_bytes)
        evaluation_document = {
            **common, "scores": _identity(score_bytes), "threshold": float(result.threshold),
            "calibration": _plain(result.calibration), "evaluation": _plain(result.evaluation),
        }
        artifacts["evaluation.json"] = _identity(persist("evaluation.json", _json_bytes(evaluation_document), MAX_JSON_BYTES))
        manifest = {**common, "status": "COMPLETE", "artifacts": artifacts}
        persist("manifest.json", _json_bytes(manifest), MAX_JSON_BYTES, manifest=True)
    except (_CLIError, CandidateArtifactError, CandidateIFError):
        raise
    except (OSError, ValueError, TypeError, OverflowError, RuntimeError) as exc:
        raise _CLIError("OUTPUT_ERROR") from exc
    return {"run_id": run_id, "status": "COMPLETE", "evidence_kind": "SYNTHETIC_ONLY"}


def main(argv=None):
    parser = _Parser(description="Engineering-toy-only 13D IF on verified synthetic candidate inputs")
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--source-fixture", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        result = run_synthetic_candidate_if(args.records, args.inputs, args.source_fixture, args.run_id, args.output)
    except _SafeError:
        print(json.dumps({"error": "INVALID_ARGUMENTS"}), file=sys.stderr)
        return 2
    except (_CLIError, CandidateArtifactError, CandidateIFError) as exc:
        print(json.dumps({"error": exc.code}), file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
