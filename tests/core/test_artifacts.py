import json
import numpy as np
import pytest
from .conftest import NAMES
from traffic_anomaly.contracts import RunConfig
from traffic_anomaly.pipeline import execute_run, score_run
from traffic_anomaly.artifacts import verify_run, load_model, read_table, SCORES_SCHEMA
from traffic_anomaly.contracts import SeriesPoint
from traffic_anomaly.synthetic import create_demo_workspace

@pytest.mark.parametrize("method", ["iforest", "current_ae", "history_ae"])
def test_pipeline_reload_artifacts_and_labels_isolated(tmp_path, method):
    create_demo_workspace(tmp_path)
    config = RunConfig(dataset_id="synthetic-w1", split_id="synthetic-split", method=method, window_minutes=3,
                       model={"hidden_widths": [4], "epochs": 1, "n_estimators": 10, "max_samples": 16})
    result = execute_run(config, tmp_path)
    directory = (tmp_path / result.manifest_path).parent
    manifest, summary = verify_run(directory)
    assert summary.evidence_kind == "SYNTHETIC_ONLY"
    assert summary.row_count == 40 and summary.valid_count == 37
    model, preprocess, meta = load_model(directory, NAMES, config)
    x = preprocess.transform(np.ones((2,134), np.float32))
    if method == "history_ae": x = np.hstack([x,x])
    before = model.score(x)
    np.testing.assert_allclose(load_model(directory, NAMES, config)[0].score(x), before, rtol=1e-5, atol=1e-6)
    rescored = score_run(config, tmp_path, directory / "model")
    a = read_table(tmp_path / result.scores_path, SCORES_SCHEMA, SeriesPoint)
    b = read_table(tmp_path / rescored.scores_path, SCORES_SCHEMA, SeriesPoint)
    assert a == b
    with pytest.raises(ValueError, match="feature order"):
        load_model(directory, tuple(reversed(NAMES)), config)
    # Alter only TEST labels: model payload, preprocessing, threshold, raw scores unchanged.
    source = tmp_path / "synthetic.csv"
    lines = source.read_text().splitlines()
    for i in range(121, 161):
        cells = lines[i].split(","); cells[135] = "1"; lines[i] = ",".join(cells)
    source.write_text("\n".join(lines) + "\n")
    changed = execute_run(config, tmp_path)
    assert read_table(tmp_path / changed.scores_path, SCORES_SCHEMA, SeriesPoint) == a
    assert json.loads((directory / "model/preprocess.json").read_text()) == json.loads((tmp_path / changed.manifest_path).parent.joinpath("model/preprocess.json").read_text())
    (directory / "model/weights.bin").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="digest"):
        load_model(directory, NAMES, config)

def test_real_data_without_gate_and_incomplete_packages_rejected(tmp_path):
    create_demo_workspace(tmp_path)
    registry = json.loads((tmp_path / "registry.json").read_text())
    registry["datasets"]["synthetic-w1"]["evidence_kind"] = "REAL_DATA"
    (tmp_path / "registry.json").write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="Data Gate"):
        execute_run(RunConfig(dataset_id="synthetic-w1", split_id="synthetic-split", method="iforest"), tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        load_model(tmp_path, NAMES, RunConfig(dataset_id="synthetic-w1", split_id="synthetic-split", method="iforest"))

def test_artifact_rejects_nonminute_timestamp_even_with_matching_digest(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from traffic_anomaly.data.audit import file_sha256
    create_demo_workspace(tmp_path)
    result=execute_run(RunConfig(dataset_id="synthetic-w1",split_id="synthetic-split",method="iforest",window_minutes=3),tmp_path)
    directory=(tmp_path/result.manifest_path).parent
    table=pq.read_table(directory/"scores.parquet")
    times=table.column("timestamp").cast(pa.int64()).to_numpy().copy()
    times[0] += 1
    table=table.set_column(0, "timestamp", pa.array(times,type=pa.timestamp("ns",tz="UTC")))
    pq.write_table(table,directory/"scores.parquet")
    manifest=json.loads((directory/"manifest.json").read_text())
    for entry in manifest["files"]:
        if entry["path"] == "scores.parquet": entry["sha256"]=file_sha256(directory/"scores.parquet")
    (directory/"manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="minute"):
        verify_run(directory)

def refresh_digest(directory, relative):
    from traffic_anomaly.data.audit import file_sha256
    path=directory/"manifest.json"
    manifest=json.loads(path.read_text())
    for entry in manifest["files"]:
        if entry["path"]==relative: entry["sha256"]=file_sha256(directory/relative)
    path.write_text(json.dumps(manifest))

@pytest.mark.parametrize("mutation", ["threshold", "metrics", "detector"])
def test_reject_cross_file_mixed_bundle_before_model_load(tmp_path, mutation):
    from traffic_anomaly.artifacts import write_table
    create_demo_workspace(tmp_path)
    config=RunConfig(dataset_id="synthetic-w1",split_id="synthetic-split",method="iforest",window_minutes=3,model={"n_estimators":3})
    result=execute_run(config,tmp_path)
    directory=(tmp_path/result.manifest_path).parent
    if mutation == "detector":
        path=directory/"model/detector.json"
        data=json.loads(path.read_text());data["seed"]=999;data["config"]["n_estimators"]=999
        path.write_text(json.dumps(data));refresh_digest(directory,"model/detector.json")
    else:
        rows=read_table(directory/"scores.parquet",SCORES_SCHEMA,SeriesPoint)
        row=next(row for row in rows if row["valid"])
        if mutation == "threshold":
            row["threshold"] += 100
            row["alarm"] = row["score"] > row["threshold"]
        else:
            row["score"]=row["threshold"]-1 if row["alarm"] else row["threshold"]+1
            row["alarm"]=not row["alarm"]
        write_table(directory/"scores.parquet",rows,SCORES_SCHEMA);refresh_digest(directory,"scores.parquet")
    with pytest.raises(ValueError,match="threshold|evaluation|detector"):
        load_model(directory,NAMES,config)
