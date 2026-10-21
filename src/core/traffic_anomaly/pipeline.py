"""Single shared execution path. This release permits synthetic training only.

Real source audit is independently available; a failed/unfinished Data Gate
cannot be bypassed by a configuration flag or a caller-supplied AuditReport.
"""
from pathlib import Path
import json
import shutil
import subprocess
import time
import tracemalloc
from uuid import uuid4
from pydantic import TypeAdapter
import numpy as np
from .contracts import (DatasetSchema, SplitBoundaries, RunResult, RunSummary, Manifest,
                        ArtifactFile, ModelMetadata, MinuteBatch, LabelRow, LABEL_NAMES, Identifier)
from .data.reader import load_minutes, load_labels
from .data.splits import split_minutes
from .data.audit import audit_dataset, file_sha256
from .features.preprocess import Preprocessor
from .features.history import build_history
from .features.eligibility import eligible_normals
from .detectors.registry import create_detector
from .evaluation.calibration import calibrate
from .evaluation.metrics import evaluate
from .evaluation.episodes import utc_minute
from .artifacts import (write_json, write_table, verify_run, load_model, safe_path,
                        SCORES_SCHEMA, CHANNEL_SCHEMA, LABEL_SCHEMA)

def registered_input(config, workspace):
    workspace = Path(workspace)
    registry = json.loads((workspace / "registry.json").read_text(encoding="utf-8"))
    entry = registry["datasets"][config.dataset_id]
    schema = DatasetSchema.model_validate(entry["schema"])
    if schema.dataset_id != config.dataset_id: raise ValueError("registered dataset identity mismatch")
    if entry["evidence_kind"] != "SYNTHETIC_ONLY":
        raise ValueError("Data Gate not passed: real execution disabled until provider clock and normal candidates are resolved")
    if not schema.dataset_id.startswith("synthetic"):
        raise ValueError("synthetic identity must be explicit")
    boundaries = SplitBoundaries.model_validate(entry["splits"][config.split_id])
    if boundaries.split_id != config.split_id: raise ValueError("split identity mismatch")
    source = safe_path(workspace, entry["source"])
    audit = audit_dataset(source, schema)
    if not audit.passed: raise ValueError("input audit failed: " + "; ".join(audit.findings))
    return load_minutes(source, schema), load_labels(source, schema), schema, boundaries, entry["evidence_kind"], audit

def transformed_history(part, preprocess, config):
    z = np.full_like(part.features, np.nan)
    z[part.row_valid] = preprocess.transform(part.features[part.row_valid])
    b = MinuteBatch(part.timestamps, z, part.feature_names, part.row_valid, part.segment_ids)
    return build_history(b, config.window_minutes, config.preprocess.epsilon)

def model_input(history, method):
    return np.hstack([history.current, history.residual]) if method == "history_ae" else history.current

def execute_run(config, workspace, *, run_id=None) -> RunResult:
    return _execute(config, Path(workspace), None, run_id)

def score_run(config, workspace, model, *, run_id=None) -> RunResult:
    model = Path(model)
    if model.name != "model": raise ValueError("model must identify a complete run model/ directory")
    return _execute(config, Path(workspace), model.parent, run_id)

def _execute(config, workspace, saved, run_id):
    # Execution identity is assigned before any fit or write, never rewritten
    # into completed artifacts. RunConfig remains the research configuration.
    run_id = TypeAdapter(Identifier).validate_python(run_id if run_id is not None else 'w1-' + uuid4().hex)
    if (workspace / 'runs' / run_id).exists() or (workspace / 'runs' / ('.' + run_id + '.tmp')).exists():
        raise FileExistsError('run identity already exists')
    started = time.perf_counter()
    batch, labels, schema, boundaries, evidence, audit = registered_input(config, workspace)
    parts = split_minutes(batch, boundaries)
    if any(not len(part.timestamps) for part in parts.values()): raise ValueError("every time split must be nonempty")
    # Compute training eligibility on the original complete axis before filtering.
    raw_history = build_history(parts["train"], config.window_minutes, config.preprocess.epsilon)
    train_mask = eligible_normals(parts["train"].timestamps, raw_history.valid, labels, config.window_minutes)
    if not train_mask.any(): raise ValueError("no eligible normal training windows")
    if saved is None:
        preprocess = Preprocessor(batch.feature_names).fit(parts["train"].features[train_mask])
        detector = create_detector(config)
    else:
        detector, preprocess, meta = load_model(saved, batch.feature_names, config)
    histories = {key: transformed_history(part, preprocess, config) for key, part in parts.items()}
    masks = {key: eligible_normals(part.timestamps, histories[key].valid, labels, config.window_minutes)
             for key, part in parts.items() if key != "test"}
    if not masks["train"].any() or not masks["calibration"].any(): raise ValueError("empty normal training/calibration windows")
    inputs = {key: model_input(history, config.method) for key, history in histories.items()}
    if saved is None:
        validation = inputs["validation"][masks["validation"]]
        if config.method != "iforest" and not len(validation): raise ValueError("no normal validation windows")
        detector.fit(inputs["train"][masks["train"]], validation if len(validation) else None)
        threshold = calibrate(detector.score(inputs["calibration"][masks["calibration"]]))
    else:
        threshold = meta.threshold
    test, history = parts["test"], histories["test"]
    valid = history.valid.copy()
    scores = np.full(len(valid), np.nan)
    scores[valid] = detector.score(inputs["test"][valid])
    nonfinite = valid & ~np.isfinite(scores)
    valid[nonfinite] = False
    alarms = valid & (scores > threshold)
    rows, channels = [], []
    errors = None
    if config.method != "iforest":
        errors = np.full_like(inputs["test"], np.nan)
        errors[valid] = detector.reconstruction_errors(inputs["test"][valid])
    for i, stamp in enumerate(test.timestamps):
        reason = "nonfinite_score" if nonfinite[i] else history.invalid_reason[i]
        rows.append({"timestamp": utc_minute(stamp), "score": float(scores[i]) if valid[i] else None,
            "threshold": threshold if valid[i] else None, "alarm": bool(alarms[i]) if valid[i] else None,
            "valid": bool(valid[i]), "invalid_reason": reason, "flow_count": None})
        channels.append({"timestamp": utc_minute(stamp),
            "current": test.features[i].tolist() if test.row_valid[i] else None,
            "history_residual": history.residual[i].tolist() if history.valid[i] else None,
            "reconstruction_error_current": errors[i,:134].tolist() if errors is not None and valid[i] else None,
            "reconstruction_error_history": errors[i,134:].tolist() if errors is not None and valid[i] and config.method == "history_ae" else None})
    evaluation = evaluate(run_id, evidence, test.timestamps, valid, alarms, labels)
    run_root = workspace / "runs"; run_root.mkdir(parents=True, exist_ok=True)
    staging, final = run_root / ("." + run_id + ".tmp"), run_root / run_id
    staging.mkdir()
    try:
        if saved is None:
            detector.save(staging / "model")
            preprocess.save(staging / "model/preprocess.json")
            meta = ModelMetadata(method=config.method, input_width=268 if config.method == "history_ae" else 134,
                feature_names=batch.feature_names, preprocess_version=config.preprocess.version, threshold=threshold,
                parameter_count=detector.parameter_count,
                payload=ArtifactFile(path="model/weights.bin", sha256=file_sha256(staging / "model/weights.bin")))
            write_json(staging / "model/metadata.json", meta)
        else:
            shutil.copytree(saved / "model", staging / "model")
        write_table(staging / "scores.parquet", rows, SCORES_SCHEMA)
        write_table(staging / "channels.parquet", channels, CHANNEL_SCHEMA)
        label_rows = [{"timestamp": utc_minute(stamp), **{k: int(labels.labels[k][i]) for k in LABEL_NAMES}}
                      for i, stamp in enumerate(labels.timestamps)]
        write_table(staging / "labels.parquet", label_rows, LABEL_SCHEMA)
        write_json(staging / "metrics.json", evaluation)
        write_json(staging / "config.json", config)
        # Python allocation peak is supplemental, not process RSS or a benchmark.
        summary = RunSummary(run_id=run_id, evidence_kind=evidence, config=config, feature_names=batch.feature_names,
            row_count=len(test.timestamps), valid_count=int(valid.sum()), elapsed_seconds=time.perf_counter()-started,
            peak_memory_bytes=tracemalloc.get_traced_memory()[1] if tracemalloc.is_tracing() else 0,
            labels_available=True)
        write_json(staging / "summary.json", summary)
        write_json(staging / "audit.json", audit)
        write_json(staging / "splits.json", boundaries)
        write_json(staging / "runtime.json", {"device": "cpu", "memory_measurement": "NOT_RUN"})
        repo = Path(__file__).resolve().parents[3]
        code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        files = [ArtifactFile(path=p.relative_to(staging).as_posix(), sha256=file_sha256(p))
                 for p in sorted(staging.rglob("*")) if p.is_file()]
        manifest = Manifest(run_id=run_id, evidence_kind=evidence, config=config, code_commit=code_commit,
            dataset_version=schema.dataset_version, feature_version=config.preprocess.version, split_version=boundaries.split_id,
            seed=config.seed, dependency_lock_sha256=file_sha256(Path(__file__).resolve().parents[1] / "requirements-cpu-lock.txt"), files=files)
        write_json(staging / "manifest.json", manifest)
        verify_run(staging)
        staging.rename(final)
    except Exception:
        # Preserve incomplete outputs for diagnosis, never publish them as a success.
        raise
    return RunResult(run_id=run_id, manifest_path=(final/"manifest.json").relative_to(workspace).as_posix(),
        summary_path=(final/"summary.json").relative_to(workspace).as_posix(), scores_path=(final/"scores.parquet").relative_to(workspace).as_posix())
