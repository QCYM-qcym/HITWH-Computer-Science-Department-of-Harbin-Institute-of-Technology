"""Real saved-artifact reads for fixed-prediction label auditing.

Fixture setup may fit artificial preprocessing and save sealed packages. The
tested CLI operation is separately guarded against producers, file writes,
source CSV access, replay and estimators. Numeric expectations are handwritten.
"""
import builtins
from contextlib import contextmanager
from dataclasses import asdict
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from traffic_anomaly import release_iforest as forest
from traffic_anomaly import release_if_result_package as result_io
from traffic_anomaly import release_input_package as prepared_io
from traffic_anomaly import release_inputs as preparation
from traffic_anomaly import release_minute_package as raw_io


def cli_api():
    try:
        return importlib.import_module('traffic_anomaly.release_if_evaluation_cli')
    except ModuleNotFoundError as error:
        if error.name == 'traffic_anomaly.release_if_evaluation_cli':
            pytest.fail('public saved-prediction label evaluation CLI is not implemented')
        raise


def sealed_case(*, scenario='mixed', view='current13'):
    # Import after cli_api() so the first RED proves the missing product seam,
    # rather than masquerading a missing test helper as a collection failure.
    from tests.core.release_if_evaluation_cases import sealed_evaluation_case
    return sealed_evaluation_case(scenario=scenario, view=view)


def save_case(root, *, scenario='mixed', view='current13'):
    """Setup only: actual codec-sealed artificial values, never an estimator."""
    case = sealed_case(scenario=scenario, view=view)
    root.mkdir()
    directories = dict(raw=root/'raw', prepared=root/'prepared', result=root/'result')
    assert raw_io.save_release_minute_package(case.raw.minutes, case.raw.segments,
                                             directories['raw']) == case.raw.identity
    assert prepared_io.save_release_input_package(case.prepared,
                                                  directories['prepared']) == case.prepared.identity
    assert result_io.save_release_if_result_package(case.package,
                                                    directories['result']) == case.package.identity
    return case, directories


def arguments(directories):
    return ['evaluate', '--result-package', str(directories['result']),
            '--raw-package', str(directories['raw']), '--prepared-package', str(directories['prepared'])]


def snapshot(*directories):
    return {(str(directory), path.name): (path.read_bytes(), path.stat().st_mtime_ns)
            for directory in directories for path in directory.iterdir()}


@pytest.fixture
def no_estimator(monkeypatch, record_property):
    original_import = builtins.__import__
    original_statistics = preparation._fit_statistics
    setup_fits = []

    def forbidden(*args, **kwargs):
        raise AssertionError('saved evaluation integration must not execute an estimator')

    def guarded_import(name, *args, **kwargs):
        if name.split('.')[0] in ('sklearn', 'torch', 'joblib'):
            return forbidden()
        return original_import(name, *args, **kwargs)

    def counted_statistics(values):
        setup_fits.append(len(values))
        return original_statistics(values)

    monkeypatch.setattr(forest, 'fit_release_iforest', forbidden)
    monkeypatch.setattr(forest, '_compute', forbidden)
    monkeypatch.setattr(builtins, '__import__', guarded_import)
    monkeypatch.setattr(preparation, '_fit_statistics', counted_statistics)
    yield setup_fits
    record_property('artificial_setup_fit_statistics_calls', len(setup_fits))
    record_property('estimator_execution', 'FORBIDDEN')


@contextmanager
def readonly_operation(monkeypatch, cli):
    original_open, original_io_open, original_os_open = builtins.open, io.open, os.open

    def forbidden(*args, **kwargs):
        raise AssertionError('read-only evaluation entered a producer, write or replay')

    def check_open(file, mode):
        if any(flag in mode for flag in ('w', 'a', 'x', '+')):
            forbidden()
        if not isinstance(file, int) and Path(file).suffix.lower() == '.csv':
            forbidden()

    def plain_open(file, mode='r', *args, **kwargs):
        check_open(file, mode)
        return original_open(file, mode, *args, **kwargs)

    def io_open(file, mode='r', *args, **kwargs):
        check_open(file, mode)
        return original_io_open(file, mode, *args, **kwargs)

    def os_open(file, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            forbidden()
        if not isinstance(file, int) and Path(file).suffix.lower() == '.csv':
            forbidden()
        return original_os_open(file, flags, *args, **kwargs)

    with monkeypatch.context() as guarded:
        for module, names in (
            (raw_io, ('save_release_minute_package',)),
            (prepared_io, ('save_release_input_package',)),
            (result_io, ('save_release_if_result_package',)),
            (preparation, ('prepare_release_inputs', 'verify_release_input_derivation',
                           '_fit_state', '_fit_statistics', '_transform', '_history')),
        ):
            for name in names:
                guarded.setattr(module, name, forbidden)
                if hasattr(cli, name):
                    guarded.setattr(cli, name, forbidden)
        guarded.setattr(builtins, 'open', plain_open)
        guarded.setattr(io, 'open', io_open)
        guarded.setattr(os, 'open', os_open)
        guarded.setattr(os, 'mkdir', forbidden)
        yield


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(',', ':'))+'\n').encode('utf-8')


def mixed_policies():
    # Hand counts from the sealed helper's published fixed pattern:
    # test local30/31 normal +/-; 32/33 attack +/-; 34/35 unknown +/-;
    # 36/37 attempted +/-; 38..47 ten normal negatives. Local0/1/2 are
    # unscored attack/attempted/unknown; the other 27 warmup rows are normal.
    return {
        'P_U': dict(calendar_test_minutes=48, scored_test_minutes=18,
            excluded_unscored_test_minutes=30,
            calendar_by_kind=dict(normal=39, attack=3, unknown=6),
            scored_by_kind=dict(normal=12, attack=2, unknown=4),
            unscored_by_kind=dict(normal=27, attack=1, unknown=2),
            confusion_counts=dict(tp=1, fp=1, tn=11, fn=1),
            metrics=dict(precision=0.5, recall=0.5, f1=0.5, fpr=1/12, fnr=0.5),
            undefined_reasons={}),
        'P_B': dict(calendar_test_minutes=48, scored_test_minutes=18,
            excluded_unscored_test_minutes=30,
            calendar_by_kind=dict(normal=42, attack=3, unknown=3),
            scored_by_kind=dict(normal=14, attack=2, unknown=2),
            unscored_by_kind=dict(normal=28, attack=1, unknown=1),
            confusion_counts=dict(tp=1, fp=2, tn=12, fn=1),
            metrics=dict(precision=1/3, recall=0.5, f1=0.4, fpr=1/7, fnr=0.5),
            undefined_reasons={}),
        'P_A': dict(calendar_test_minutes=48, scored_test_minutes=18,
            excluded_unscored_test_minutes=30,
            calendar_by_kind=dict(normal=39, attack=6, unknown=3),
            scored_by_kind=dict(normal=12, attack=4, unknown=2),
            unscored_by_kind=dict(normal=27, attack=2, unknown=1),
            confusion_counts=dict(tp=2, fp=1, tn=11, fn=2),
            metrics=dict(precision=2/3, recall=0.5, f1=4/7, fpr=1/12, fnr=0.5),
            undefined_reasons={}),
    }


def no_test_policies():
    return {policy: dict(calendar_test_minutes=0, scored_test_minutes=0,
        excluded_unscored_test_minutes=0,
        calendar_by_kind=dict(normal=0, attack=0, unknown=0),
        scored_by_kind=dict(normal=0, attack=0, unknown=0),
        unscored_by_kind=dict(normal=0, attack=0, unknown=0),
        confusion_counts=dict(tp=0, fp=0, tn=0, fn=0),
        metrics=dict(precision=None, recall=None, f1=None, fpr=None, fnr=None),
        undefined_reasons=dict(precision='NO_POSITIVE_LABELED_TEST_PREDICTIONS',
            recall='NO_SCORED_TEST_ATTACK', f1='NO_ATTACK_OR_POSITIVE_LABELED_TEST_PREDICTIONS',
            fpr='NO_SCORED_TEST_NORMAL', fnr='NO_SCORED_TEST_ATTACK'))
        for policy in ('P_U', 'P_B', 'P_A')}


def expected_report(case, policies):
    return dict(version=1,
        profile_id='c17-release-iforest-fixed-prediction-label-audit-v1',
        status='SAVED_PREDICTION_LABEL_AUDIT',
        scope='SAVED_RESULT_LABEL_SENSITIVITY_INTERNAL_CONSISTENCY_ONLY',
        unit='minute', result_identity=asdict(case.package.identity),
        input_references=dict(raw=asdict(case.raw.identity), prepared=asdict(case.prepared.identity)),
        configuration_sha256=case.pair.configuration_sha256, view=case.package.context.view,
        audit_fit_policy='P_U', policy_status='AUDIT_ONLY', source_authentication='NOT_AUTHENTICATED',
        time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY', model_execution='NOT_AUTHENTICATED',
        prediction_basis='FIXED_SAVED_PREDICTIONS_NO_REFIT', policies=policies)


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_real_disk_saved_packages_evaluate_without_producer_or_model(
        tmp_path, monkeypatch, capfdbinary, no_estimator, view):
    cli = cli_api()
    case, directories = save_case(tmp_path/'inputs', view=view)
    before = snapshot(*directories.values())
    fit_count = len(no_estimator)
    with readonly_operation(monkeypatch, cli):
        status = cli.main(arguments(directories))
    stdout, stderr = capfdbinary.readouterr()
    assert status == 0 and stderr == b''
    document = json.loads(stdout)
    assert stdout == canonical(expected_report(case, mixed_policies()))
    assert stdout == canonical(document) and len(stdout) <= 16384
    assert document['status'] == 'SAVED_PREDICTION_LABEL_AUDIT'
    assert document['result_identity'] == asdict(case.package.identity)
    assert document['input_references'] == dict(raw=asdict(case.raw.identity),
                                                prepared=asdict(case.prepared.identity))
    assert document['view'] == view
    assert document['audit_fit_policy'] == 'P_U'
    assert document['prediction_basis'] == 'FIXED_SAVED_PREDICTIONS_NO_REFIT'
    assert document['policy_status'] == 'AUDIT_ONLY'
    assert document['source_authentication'] == document['model_execution'] == 'NOT_AUTHENTICATED'
    assert document['time_basis'] == 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'
    assert list(document['policies']) == ['P_A', 'P_B', 'P_U']
    assert len(no_estimator) == fit_count
    assert snapshot(*directories.values()) == before


def test_legal_saved_pair_without_test_segment_reports_all_null_metrics(
        tmp_path, monkeypatch, capfdbinary, no_estimator):
    cli = cli_api()
    case, directories = save_case(tmp_path/'without-test', scenario='no_test')
    assert case.pair.population.train_indices and case.pair.population.calibration_indices
    assert 'test' not in case.pair.roles
    before = snapshot(*directories.values())
    fit_count = len(no_estimator)
    with readonly_operation(monkeypatch, cli):
        status = cli.main(arguments(directories))
    stdout, stderr = capfdbinary.readouterr()
    assert status == 0 and stderr == b''
    assert stdout == canonical(expected_report(case, no_test_policies()))
    assert len(no_estimator) == fit_count
    assert snapshot(*directories.values()) == before


def test_another_legal_disk_pair_rejects_result_binding_without_writes(
        tmp_path, monkeypatch, capfdbinary, no_estimator):
    cli = cli_api()
    original, directories = save_case(tmp_path/'original')
    other, other_directories = save_case(tmp_path/'another', scenario='no_test')
    assert original.raw.identity != other.raw.identity
    assert original.prepared.identity != other.prepared.identity
    before = snapshot(*directories.values(), *other_directories.values())
    mixed_directories = dict(result=directories['result'], raw=other_directories['raw'],
                             prepared=other_directories['prepared'])
    fit_count = len(no_estimator)
    with readonly_operation(monkeypatch, cli):
        status = cli.main(arguments(mixed_directories))
    stdout, stderr = capfdbinary.readouterr()
    assert status == 2 and stdout == b''
    assert stderr == b'{"error":"INPUT_BINDING_MISMATCH"}\n'
    assert len(no_estimator) == fit_count
    assert snapshot(*directories.values(), *other_directories.values()) == before


def test_corrupt_result_member_retains_integrity_error_and_all_input_bytes(
        tmp_path, monkeypatch, capfdbinary, no_estimator):
    cli = cli_api()
    _, directories = save_case(tmp_path/'original')
    corrupt = tmp_path/'corrupt-result'
    shutil.copytree(directories['result'], corrupt)
    member = corrupt/'result.json'
    member.write_bytes(member.read_bytes()+b' ')
    before = snapshot(*directories.values(), corrupt)
    fit_count = len(no_estimator)
    with readonly_operation(monkeypatch, cli):
        status = cli.main(arguments(dict(directories, result=corrupt)))
    stdout, stderr = capfdbinary.readouterr()
    assert status == 2 and stdout == b''
    assert stderr == b'{"error":"INTEGRITY_MISMATCH"}\n'
    assert len(no_estimator) == fit_count
    assert snapshot(*directories.values(), corrupt) == before


def test_stdout_flush_failure_keeps_loadable_originals_and_host_stream(
        tmp_path, monkeypatch, capfdbinary, no_estimator):
    cli = cli_api()
    case, directories = save_case(tmp_path/'original')
    before = snapshot(*directories.values())
    fit_count = len(no_estimator)
    sent = []

    class FlushFailure:
        def write(self, payload):
            sent.append(payload)
            return len(payload)

        def flush(self):
            raise OSError('private-output-flush-sentinel')

    host = SimpleNamespace(buffer=FlushFailure())
    with monkeypatch.context() as streams:
        streams.setattr(sys, 'stdout', host)
        with readonly_operation(monkeypatch, cli):
            status = cli.main(arguments(directories))
        assert sys.stdout is host
    stdout, stderr = capfdbinary.readouterr()
    assert status == 2 and stdout == b''
    assert stderr == b'{"error":"OUTPUT_ERROR"}\n'
    assert sent == [canonical(expected_report(case, mixed_policies()))]
    assert len(no_estimator) == fit_count
    assert snapshot(*directories.values()) == before
    assert raw_io.load_release_minute_package(directories['raw']) == case.raw
    assert prepared_io.load_release_input_package(directories['prepared']) == case.prepared
    assert result_io.load_release_if_result_package(directories['result']) == case.package
