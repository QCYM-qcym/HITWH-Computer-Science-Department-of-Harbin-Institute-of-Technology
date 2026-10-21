"""Validate local CPU packages with tiny synthetic arrays, never a research run."""
import json
from pathlib import Path
import tempfile

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.ensemble import IsolationForest
import torch


def main():
    torch.manual_seed(42)
    torch.set_num_threads(1)
    x = torch.rand(8, 134, device="cpu")
    model = torch.nn.Sequential(torch.nn.Linear(134, 8), torch.nn.ReLU(), torch.nn.Linear(8, 134))
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    losses = []
    for _ in range(3):
        optimizer.zero_grad()
        loss = ((model(x) - x) ** 2).mean()
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    assert losses[-1] < losses[0]
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        torch.save(model.state_dict(), root / "weights.pt")
        restored = torch.nn.Sequential(torch.nn.Linear(134, 8), torch.nn.ReLU(), torch.nn.Linear(8, 134))
        restored.load_state_dict(torch.load(root / "weights.pt", weights_only=True, map_location="cpu"))
        with torch.no_grad():
            assert torch.equal(model(x), restored(x))
        array = x.numpy()
        forest = IsolationForest(n_estimators=3, random_state=42).fit(array)
        assert np.isfinite(forest.score_samples(array)).all()
        table = pa.table({"score": [None, 1.0], "valid": [False, True]})
        pq.write_table(table, root / "scores.parquet")
        assert table.equals(pq.read_table(root / "scores.parquet"))
    print(json.dumps({"evidence_kind": "SYNTHETIC_ONLY", "torch": torch.__version__,
                      "device": "cpu", "cuda_available": torch.cuda.is_available(),
                      "losses": losses, "reload_equal": True, "iforest_finite": True,
                      "parquet_null_roundtrip": True}))


if __name__ == "__main__":
    main()
