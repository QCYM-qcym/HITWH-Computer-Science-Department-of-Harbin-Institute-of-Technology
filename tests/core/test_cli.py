import json
import subprocess
import sys
from traffic_anomaly.contracts import RunConfig

def test_cli_demo_run_score_verify_and_refuse_overwrite(tmp_path):
    base = [sys.executable, "-m", "traffic_anomaly.cli"]
    def run(*args):
        return subprocess.run([*base,*map(str,args)], text=True, capture_output=True)
    assert run("demo", "--workspace", tmp_path).returncode == 0
    assert run("demo", "--workspace", tmp_path).returncode != 0
    config = RunConfig(dataset_id="synthetic-w1", split_id="synthetic-split", method="iforest", window_minutes=3,
                       model={"n_estimators": 5, "max_samples": 16})
    path=tmp_path/"config.json"; path.write_text(config.model_dump_json())
    r=run("run","--config",path,"--workspace",tmp_path)
    assert r.returncode == 0, r.stderr
    result=json.loads(r.stdout)
    directory=(tmp_path/result["manifest_path"]).parent
    assert run("verify","--run",directory).returncode == 0
    assert run("score","--model",directory/"model","--config",path,"--workspace",tmp_path).returncode == 0
