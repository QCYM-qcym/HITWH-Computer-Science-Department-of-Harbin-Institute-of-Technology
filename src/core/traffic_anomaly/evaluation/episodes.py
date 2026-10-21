import numpy as np
from ..contracts import EvaluationInterval

def utc_minute(t):
    return np.datetime_as_string(t.astype("datetime64[s]"), unit="s") + "Z"

def episodes(timestamps, selected):
    groups, start = [], None
    for i, flag in enumerate(selected):
        if start is not None and (not flag or timestamps[i] - timestamps[i-1] != np.timedelta64(1, "m")):
            groups.append((start, i)); start = None
        if flag and start is None: start = i
    if start is not None: groups.append((start, len(selected)))
    return groups

def error_intervals(times, false_positive, attacks, detected):
    intervals = []
    for start, end in episodes(times, false_positive):
        intervals.append(EvaluationInterval(start=utc_minute(times[start]), end=utc_minute(times[end-1] + np.timedelta64(1, "m")),
                                            kind="false_positive", minute_count=end-start))
    for start, end in episodes(times, attacks):
        if not detected[start:end].any():
            intervals.append(EvaluationInterval(start=utc_minute(times[start]), end=utc_minute(times[end-1] + np.timedelta64(1, "m")),
                                                kind="missed_attack", minute_count=end-start))
    return intervals
