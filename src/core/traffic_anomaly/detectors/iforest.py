import json
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from ..contracts import ModelConfig

def checked_matrix(x, width=None):
    x = np.asarray(x, np.float32)
    if x.ndim != 2 or x.shape[1] not in (134, 268) or (width is not None and x.shape[1] != width) or not np.isfinite(x).all():
        raise ValueError("detector requires finite compatible feature matrix")
    return x

class IsolationForestDetector:
    def __init__(self, config=None, seed=42):
        self.config = config or ModelConfig()
        self.seed = seed
        self.model = None
        self.input_width = 134

    @property
    def parameter_count(self):
        return sum(tree.tree_.node_count for tree in self.model.estimators_)

    def fit(self, x_train, x_val=None):
        x = checked_matrix(x_train, 134)
        if not len(x): raise ValueError("empty IF training matrix")
        self.model = IsolationForest(n_estimators=self.config.n_estimators, max_samples=min(self.config.max_samples, len(x)),
                                     random_state=self.seed, n_jobs=1).fit(x)

    def score(self, x):
        if self.model is None: raise ValueError("detector is not fitted")
        x = checked_matrix(x, 134)
        return -self.model.score_samples(x) if len(x) else np.empty(0, np.float64)

    def save(self, directory):
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, directory / "weights.bin")
        (directory / "detector.json").write_text(json.dumps({"kind": "iforest", "config": self.config.model_dump(), "seed": self.seed}), encoding="utf-8")

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        state = json.loads((directory / "detector.json").read_text(encoding="utf-8"))
        if state["kind"] != "iforest": raise ValueError("wrong detector kind")
        d = cls(ModelConfig.model_validate(state["config"]), state["seed"])
        d.model = joblib.load(directory / "weights.bin")
        if not isinstance(d.model, IsolationForest) or d.model.n_features_in_ != 134: raise ValueError("incompatible IF payload")
        return d
