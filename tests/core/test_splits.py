import numpy as np
from .conftest import batch
from traffic_anomaly.contracts import SplitBoundaries
from traffic_anomaly.data.splits import split_minutes

def test_four_half_open_splits_do_not_share_history():
    b = batch(range(8))
    spans = [("train", 0, 2), ("validation", 2, 4), ("calibration", 4, 6), ("test", 6, 8)]
    bounds = SplitBoundaries(split_id="manual", **{k: {"start": f"2026-01-01T00:{s:02d}:00Z", "end": f"2026-01-01T00:{e:02d}:00Z"} for k, s, e in spans})
    parts = split_minutes(b, bounds)
    assert [p.features[:, 0].tolist() for p in parts.values()] == [[0, 1], [2, 3], [4, 5], [6, 7]]
    assert all(p.segment_ids[0] == 0 for p in parts.values())
    assert sum(len(p.timestamps) for p in parts.values()) == 8
