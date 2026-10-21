"""Explicit synthetic-only CLI fixture; never claims to be UGR data."""
import csv
from pathlib import Path
import numpy as np
from .contracts import DatasetSchema, LABEL_NAMES
from .artifacts import write_json
from .evaluation.episodes import utc_minute

def create_demo_workspace(workspace):
    workspace = Path(workspace); workspace.mkdir(parents=True, exist_ok=True)
    if (workspace / "registry.json").exists() or (workspace / "synthetic.csv").exists():
        raise ValueError("demo refuses to overwrite an existing registry or source")
    names = tuple(f"feature_{i:03d}" for i in range(134))
    schema = DatasetSchema(dataset_id="synthetic-w1", dataset_version="manual-v1", feature_names=names,
                           source_timezone="UTC", time_basis_source="explicitly generated UTC synthetic minutes")
    times = np.datetime64("2026-01-01T00:00", "ns") + np.arange(161) * np.timedelta64(1,"m")
    rng = np.random.default_rng(42)
    with (workspace / "synthetic.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f); writer.writerow(["timestamp", *names, *LABEL_NAMES])
        for i in range(160):
            x = rng.integers(5, 15, size=134)
            labels = [0] * 8
            if 135 <= i <= 139: x *= 10; labels[0] = 1
            if i == 145: labels[7] = 1
            writer.writerow([utc_minute(times[i]), *x.tolist(), *labels])
    boundaries = {name: {"start": utc_minute(times[start]), "end": utc_minute(times[end])}
                  for name, start, end in (("train",0,40),("validation",40,80),("calibration",80,120),("test",120,160))}
    boundaries["split_id"] = "synthetic-split"
    write_json(workspace / "registry.json", {"datasets": {"synthetic-w1": {"source": "synthetic.csv",
        "schema": schema.model_dump(mode="json"), "evidence_kind": "SYNTHETIC_ONLY",
        "splits": {"synthetic-split": boundaries}}}})
