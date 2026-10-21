import csv
import numpy as np
import pytest
from traffic_anomaly.contracts import DatasetSchema, MinuteBatch, LabelBatch, LABEL_NAMES

NAMES = tuple(f"feature_{i:03d}" for i in range(134))

@pytest.fixture
def schema():
    return DatasetSchema(dataset_id="synthetic-w1", dataset_version="manual-v1",
                         feature_names=NAMES, source_timezone="UTC",
                         time_basis_source="hand constructed UTC example")

def batch(values, offsets=None, valid=None, segments=None):
    x = np.asarray(values, dtype=np.float32)
    if x.ndim == 1:
        x = np.repeat(x[:, None], 134, axis=1)
    n = len(x)
    t = np.datetime64("2026-01-01T00:00", "ns") + np.asarray(range(n) if offsets is None else offsets) * np.timedelta64(1, "m")
    return MinuteBatch(t, x, NAMES, np.ones(n, bool) if valid is None else np.array(valid, bool),
                       np.zeros(n, np.int64) if segments is None else np.array(segments, np.int64))

def labels_for(b, changes=None):
    labels = {name: np.zeros(len(b.timestamps), np.int64) for name in LABEL_NAMES}
    for name, entries in (changes or {}).items():
        for i, value in entries.items():
            labels[name][i] = value
    return LabelBatch(b.timestamps.copy(), labels)

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", *NAMES, *LABEL_NAMES])
        for stamp, value, changes in rows:
            writer.writerow([stamp, *([value] * 134), *(changes.get(k, 0) for k in LABEL_NAMES)])
    return path
