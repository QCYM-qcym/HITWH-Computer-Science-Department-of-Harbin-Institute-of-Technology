import numpy as np
import pytest
from traffic_anomaly.contracts import ModelConfig
from traffic_anomaly.detectors.iforest import IsolationForestDetector
from traffic_anomaly.detectors.autoencoder import AutoencoderDetector

def test_iforest_direction_and_reload(tmp_path):
    train = np.random.default_rng(42).normal(0, 0.01, (32, 134)).astype(np.float32)
    d = IsolationForestDetector(ModelConfig(n_estimators=10, max_samples=16), seed=42)
    d.fit(train)
    x = np.vstack([train[:1], np.full((1, 134), 100., np.float32)])
    scores = d.score(x)
    assert scores[1] > scores[0]
    d.save(tmp_path)
    np.testing.assert_allclose(IsolationForestDetector.load(tmp_path).score(x), scores, rtol=1e-5, atol=1e-6)
    with pytest.raises(ValueError):
        d.score(np.ones((1, 268), np.float32))

@pytest.mark.parametrize("width", [134, 268])
def test_ae_mean_squared_error_and_reload(tmp_path, width):
    x = np.random.default_rng(42).normal(size=(9, width)).astype(np.float32)
    d = AutoencoderDetector(width, ModelConfig(hidden_widths=[4], epochs=1, batch_size=4), seed=42)
    d.fit(x, x)
    errors = d.reconstruction_errors(x)
    np.testing.assert_allclose(d.score(x), errors.mean(axis=1), rtol=1e-6)
    if width == 268:
        np.testing.assert_allclose(d.score(x), (errors[:, :134].mean(axis=1) + errors[:, 134:].mean(axis=1)) / 2, rtol=1e-6)
    d.save(tmp_path)
    np.testing.assert_allclose(AutoencoderDetector.load(tmp_path).score(x), d.score(x), rtol=1e-5, atol=1e-6)
