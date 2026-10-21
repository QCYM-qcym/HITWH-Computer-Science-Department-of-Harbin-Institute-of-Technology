import numpy as np

def intersect_timestamp_masks(series):
    if not series: raise ValueError("at least one series required")
    common = series[0][0][series[0][1]]
    for times, valid in series[1:]:
        common = np.intersect1d(common, times[valid], assume_unique=True)
    return [np.isin(times, common) & valid for times, valid in series]
