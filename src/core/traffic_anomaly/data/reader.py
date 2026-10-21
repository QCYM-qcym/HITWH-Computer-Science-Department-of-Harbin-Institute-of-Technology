"""Read canonical CSV, never infer UGR timestamps from row numbers."""
import csv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np
from ..contracts import DatasetSchema, MinuteBatch, LabelBatch, LABEL_NAMES

def read_rows(source, schema: DatasetSchema):
    try:
        zone = timezone.utc if schema.source_timezone == "UTC" else ZoneInfo(schema.source_timezone)
    except (ValueError, KeyError) as exc:
        raise ValueError("unknown source timezone") from exc
    if schema.time_basis_source.strip().lower() in {"unknown", "tbd", "unverified"}:
        raise ValueError("unverified timezone source")
    with open(source, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        expected = ["timestamp", *schema.feature_names]
        fields = reader.fieldnames or []
        if fields != expected and fields != expected + list(LABEL_NAMES):
            raise ValueError("columns must match timestamp, ordered 134 features, optional eight labels")
        has_labels = fields == expected + list(LABEL_NAMES)
        grouped = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("incomplete columns")
            stamp = datetime.fromisoformat(row["timestamp"])
            if stamp.second or stamp.microsecond:
                raise ValueError("timestamps must identify a whole minute")
            if stamp.tzinfo is None:
                # Ambiguous/nonexistent local clock times require an explicit offset.
                a, b = stamp.replace(tzinfo=zone, fold=0), stamp.replace(tzinfo=zone, fold=1)
                if a.utcoffset() != b.utcoffset():
                    raise ValueError("ambiguous timezone offset")
                stamp = a
            stamp = np.datetime64(stamp.astimezone(timezone.utc).replace(tzinfo=None), "ns")
            grouped.setdefault(stamp, []).append(row)
    return grouped, has_labels

def segments(timestamps, valid):
    ids = np.zeros(len(timestamps), np.int64)
    if len(ids) > 1:
        ids[1:] = np.cumsum((np.diff(timestamps) != np.timedelta64(1, "m")) | ~valid[:-1] | ~valid[1:])
    return ids

def load_minutes(source, schema: DatasetSchema) -> MinuteBatch:
    grouped, _ = read_rows(source, schema)
    times = np.array(sorted(grouped), dtype="datetime64[ns]")
    values = np.full((len(times), 134), np.nan, np.float32)
    valid = np.zeros(len(times), bool)
    for i, t in enumerate(times):
        rows = grouped[t]
        if any(row != rows[0] for row in rows[1:]):
            continue
        try:
            with np.errstate(over="ignore", invalid="ignore"):
                values[i] = [float(rows[0][k]) for k in schema.feature_names]
            valid[i] = bool(np.isfinite(values[i]).all() and (values[i] >= 0).all())
        except ValueError:
            pass
    return MinuteBatch(times, values, schema.feature_names, valid, segments(times, valid))

def load_labels(source, schema: DatasetSchema) -> LabelBatch:
    grouped, has_labels = read_rows(source, schema)
    if not has_labels:
        raise ValueError("labels unavailable")
    times = np.array(sorted(grouped), dtype="datetime64[ns]")
    labels = {k: np.zeros(len(times), np.int64) for k in LABEL_NAMES}
    for i, t in enumerate(times):
        rows = grouped[t]
        if any(row != rows[0] for row in rows[1:]):
            raise ValueError("conflicting minute cannot be assigned labels")
        for k in LABEL_NAMES:
            try:
                value = int(rows[0][k])
                if value < 0:
                    raise ValueError()
                labels[k][i] = value
            except (ValueError, OverflowError) as exc:
                raise ValueError("labels must be nonnegative int64 counts") from exc
    return LabelBatch(times, labels)
