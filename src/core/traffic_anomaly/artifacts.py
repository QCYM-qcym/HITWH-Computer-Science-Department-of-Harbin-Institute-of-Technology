"""Atomic run bundles and checked model loading for CLI and API consumers."""
from pathlib import Path
import json
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from . import contracts
from .data.audit import file_sha256

def write_json(path, value):
    if hasattr(value, "model_dump"): value = value.model_dump(mode="json")
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")

def safe_path(root, relative):
    path = Path(root) / relative
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("artifact path escapes its root")
    if path.is_symlink(): raise ValueError("artifact symlinks are not supported")
    return path

TIME = pa.timestamp("ns", tz="UTC")
SCORES_SCHEMA = pa.schema([("timestamp", TIME), ("score", pa.float64()), ("threshold", pa.float64()),
    ("alarm", pa.bool_()), ("valid", pa.bool_()), ("invalid_reason", pa.string()), ("flow_count", pa.float64())])
CHANNEL_SCHEMA = pa.schema([("timestamp", TIME), *[(name, pa.list_(pa.float32())) for name in
    ("current", "history_residual", "reconstruction_error_current", "reconstruction_error_history")]])
LABEL_SCHEMA = pa.schema([("timestamp", TIME), *[(k, pa.int64()) for k in contracts.LABEL_NAMES]])

def write_table(path, rows, schema):
    fields = {k: [row[k] for row in rows] for k in schema.names}
    fields["timestamp"] = [np.datetime64(s[:-1], "ns").astype(np.int64).item() for s in fields["timestamp"]]
    pq.write_table(pa.Table.from_pydict(fields, schema=schema), path)

def read_table(path, schema, model):
    table = pq.read_table(path)
    if table.schema != schema: raise ValueError("incompatible parquet schema")
    ns = table.column("timestamp").cast(pa.int64()).to_pylist()
    if any(t is None for t in ns) or any(a >= b for a, b in zip(ns, ns[1:])):
        raise ValueError("invalid or unordered artifact time axis")
    if any(t % 60_000_000_000 for t in ns):
        raise ValueError("artifact timestamps must identify whole minutes")
    # UTC is already part of the Arrow type. Avoid a dependency on the host's
    # IANA timezone database when converting an absolute ns epoch to JSON.
    rows = table.drop(["timestamp"]).to_pylist()
    for row, t in zip(rows, ns):
        row["timestamp"] = np.datetime_as_string(np.datetime64(t, "ns").astype("datetime64[s]"), unit="s") + "Z"
        model.model_validate(row)
    return rows

def verify_run(directory):
    """Validate integrity and cross-file semantics before consumers see success."""
    directory = Path(directory)
    manifest = contracts.Manifest.model_validate_json((directory / "manifest.json").read_text(encoding="utf-8"))
    by_path = {f.path: f for f in manifest.files}
    for entry in manifest.files:
        path = safe_path(directory, entry.path)
        if not path.is_file() or file_sha256(path) != entry.sha256:
            raise ValueError("artifact digest mismatch or missing file")
    summary = contracts.RunSummary.model_validate_json((directory / "summary.json").read_text(encoding="utf-8"))
    config = contracts.RunConfig.model_validate_json((directory / "config.json").read_text(encoding="utf-8"))
    meta = contracts.ModelMetadata.model_validate_json((directory / "model/metadata.json").read_text(encoding="utf-8"))
    state = contracts.PreprocessState.model_validate_json((directory / "model/preprocess.json").read_text(encoding="utf-8"))
    evaluation = contracts.Evaluation.model_validate_json((directory / "metrics.json").read_text(encoding="utf-8"))
    if summary.run_id != manifest.run_id or evaluation.run_id != manifest.run_id or summary.config != config or manifest.config != config:
        raise ValueError("run/config cross-file mismatch")
    if summary.evidence_kind != manifest.evidence_kind or evaluation.evidence_kind != manifest.evidence_kind:
        raise ValueError("evidence kind mismatch")
    if meta.payload.path not in by_path or by_path[meta.payload.path] != meta.payload:
        raise ValueError("model payload digest not bound by manifest")
    if "model/detector.json" not in by_path:
        raise ValueError("missing detector configuration")
    contracts.validate_model_compatibility(meta, summary.feature_names, state, config)
    detector_state = json.loads((directory / "model/detector.json").read_text(encoding="utf-8"))
    expected_kind = "iforest" if config.method == "iforest" else "ae"
    if (detector_state.get("kind") != expected_kind or detector_state.get("seed") != config.seed
            or contracts.ModelConfig.model_validate(detector_state.get("config")) != config.model
            or (expected_kind == "ae" and detector_state.get("input_width") != meta.input_width)):
        raise ValueError("detector configuration differs from declared run")
    scores = read_table(directory / "scores.parquet", SCORES_SCHEMA, contracts.SeriesPoint)
    channels = read_table(directory / "channels.parquet", CHANNEL_SCHEMA, contracts.ChannelRow)
    if len(scores) != summary.row_count or sum(row["valid"] for row in scores) != summary.valid_count or [r["timestamp"] for r in scores] != [r["timestamp"] for r in channels]:
        raise ValueError("score/channel axes or summary count mismatch")
    if any(row["valid"] and row["threshold"] != meta.threshold for row in scores):
        raise ValueError("saved score threshold differs from model threshold")
    if summary.labels_available != ("labels.parquet" in by_path):
        raise ValueError("label availability mismatch")
    labels = None
    if summary.labels_available:
        label_rows = read_table(directory / "labels.parquet", LABEL_SCHEMA, contracts.LabelRow)
        labels = contracts.LabelBatch(np.array([row["timestamp"][:-1] for row in label_rows], dtype="datetime64[ns]"),
            {k: np.array([row[k] for row in label_rows], dtype=np.int64) for k in contracts.LABEL_NAMES})
    from .evaluation.metrics import evaluate
    computed = evaluate(manifest.run_id, manifest.evidence_kind,
        np.array([row["timestamp"][:-1] for row in scores], dtype="datetime64[ns]"),
        np.array([row["valid"] for row in scores], dtype=bool),
        np.array([row["alarm"] is True for row in scores], dtype=bool), labels)
    for field in ("available", "metrics", "normal_coverage", "attack_coverage", "excluded_attack_minutes", "background_only_minutes", "intervals"):
        if getattr(computed, field) != getattr(evaluation, field):
            raise ValueError("saved evaluation differs from scores and labels")
    return manifest, summary

def load_model(directory, feature_names, config):
    """Only public model loading boundary: integrity -> compatibility -> runtime."""
    directory = Path(directory)
    manifest, summary = verify_run(directory)
    meta = contracts.ModelMetadata.model_validate_json((directory / "model/metadata.json").read_text(encoding="utf-8"))
    state = contracts.PreprocessState.model_validate_json((directory / "model/preprocess.json").read_text(encoding="utf-8"))
    contracts.validate_model_compatibility(meta, tuple(feature_names), state, config)
    if config != manifest.config:
        raise ValueError("scoring configuration must equal saved configuration")
    from .detectors.registry import detector_type
    from .features.preprocess import Preprocessor
    detector = detector_type(meta.method).load(directory / "model")
    if detector.input_width != meta.input_width:
        raise ValueError("payload width mismatch")
    return detector, Preprocessor.load(directory / "model/preprocess.json"), meta
