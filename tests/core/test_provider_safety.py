"""Corrupted provider metadata/labels must not become plausible counts."""
import numpy as np
import csv
import pytest
from scipy.io import savemat
from traffic_anomaly.contracts import LABEL_NAMES
from traffic_anomaly.data.provider import profile_provider


def payload():
    return dict(X=np.ones((2, 134)), test=np.ones((2, 134)),
        Y=np.zeros((2, 8)), Yt=np.zeros((2, 8)),
        obs_l=np.array(['201603190000', '201603190001'], object),
        obs_lt=np.array(['201607280046', '201607280047'], object),
        var_l=np.array([f'f{i}' for i in range(134)], object),
        yvar_l=np.array(LABEL_NAMES, object))


@pytest.mark.parametrize('value', [np.nan, -1, .5, np.inf])
def test_invalid_labels_are_unknown_never_attack_or_background(tmp_path, value):
    values = payload(); values['Y'][0, 0] = value
    path = tmp_path / 'v3.mat'; savemat(path, values)
    report = profile_provider(path)
    part = report['train']
    assert part['normal_candidates'] == 1
    assert part['attack_minutes'] == part['background_only_minutes'] == 0
    assert part['label_unavailable_minutes'] == 1
    assert part['valid_labeled_minutes'] == 1
    assert sum(part[k] for k in ('normal_candidates', 'attack_minutes',
                               'background_only_minutes', 'label_unavailable_minutes')) == part['rows']
    assert report['structure_trusted'] is False


def test_provider_rejects_wrong_label_order_and_width(tmp_path):
    values = payload(); values['yvar_l'] = np.roll(values['yvar_l'], 1)
    path = tmp_path / 'v3.mat'; savemat(path, values)
    with pytest.raises(ValueError, match='label order'):
        profile_provider(path)
    values = payload(); values['X'] = values['X'][:, :133]
    savemat(path, values)
    with pytest.raises(ValueError, match='134'):
        profile_provider(path)


def test_author_partition_is_not_a_frozen_project_split(tmp_path):
    values = payload()
    values['Yt'][:, 4] = 1
    values['Yt'][0, :2] = 1
    path = tmp_path / 'v3.mat'; savemat(path, values)
    report = profile_provider(path)
    part = report['test']
    assert part['normal_candidates'] == 0
    assert part['attack_minutes'] == part['background_only_minutes'] == 1
    assert part['attack_background_overlap_minutes'] == 1
    assert part['multiple_primary_attack_minutes'] == 1
    assert part['per_label_positive_minutes']['dos'] == 1
    assert part['valid_minutes'] == 2
    for name in ('train', 'validation', 'calibration', 'test'):
        span = report['project_splits'][name]
        assert span['status'] == 'NOT_DEFINED'
        assert span['rows'] is None and span['normal_candidates'] is None
        assert span['per_label_positive_minutes'] is None
        assert span['unmatched_feature_label_rows'] is None
        assert span['invalid_count_rows'] is None
    assert report['source_timezone'] is None and report['gate_passed'] is False

def test_csv_feature_label_join_mismatches_are_counted(tmp_path):
    values = payload(); path = tmp_path / 'v3.mat'; savemat(path, values)
    for part, xk, yk, tk in (('train', 'X', 'Y', 'obs_l'), ('test', 'test', 'Yt', 'obs_lt')):
        for prefix, key, nk in (('X', xk, 'var_l'), ('Y', yk, 'yvar_l')):
            clocks = list(values[tk])
            if part == 'test' and prefix == 'Y':
                clocks[-1] = '201607280048'
            with (tmp_path / f'UGR16v3.{prefix}{part}.csv').open('w', newline='') as f:
                writer = csv.writer(f); writer.writerow(['Row', *values[nk]])
                for stamp, row in zip(clocks, values[key]): writer.writerow([stamp, *(int(v) for v in row)])
    report = profile_provider(path, tmp_path)
    assert report['test']['unmatched_feature_label_rows'] == 2
    assert report['structure_trusted'] is False
