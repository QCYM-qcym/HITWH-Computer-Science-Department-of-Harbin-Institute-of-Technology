from pathlib import Path
import numpy as np
from ..contracts import PreprocessState

class Preprocessor:
    def __init__(self, feature_names):
        self.feature_names = tuple(feature_names)
        self.state = None

    @staticmethod
    def _log(x):
        x = np.asarray(x, np.float64)
        if x.ndim != 2 or x.shape[1] != 134 or not np.isfinite(x).all() or (x < 0).any():
            raise ValueError("expected finite nonnegative (n,134) counts")
        return np.log1p(x)

    def fit(self, x):
        z = self._log(x)
        if not len(z):
            raise ValueError("empty training normal candidates")
        scale = z.std(axis=0)
        scale[scale == 0] = 1
        self.state = PreprocessState(feature_names=self.feature_names, mean=z.mean(axis=0).tolist(),
                                     scale=scale.tolist(), n_samples_seen=len(z))
        return self

    def transform(self, x):
        if self.state is None:
            raise ValueError("preprocessor is not fitted")
        return ((self._log(x) - np.array(self.state.mean)) / np.array(self.state.scale)).astype(np.float32)

    def save(self, path):
        Path(path).write_text(self.state.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        state = PreprocessState.model_validate_json(Path(path).read_text(encoding="utf-8"))
        instance = cls(state.feature_names)
        instance.state = state
        return instance
