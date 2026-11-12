"""The learned-only projection is pure, bounded and has no replay authority."""
from dataclasses import replace
import importlib
import importlib.util
import json
import subprocess
import sys
import textwrap

import pytest

from tests.core.test_release_if_learned_contract import NAMES, package
from traffic_anomaly import release_if_learned_contract as contract


def api():
    name = 'traffic_anomaly.release_if_learned_summary'
    assert importlib.util.find_spec(name) is not None, 'missing learned-only public summary'
    return importlib.import_module(name)


def reference(identity):
    return dict(profile_id=identity.profile_id, context_sha256=identity.context_sha256,
                manifest_sha256=identity.manifest_sha256,
                manifest_byte_count=identity.manifest_byte_count)


@pytest.mark.parametrize('view,width,m,nodes', [('current13', 13, 1, 16), ('h30_26', 26, 2, 48)])
def test_summary_exact_projection_and_negative_checks(view, width, m, nodes):
    summarize = api().summarize_release_if_learned
    saved = package(view=view, m=m)
    columns = ['current:' + name for name in NAMES]
    if width == 26:
        columns.extend('residual_h30:' + name for name in NAMES)
    expected = dict(
        version=1, profile_id='c17-release-iforest-learned-summary-v1',
        scope='SAVED_LEARNED_INTERNAL_CONSISTENCY_ONLY', learned_identity=reference(saved.identity),
        view=view,
        input_references=dict(raw=reference(saved.context.raw_identity),
                              prepared=reference(saved.context.prepared_identity)),
        result_reference=reference(saved.context.result_identity),
        declarations=dict(configuration_sha256='c' * 64, population_sha256='d' * 64,
                          input_rules_id='c17-release-log1p-mad-input-rules-v1', feature_columns=columns,
                          model_configuration=dict(input_width=width, n_estimators=16, max_samples=m,
                                                   max_features=1.0, bootstrap=False, contamination='auto',
                                                   random_state=42, n_jobs=1),
                          fit_runtime_id='python314-numpy254-sklearn191-joblib160-serial-wm1024-v1'),
        counts=dict(total=100, training=m, calibration=1, preprocessing_fit=40, trees=16, nodes=nodes),
        checks=dict(byte_integrity='MATCHED', structure='MATCHED', numerical_replay='NOT_RUN',
                    input_pair_binding='NOT_PERFORMED', result_binding='NOT_PERFORMED',
                    source_authentication='NOT_AUTHENTICATED', model_origin='NOT_AUTHENTICATED'))
    actual = summarize(saved)
    # JSON distinguishes 1 from true, and 1 from 1.0.
    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert type(actual['declarations']['feature_columns']) is list
    actual['declarations']['feature_columns'].clear()
    actual['declarations']['model_configuration']['n_jobs'] = 42
    actual['input_references']['raw'].clear()
    assert summarize(saved) == expected


@pytest.mark.parametrize('change,code', [
    ('foreign', 'INVALID_LEARNED_ARGUMENTS'), ('missing', 'INVALID_LEARNED_PACKAGE'),
    ('report', 'INTEGRITY_MISMATCH'), ('identity', 'INTEGRITY_MISMATCH'),
    ('oversize', 'RESOURCE_LIMIT'),
])
def test_invalid_input_uses_codec_errors(change, code):
    summarize = api().summarize_release_if_learned
    saved = package()
    if change == 'foreign':
        class Foreign:
            def __getattribute__(self, name):
                raise AssertionError('do not inspect a foreign object')
        saved = Foreign()
    elif change == 'missing':
        object.__delattr__(saved.context, 'view')
    elif change == 'report':
        saved = replace(saved, load_report=replace(saved.load_report, numerical_replay='MATCHED'))
    elif change == 'identity':
        saved = replace(saved, identity=replace(saved.identity, context_sha256='f' * 64))
    else:
        saved = replace(saved, context=replace(saved.context, minute_count=10001))
    with pytest.raises(contract.ReleaseIFLearnedError) as caught:
        summarize(saved)
    assert type(caught.value) is contract.ReleaseIFLearnedError
    assert caught.value.args == (code,)


def test_summary_limit_includes_final_lf(monkeypatch):
    module = api()
    saved = package(view='h30_26')
    projection = module.summarize_release_if_learned(saved)
    payload = (json.dumps(projection, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':')) + '\n').encode()
    assert module._SUMMARY_BYTE_LIMIT == 16384
    monkeypatch.setattr(module, '_SUMMARY_BYTE_LIMIT', len(payload))
    assert module.summarize_release_if_learned(saved) == projection
    monkeypatch.setattr(module, '_SUMMARY_BYTE_LIMIT', len(payload) - 1)
    with pytest.raises(contract.ReleaseIFLearnedError) as caught:
        module.summarize_release_if_learned(saved)
    assert caught.value.args == ('RESOURCE_LIMIT',)


def test_summary_preserves_exact_error_and_maps_foreign_and_memory_failures(monkeypatch):
    module = api()
    class ForeignError(contract.ReleaseIFLearnedError):
        @property
        def code(self):
            raise AssertionError('do not trust a subclass code')
    foreign = ForeignError.__new__(ForeignError)
    known = contract.ReleaseIFLearnedError('INPUT_BINDING_MISMATCH')
    for fault, code in ((known, 'INPUT_BINDING_MISMATCH'), (foreign, 'LEARNED_ERROR'),
                        (RuntimeError('private details'), 'LEARNED_ERROR'),
                        (MemoryError('private details'), 'RESOURCE_LIMIT')):
        def fail(_package):
            raise fault
        monkeypatch.setattr(module, 'encode_release_if_learned_package', fail)
        with pytest.raises(contract.ReleaseIFLearnedError) as caught:
            module.summarize_release_if_learned(None)
        assert type(caught.value) is contract.ReleaseIFLearnedError
        assert caught.value.args == (code,)
        if fault is known:
            assert caught.value is known


def test_cold_summary_avoids_files_numerical_and_model_operations():
    api()
    members = dict(contract.encode_release_if_learned_package(package()))
    script = textwrap.dedent("""
        import builtins, json, sys
        blocked = {'numpy', 'sklearn', 'joblib', 'torch', 'cloudpickle', 'pickle'}
        blocked_products = {'traffic_anomaly.release_if_learned', 'traffic_anomaly.release_iforest',
            'traffic_anomaly.release_inputs', 'traffic_anomaly._iforest_numeric_score',
            'traffic_anomaly.release_if_learned_package', 'traffic_anomaly.evaluation.calibration'}
        def forbidden_name(name):
            return name.split('.')[0] in blocked or name in blocked_products
        assert not any(forbidden_name(name) for name in sys.modules)
        attempts = []
        original = builtins.__import__
        def guard(name, *args, **kwargs):
            if forbidden_name(name):
                attempts.append(name)
                raise AssertionError(name)
            return original(name, *args, **kwargs)
        class Fence:
            def find_spec(self, fullname, path=None, target=None):
                if forbidden_name(fullname):
                    attempts.append(fullname)
                    raise AssertionError(fullname)
        builtins.__import__ = guard
        sys.meta_path.insert(0, Fence())
        from traffic_anomaly.release_if_learned_contract import decode_release_if_learned_package
        from traffic_anomaly.release_if_learned_summary import summarize_release_if_learned
        from traffic_anomaly import iforest_numeric_state as p1
        saved = decode_release_if_learned_package({
            name: bytes.fromhex(value) for name, value in json.loads(sys.stdin.read()).items()})
        def forbid_score(*args, **kwargs):
            attempts.append('p1 score')
            raise AssertionError('p1 score')
        p1.score_iforest_numeric_state = forbid_score
        def audit(event, args):
            if event in {'open', 'os.listdir', 'os.scandir'}:
                attempts.append(event)
                raise AssertionError(event)
        sys.addaudithook(audit)
        result = summarize_release_if_learned(saved)
        assert result['checks']['numerical_replay'] == 'NOT_RUN'
        assert result['counts']['nodes'] == 48
        assert not attempts
        assert not any(forbidden_name(name) for name in sys.modules)
        print('COLD_SUMMARY_PASS')
    """)
    child = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', script],
                           input=json.dumps({name: value.hex() for name, value in members.items()}),
                           capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    assert child.stdout == 'COLD_SUMMARY_PASS\n'
    assert child.stderr == ''
