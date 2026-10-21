import numpy as np
from datetime import datetime
from ..contracts import MinuteBatch
from .reader import segments
from .clock import utc_nanosecond_minute

def split_minutes(batch, boundaries):
    result = {}
    for name in ("train", "validation", "calibration", "test"):
        span = getattr(boundaries, name)
        start, end = (utc_nanosecond_minute(datetime.fromisoformat(value)) for value in (span.start, span.end))
        select = (batch.timestamps >= start) & (batch.timestamps < end)
        times, valid = batch.timestamps[select], batch.row_valid[select]
        # Preserve explicit boundaries within a part, but rebase to a fresh history.
        ids = batch.segment_ids[select].copy()
        if len(ids):
            ids -= ids[0]
        result[name] = MinuteBatch(times, batch.features[select].copy(), batch.feature_names, valid.copy(), ids)
    return result
