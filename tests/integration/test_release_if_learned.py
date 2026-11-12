"""Two real source-fixture fits and independent saved numerical replay.

This hand-declared pair is N176/common55/train17/calibration4/preprocessing18.
It does not load/authenticate raw or prepared packages and is not installed A.
There is exactly one real fresh operation per view in this file, without retry.
"""
from dataclasses import asdict
from functools import wraps
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


_COMMON = (*range(31, 48), *range(78, 88), *range(118, 128), *range(158, 176))
_TRAIN = tuple(range(31, 48))
_CALIBRATION = (124, 125, 126, 127)
_PREPROCESSING = tuple(range(30, 48))


_REPLAY_CHILD = r'''
import builtins, importlib, json, sys, sysconfig
from pathlib import Path

models = {'sklearn', 'joblib', 'torch', 'cloudpickle'}
assert not any(name.split('.')[0] in models | {'numpy', 'pickle'} for name in sys.modules)
attempts, bootstrap_pickle = [], []
phase = 'numpy-bootstrap'
original_import = builtins.__import__
original_module = importlib.import_module
def forbidden(label):
    def blocked(*args, **kwargs):
        attempts.append(label)
        raise AssertionError('forbidden operation: ' + label)
    return blocked
def check(name):
    root = name.lstrip('.').split('.')[0]
    if root in models or root == 'pickle' and phase != 'numpy-bootstrap':
        forbidden('import:' + name)()
    if root == 'pickle':
        bootstrap_pickle.append(name)
def guarded_import(name, *args, **kwargs):
    check(name)
    return original_import(name, *args, **kwargs)
def guarded_module(name, *args, **kwargs):
    check(name)
    return original_module(name, *args, **kwargs)
builtins.__import__ = guarded_import
importlib.import_module = guarded_module

# Dependency setup allows NumPy's observed stdlib pickle import, with models
# blocked throughout. Product replay below has strict pickle fences as well.
import numpy as np
assert np.__version__ == '2.5.4'
assert bootstrap_pickle and 'pickle' in sys.modules
pickle_module = sys.modules['pickle']
assert Path(pickle_module.__file__).name == 'pickle.py'
assert Path(pickle_module.__file__).parent == Path(sysconfig.get_path('stdlib'))
phase = 'guarded-replay'
for name in ('load', 'loads', 'dump', 'dumps'):
    setattr(pickle_module, name, forbidden('pickle.' + name))

from tests.core.release_if_result_cases import hand_pair
from traffic_anomaly import release_if_learned as operation
from traffic_anomaly import release_if_learned_package as learned_disk
from traffic_anomaly import release_if_result_package as result_disk
from traffic_anomaly import release_if_result_contract as saved
from traffic_anomaly import iforest_numeric_state as p1
from traffic_anomaly import release_iforest as old
from traffic_anomaly import release_inputs as preparation
from traffic_anomaly import release_input_package as prepared_disk
from traffic_anomaly import release_minute_package as raw_disk
from traffic_anomaly.evaluation import calibration

for owner, names in (
    (operation, ('fit_release_iforest_learned', '_models')),
    (old, ('fit_release_iforest', '_compute')),
    (preparation, ('prepare_release_inputs', 'verify_release_input_derivation')),
    (prepared_disk, ('load_release_input_package',)),
    (raw_disk, ('load_release_minute_package',)),
):
    for name in names:
        setattr(owner, name, forbidden(owner.__name__ + '.' + name))

pair = hand_pair()
common = (*range(31,48), *range(78,88), *range(118,128), *range(158,176))
assert len(pair.prepared_minutes.common_valid) == 176
assert tuple(i for i, ok in enumerate(pair.prepared_minutes.common_valid) if ok) == common
assert pair.population.train_indices == tuple(range(31,48))
assert pair.population.calibration_indices == (124,125,126,127)
assert pair.population.preprocessing_fit_indices == tuple(range(30,48))

score_calls, replay_calibration, codec_calibration = [], [], []
real_score, real_calibrate = p1.score_iforest_numeric_state, calibration.calibrate
def score(state, matrix):
    values = real_score(state, matrix)
    score_calls.append((state.input_width, values))
    assert matrix.shape == (55, state.input_width) and matrix.dtype == np.dtype('float32')
    return values
def replay_q99(values, *args, **kwargs):
    replay_calibration.append(tuple(values))
    return real_calibrate(values, *args, **kwargs)
def codec_q99(values, *args, **kwargs):
    codec_calibration.append(tuple(values))
    return real_calibrate(values, *args, **kwargs)
p1.score_iforest_numeric_state = score
calibration.calibrate = replay_q99
saved.calibrate = codec_q99

root = Path(sys.argv[1])
reports = []
for view, width in (('current13',13), ('h30_26',26)):
    result = result_disk.load_release_if_result_package(root / view / 'result')
    learned = learned_disk.load_release_if_learned_package(root / view / 'learned')
    report = operation.replay_release_iforest_learned(learned, pair, result)
    values = score_calls[-1][1]
    assert len(values) == 55
    assert tuple(value.hex() for value in values) == tuple(result.result.scores[i].hex() for i in common)
    by_index = dict(zip(common, values, strict=True))
    selected = tuple(by_index[i] for i in (124,125,126,127))
    threshold = float(np.quantile(np.asarray(selected, dtype=np.float64), 0.99, method='linear'))
    assert threshold.hex() == result.result.threshold.hex()
    assert result.result.predictions == tuple(by_index[i] > threshold if i in by_index else None for i in range(176))
    assert all(result.result.scores[i] is None and result.result.predictions[i] is None
               for i in range(176) if i not in by_index)
    assert replay_calibration[-1] == selected
    assert (report.scored_count, report.calibration_count) == (55,4)
    assert (report.score_replay, report.calibration_replay, report.prediction_replay) == ('MATCHED',)*3
    assert report.scope == 'EXPLICIT_INPUT_NUMERICAL_REPLAY_ONLY'
    assert report.source_authentication == 'NOT_AUTHENTICATED'
    assert report.derivation_replay == 'NOT_PERFORMED'
    assert report.learned_identity == learned.identity
    assert report.result_identity == learned.context.result_identity
    reports.append({'view':view, 'score_hex':[value.hex() for value in values],
                    'q99_hex':threshold.hex(), 'scored_count':55, 'calibration_count':4})
assert len(score_calls) == 2 and sum(len(values) for _,values in score_calls) == 110
assert len(replay_calibration) == 2 and sum(map(len,replay_calibration)) == 8
assert codec_calibration and all(len(values) == 4 for values in codec_calibration)
assert attempts == []
assert not any(name.split('.')[0] in models for name in sys.modules)
print(json.dumps({'status':'SOURCE_REPLAY_MATCHED', 'views':reports,
    'model_imports':0, 'model_calls':0, 'p1_calls':2, 'score_values':110,
    'replay_calibration_rows':8, 'codec_calibration_calls':len(codec_calibration),
    'numpy_bootstrap_pickle_imports':bootstrap_pickle,
    'pickle_operation_attempts':0}, sort_keys=True))
'''


def test_two_real_views_saved_and_independent_moved_replay(tmp_path, monkeypatch):
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from tests.core.release_if_result_cases import hand_pair
    from traffic_anomaly import release_if_learned as operation
    from traffic_anomaly import release_if_learned_package as learned_disk
    from traffic_anomaly import release_if_result_package as result_disk
    from traffic_anomaly import release_if_result_contract as saved
    from traffic_anomaly import iforest_numeric_state as p1
    from traffic_anomaly import release_iforest as old
    from traffic_anomaly import release_inputs as preparation
    from traffic_anomaly.evaluation import calibration

    pair = hand_pair()
    assert len(pair.prepared_minutes.common_valid) == 176
    assert tuple(i for i, ok in enumerate(pair.prepared_minutes.common_valid) if ok) == _COMMON
    assert (pair.population.train_indices, pair.population.calibration_indices,
            pair.population.preprocessing_fit_indices) == (_TRAIN, _CALIBRATION, _PREPROCESSING)
    assert len(_COMMON) == 55 and pair.prepared_minutes.common_valid[30] is False

    records, p1_scores, model_calibration, codec_calibration = [], [], [], []
    forbidden_attempts = []
    original_init, original_fit, original_score = IsolationForest.__init__, IsolationForest.fit, IsolationForest.score_samples
    real_p1, real_make, real_calibrate = p1.score_iforest_numeric_state, saved.make_release_if_result_package, calibration.calibrate

    @wraps(original_init)
    def constructed(self, *args, **kwargs):
        records.append({'instance_id': id(self), 'fits': 0, 'score_calls': 0})
        return original_init(self, *args, **kwargs)

    @wraps(original_fit)
    def fitted(self, matrix, *args, **kwargs):
        record = records[-1]
        assert record['instance_id'] == id(self)
        record['fits'] += 1
        record['train_shape'] = list(matrix.shape)
        assert matrix.shape == (17, 13 if len(records) == 1 else 26)
        assert type(matrix) is np.ndarray and matrix.dtype == np.dtype('float32')
        return original_fit(self, matrix, *args, **kwargs)

    @wraps(original_score)
    def scored(self, matrix, *args, **kwargs):
        record = records[-1]
        assert record['instance_id'] == id(self) and record['fits'] == 1
        record['score_calls'] += 1
        assert matrix.shape == (55, 13 if len(records) == 1 else 26)
        returned = original_score(self, matrix, *args, **kwargs)
        # Preserve the estimator's original array before returning to product
        # result formation; only primitive copies enter diagnostic artifacts.
        record['original_hex'] = [(-float(value)).hex() for value in returned.copy()]
        return returned

    def numeric_score(state, matrix):
        values = real_p1(state, matrix)
        p1_scores.append({'width':state.input_width, 'score_hex':[value.hex() for value in values]})
        return values

    def made(explicit_pair, result):
        assert records[-1]['score_calls'] == 1
        assert [result.scores[i].hex() for i in _COMMON] == records[-1]['original_hex']
        return real_make(explicit_pair, result)

    def model_q99(values, *args, **kwargs):
        model_calibration.append(tuple(values))
        return real_calibrate(values, *args, **kwargs)

    def codec_q99(values, *args, **kwargs):
        codec_calibration.append(tuple(values))
        return real_calibrate(values, *args, **kwargs)

    def forbidden(*args, **kwargs):
        forbidden_attempts.append('old-fit-or-preparation')
        raise AssertionError('old fit or preparation is outside this source integration')

    monkeypatch.setattr(IsolationForest, '__init__', constructed)
    monkeypatch.setattr(IsolationForest, 'fit', fitted)
    monkeypatch.setattr(IsolationForest, 'score_samples', scored)
    monkeypatch.setattr(p1, 'score_iforest_numeric_state', numeric_score)
    monkeypatch.setattr(saved, 'make_release_if_result_package', made)
    monkeypatch.setattr(calibration, 'calibrate', model_q99)
    monkeypatch.setattr(saved, 'calibrate', codec_q99)
    monkeypatch.setattr(old, 'fit_release_iforest', forbidden)
    monkeypatch.setattr(old, '_compute', forbidden)
    monkeypatch.setattr(preparation, 'prepare_release_inputs', forbidden)
    monkeypatch.setattr(preparation, 'verify_release_input_derivation', forbidden)

    saved_root = tmp_path / 'saved'
    saved_root.mkdir()
    try:
        for ordinal, (view, width) in enumerate((('current13',13), ('h30_26',26))):
            root = saved_root / view
            root.mkdir()
            run = operation.fit_release_iforest_learned(pair, view=view)
            result, learned = run.result_package, run.learned_package
            assert len(records) == ordinal + 1
            assert records[-1]['fits'] == records[-1]['score_calls'] == 1
            assert p1_scores[-1]['score_hex'] == records[-1]['original_hex']
            assert len(p1_scores[-1]['score_hex']) == 55 and p1_scores[-1]['width'] == width
            assert len(learned.state.trees) == 16 and learned.state.max_samples == 17
            assert all(len(tree.nodes) <= 33 for tree in learned.state.trees)
            values = result.result.scores
            selected = tuple(values[i] for i in _CALIBRATION)
            threshold = float(np.quantile(np.asarray(selected, dtype=np.float64), 0.99, method='linear'))
            assert threshold.hex() == result.result.threshold.hex()
            assert model_calibration[-1] == selected
            assert result.result.predictions == tuple(value > threshold if value is not None else None for value in values)
            assert tuple(i for i, value in enumerate(values) if value is not None) == _COMMON
            assert learned.context.train_count == 17 and learned.context.calibration_count == 4
            assert learned.context.preprocessing_fit_count == 18
            assert asdict(learned.context.result_identity) == asdict(result.identity)
            assert result_disk.save_release_if_result_package(result, root / 'result') == result.identity
            assert learned_disk.save_release_if_learned_package(learned, root / 'learned') == learned.identity
            assert result_disk.load_release_if_result_package(root / 'result') == result
            assert learned_disk.load_release_if_learned_package(root / 'learned') == learned
    finally:
        (tmp_path / 'fit-diagnostics.json').write_text(json.dumps({'records':records,
            'p1_scores':p1_scores, 'model_calibration_calls':len(model_calibration),
            'codec_calibration_calls':len(codec_calibration)}, sort_keys=True), encoding='utf-8')

    assert len(records) == 2 and sum(record['fits'] for record in records) == 2
    assert sum(record['score_calls'] for record in records) == 2
    assert len(p1_scores) == 2 and sum(len(row['score_hex']) for row in p1_scores) == 110
    assert len(model_calibration) == 2 and sum(map(len,model_calibration)) == 8
    assert codec_calibration and all(len(values) == 4 for values in codec_calibration)
    assert forbidden_attempts == []
    moved = tmp_path / 'moved'
    shutil.copytree(saved_root, moved)
    saved_root.rename(tmp_path / 'old-location')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    child = subprocess.run([sys.executable, '-B', '-c', _REPLAY_CHILD, str(moved)],
                           capture_output=True, timeout=60, env=env)
    (tmp_path / 'replay.stdout').write_bytes(child.stdout)
    (tmp_path / 'replay.stderr').write_bytes(child.stderr)
    assert child.returncode == 0, (child.stdout + child.stderr)[:8192]
    receipt = json.loads(child.stdout)
    assert receipt['status'] == 'SOURCE_REPLAY_MATCHED'
    assert (receipt['score_values'], receipt['replay_calibration_rows']) == (110,8)
    assert receipt['model_imports'] == receipt['model_calls'] == receipt['pickle_operation_attempts'] == 0
    assert receipt['numpy_bootstrap_pickle_imports']
    assert [row['score_hex'] for row in receipt['views']] == [row['score_hex'] for row in p1_scores]
