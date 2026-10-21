import csv
import numpy as np
from scipy.io import savemat
from traffic_anomaly.data.provider import profile_provider

def test_provider_profile_detects_clock_gaps_and_csv_alignment(tmp_path):
    values = {"X": np.ones((3,134), np.int32), "test": np.ones((2,134), np.int32),
        "Y": np.zeros((3,8), np.int32), "Yt": np.zeros((2,8), np.int32),
        "obs_l": np.array(["201603190000","201603190001","201603190003"], object),
        "obs_lt": np.array(["201607280046","201607280048"], object),
        "var_l": np.array([f"f{i}" for i in range(134)], object),
        "yvar_l": np.array(["dos","scan11","scan44","botnet","blacklist","udpscan","sshscan","spam"], object)}
    savemat(tmp_path / "v3.mat", values)
    report = profile_provider(tmp_path / "v3.mat")
    assert report["gate_passed"] is False
    assert report["train"]["missing_minutes"] == 1
    assert report["test"]["missing_minutes"] == 1
    assert report["source_timezone"] is None
    assert report["train"]["rows"] == 3

def test_provider_csv_row_column_is_clock_not_feature(tmp_path):
    values = {"X": np.ones((2,134), np.int32), "test": np.ones((2,134), np.int32),
        "Y": np.zeros((2,8), np.int32), "Yt": np.zeros((2,8), np.int32),
        "obs_l": np.array(["201603190000","201603190001"], object),
        "obs_lt": np.array(["201607280046","201607280048"], object),
        "var_l": np.array([f"f{i}" for i in range(134)], object),
        "yvar_l": np.array(["dos","scan11","scan44","botnet","blacklist","udpscan","sshscan","spam"], object)}
    savemat(tmp_path / "v3.mat", values)
    for part, xk, yk, tk in (("train","X","Y","obs_l"),("test","test","Yt","obs_lt")):
        for prefix, vk, nk in (("X",xk,"var_l"),("Y",yk,"yvar_l")):
            with (tmp_path / f"UGR16v3.{prefix}{part}.csv").open("w", newline="") as f:
                writer=csv.writer(f); writer.writerow(["Row", *values[nk]])
                for stamp, row in zip(values[tk], values[vk]): writer.writerow([stamp,*row])
    report=profile_provider(tmp_path / "v3.mat", tmp_path)
    assert report["train"]["X_csv_mat_equal"] is True
    assert report["test"]["Y_csv_clock_matches"] is True
    assert any("No normal" in reason for reason in report["blockers"]) is False

def test_zero_normal_test_blocks_false_positive_evaluation(tmp_path):
    values = {"X": np.ones((2,134), np.int32), "test": np.ones((2,134), np.int32),
        "Y": np.zeros((2,8), np.int32), "Yt": np.ones((2,8), np.int32),
        "obs_l": np.array(["201603190000","201603190001"], object),
        "obs_lt": np.array(["201607280046","201607280048"], object),
        "var_l": np.array([f"f{i}" for i in range(134)], object),
        "yvar_l": np.array(["dos","scan11","scan44","botnet","blacklist","udpscan","sshscan","spam"], object)}
    savemat(tmp_path / "v3.mat", values)
    report=profile_provider(tmp_path / "v3.mat")
    assert any("No normal" in reason for reason in report["blockers"])
