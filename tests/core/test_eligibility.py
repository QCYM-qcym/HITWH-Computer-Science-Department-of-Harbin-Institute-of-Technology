from .conftest import batch, labels_for
from traffic_anomaly.features.history import build_history
from traffic_anomaly.features.eligibility import eligible_normals, common_minutes

def test_training_requires_normal_current_and_every_history_minute():
    b = batch([1] * 8)
    h = build_history(b, 2, 1e-6)
    labs = labels_for(b, {"dos": {2: 1}})
    assert eligible_normals(b.timestamps, h.valid, labs, 2).tolist() == [False, False, False, False, False, True, True, True]
    # History itself consumes no labels, including testing history contaminated by attack.
    assert h.valid.tolist() == [False, False, True, True, True, True, True, True]

def test_common_minutes_intersect_all_windows():
    b = batch([1] * 5)
    assert common_minutes([build_history(b, 1, 1e-6).valid, build_history(b, 3, 1e-6).valid]).tolist() == [False, False, False, True, True]
