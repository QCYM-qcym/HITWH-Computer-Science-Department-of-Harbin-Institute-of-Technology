import pytest
from traffic_anomaly.contracts import SplitBoundaries
from traffic_anomaly.data.splits import split_minutes
from .conftest import batch


def test_split_boundaries_cannot_wrap_numpy_nanosecond_range():
    spans = {name: {'start': f'2500-01-01T0{i}:00:00Z', 'end': f'2500-01-01T0{i+1}:00:00Z'}
             for i, name in enumerate(('train', 'validation', 'calibration', 'test'))}
    bounds = SplitBoundaries(split_id='invalid-range', **spans)
    with pytest.raises(ValueError, match='range'):
        split_minutes(batch([1, 2]), bounds)
