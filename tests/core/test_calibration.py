import numpy as np
import pytest
from traffic_anomaly.evaluation.calibration import calibrate

def test_linear_99_percentile_strict_exceedance():
    assert calibrate(np.array([0., 1., 2., 3.])) == pytest.approx(2.97)
    threshold = calibrate(np.ones(4))
    assert not bool(1.0 > threshold)

@pytest.mark.parametrize("values", [[], [float('nan')], [float('inf')]])
def test_invalid_calibration_fails(values):
    with pytest.raises(ValueError):
        calibrate(np.array(values))
