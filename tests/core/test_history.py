import numpy as np
from .conftest import batch
from traffic_anomaly.features.history import build_history

def test_median_mad_causal_and_signed():
    b = batch([1, 2, 3, 5, -4])
    h = build_history(b, 3, 1e-6)
    assert h.valid.tolist() == [False, False, False, True, True]
    np.testing.assert_allclose(h.residual[3], 3 / 1.000001)
    assert (h.residual[4] < 0).all()
    changed = batch([1, 2, 3, 5, 999])
    np.testing.assert_array_equal(build_history(changed, 3, 1e-6).residual[3], h.residual[3])

def test_gap_invalid_and_explicit_segment_reset_history():
    b = batch([1, 1, 1, 1, 1, 1], offsets=[0, 1, 3, 4, 5, 6],
              valid=[True, True, True, False, True, True], segments=[0, 0, 1, 2, 3, 3])
    h = build_history(b, 1, 1e-6)
    assert h.valid.tolist() == [False, True, False, False, False, True]
    assert h.invalid_reason[2] == "gap"
    assert h.invalid_reason[3] == "invalid_input"
    assert np.isfinite(h.residual[h.valid]).all()

def test_zero_mad_stays_finite():
    h = build_history(batch([2, 2, 2, 5]), 3, 1e-6)
    np.testing.assert_allclose(h.residual[3], 3000000)
