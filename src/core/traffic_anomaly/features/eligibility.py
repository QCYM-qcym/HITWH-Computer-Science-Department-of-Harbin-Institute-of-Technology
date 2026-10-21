import numpy as np
from ..data.labels import align_labels, classify_labels

def eligible_normals(timestamps, valid, labels, window):
    normal, _, _ = classify_labels(align_labels(timestamps, labels))
    eligible = np.zeros(len(timestamps), bool)
    for i in range(window, len(timestamps)):
        eligible[i] = valid[i] and normal[i-window:i+1].all() and np.all(np.diff(timestamps[i-window:i+1]) == np.timedelta64(1, "m"))
    return eligible

def common_minutes(masks):
    if not masks or any(m.shape != masks[0].shape for m in masks):
        raise ValueError("aligned nonempty masks required")
    return np.logical_and.reduce(masks)
