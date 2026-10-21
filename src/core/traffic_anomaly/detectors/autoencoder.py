import copy
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from ..contracts import ModelConfig
from .iforest import checked_matrix

class AutoencoderDetector:
    def __init__(self, input_width=134, config=None, seed=42):
        if input_width not in (134, 268): raise ValueError("input must be 134 or 268")
        self.input_width, self.config, self.seed = input_width, config or ModelConfig(), seed
        widths = [input_width, *self.config.hidden_widths, *reversed(self.config.hidden_widths[:-1]), input_width]
        with torch.random.fork_rng():
            torch.manual_seed(seed)
            layers = []
            for i, (left, right) in enumerate(zip(widths, widths[1:])):
                layers.append(nn.Linear(left, right))
                if i < len(widths) - 2: layers.append(nn.ReLU())
            self.network = nn.Sequential(*layers).cpu()
        self.fitted = False
        self.validation_losses = []

    @property
    def parameter_count(self):
        return sum(p.numel() for p in self.network.parameters())

    def fit(self, x_train, x_val=None):
        x = checked_matrix(x_train, self.input_width)
        if not len(x): raise ValueError("empty AE training matrix")
        val = None if x_val is None else checked_matrix(x_val, self.input_width)
        if val is not None and not len(val): raise ValueError("empty validation matrix")
        rng = np.random.default_rng(self.seed)
        optimizer = torch.optim.Adam(self.network.parameters(), lr=self.config.learning_rate)
        best, state = float("inf"), None
        for _ in range(self.config.epochs):
            self.network.train()
            indexes = rng.permutation(len(x))
            for start in range(0, len(x), self.config.batch_size):
                tensor = torch.from_numpy(x[indexes[start:start+self.config.batch_size]])
                optimizer.zero_grad()
                loss = torch.mean((self.network(tensor) - tensor) ** 2)
                if not torch.isfinite(loss): raise ValueError("nonfinite training loss; configuration requires validation")
                loss.backward(); optimizer.step()
            if val is not None:
                error = float(self.reconstruction_errors(val).mean())
                self.validation_losses.append(error)
                if error < best: best, state = error, copy.deepcopy(self.network.state_dict())
        if state is not None: self.network.load_state_dict(state)
        self.fitted = True

    def reconstruction_errors(self, x):
        x = checked_matrix(x, self.input_width)
        self.network.eval()
        pieces = []
        with torch.inference_mode():
            for start in range(0, len(x), self.config.batch_size):
                tensor = torch.from_numpy(x[start:start+self.config.batch_size])
                pieces.append(((self.network(tensor) - tensor) ** 2).numpy())
        result = np.concatenate(pieces) if pieces else np.empty((0, self.input_width), np.float32)
        if not np.isfinite(result).all(): raise ValueError("nonfinite reconstruction error")
        return result

    def score(self, x):
        if not self.fitted: raise ValueError("detector is not fitted")
        return self.reconstruction_errors(x).mean(axis=1).astype(np.float64)

    def save(self, directory):
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        torch.save(self.network.state_dict(), directory / "weights.bin")
        (directory / "detector.json").write_text(json.dumps({"kind": "ae", "input_width": self.input_width,
            "config": self.config.model_dump(), "seed": self.seed}), encoding="utf-8")

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        state = json.loads((directory / "detector.json").read_text(encoding="utf-8"))
        if state["kind"] != "ae": raise ValueError("wrong detector kind")
        d = cls(state["input_width"], ModelConfig.model_validate(state["config"]), state["seed"])
        d.network.load_state_dict(torch.load(directory / "weights.bin", map_location="cpu", weights_only=True))
        d.fitted = True
        return d
