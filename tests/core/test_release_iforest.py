"""Hand-valued release IF contract tests; fixture construction performs no preparation."""
from dataclasses import asdict, replace, FrozenInstanceError
from datetime import datetime, timedelta
import builtins
import hashlib
import importlib
import json
import math
import sys
import types

import numpy as np
import pytest

from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
from traffic_anomaly._release_minutes import ReleaseSegment
from traffic_anomaly.release_minute_contract import ReleaseMinutePackageIdentity
from traffic_anomaly.release_inputs import (
    ReleasePreparationConfig, ReleaseInputIdentity, ReleasePreprocessState,
    ReleasePreparedHistory, ReleasePreparedMinutes, ReleaseInputLabels,
    ReleasePolicyQualification,
)
from traffic_anomaly.release_model_inputs import (
    ReleaseModelInputPair, ReleaseModelLabelSidecar, ReleaseModelPopulation,
)

TRAIN = tuple(range(30, 48))
CAL = tuple(range(118, 128))
COMMON = (*range(30, 48), *range(78, 88), *range(118, 128), *range(158, 176))
QUAL = ('train_full_history_normal', 'calibration_full_history_normal',
        'validation_current_normal', 'validation_current_attack', 'validation_current_unknown',
        'test_current_normal', 'test_current_attack', 'test_current_unknown')


def _digest(doc):
    payload = (json.dumps(doc, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':')) + '\n').encode()
    return hashlib.sha256(payload).hexdigest()


def _mask(indices, n=176):
    return tuple(i in indices for i in range(n))


def _case(*, kinds=None, train=TRAIN, cal=CAL, fit=TRAIN,
          invalid_train=False, invalid_first=False):
    # Four hand-chosen segments: 48/40/40/48. First 30 rows of each
    # cannot have a complete 31-minute current-plus-history normal window.
    start = datetime(2026, 1, 1)
    bounds = (0, 48, 88, 128, 176)
    roles = ('train', 'validation', 'calibration', 'test')
    segments = tuple(ReleaseSegment(f's{j}', role, start + timedelta(minutes=a),
                                    start + timedelta(minutes=b))
                     for j, (role, a, b) in enumerate(zip(roles, bounds, bounds[1:])))
    ordinals = (0,) * 48 + (1,) * 40 + (2,) * 40 + (3,) * 48
    stamps = tuple(start + timedelta(minutes=i) for i in range(176))
    valid = tuple(not (invalid_train and i < 48 or invalid_first and i == 0)
                  for i in range(176))
    current = tuple(tuple(float(i) + j / 100 for j in range(13))
                    if valid[i] else (None,) * 13 for i in range(176))
    histories = []
    for window in (15, 30):
        good, reasons = [], []
        for i, ordinal in enumerate(ordinals):
            local = i - bounds[ordinal]
            if invalid_train and ordinal == 0 or invalid_first and i == 0:
                ok, reason = False, 'invalid_input'
            elif invalid_first and ordinal == 0:
                ok = local >= window + 1
                reason = None if ok else 'invalid_input'
            else:
                ok = local >= window
                reason = None if ok else ('warmup' if ordinal == 0 else 'boundary')
            good.append(ok)
            reasons.append(reason)
        residual = tuple(tuple(-float(i) - j / 10 for j in range(13))
                         if good[i] else (None,) * 13 for i in range(176))
        histories.append(ReleasePreparedHistory(window, residual, tuple(good), tuple(reasons)))
    common_indices = COMMON
    if invalid_train:
        common_indices = (*range(78, 88), *range(118, 128), *range(158, 176))
    elif invalid_first:
        common_indices = (*range(31, 48), *range(78, 88), *range(118, 128), *range(158, 176))
    common = _mask(common_indices)
    minutes = ReleasePreparedMinutes(stamps, ordinals, (True,) * 176, current, valid,
        tuple(None if ok else 'nonfinite_transform' for ok in valid), tuple(histories), common)
    if kinds is None:
        kinds = (('normal',) * 3,) * 176
    quals = []
    for column, policy in enumerate(('P_U', 'P_B', 'P_A')):
        masks = [_mask(train), _mask(cal)]
        for role in ('validation', 'test'):
            for kind in ('normal', 'attack', 'unknown'):
                masks.append(tuple(i in common_indices and roles[ordinals[i]] == role
                                   and kinds[i][column] == kind for i in range(176)))
        quals.append(ReleasePolicyQualification(policy, *masks))
    labels = ReleaseInputLabels(('P_U', 'P_B', 'P_A'), kinds, _mask(fit), fit, tuple(quals))
    config = ReleasePreparationConfig(1, 'c17-release-log1p-mad-input-rules-v1',
        G13U_FEATURE_NAMES, (15, 30), 30, 1e-6, 'P_U', 'AUDIT_ONLY')
    state = ReleasePreprocessState((0.,) * 13, (1.,) * 13, len(fit), 30, 'P_U',
        _digest(dict(schema_version=1, minute_count=176, mask=_mask(fit))), 'e' * 64)
    joined = tuple(tuple(c + r if ok else (None,) * 26
                         for c, r, ok in zip(current, h.residual, h.valid)) for h in histories)
    return ReleaseModelInputPair('c17-release-model-input-pair-v1',
        ReleaseMinutePackageIdentity('c17-release-minute-package-v1', 'a' * 64, 'b' * 64, 123),
        ReleaseInputIdentity('c17-release-prepared-input-package-v1', 'c' * 64, 'd' * 64, 456),
        config, _digest(asdict(config)), state, segments,
        tuple(f's{j}' for j in ordinals), tuple(roles[j] for j in ordinals),
        tuple(tuple(float(i + j) for j in range(13)) for i in range(176)),
        minutes, joined[0], joined[1], ReleaseModelLabelSidecar(labels, (False,) * 176),
        ReleaseModelPopulation('P_U', _mask(fit), fit, _mask(train), train, _mask(cal), cal),
        'PACKAGE_INTERNAL_CONSISTENCY_ONLY', 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY',
        'c17-release-91-v1', 'NOT_AUTHENTICATED', 'SOURCE_WALL_CLOCK_COMPLETION_PROXY')


def _forged_identity(value, **changes):
    # Deliberately bypass constructor validation to exercise the consumer boundary.
    forged = object.__new__(type(value))
    for name, original in asdict(value).items():
        object.__setattr__(forged, name, changes.get(name, original))
    return forged


def _api():
    # Keep missing implementation an assertion failure, rather than collection error.
    try:
        return importlib.import_module('traffic_anomaly.release_iforest')
    except ModuleNotFoundError as exc:
        if exc.name != 'traffic_anomaly.release_iforest':
            raise
        pytest.fail('release IF consumer is not implemented')


def _reject(pair, code='INVALID_IF_INPUT', view='current13'):
    api = _api()
    with pytest.raises(api.ReleaseIFError) as error:
        api._validated_inputs(pair, view)
    assert error.value.code == code
    assert str(error.value) == code


def _set(values, index, value):
    return values[:index] + (value,) + values[index + 1:]


def test_hand_fixture_has_31_minute_qualification_and_common_axis():
    api = _api()
    pair = _case()
    for view, width in (('current13', 13), ('h30_26', 26)):
        values = api._validated_inputs(pair, view)
        assert values.train_indices == TRAIN
        assert values.calibration_indices == CAL
        assert values.common_indices == COMMON
        assert values.matrix.shape == (176, width)
    assert pair.population.train_mask[29] is False
    assert pair.population.train_mask[30] is True
    assert len(COMMON) == 56
    # H15 already ready while H30 still in warmup: do not zero both joins.
    assert pair.joined_h15[15] != (None,) * 26
    assert pair.joined_h30[15] == (None,) * 26


@pytest.mark.parametrize('view', [None, [], 'h15_26', 'current134', True])
def test_invalid_view(view):
    _reject(_case(), 'INVALID_IF_ARGUMENTS', view)


@pytest.mark.parametrize('indices', [(30, 30), (31, 30), (True,), (-1,), (176,), (118,)])
def test_train_indices_must_exactly_match_saved_population(indices):
    p = _case()
    _reject(replace(p, population=replace(p.population, train_indices=indices)))


@pytest.mark.parametrize('name', ['policy', 'fit_mask', 'fit_indices', 'train_mask', 'cal_mask',
                                  'role', 'segment_id', 'raw_negative', 'width', 'joined_order',
                                  'joined_value', 'warmup', 'boundary', 'gap', 'invalid_common',
                                  'sidecar', 'profile', 'scope', 'audit'])
def test_rejects_forged_pair_boundaries(name):
    p = _case()
    m = p.prepared_minutes
    if name == 'policy': p = replace(p, population=replace(p.population, policy='P_B'))
    elif name == 'fit_mask': p = replace(p, population=replace(p.population, preprocessing_fit_mask=(True,) * 176))
    elif name == 'fit_indices': p = replace(p, population=replace(p.population, preprocessing_fit_indices=(30,)))
    elif name == 'train_mask': p = replace(p, population=replace(p.population, train_mask=(False,) * 176))
    elif name == 'cal_mask': p = replace(p, population=replace(p.population, calibration_mask=(False,) * 176))
    elif name == 'role': p = replace(p, roles=_set(p.roles, 30, 'test'))
    elif name == 'segment_id': p = replace(p, segment_ids=_set(p.segment_ids, 30, 's1'))
    elif name == 'raw_negative': p = replace(p, raw_values=_set(p.raw_values, 0, (-1.,) * 13))
    elif name == 'width': p = replace(p, prepared_minutes=replace(m, current_values=_set(m.current_values, 30, (1.,) * 12)))
    elif name == 'joined_order': p = replace(p, joined_h30=_set(p.joined_h30, 30, p.joined_h30[30][13:] + p.joined_h30[30][:13]))
    elif name == 'joined_value': p = replace(p, joined_h30=_set(p.joined_h30, 30, (0.,) * 26))
    elif name in ('warmup', 'boundary', 'invalid_common'):
        i = {'warmup': 29, 'boundary': 48, 'invalid_common': 0}[name]
        p = replace(p, prepared_minutes=replace(m, common_valid=_set(m.common_valid, i, True)))
    elif name == 'gap': p = replace(p, prepared_minutes=replace(m, timestamps=_set(m.timestamps, 20, m.timestamps[20] + timedelta(seconds=30))))
    elif name == 'sidecar': p = replace(p, labels=replace(p.labels, definite_attack_present=(0,) * 176))
    elif name == 'profile': p = replace(p, profile_id='other')
    elif name == 'scope': p = replace(p, raw_scope='ACCEPTED')
    elif name == 'audit': p = replace(p, configuration=replace(p.configuration, policy_status='FINAL'))
    _reject(p)


@pytest.mark.parametrize(('field', 'bad'), [
    ('context_sha256', 'A' * 64), ('manifest_sha256', 'z' * 64),
    ('profile_id', 'other'), ('manifest_byte_count', True),
    ('manifest_byte_count', 0), ('manifest_byte_count', 65537),
])
@pytest.mark.parametrize('slot', ['raw_identity', 'prepared_identity'])
def test_identity_structure_is_checked_before_model(slot, field, bad):
    p = _case()
    _reject(replace(p, **{slot: _forged_identity(getattr(p, slot), **{field: bad})}))


@pytest.mark.parametrize('slot', ['raw_identity', 'prepared_identity'])
def test_identity_requires_exact_distinct_dataclass(slot):
    p = _case()
    for bad in ({}, p.prepared_identity if slot == 'raw_identity' else p.raw_identity):
        _reject(replace(p, **{slot: bad}))


@pytest.mark.parametrize('value', ['x', 'A' * 64, 'f' * 64, True])
def test_configuration_hash_must_match_saved_configuration(value):
    _reject(replace(_case(), configuration_sha256=value))


@pytest.mark.parametrize(('index', 'role'), [(30, 'train'), (118, 'calibration'), (158, 'holdout')])
@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_float32_overflow_rejected_across_all_common_populations(index, role, view):
    p = _case()
    m = p.prepared_minutes
    row = (1e39,) + m.current_values[index][1:]
    current = _set(m.current_values, index, row)
    joins = {f'joined_h{h.window}': _set(getattr(p, f'joined_h{h.window}'), index,
                                      row + h.residual[index]) for h in m.histories}
    _reject(replace(p, prepared_minutes=replace(m, current_values=current), **joins),
            'INVALID_INPUT_NUMERIC', view)


@pytest.mark.parametrize(('point', 'kind', 'train', 'cal', 'fit'), [
    (0, 'attack', tuple(range(31, 48)), CAL, tuple(range(31, 48))),
    (0, 'unknown', tuple(range(31, 48)), CAL, tuple(range(31, 48))),
    (88, 'attack', TRAIN, tuple(range(119, 128)), TRAIN),
    (88, 'unknown', TRAIN, tuple(range(119, 128)), TRAIN),
])
def test_history_label_changes_shrink_qualification_without_canceling_common(point, kind, train, cal, fit):
    kinds = _set((('normal',) * 3,) * 176, point, (kind,) * 3)
    # A stale claim is rejected. Correct synchronized masks are accepted.
    _reject(_case(kinds=kinds))
    p = _case(kinds=kinds, train=train, cal=cal, fit=fit)
    values = _api()._validated_inputs(p, 'current13')
    assert values.common_indices == COMMON
    assert values.train_indices == train
    assert values.calibration_indices == cal


def test_population_empty_errors_precede_import_or_construction(monkeypatch):
    api = _api()
    no_train = _case(invalid_train=True, train=())
    kinds = tuple(('attack',) * 3 if 88 <= i < 128 else ('normal',) * 3 for i in range(176))
    no_cal = _case(kinds=kinds, cal=())
    both = replace(no_train, labels=no_cal.labels,
                   population=replace(no_train.population, calibration_mask=(False,) * 176,
                                      calibration_indices=()))
    # Both needs qualification synchronized with the invalid training rows.
    both = replace(both, labels=replace(both.labels, saved=replace(both.labels.saved,
        qualification_masks=tuple(replace(q, train_full_history_normal=(False,) * 176)
                                  for q in both.labels.saved.qualification_masks))))
    attempts = []
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name == 'sklearn' or name.startswith('sklearn.'):
            attempts.append(name)
            raise AssertionError('model import attempted before population validation')
        return original(name, *args, **kwargs)
    with monkeypatch.context() as guard:
        guard.setattr(builtins, '__import__', guarded)
        for pair, code in ((no_train, 'NO_TRAINING_NORMAL'),
                           (no_cal, 'NO_CALIBRATION_NORMAL'), (both, 'NO_TRAINING_NORMAL')):
            with pytest.raises(api.ReleaseIFError, match=f'^{code}$'):
                api.fit_release_iforest(pair, view='current13')
    assert attempts == []


def test_axis_and_segment_resource_limits():
    p = _case()
    _reject(replace(p, prepared_minutes=replace(p.prepared_minutes,
        timestamps=(p.prepared_minutes.timestamps[0],) * 10001)), 'RESOURCE_LIMIT')
    _reject(replace(p, segments=p.segments * 2), 'RESOURCE_LIMIT')


def test_invalid_top_level_and_unknown_error_are_safe():
    _reject(object(), 'INVALID_IF_ARGUMENTS')
    assert str(_api().ReleaseIFError('secret/path')) == 'INVALID_IF_INPUT'


def _spy(monkeypatch, output=None, failure=None):
    """Replace only the slow estimator; all consumer checks/calibration stay real."""
    seen = {'construct': [], 'fit': [], 'score': []}
    class Forest:
        def __init__(self, **kwargs):
            seen['construct'].append(kwargs)
            if failure == 'construct':
                raise RuntimeError('private/path')
        def fit(self, values):
            seen['fit'].append(values.copy())
            if failure == 'fit':
                raise RuntimeError('private/path')
            return self
        def score_samples(self, values):
            seen['score'].append(values.copy())
            if failure == 'score':
                raise RuntimeError('private/path')
            return -values[:, 0].astype(np.float64) if output is None else output(values)
    root = types.ModuleType('sklearn')
    root.__path__ = []
    ensemble = types.ModuleType('sklearn.ensemble')
    ensemble.IsolationForest = Forest
    root.ensemble = ensemble
    monkeypatch.setitem(sys.modules, 'sklearn', root)
    monkeypatch.setitem(sys.modules, 'sklearn.ensemble', ensemble)
    return seen


@pytest.mark.parametrize(('view', 'width'), [('current13', 13), ('h30_26', 26)])
def test_model_only_fits_model_train_and_scores_common_preserving_identity(monkeypatch, view, width):
    api = _api()
    p = _case(invalid_first=True, train=tuple(range(31, 48)))
    seen = _spy(monkeypatch)
    result = api.fit_release_iforest(p, view=view)
    source = p.prepared_minutes.current_values if width == 13 else p.joined_h30
    assert len(seen['fit']) == len(seen['score']) == len(seen['construct']) == 1
    np.testing.assert_array_equal(seen['fit'][0], np.asarray([source[i] for i in range(31, 48)], np.float32))
    common = (*range(31, 48), *range(78, 88), *range(118, 128), *range(158, 176))
    np.testing.assert_array_equal(seen['score'][0], np.asarray([source[i] for i in common], np.float32))
    assert seen['fit'][0].shape == (17, width)
    assert seen['construct'][0] == dict(n_estimators=16, max_samples=17, max_features=1.0,
        bootstrap=False, contamination='auto', random_state=42, n_jobs=1)
    assert result.preprocessing_fit_indices == TRAIN
    assert result.train_indices == tuple(range(31, 48))
    assert result.calibration_indices == CAL
    assert result.raw_identity is p.raw_identity
    assert result.prepared_identity is p.prepared_identity
    assert result.configuration_sha256 == p.configuration_sha256
    assert len(result.scores) == len(result.predictions) == len(result.scored_mask) == 176
    for i in range(176):
        if i in common:
            assert result.scores[i] == float(i)
            assert result.predictions[i] is (result.scores[i] > result.threshold)
        else:
            assert result.scores[i] is result.predictions[i] is None
        assert result.scored_mask[i] is (i in common)
    assert not hasattr(result, 'model')
    for obj, name in ((result, 'threshold'), (result.configuration, 'n_jobs')):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, None)


def test_consumer_does_not_prepare_or_access_saved_packages(monkeypatch):
    p = _case()
    api = _api()
    _spy(monkeypatch)
    attempted = []
    def forbidden(*args, **kwargs):
        attempted.append(True)
        raise AssertionError('external action attempted')
    targets = {
        'traffic_anomaly.release_inputs': ('prepare_release_inputs', '_fit_state',
            '_fit_statistics', '_transform', '_history', 'verify_release_input_derivation'),
        'traffic_anomaly.release_input_package': ('load_release_input_package', 'save_release_input_package'),
        'traffic_anomaly.release_minute_package': ('load_release_minute_package', 'save_release_minute_package'),
    }
    for module_name, names in targets.items():
        module = importlib.import_module(module_name)
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    # Narrow estimator stub avoids sklearn import I/O. This guards consumer file access,
    # not arbitrary interpreter imports, pytest capture, or sklearn's loading machinery.
    original_open = builtins.open
    def guarded(path, *args, **kwargs):
        if str(path).endswith(('.csv', '.json', '.zip')):
            return forbidden(path, *args, **kwargs)
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded)
    result = api.fit_release_iforest(p, view='current13')
    assert len(result.train_indices) == 18
    assert attempted == []


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_holdout_labels_preserve_numeric_outputs_and_each_input_identity(monkeypatch, view):
    api = _api()
    first = _case()
    kinds = _set(first.labels.saved.label_kinds, 158, ('attack',) * 3)
    second = _case(kinds=kinds)
    second = replace(second, raw_identity=replace(second.raw_identity, manifest_sha256='2' * 64),
                     prepared_identity=replace(second.prepared_identity, manifest_sha256='3' * 64))
    _spy(monkeypatch)
    a = api.fit_release_iforest(first, view=view)
    b = api.fit_release_iforest(second, view=view)
    for name in ('scores', 'predictions', 'scored_mask', 'train_indices', 'calibration_indices',
                 'preprocessing_fit_indices', 'threshold', 'configuration'):
        assert getattr(a, name) == getattr(b, name)
    assert a.raw_identity is first.raw_identity and b.raw_identity is second.raw_identity
    assert a.prepared_identity is first.prepared_identity and b.prepared_identity is second.prepared_identity
    assert a.configuration_sha256 == first.configuration_sha256
    assert b.configuration_sha256 == second.configuration_sha256


def test_holdout_numeric_changes_do_not_touch_fit_or_calibration(monkeypatch):
    api = _api()
    p = _case()
    seen = _spy(monkeypatch)
    a = api.fit_release_iforest(p, view='current13')
    row = (999.,) * 13
    second = replace(p, prepared_minutes=replace(p.prepared_minutes,
        current_values=_set(p.prepared_minutes.current_values, 158, row)),
        joined_h15=_set(p.joined_h15, 158, row + p.prepared_minutes.histories[0].residual[158]),
        joined_h30=_set(p.joined_h30, 158, row + p.prepared_minutes.histories[1].residual[158]))
    b = api.fit_release_iforest(second, view='current13')
    np.testing.assert_array_equal(seen['fit'][0], seen['fit'][1])
    assert a.threshold == b.threshold
    assert a.scores[158] != b.scores[158]


def test_q99_linear_and_strict_greater_boundaries(monkeypatch):
    api = _api()
    kinds = _set((('normal',) * 3,) * 176, 93, ('attack',) * 3)
    p = _case(kinds=kinds, cal=(124, 125, 126, 127))
    threshold = 3 * .99  # linear rank (n-1)*q = 2.97
    table = {124: 0., 125: 1., 126: 2., 127: 3., 158: threshold,
             159: np.nextafter(threshold, np.inf), 160: np.nextafter(threshold, -np.inf)}
    _spy(monkeypatch, lambda x: -np.array([table.get(int(row[0]), 0.) for row in x]))
    result = api.fit_release_iforest(p, view='current13')
    assert result.threshold == pytest.approx(2.97)
    assert result.predictions[158:161] == (False, True, False)


@pytest.mark.parametrize('single', [False, True])
def test_single_calibration_and_ties_are_valid(monkeypatch, single):
    api = _api()
    p = _case()
    if single:
        kinds = _set(p.labels.saved.label_kinds, 96, ('unknown',) * 3)
        p = _case(kinds=kinds, cal=(127,))
    _spy(monkeypatch, lambda x: np.full(len(x), -1.))
    result = api.fit_release_iforest(p, view='current13')
    assert result.threshold == 1.
    assert all(value is False for value in result.predictions if value is not None)


@pytest.mark.parametrize('bad', ['nan', 'inf', 'matrix', 'short', 'bool', 'complex', 'qoverflow'])
def test_malformed_model_scores_are_controlled(monkeypatch, bad):
    api = _api()
    def output(x):
        n = len(x)
        return {'nan': np.full(n, np.nan), 'inf': np.full(n, np.inf),
            'matrix': np.ones((n, 1)), 'short': np.ones(n - 1),
            'bool': np.ones(n, bool), 'complex': np.ones(n, complex),
            'qoverflow': np.asarray([-1.7e308 if row[0] == 127 else 1.7e308 for row in x])}[bad]
    _spy(monkeypatch, output)
    with pytest.raises(api.ReleaseIFError, match='^INVALID_MODEL_SCORES$'):
        api.fit_release_iforest(_case(), view='current13')


def test_unsigned_scores_convert_before_negation(monkeypatch):
    api = _api()
    _spy(monkeypatch, lambda x: np.ones(len(x), dtype=np.uint8))
    result = api.fit_release_iforest(_case(), view='current13')
    assert result.scores[30] == result.threshold == -1.


@pytest.mark.parametrize('stage', ['construct', 'fit', 'score'])
def test_model_failures_do_not_leak_original_messages(monkeypatch, stage):
    api = _api()
    _spy(monkeypatch, failure=stage)
    with pytest.raises(api.ReleaseIFError, match='^MODEL_ERROR$'):
        api.fit_release_iforest(_case(), view='current13')


def test_missing_optional_model_dependency_is_controlled(monkeypatch):
    api = _api()
    original = builtins.__import__
    def no_model(name, *args, **kwargs):
        if name == 'sklearn' or name.startswith('sklearn.'):
            raise ModuleNotFoundError('private/path')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', no_model)
    with pytest.raises(api.ReleaseIFError, match='^MODEL_UNAVAILABLE$'):
        api.fit_release_iforest(_case(), view='current13')


def _result(monkeypatch):
    _spy(monkeypatch)
    return _api().fit_release_iforest(_case(), view='current13')


def test_summary_is_a_bounded_structural_report_with_original_identities(monkeypatch):
    api = _api()
    p = _case()
    _spy(monkeypatch)
    result = api.fit_release_iforest(p, view='current13')
    summary = api.summarize_release_iforest(result)
    assert set(summary) == {'version', 'profile_id', 'status', 'view', 'configuration',
        'raw_identity', 'prepared_identity', 'configuration_sha256', 'minute_counts',
        'threshold', 'calibration', 'limitations'}
    assert summary['status'] == 'ENGINEERING_COMPUTED'
    assert summary['minute_counts'] == dict(total=176, scored=56, training=18,
                                           calibration=10, preprocessing_fit=18)
    for slot in ('raw_identity', 'prepared_identity'):
        assert summary[slot] == asdict(getattr(p, slot))
    assert summary['configuration_sha256'] == p.configuration_sha256
    assert summary['calibration']['quantile'] == .99
    assert summary['calibration']['method'] == 'linear'
    assert summary['calibration']['comparison'] == 'STRICT_GREATER'
    assert summary['calibration']['equal_threshold_count'] == 0
    assert summary['calibration']['above_threshold_count'] == 1
    assert set(summary['limitations']) == {'ENGINEERING_DEFAULTS_ONLY', 'AUDIT_ONLY',
        'NOT_AUTHENTICATED', 'SOURCE_WALL_CLOCK_COMPLETION_PROXY',
        'DERIVATION_REPLAY_NOT_PERFORMED', 'NOT_REESTIMATED', 'EXTERNAL_ACCEPTANCE_NOT_ESTABLISHED'}
    text = json.dumps(summary, allow_nan=False)
    assert all(word not in text for word in ('GATE_PASSED', '"VERIFIED"', '"ACCEPTED"'))
    # A structurally self-consistent altered threshold is not an authenticated Q99 receipt.
    altered = replace(result, threshold=result.threshold - .001)
    assert api.summarize_release_iforest(altered)['threshold'] == altered.threshold
    changed_id = replace(result.raw_identity, manifest_sha256='f' * 64)
    assert api.summarize_release_iforest(replace(result, raw_identity=changed_id))['raw_identity']['manifest_sha256'] == 'f' * 64


@pytest.mark.parametrize('bad', ['prediction', 'threshold_nan', 'threshold_comparison', 'score_inf',
    'missing_score', 'unscored_value', 'mask_int', 'train_duplicate', 'train_bool', 'train_cal',
    'train_fit', 'configuration_type', 'configuration_width', 'configuration_max_samples',
    'configuration_bool', 'identity_dict', 'identity_profile', 'identity_hash', 'identity_count',
    'configuration_hash', 'profile', 'view', 'empty_train', 'empty_cal'])
def test_summary_rejects_inconsistent_or_unsafe_results(monkeypatch, bad):
    api = _api()
    r = _result(monkeypatch)
    if bad == 'prediction': r = replace(r, predictions=_set(r.predictions, 30, True))
    elif bad == 'threshold_nan': r = replace(r, threshold=math.nan)
    elif bad == 'threshold_comparison': r = replace(r, threshold=0.)
    elif bad == 'score_inf': r = replace(r, scores=_set(r.scores, 30, math.inf))
    elif bad == 'missing_score': r = replace(r, scores=_set(r.scores, 30, None))
    elif bad == 'unscored_value': r = replace(r, scores=_set(r.scores, 0, 0.))
    elif bad == 'mask_int': r = replace(r, scored_mask=_set(r.scored_mask, 0, 0))
    elif bad == 'train_duplicate': r = replace(r, train_indices=(30, 30))
    elif bad == 'train_bool': r = replace(r, train_indices=(True,))
    elif bad == 'train_cal': r = replace(r, train_indices=(118,))
    elif bad == 'train_fit': r = replace(r, preprocessing_fit_indices=(31,))
    elif bad == 'configuration_type': r = replace(r, configuration=asdict(r.configuration))
    elif bad == 'configuration_width': r = replace(r, configuration=replace(r.configuration, input_width=26))
    elif bad == 'configuration_max_samples': r = replace(r, configuration=replace(r.configuration, max_samples=1))
    elif bad == 'configuration_bool': r = replace(r, configuration=replace(r.configuration, bootstrap=0))
    elif bad == 'identity_dict': r = replace(r, raw_identity=asdict(r.raw_identity))
    elif bad == 'identity_profile': r = replace(r, prepared_identity=replace(r.prepared_identity, profile_id='other'))
    elif bad == 'identity_hash': r = replace(r, raw_identity=_forged_identity(r.raw_identity, context_sha256='G' * 64))
    elif bad == 'identity_count': r = replace(r, prepared_identity=replace(r.prepared_identity, manifest_byte_count=True))
    elif bad == 'configuration_hash': r = replace(r, configuration_sha256='X' * 64)
    elif bad == 'profile': r = replace(r, profile_id='VERIFIED')
    elif bad == 'view': r = replace(r, view='h15_26')
    elif bad == 'empty_train': r = replace(r, train_indices=())
    elif bad == 'empty_cal': r = replace(r, calibration_indices=())
    with pytest.raises(api.ReleaseIFError, match='^INVALID_IF_RESULT$'):
        api.summarize_release_iforest(r)


def test_summary_allows_preprocessing_fit_minutes_outside_scored_axis(monkeypatch):
    api = _api()
    p = _case(invalid_first=True, train=tuple(range(31, 48)))
    _spy(monkeypatch)
    r = api.fit_release_iforest(p, view='current13')
    assert r.scored_mask[30] is False
    assert api.summarize_release_iforest(r)['minute_counts']['preprocessing_fit'] == 18


def test_non_axis_upstream_resource_error_remains_invalid_input():
    p = _case()
    # n_samples_seen is a malformed saved state, not an axis/segment resource limit.
    _reject(replace(p, preprocessing=replace(p.preprocessing, n_samples_seen=177)))


def test_invalid_prepared_input_cannot_forge_common():
    p = _case(invalid_first=True, train=tuple(range(31, 48)))
    _reject(replace(p, prepared_minutes=replace(p.prepared_minutes,
        common_valid=_set(p.prepared_minutes.common_valid, 0, True))))


def test_upstream_axis_expansion_over_limit_is_resource_limit():
    p = _case()
    first = p.segments[0]
    oversized = replace(first, end=first.start + timedelta(minutes=10001))
    _reject(replace(p, segments=(oversized,)), 'RESOURCE_LIMIT')


def test_invalid_numeric_input_precedes_estimator_construction_and_import(monkeypatch):
    api = _api()
    p = _case()
    m = p.prepared_minutes
    row = (1e39,) * 13
    p = replace(p, prepared_minutes=replace(m, current_values=_set(m.current_values, 158, row)),
        joined_h15=_set(p.joined_h15, 158, row + m.histories[0].residual[158]),
        joined_h30=_set(p.joined_h30, 158, row + m.histories[1].residual[158]))
    attempts = []
    original = builtins.__import__
    def guard(name, *args, **kwargs):
        if name == 'sklearn' or name.startswith('sklearn.'):
            attempts.append(name)
            raise AssertionError('model loaded before validation')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guard)
    with pytest.raises(api.ReleaseIFError, match='^INVALID_INPUT_NUMERIC$'):
        api.fit_release_iforest(p, view='current13')
    assert attempts == []


def test_keyboard_interrupt_is_not_converted_to_model_error(monkeypatch):
    api = _api()
    def interrupted(values):
        raise KeyboardInterrupt
    _spy(monkeypatch, interrupted)
    with pytest.raises(KeyboardInterrupt):
        api.fit_release_iforest(_case(), view='current13')


@pytest.mark.parametrize('bad', ['labels_type', 'fit_indices_type', 'fit_indices_length'])
def test_saved_fit_indices_rejected_before_shared_content_traversal(monkeypatch, bad):
    api = _api()
    p = _case()
    labels = p.labels.saved
    if bad == 'labels_type':
        labels = asdict(labels)
    elif bad == 'fit_indices_type':
        labels = replace(labels, fit_indices=list(labels.fit_indices))
    else:
        # Every integer is valid, but an n+1 tuple is impossible on this axis.
        labels = replace(labels, fit_indices=(30,) * (len(p.prepared_minutes.timestamps) + 1))
    p = replace(p, labels=replace(p.labels, saved=labels))
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('shared helper called before bounded label precheck')
    monkeypatch.setattr(api, '_validate_content', forbidden)
    _reject(p)
    assert attempts == []
