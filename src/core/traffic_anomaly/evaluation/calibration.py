import numpy as np

def calibrate(scores, quantile=0.99):
    scores = np.asarray(scores, np.float64)
    if quantile != 0.99 or scores.ndim != 1 or not scores.size or not np.isfinite(scores).all():
        raise ValueError("calibration requires nonempty finite scores and the frozen 99% quantile")
    return float(np.quantile(scores, quantile, method="linear"))
