"""Explicit UTC conversion with no machine-local timezone or ns wraparound."""
from datetime import datetime, timezone
import numpy as np


def utc_nanosecond_minute(value: datetime) -> np.datetime64:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('UTC conversion requires an explicit timezone')
    utc = value.astimezone(timezone.utc).replace(tzinfo=None)
    stamp = np.datetime64(utc, 'ns')
    if np.isnat(stamp) or stamp.astype('datetime64[us]').item() != utc:
        raise ValueError('timestamp outside supported nanosecond range')
    if stamp != stamp.astype('datetime64[m]').astype('datetime64[ns]'):
        raise ValueError('UTC timestamps must identify a whole minute')
    return stamp
