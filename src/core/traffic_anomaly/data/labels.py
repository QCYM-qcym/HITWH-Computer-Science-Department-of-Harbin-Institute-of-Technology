import numpy as np
from ..contracts import LABEL_NAMES

def align_labels(timestamps, labels):
    """Unknown minutes stay -1; absence is never a normal zero label."""
    aligned = np.full((len(timestamps), 8), -1, np.int64)
    if labels is None or len(labels.timestamps) == 0:
        return aligned
    indexes = np.searchsorted(labels.timestamps, timestamps)
    found = indexes < len(labels.timestamps)
    found[found] &= labels.timestamps[indexes[found]] == timestamps[found]
    aligned[found] = np.column_stack([labels.labels[k] for k in LABEL_NAMES])[indexes[found]]
    return aligned

def classify_labels(aligned):
    known = (aligned >= 0).all(axis=1)
    attack = known & (aligned[:, :4] > 0).any(axis=1)
    background = known & ~attack & (aligned[:, 4:] > 0).any(axis=1)
    normal = known & (aligned == 0).all(axis=1)
    return normal, attack, background
