from hashlib import sha256
import numpy as np
from ..contracts import AuditReport
from .reader import read_rows, load_minutes, load_labels

def file_sha256(path):
    h = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def audit_dataset(source, schema) -> AuditReport:
    findings, passed, count = [], False, 0
    try:
        grouped, has_labels = read_rows(source, schema)
        b = load_minutes(source, schema)
        count = len(b.timestamps)
        duplicates = sum(len(rows) - 1 for rows in grouped.values())
        if duplicates:
            findings.append(f"duplicate_rows={duplicates}; identical rows deduplicated, conflicts invalidated")
        invalid = int((~b.row_valid).sum())
        gaps = int((np.diff(b.timestamps) != np.timedelta64(1, "m")).sum())
        findings.extend([f"invalid_or_conflicting_minutes={invalid}", f"gap_count={gaps}"])
        if has_labels:
            load_labels(source, schema)
        else:
            findings.append("labels unavailable; no training or calibration")
        passed = bool(count and invalid == 0 and has_labels)
    except ValueError as exc:
        findings.append(str(exc))
    return AuditReport(dataset_id=schema.dataset_id, passed=passed,
                       evidence_kind="SYNTHETIC_ONLY" if schema.dataset_id.startswith("synthetic") else "REAL_DATA",
                       row_count=count, findings=findings, source_sha256=file_sha256(source))
