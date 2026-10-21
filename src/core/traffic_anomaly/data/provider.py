"""Bounded profile of provider UGR16v3 MAT and optional full CSV alignment.

This never invents a timezone or declares a Data Gate pass.
"""
from datetime import datetime
from pathlib import Path
import csv
from collections import Counter
import numpy as np
from scipy.io import loadmat
from .audit import file_sha256
from ..contracts import LABEL_NAMES

def count_rows_valid(values):
    """Provider payloads are finite, nonnegative integral counts, not features after scaling."""
    return (np.isfinite(values) & (values >= 0) & (values < 2**63)
            & (values == np.floor(values))).all(axis=1)

def profile_provider(source, csv_root=None):
    m = loadmat(source, squeeze_me=True)
    report = {"report_version": "provider-audit-v2", "evidence_kind": "REAL_DATA", "gate_passed": False,
              "structure_trusted": True, "source_timezone": None, "minute_anchor": "UNVERIFIED",
              "mat_sha256": file_sha256(source), "feature_names": [str(s) for s in m["var_l"]],
              "label_names": [str(s) for s in m["yvar_l"]],
              "blockers": ["Source clock timezone has no verified evidence; UTC boundaries not frozen.",
                           "License conditions, normal candidates and four UTC splits need review."]}
    if tuple(report['label_names']) != LABEL_NAMES:
        raise ValueError('provider label order must match the eight-label contract')
    if len(report['feature_names']) != 134 or len(set(report['feature_names'])) != 134:
        raise ValueError('provider requires 134 unique feature names')
    # Author's train/test partitions are not the project's frozen four UTC spans.
    report['project_splits'] = {name: {
        'status': 'NOT_DEFINED', 'reason': 'Source timezone and four project boundaries are not frozen',
        'rows': None, 'valid_minutes': None, 'normal_candidates': None, 'attack_minutes': None,
        'background_only_minutes': None, 'label_unavailable_minutes': None,
        'valid_labeled_minutes': None, 'label_missing_minutes': None, 'invalid_count_rows': None,
        'unmatched_feature_label_rows': None, 'per_label_positive_minutes': None,
        'attack_background_overlap_minutes': None, 'multiple_primary_attack_minutes': None,
    } for name in ('train', 'validation', 'calibration', 'test')}
    for part, xk, yk, tk in (("train", "X", "Y", "obs_l"), ("test", "test", "Yt", "obs_lt")):
        x, y = np.atleast_2d(m[xk]), np.atleast_2d(m[yk])
        text = [str(s) for s in np.atleast_1d(m[tk])]
        if x.ndim != 2 or x.shape[1] != 134 or y.ndim != 2 or y.shape[1] != 8:
            raise ValueError('provider matrices require 134 features and eight labels')
        if not len(x) or len(x) != len(y) or len(x) != len(text):
            raise ValueError('provider feature, label and clock row counts must align and be nonempty')
        t = np.array([datetime.strptime(s, "%Y%m%d%H%M") for s in text], dtype="datetime64[m]")
        diff = np.diff(t).astype(np.int64)
        feature_valid, known = count_rows_valid(x), count_rows_valid(y)
        normal = known & (y == 0).all(axis=1)
        attack = known & (y[:, :4] > 0).any(axis=1)
        background = known & ~attack & (y[:, 4:] > 0).any(axis=1)
        if part == "test" and not normal.any():
            report["blockers"].append("No normal test candidates under the frozen eight-label policy; FPR cannot be evaluated.")
        info = {"rows": len(x), "feature_width": x.shape[1], "label_width": y.shape[1],
                "first_local_clock": text[0], "last_local_clock": text[-1],
                "aligned_lengths": len(x) == len(y) == len(t),
                "gap_count": int((diff > 1).sum()), "missing_minutes": int(np.maximum(diff-1, 0).sum()),
                "duplicate_timestamps": int((diff == 0).sum()), "reverse_timestamps": int((diff < 0).sum()),
                "invalid_count_rows": int((~feature_valid).sum()),
                "valid_minutes": int(len(np.unique(t[feature_valid]))),
                "valid_labeled_minutes": int((feature_valid & known).sum()),
                "label_missing_minutes": int(np.isnan(y).any(axis=1).sum()),
                "label_unavailable_minutes": int((~known).sum()),
                "unmatched_feature_label_rows": 0,
                "normal_candidates": int(normal.sum()), "attack_minutes": int(attack.sum()),
                "background_only_minutes": int(background.sum()),
                "per_label_positive_minutes": {name: int((known & (y[:, i] > 0)).sum()) for i, name in enumerate(LABEL_NAMES)},
                "attack_background_overlap_minutes": int((attack & (y[:, 4:] > 0).any(axis=1)).sum()),
                "multiple_primary_attack_minutes": int((known & ((y[:, :4] > 0).sum(axis=1) > 1)).sum())}
        if not feature_valid.all() or not known.all() or (diff <= 0).any():
            report['structure_trusted'] = False
            report['blockers'].append(f'{part}: invalid counts/labels or duplicate/reversed clock records')
        if csv_root is not None:
            csv_axes = {}
            for prefix, expected, names in (("X", x, report["feature_names"]), ("Y", y, report["label_names"])):
                path = Path(csv_root) / f"UGR16v3.{prefix}{part}.csv"
                with path.open(newline="", encoding="utf-8-sig") as f:
                    rows = csv.reader(f)
                    header = next(rows)
                    raw_rows = list(rows)
                    clocks = [row[0] for row in raw_rows]
                    csv_axes[prefix] = Counter(clocks)
                    values = np.array([[int(c) for c in row[1:]] for row in raw_rows], dtype=np.int64)
                info[prefix + "_csv_sha256"] = file_sha256(path)
                info[prefix + "_csv_header_matches"] = header == ["Row", *names]
                info[prefix + "_csv_clock_matches"] = clocks == text
                info[prefix + "_csv_mat_equal"] = values.shape == expected.shape and bool(np.array_equal(values, expected))
                if not info[prefix + "_csv_mat_equal"] or header != ["Row", *names] or clocks != text:
                    report['structure_trusted'] = False
                    report["blockers"].append(f"{part} {prefix} CSV/MAT alignment failed")
            keys = csv_axes['X'].keys() | csv_axes['Y'].keys()
            info['unmatched_feature_label_rows'] = sum(abs(csv_axes['X'][k] - csv_axes['Y'][k]) for k in keys)
        report[part] = info
    return report
