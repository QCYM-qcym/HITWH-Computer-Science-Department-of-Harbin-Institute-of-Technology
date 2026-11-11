"""Fixed-prediction test-minute arithmetic, independent literal expectations."""
from dataclasses import asdict, replace
import builtins
import importlib
import io
import json
import os
from pathlib import Path

import numpy as np
import pytest

from tests.core.release_if_evaluation_cases import sealed_evaluation_case


def api():
    try:
        module = importlib.import_module('traffic_anomaly.release_if_evaluation')
    except ModuleNotFoundError as error:
        if error.name != 'traffic_anomaly.release_if_evaluation':
            raise
        pytest.fail('pure saved-prediction evaluator is missing')
    assert callable(getattr(module, 'evaluate_release_if_result', None)), 'public evaluator is missing'
    return module


def mixed_policy(policy):
    # Independent hand calculation: four scored test alarms are normal,
    # attack, unknown, attempted. Policy only changes the attempted labels.
    values = {
        'P_U': ((39, 3, 6), (12, 2, 4), (27, 1, 2), (1, 1, 11, 1), (.5, .5, .5, 1/12, .5)),
        'P_B': ((42, 3, 3), (14, 2, 2), (28, 1, 1), (1, 2, 12, 1), (1/3, .5, .4, 1/7, .5)),
        'P_A': ((39, 6, 3), (12, 4, 2), (27, 2, 1), (2, 1, 11, 2), (2/3, .5, 4/7, 1/12, .5)),
    }
    calendar, scored, unscored, counts, metrics = values[policy]
    return dict(calendar_test_minutes=48, scored_test_minutes=18, excluded_unscored_test_minutes=30,
        calendar_by_kind=dict(zip(('normal', 'attack', 'unknown'), calendar)),
        scored_by_kind=dict(zip(('normal', 'attack', 'unknown'), scored)),
        unscored_by_kind=dict(zip(('normal', 'attack', 'unknown'), unscored)),
        confusion_counts=dict(zip(('tp', 'fp', 'tn', 'fn'), counts)),
        metrics=dict(zip(('precision', 'recall', 'f1', 'fpr', 'fnr'), metrics)), undefined_reasons={})


def expected_report(case):
    return dict(version=1, profile_id='c17-release-iforest-fixed-prediction-label-audit-v1',
        status='SAVED_PREDICTION_LABEL_AUDIT', scope='SAVED_RESULT_LABEL_SENSITIVITY_INTERNAL_CONSISTENCY_ONLY',
        unit='minute', result_identity=asdict(case.package.identity),
        input_references=dict(raw=asdict(case.raw.identity), prepared=asdict(case.prepared.identity)),
        configuration_sha256=case.pair.configuration_sha256, view=case.result.view, audit_fit_policy='P_U',
        policy_status='AUDIT_ONLY', source_authentication='NOT_AUTHENTICATED',
        time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY', model_execution='NOT_AUTHENTICATED',
        prediction_basis='FIXED_SAVED_PREDICTIONS_NO_REFIT',
        policies={policy: mixed_policy(policy) for policy in ('P_U', 'P_B', 'P_A')})


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def test_mixed_fixed_predictions_report_only_common_test_minutes():
    c = api()  # Missing interface is RED before any setup/preprocessing runs.
    case = sealed_evaluation_case()
    payload = c.evaluate_release_if_result(case.package, case.pair)
    assert type(payload) is bytes
    assert c.EVALUATION_BYTE_LIMIT == 16384
    assert payload == canonical(expected_report(case))
    assert len(json.loads(payload)) == 16
    assert all(len(report) == 9 for report in json.loads(payload)['policies'].values())
    assert len(payload) <= 16384


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_policy_mapping_uses_fixed_saved_predictions_and_canonical_object_order(view):
    c = api()
    case = sealed_evaluation_case(view=view)
    payload = c.evaluate_release_if_result(case.package, case.pair)
    report = json.loads(payload)
    assert payload == canonical(expected_report(case))
    assert tuple(report['policies']) == ('P_A', 'P_B', 'P_U')
    assert case.pair.labels.saved.policies == ('P_U', 'P_B', 'P_A')
    assert report['audit_fit_policy'] == 'P_U' and report['view'] == view
    assert case.result.predictions[162] is True  # unknown across all policies
    assert case.result.predictions[164] is True  # attempted changes interpretation
    assert case.result.predictions[30] is case.result.predictions[78] is True  # not test
    assert case.result.predictions[128] is None
    assert all(type(value) is int for policy in report['policies'].values()
        for value in policy['confusion_counts'].values())


REASONS = dict(precision='NO_POSITIVE_LABELED_TEST_PREDICTIONS', recall='NO_SCORED_TEST_ATTACK',
    fnr='NO_SCORED_TEST_ATTACK', fpr='NO_SCORED_TEST_NORMAL',
    f1='NO_ATTACK_OR_POSITIVE_LABELED_TEST_PREDICTIONS')


def edge_policy(scenario, policy):
    if scenario in ('no_test', 'all_unknown'):
        calendar, scored, excluded = (0, 0, 0) if scenario == 'no_test' else (48, 18, 30)
        return dict(calendar_test_minutes=calendar, scored_test_minutes=scored,
            excluded_unscored_test_minutes=excluded,
            calendar_by_kind=dict(normal=0, attack=0, unknown=calendar),
            scored_by_kind=dict(normal=0, attack=0, unknown=scored),
            unscored_by_kind=dict(normal=0, attack=0, unknown=excluded),
            confusion_counts=dict(tp=0, fp=0, tn=0, fn=0),
            metrics=dict(precision=None, recall=None, f1=None, fpr=None, fnr=None),
            undefined_reasons=REASONS)
    if scenario == 'no_normal':
        return dict(calendar_test_minutes=48, scored_test_minutes=18, excluded_unscored_test_minutes=30,
            calendar_by_kind=dict(normal=0, attack=48, unknown=0),
            scored_by_kind=dict(normal=0, attack=18, unknown=0),
            unscored_by_kind=dict(normal=0, attack=30, unknown=0),
            confusion_counts=dict(tp=4, fp=0, tn=0, fn=14),
            metrics=dict(precision=1., recall=2/9, f1=4/11, fpr=None, fnr=7/9),
            undefined_reasons=dict(fpr=REASONS['fpr']))
    if scenario == 'no_attack':
        return dict(calendar_test_minutes=48, scored_test_minutes=18, excluded_unscored_test_minutes=30,
            calendar_by_kind=dict(normal=48, attack=0, unknown=0),
            scored_by_kind=dict(normal=18, attack=0, unknown=0),
            unscored_by_kind=dict(normal=30, attack=0, unknown=0),
            confusion_counts=dict(tp=0, fp=4, tn=14, fn=0),
            metrics=dict(precision=0., recall=None, f1=0., fpr=2/9, fnr=None),
            undefined_reasons=dict(recall=REASONS['recall'], fnr=REASONS['fnr']))
    expected = mixed_policy(policy)
    counts = {'P_U': (12, 2), 'P_B': (14, 2), 'P_A': (12, 4)}[policy]
    expected.update(confusion_counts=dict(tp=0, fp=0, tn=counts[0], fn=counts[1]),
        metrics=dict(precision=None, recall=0., f1=0., fpr=0., fnr=1.),
        undefined_reasons=dict(precision=REASONS['precision']))
    return expected


@pytest.mark.parametrize('scenario', ['no_test', 'no_normal', 'no_attack', 'no_positive', 'all_unknown'])
@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_valid_empty_and_zero_denominators_preserve_zero_float_vs_null(scenario, view):
    c = api()
    case = sealed_evaluation_case(scenario=scenario, view=view)
    result = json.loads(c.evaluate_release_if_result(case.package, case.pair))
    assert case.result.train_indices and case.result.calibration_indices
    assert result['policies'] == {policy: edge_policy(scenario, policy) for policy in ('P_U', 'P_B', 'P_A')}
    for report in result['policies'].values():
        assert set(report['undefined_reasons']) == {key for key, value in report['metrics'].items() if value is None}
        assert all(value is None or type(value) is float for value in report['metrics'].values())
    if scenario == 'no_positive':
        assert result['policies']['P_U']['metrics']['fpr'] == 0.
        assert result['policies']['P_U']['metrics']['f1'] == 0.


def test_verify_precedes_arithmetic_once_and_confusion_gets_boolean_vectors(monkeypatch):
    c = api()
    case = sealed_evaluation_case()
    events = []
    verify, confusion = c.verify_release_if_result_pair, c.confusion
    def checked_verify(package, pair):
        assert events == []
        verify(package, pair)
        events.append('verified')
    def checked_confusion(normal, attack, valid, alarms):
        assert events[0] == 'verified'
        assert all(type(vector) is np.ndarray and vector.shape == (176,) and vector.dtype == np.bool_
                   for vector in (normal, attack, valid, alarms))
        assert int(valid.sum()) == 18
        assert not valid[30] and not valid[78] and not valid[128]
        assert alarms[162] and alarms[164] and not alarms[128]
        events.append('confusion')
        return confusion(normal, attack, valid, alarms)
    monkeypatch.setattr(c, 'verify_release_if_result_pair', checked_verify)
    monkeypatch.setattr(c, 'confusion', checked_confusion)
    assert c.evaluate_release_if_result(case.package, case.pair) == canonical(expected_report(case))
    assert events == ['verified', 'confusion', 'confusion', 'confusion']


def reject(call, code):
    c = api()
    with pytest.raises(c.ReleaseIFEvaluationError) as error:
        call()
    assert error.value.code == code and str(error.value) == code


@pytest.mark.parametrize('bad', ['package_object', 'pair_object', 'package_subclass', 'pair_subclass'])
def test_wrong_exact_parameter_types_do_not_call_verify(monkeypatch, bad):
    c = api()
    case = sealed_evaluation_case()
    package, pair = case.package, case.pair
    if bad == 'package_object': package = object()
    elif bad == 'pair_object': pair = object()
    elif bad == 'package_subclass': package = object.__new__(type('OtherPackage', (type(package),), {}))
    else: pair = object.__new__(type('OtherPair', (type(pair),), {}))
    def forbidden(*args): raise AssertionError('invalid arguments reached verifier')
    monkeypatch.setattr(c, 'verify_release_if_result_pair', forbidden)
    reject(lambda: c.evaluate_release_if_result(package, pair), 'INVALID_EVALUATION_ARGUMENTS')


@pytest.mark.parametrize(('mutation', 'code'), [('identity', 'INVALID_EVALUATION_INPUT'),
    ('threshold', 'INVALID_EVALUATION_INPUT'), ('axis', 'INPUT_BINDING_MISMATCH'),
    ('population', 'INVALID_EVALUATION_INPUT'), ('other_pair', 'INPUT_BINDING_MISMATCH')])
def test_actual_verify_rejects_bad_inputs_before_confusion(monkeypatch, mutation, code):
    from datetime import timedelta
    c = api()
    case = sealed_evaluation_case()
    package, pair = case.package, case.pair
    if mutation == 'identity':
        package = replace(package, identity=replace(package.identity, manifest_sha256='f' * 64))
    elif mutation == 'threshold':
        result = replace(package.result, threshold=-1.)
        package = replace(package, result=result)
    elif mutation == 'population':
        package = replace(package, result=replace(package.result, train_indices=(31,)))
    elif mutation == 'axis':
        pair = replace(pair, segments=tuple(replace(segment, start=segment.start + timedelta(days=1),
            end=segment.end + timedelta(days=1)) for segment in pair.segments),
            prepared_minutes=replace(pair.prepared_minutes,
                timestamps=tuple(stamp + timedelta(days=1) for stamp in pair.prepared_minutes.timestamps)))
    else:
        pair = sealed_evaluation_case(scenario='no_attack').pair
    def forbidden(*args): raise AssertionError('unverified input reached confusion')
    monkeypatch.setattr(c, 'confusion', forbidden)
    reject(lambda: c.evaluate_release_if_result(package, pair), code)


@pytest.mark.parametrize(('code', 'expected'), [
    ('RESOURCE_LIMIT', 'RESOURCE_LIMIT'), ('INPUT_BINDING_MISMATCH', 'INPUT_BINDING_MISMATCH'),
    ('INVALID_PACKAGE', 'INVALID_EVALUATION_INPUT'), ('INCOMPATIBLE_PACKAGE', 'INVALID_EVALUATION_INPUT'),
    ('INTEGRITY_MISMATCH', 'INVALID_EVALUATION_INPUT'), ('INCONSISTENT_PACKAGE', 'INVALID_EVALUATION_INPUT'),
    ('INVALID_PACKAGE_ARGUMENTS', 'EVALUATION_ERROR'), ('OUTPUT_ERROR', 'EVALUATION_ERROR'),
    ('INVALID_PACKAGE_PATH', 'EVALUATION_ERROR'), (None, 'EVALUATION_ERROR'), ([], 'EVALUATION_ERROR'),
])
def test_pure_error_domain_maps_only_exact_allowed_verifier_codes(monkeypatch, code, expected):
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    c = api()
    case = sealed_evaluation_case()
    error = ReleaseIFResultPackageError('INVALID_PACKAGE')
    error.code = code
    def fail(*args): raise error
    monkeypatch.setattr(c, 'verify_release_if_result_pair', fail)
    reject(lambda: c.evaluate_release_if_result(case.package, case.pair), expected)


@pytest.mark.parametrize('kind', ['unknown', 'subclass', 'known_getter', 'known_interrupt', 'direct_interrupt'])
def test_unknown_errors_skip_getters_known_getter_failures_are_safe_and_interrupts_propagate(monkeypatch, kind):
    from traffic_anomaly.release_if_result_contract import ReleaseIFResultPackageError
    c = api()
    case = sealed_evaluation_case()
    reads = []
    class UnknownError(ValueError):
        @property
        def code(self):
            reads.append(True)
            raise KeyboardInterrupt('private unknown getter')
    if kind == 'unknown': error = UnknownError('private')
    elif kind == 'subclass':
        class OtherError(ReleaseIFResultPackageError): pass
        error = OtherError('INPUT_BINDING_MISMATCH')
    elif kind == 'direct_interrupt': error = KeyboardInterrupt('private')
    else:
        error = ReleaseIFResultPackageError('INVALID_PACKAGE')
        def getter(self):
            reads.append(True)
            if kind == 'known_interrupt': raise KeyboardInterrupt('private')
            raise RuntimeError('private')
        monkeypatch.setattr(ReleaseIFResultPackageError, 'code', property(getter), raising=False)
    def fail(*args): raise error
    monkeypatch.setattr(c, 'verify_release_if_result_pair', fail)
    if kind in ('known_interrupt', 'direct_interrupt'):
        with pytest.raises(KeyboardInterrupt):
            c.evaluate_release_if_result(case.package, case.pair)
    else:
        reject(lambda: c.evaluate_release_if_result(case.package, case.pair), 'EVALUATION_ERROR')
    assert reads == ([True] if kind in ('known_getter', 'known_interrupt') else [])


def test_pure_operation_never_calls_producers_files_or_model_after_setup(monkeypatch):
    c = api()
    case = sealed_evaluation_case()  # Actual artificial prepare happens here, before guards.
    def forbidden(*args, **kwargs): raise AssertionError('readonly evaluation attempted producer or I/O')
    products = {
        'traffic_anomaly.release_inputs': ('prepare_release_inputs', 'verify_release_input_derivation',
            '_fit_state', '_fit_statistics', '_transform', '_history'),
        'traffic_anomaly.release_iforest': ('fit_release_iforest', '_compute'),
        'traffic_anomaly._release_disk': ('_aggregate_release_files',),
        'traffic_anomaly.release_if_result_contract': ('make_release_if_result_package',),
        'traffic_anomaly.release_example': ('build_release_example',),
        'traffic_anomaly.release_minute_package': ('load_release_minute_package', 'save_release_minute_package'),
        'traffic_anomaly.release_input_package': ('load_release_input_package', 'save_release_input_package'),
        'traffic_anomaly.release_if_result_package': ('load_release_if_result_package', 'save_release_if_result_package'),
        'traffic_anomaly.evaluation.metrics': ('evaluate',),
    }
    modules = [(importlib.import_module(name), functions) for name, functions in products.items()]
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name in ('sklearn', 'torch') or name.startswith(('sklearn.', 'torch.')):
            return forbidden()
        return original_import(name, *args, **kwargs)
    with monkeypatch.context() as guard:
        for module, functions in modules:
            for function in functions: guard.setattr(module, function, forbidden)
        guard.setattr(builtins, '__import__', guarded_import)
        guard.setattr(builtins, 'open', forbidden)
        guard.setattr(io, 'open', forbidden)
        for name in ('open', 'stat', 'lstat', 'resolve'):
            guard.setattr(Path, name, forbidden)
        for name in ('open', 'stat', 'lstat', 'scandir'):
            guard.setattr(os, name, forbidden)
        payload = c.evaluate_release_if_result(case.package, case.pair)
    assert payload == canonical(expected_report(case))


@pytest.mark.parametrize('mutation', ['counts_bool', 'counts_conservation', 'metric_bool', 'metric_nan', 'metric_null'])
def test_arithmetic_type_finite_and_conservation_failures_become_evaluation_error(monkeypatch, mutation):
    from types import SimpleNamespace
    c = api()
    case = sealed_evaluation_case()
    original = c.confusion
    def broken(*args):
        result = original(*args)
        values = {name: getattr(result, name) for name in ('tp', 'fp', 'tn', 'fn', 'precision', 'recall', 'f1', 'fpr')}
        if mutation == 'counts_bool': values['tp'] = True
        elif mutation == 'counts_conservation': values['tn'] = 0
        elif mutation == 'metric_bool': values['precision'] = True
        elif mutation == 'metric_nan': values['precision'] = float('nan')
        else: values['precision'] = None
        return SimpleNamespace(**values)
    monkeypatch.setattr(c, 'confusion', broken)
    reject(lambda: c.evaluate_release_if_result(case.package, case.pair), 'EVALUATION_ERROR')


def test_actual_byte_limit_counts_lf_and_unknown_error_constructor_is_safe(monkeypatch):
    c = api()
    case = sealed_evaluation_case()
    expected = canonical(expected_report(case))
    monkeypatch.setattr(c, 'EVALUATION_BYTE_LIMIT', len(expected) - 1)
    reject(lambda: c.evaluate_release_if_result(case.package, case.pair), 'RESOURCE_LIMIT')
    monkeypatch.setattr(c, 'EVALUATION_BYTE_LIMIT', len(expected))
    assert c.evaluate_release_if_result(case.package, case.pair) == expected
    assert str(c.ReleaseIFEvaluationError('private')) == 'EVALUATION_ERROR'
    assert str(c.ReleaseIFEvaluationError(['RESOURCE_LIMIT'])) == 'EVALUATION_ERROR'
