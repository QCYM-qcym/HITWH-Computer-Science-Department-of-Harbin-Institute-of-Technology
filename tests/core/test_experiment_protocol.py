import numpy as np
import pytest
from traffic_anomaly.evaluation.coverage import intersect_timestamp_masks

def test_intersection_uses_time_not_row_positions():
    t = np.array(["2026-01-01T00:00", "2026-01-01T00:01", "2026-01-01T00:02"], dtype="datetime64[ns]")
    masks = intersect_timestamp_masks([(t, np.array([False, True, True])), (t[1:], np.array([False, True]))])
    assert masks[0].tolist() == [False, False, True]
    assert masks[1].tolist() == [False, True]
