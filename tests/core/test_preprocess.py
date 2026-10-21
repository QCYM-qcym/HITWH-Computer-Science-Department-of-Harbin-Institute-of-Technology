import numpy as np
import pytest
from conftest import NAMES
from traffic_anomaly.features.preprocess import Preprocessor

def test_log_then_train_only_scale_and_reload(tmp_path):
    p = Preprocessor(NAMES)
    x = np.repeat(np.array([[0], [3]], np.float32), 134, axis=1)
    p.fit(x)
    np.testing.assert_allclose(p.transform(x)[:, 0], [-1, 1])
    before = p.state.model_dump()
    p.transform(np.full((1, 134), 1e30, np.float32))
    assert p.state.model_dump() == before
    p.save(tmp_path / "preprocess.json")
    np.testing.assert_array_equal(Preprocessor.load(tmp_path / "preprocess.json").transform(x), p.transform(x))

def test_constant_counts_and_negative_rejected():
    p = Preprocessor(NAMES).fit(np.ones((3, 134), np.float32))
    assert p.state.scale == [1.0] * 134
    with pytest.raises(ValueError):
        p.transform(np.full((1, 134), -1, np.float32))
