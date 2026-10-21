"""Bounded profile of provider UGR16v3 MAT and optional full CSV alignment.

This never invents a timezone or declares a Data Gate pass.
"""
from datetime import datetime
from pathlib import Path
import csv
import numpy as np
from scipy.io import loadmat
from .audit import file_sha256

def profile_provider(source, csv_root=None):
    m = loadmat(source, squeeze_me=True)
    report = {"evidence_kind": "REAL_DATA", "gate_passed": False, "source_timezone": None,
              "mat_sha256": file_sha256(source), "feature_names": [str(s) for s in m["var_l"]],
              "label_names": [str(s) for s in m["yvar_l"]],
              "blockers": ["Source clock timezone has no verified evidence; UTC boundaries not frozen.",
                           "License conditions, normal candidates and four UTC splits need review."]}
    for part, xk, yk, tk in (("train", "X", "Y", "obs_l"), ("test", "test", "Yt", "obs_lt")):
        x, y = np.asarray(m[xk]), np.asarray(m[yk])
        text = [str(s) for s in np.atleast_1d(m[tk])]
        t = np.array([datetime.strptime(s, "%Y%m%d%H%M") for s in text], dtype="datetime64[m]")
        diff = np.diff(t).astype(np.int64)
        normal = (y == 0).all(axis=1)
        attack = (y[:, :4] > 0).any(axis=1)
        if part == "test" and not normal.any():
            report["blockers"].append("No normal test candidates under the frozen eight-label policy; FPR cannot be evaluated.")
        info = {"rows": len(x), "feature_width": x.shape[1], "label_width": y.shape[1],
                "first_local_clock": text[0], "last_local_clock": text[-1],
                "aligned_lengths": len(x) == len(y) == len(t),
                "gap_count": int((diff > 1).sum()), "missing_minutes": int(np.maximum(diff-1, 0).sum()),
                "duplicate_timestamps": int((diff == 0).sum()), "reverse_timestamps": int((diff < 0).sum()),
                "invalid_count_rows": int((~np.isfinite(x).all(axis=1) | (x < 0).any(axis=1)).sum()),
                "normal_candidates": int(normal.sum()), "attack_minutes": int(attack.sum()),
                "background_only_minutes": int((~normal & ~attack).sum())}
        if csv_root is not None:
            for prefix, expected, names in (("X", x, report["feature_names"]), ("Y", y, report["label_names"])):
                path = Path(csv_root) / f"UGR16v3.{prefix}{part}.csv"
                with path.open(newline="", encoding="utf-8-sig") as f:
                    rows = csv.reader(f)
                    header = next(rows)
                    raw_rows = list(rows)
                    clocks = [row[0] for row in raw_rows]
                    values = np.array([[int(c) for c in row[1:]] for row in raw_rows], dtype=np.int64)
                info[prefix + "_csv_sha256"] = file_sha256(path)
                info[prefix + "_csv_header_matches"] = header == ["Row", *names]
                info[prefix + "_csv_clock_matches"] = clocks == text
                info[prefix + "_csv_mat_equal"] = values.shape == expected.shape and bool(np.array_equal(values, expected))
                if not info[prefix + "_csv_mat_equal"] or header != ["Row", *names] or clocks != text:
                    report["blockers"].append(f"{part} {prefix} CSV/MAT alignment failed")
        report[part] = info
    return report
