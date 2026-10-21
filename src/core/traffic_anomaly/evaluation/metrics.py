import numpy as np
from ..contracts import Metrics, Evaluation, Coverage
from ..data.labels import align_labels, classify_labels
from .episodes import error_intervals

def confusion(normal, attack, valid, alarms):
    tp, fp = int((attack & valid & alarms).sum()), int((normal & valid & alarms).sum())
    tn, fn = int((normal & valid & ~alarms).sum()), int((attack & valid & ~alarms).sum())
    ratios = {"precision": (tp, tp+fp), "recall": (tp, tp+fn), "f1": (2*tp, 2*tp+fp+fn), "fpr": (fp, fp+tn)}
    return Metrics(tp=tp, fp=fp, tn=tn, fn=fn,
                   **{k: n/d if d else None for k, (n, d) in ratios.items()},
                   undefined_reasons=[k for k, (_, d) in ratios.items() if not d])

def evaluate(run_id, evidence_kind, timestamps, valid, alarms, labels):
    if valid.shape != timestamps.shape or alarms.shape != timestamps.shape or valid.dtype != bool or alarms.dtype != bool:
        raise ValueError("evaluation axes and boolean masks must align")
    normal, attack, background = classify_labels(align_labels(timestamps, labels))
    available = bool((normal | attack).any())
    return Evaluation(run_id=run_id, evidence_kind=evidence_kind, available=available,
        reason=None if available else "No aligned normal/primary-attack labels",
        metrics=confusion(normal, attack, valid, alarms) if available else None,
        normal_coverage=Coverage(eligible=int((normal & valid).sum()), total=int(normal.sum())),
        attack_coverage=Coverage(eligible=int((attack & valid).sum()), total=int(attack.sum())),
        excluded_attack_minutes=int((attack & ~valid).sum()), background_only_minutes=int(background.sum()),
        intervals=error_intervals(timestamps, normal & valid & alarms, attack, attack & valid & alarms),
        high_load_metrics=None, high_load_unavailable_reason="Protocol flow-count exclusivity and coverage not verified")
