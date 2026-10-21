import math
import numpy as np
from ..contracts import HistoryBatch

def build_history(batch, window: int, epsilon: float) -> HistoryBatch:
    if not isinstance(window, int) or isinstance(window, bool) or window < 1 or not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("window and epsilon must be positive and finite")
    n = len(batch.timestamps)
    residual = np.full((n, 134), np.nan, np.float32)
    valid, reasons, start = np.zeros(n, bool), [], 0
    for i in range(n):
        reset = i > 0 and (batch.segment_ids[i] != batch.segment_ids[i-1] or
                batch.timestamps[i] - batch.timestamps[i-1] != np.timedelta64(1, "m") or not batch.row_valid[i-1])
        if reset:
            start = i
        if not batch.row_valid[i]:
            reasons.append("invalid_input")
            start = i + 1
        elif i - start < window:
            reasons.append("gap" if start > 0 else "warmup")
        else:
            past = batch.features[i-window:i].astype(np.float64)
            median = np.median(past, axis=0)
            mad = np.median(np.abs(past - median), axis=0)
            with np.errstate(over="ignore", invalid="ignore"):
                residual[i] = (batch.features[i].astype(np.float64) - median) / (mad + epsilon)
            valid[i] = np.isfinite(residual[i]).all()
            reasons.append(None if valid[i] else "invalid_input")
            if not valid[i]:
                start = i + 1
    return HistoryBatch(batch.timestamps.copy(), batch.features.copy(), residual, valid, tuple(reasons))
