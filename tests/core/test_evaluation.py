import numpy as np
from .conftest import batch, labels_for
from traffic_anomaly.evaluation.metrics import evaluate

def test_confusion_coverage_background_and_completely_missed_episode():
    b = batch([1] * 7)
    labels = labels_for(b, {"dos": {0: 1, 1: 1, 2: 1}, "spam": {2: 1, 3: 1}})
    result = evaluate("manual", "SYNTHETIC_ONLY", b.timestamps,
                      np.array([False, True, True, True, True, True, True]),
                      np.array([False, False, False, True, True, False, False]), labels)
    assert (result.metrics.tp, result.metrics.fp, result.metrics.tn, result.metrics.fn) == (0, 1, 2, 2)
    assert result.normal_coverage.total == 3
    assert result.attack_coverage.total == 3
    assert result.excluded_attack_minutes == 1
    assert result.background_only_minutes == 1
    missed = [e for e in result.intervals if e.kind == "missed_attack"]
    assert missed[0].start == "2026-01-01T00:00:00Z"
    assert missed[0].end == "2026-01-01T00:03:00Z"
    assert missed[0].minute_count == 3
    assert result.high_load_metrics is None

def test_zero_denominators_and_missing_labels():
    b = batch([1, 1])
    e = evaluate("zero", "SYNTHETIC_ONLY", b.timestamps, np.ones(2, bool), np.zeros(2, bool), labels_for(b))
    assert e.metrics.precision is None and e.metrics.recall is None
    assert e.metrics.f1 is None and e.metrics.fpr == 0
    assert sorted(e.metrics.undefined_reasons) == ["f1", "precision", "recall"]
    assert not evaluate("missing", "SYNTHETIC_ONLY", b.timestamps, np.ones(2, bool), np.zeros(2, bool), None).available

def test_partial_hit_does_not_expand_predictions():
    b = batch([1] * 3)
    e = evaluate("partial", "SYNTHETIC_ONLY", b.timestamps, np.ones(3, bool), np.array([True, False, False]), labels_for(b, {"dos": {0: 1, 1: 1, 2: 1}}))
    assert e.metrics.tp == 1 and e.metrics.fn == 2
