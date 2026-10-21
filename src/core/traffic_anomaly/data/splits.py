import numpy as np
from ..contracts import MinuteBatch
from .reader import segments

def split_minutes(batch, boundaries):
    result = {}
    for name in ("train", "validation", "calibration", "test"):
        span = getattr(boundaries, name)
        select = (batch.timestamps >= np.datetime64(span.start[:-1], "ns")) & (batch.timestamps < np.datetime64(span.end[:-1], "ns"))
        times, valid = batch.timestamps[select], batch.row_valid[select]
        # Preserve explicit boundaries within a part, but rebase to a fresh history.
        ids = batch.segment_ids[select].copy()
        if len(ids):
            ids -= ids[0]
        result[name] = MinuteBatch(times, batch.features[select].copy(), batch.feature_names, valid.copy(), ids)
    return result
