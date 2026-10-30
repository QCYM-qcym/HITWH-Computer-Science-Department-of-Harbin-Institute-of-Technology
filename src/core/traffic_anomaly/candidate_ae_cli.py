"""Bounded synthetic AE execution and strict JSON-only weight persistence."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import re
import stat
import sys

import numpy as np

from .candidate_artifacts import CandidateArtifactError, load_verified_candidate_artifacts
from .candidate_cli import _Parser, _SafeError


MODEL_PROFILE_ID = "c17-i1-g13u-ae-synthetic-v1"
MAX_WEIGHTS_BYTES = 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]*\Z")


class _CLIError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _BoundedBuffer(io.BytesIO):
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


def compute_synthetic_candidate_ae(snapshot, *, method, history_window=None):
    from .candidate_autoencoder import compute_synthetic_candidate_ae as compute
    return compute(snapshot, method=method, history_window=history_window)


def replay_candidate_ae(snapshot, result, network):
    from .candidate_autoencoder import replay_candidate_ae as replay
    return replay(snapshot, result, network)


def encode_candidate_ae_weights(network, binding):
    from .candidate_ae_weights import encode_candidate_ae_weights as encode
    return encode(network, binding)


def parse_candidate_ae_weights(payload, expected_binding):
    from .candidate_ae_weights import parse_candidate_ae_weights as parse
    return parse(payload, expected_binding)


def rebuild_candidate_ae_from_json(document, expected_binding):
    from .candidate_ae_weights import rebuild_candidate_ae_from_json as rebuild
    return rebuild(document, expected_binding)


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


def _json_bytes(value, limit=None):
    with _BoundedBuffer(MAX_JSON_BYTES if limit is None else limit) as payload:
        with io.TextIOWrapper(payload, encoding="utf-8") as stream:
            json.dump(value, stream, allow_nan=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            return payload.getvalue()


def _ordinary_parent(path):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024
            or not stat.S_ISDIR(info.st_mode)):
        raise _CLIError("UNSAFE_OUTPUT")


def _check_output(records, inputs, source, output):
    paths = tuple(path.absolute() for path in (records, inputs, source, output))
    output_info = None
    # Lexical checks precede resolve, which would otherwise hide links/junctions.
    for index, path in enumerate(paths):
        for parent in reversed(path.parents):
            _ordinary_parent(parent)
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


def _check_owned_parent(path):
    for parent in reversed(path.absolute().parents):
        _ordinary_parent(parent)


def _write_payload(path, payload, *, manifest=False):
    _check_owned_parent(path)
    created = False
    try:
        with path.open("xb") as stream:
            created = True
            if stream.write(payload) != len(payload):
                raise OSError("incomplete_output_write")
    except BaseException:
        if manifest and created:
            path.unlink(missing_ok=True)
        raise


def _read_own_payload(path, expected, limit):
    _check_owned_parent(path)
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
    import torch
    return {"python": platform.python_version(), "numpy": np.__version__, "torch": str(torch.__version__)}


def _common(snapshot, result, run_id):
    configuration = _plain(result.configuration)
    encoded = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {
        "schema_version": 1, "run_id": run_id, "model_profile_id": MODEL_PROFILE_ID,
        "evidence_kind": "SYNTHETIC_ONLY", "time_basis": "synthetic_source_clock",
        "policy_status": "AUDIT_ONLY", "scope": "ENGINEERING_TOY_ONLY",
        "selected_policy": snapshot.report["selected_policy"], "score_direction": "HIGHER_IS_MORE_ANOMALOUS",
        "value_space": "prepared", "feature_names": list(snapshot.feature_names), "qualification_windows": [15, 30],
        "configuration": configuration, "configuration_sha256": hashlib.sha256(encoded).hexdigest(),
        "library_versions": _versions(), "provenance": _plain(snapshot.provenance),
        "preprocessing_state": _plain(snapshot.preprocessing_state), "runtime": _plain(result.runtime),
    }


def _score_document(snapshot, result, common, method, history_window):
    n = len(snapshot.timestamps)
    scores, valid, alarms = np.asarray(result.scores), np.asarray(result.score_valid), np.asarray(result.alarms)
    current = np.asarray(result.current_reconstruction_mse)
    history = np.asarray(result.history_deviation_reconstruction_mse)
    arrays = (scores, valid, alarms, current, history)
    if (any(value.shape != (n,) for value in arrays) or valid.dtype != np.dtype(bool)
            or alarms.dtype != np.dtype(bool) or not np.array_equal(valid, snapshot.common_valid)
            or any(value.dtype != np.dtype("float64") for value in (scores, current, history))
            or not np.isfinite(scores[valid]).all() or not np.isnan(scores[~valid]).all()
            or not np.isfinite(current[valid]).all() or not np.isnan(current[~valid]).all()
            or (current[valid] < 0).any() or alarms[~valid].any() or not math.isfinite(result.threshold)):
        raise _CLIError("INVALID_MODEL_RESULT")
    if method == "current_ae":
        if not np.isnan(history).all():
            raise _CLIError("INVALID_MODEL_RESULT")
        expected_score = current
    else:
        if (not np.isfinite(history[valid]).all() or not np.isnan(history[~valid]).all()
                or (history[valid] < 0).any()):
            raise _CLIError("INVALID_MODEL_RESULT")
        with np.errstate(over="ignore", invalid="ignore"):
            expected_score = .5 * current + .5 * history
    configuration = result.configuration
    width = 13 if method == "current_ae" else 26
    losses = result.training_losses
    if (not np.array_equal(scores[valid], expected_score[valid])
            or configuration["method"] != method or configuration["history_window"] != history_window
            or configuration["input_width"] != width or configuration["architecture"] != [width, 8, 3, 8, width]
            or configuration["parameter_count"] != (288 if width == 13 else 509)
            or len(losses) != 5 or any(not math.isfinite(value) or value < 0 for value in losses)):
        raise _CLIError("INVALID_MODEL_RESULT")
    return {
        **common, "timestamps": [str(value) for value in snapshot.timestamps],
        "segment_ids": snapshot.segment_ids.tolist(), "partitions": snapshot.partitions.tolist(),
        "current_input_valid": snapshot.row_valid.tolist(), "common_valid": snapshot.common_valid.tolist(),
        "score_valid": valid.tolist(), "scores": [float(value) if keep else None for value, keep in zip(scores, valid)],
        "alarms": [bool(value) if keep else None for value, keep in zip(alarms, valid)],
        "current_reconstruction_mse": [float(value) if keep else None for value, keep in zip(current, valid)],
        "history_deviation_reconstruction_mse": [float(value) if keep and method == "history_ae" else None for value, keep in zip(history, valid)],
        "history_deviation_reconstruction_mse_status": "NOT_APPLICABLE" if method == "current_ae" else "APPLICABLE",
        "history_invalid_reason": {str(window): list(value.invalid_reason) for window, value in snapshot.histories.items()},
        "threshold": float(result.threshold), "calibration": _plain(result.calibration),
    }


def run_synthetic_candidate_ae(records, inputs, source_fixture, run_id, output, *, method, history_window=None):
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise _CLIError("INVALID_RUN_ID")
    if (method not in ("current_ae", "history_ae")
            or method == "current_ae" and history_window is not None
            or method == "history_ae" and (type(history_window) is not int or history_window not in (15, 30))):
        raise _CLIError("INVALID_METHOD_WINDOW")
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
        _ordinary_parent(output)
        result = compute_synthetic_candidate_ae(snapshot, method=method, history_window=history_window)
        common = _common(snapshot, result, run_id)
        scores = _score_document(snapshot, result, common, method, history_window)
        weights_document = encode_candidate_ae_weights(result.model, common)
        weights_bytes = _json_bytes(weights_document, MAX_WEIGHTS_BYTES)
        used, artifacts = 0, {}

        def persist(name, payload, limit, *, manifest=False):
            nonlocal used
            if len(payload) > limit or used + len(payload) > MAX_TOTAL_BYTES:
                raise _CLIError("RESOURCE_LIMIT")
            used += len(payload)
            path = output / name
            _write_payload(path, payload, manifest=manifest)
            return payload if manifest else _read_own_payload(path, payload, limit)

        saved_weights = persist("weights.json", weights_bytes, MAX_WEIGHTS_BYTES)
        artifacts["weights.json"] = _identity(saved_weights)
        parsed = parse_candidate_ae_weights(saved_weights, common)
        network = rebuild_candidate_ae_from_json(parsed, common)
        replay_candidate_ae(snapshot, result, network)
        model_state = {**common, "weights": _identity(saved_weights), "fit_indices": list(result.fit_indices),
                       "calibration_indices": list(result.calibration_indices), "training_losses": _plain(result.training_losses)}
        artifacts["model-state.json"] = _identity(persist("model-state.json", _json_bytes(model_state), MAX_JSON_BYTES))
        score_bytes = persist("scores.json", _json_bytes(scores), MAX_JSON_BYTES)
        artifacts["scores.json"] = _identity(score_bytes)
        evaluation = {**common, "scores": _identity(score_bytes), "threshold": float(result.threshold),
                      "calibration": _plain(result.calibration), "evaluation": _plain(result.evaluation)}
        artifacts["evaluation.json"] = _identity(persist("evaluation.json", _json_bytes(evaluation), MAX_JSON_BYTES))
        manifest = {**common, "status": "COMPLETE", "artifacts": artifacts,
                    "fit_indices": list(result.fit_indices), "calibration_indices": list(result.calibration_indices),
                    "training_losses": _plain(result.training_losses)}
        persist("manifest.json", _json_bytes(manifest), MAX_JSON_BYTES, manifest=True)
    except (_CLIError, CandidateArtifactError):
        raise
    except ImportError as exc:
        raise _CLIError("DEPENDENCY_UNAVAILABLE") from exc
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RuntimeError) as exc:
        code = getattr(exc, "code", None)
        if isinstance(code, str) and _ERROR_CODE.fullmatch(code):
            raise _CLIError(code) from exc
        raise _CLIError("OUTPUT_ERROR") from exc
    return {"run_id": run_id, "status": "COMPLETE", "evidence_kind": "SYNTHETIC_ONLY"}


def main(argv=None):
    parser = _Parser(description="Engineering-toy-only current/history AE with strict JSON weights")
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--source-fixture", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--method", choices=("current_ae", "history_ae"), required=True)
    parser.add_argument("--history-window", type=int, choices=(15, 30))
    try:
        args = parser.parse_args(argv)
        result = run_synthetic_candidate_ae(args.records, args.inputs, args.source_fixture, args.run_id, args.output,
                                            method=args.method, history_window=args.history_window)
    except _SafeError:
        print(json.dumps({"error": "INVALID_ARGUMENTS"}), file=sys.stderr)
        return 2
    except (_CLIError, CandidateArtifactError) as exc:
        print(json.dumps({"error": exc.code}), file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
