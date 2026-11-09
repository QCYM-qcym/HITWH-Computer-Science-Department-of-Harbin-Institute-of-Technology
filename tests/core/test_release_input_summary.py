"""Hand-written projection snapshots; no preparation, replay or package I/O."""
from dataclasses import replace
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from traffic_anomaly.release_inputs import (
    ReleaseInputContext, ReleaseInputIdentity, ReleaseInputLabels,
    ReleaseInputLoadReport, ReleaseInputReplayReport, ReleasePolicyQualification,
    ReleasePreparationConfig, ReleasePreparedHistory, ReleasePreparedInputs,
    ReleasePreparedMinutes, ReleasePreprocessState, ReleaseReplayChecks,
    ReleaseReplayTolerance,
)
from traffic_anomaly.release_minute_contract import ReleaseMinutePackageIdentity


_FIXTURE = Path(__file__).parents[1] / 'fixtures/release-input-view-summary-v1.json'
_QUALIFICATIONS = (
    'train_full_history_normal', 'calibration_full_history_normal',
    'validation_current_normal', 'validation_current_attack', 'validation_current_unknown',
    'test_current_normal', 'test_current_attack', 'test_current_unknown',
)
_RAW = Path('C:/unopened/raw=@daily')
_PREPARED = Path('C:/unopened/prepared=@daily')
_OUTPUT = Path('C:/unopened/new-prepared')


def _mask(count, total):
    return (True,) * count + (False,) * (total - count)


class _Unreadable:
    """Fail and record even if an unexpected field access is later swallowed."""
    def __init__(self, attempts):
        self.attempts = attempts

    def _fail(self, *args, **kwargs):
        self.attempts.append('unprojected_field')
        raise AssertionError('unprojected field consumed')

    __iter__ = __len__ = __getitem__ = __float__ = _fail

    def __getattr__(self, name):
        return self._fail()


def _handwritten_saved(case, attempts):
    # Literal counts and identities come from the accepted hand calculation,
    # independently of the read-only expected JSON and the projection function.
    if case == 'general':
        total, h15, common, fit = 176, 116, 56, 18
        a, b, c, d, e, f, g = '1', '2', '3', '4', '5', '6', '7'
        input_bytes, raw_bytes = 1024, 2048
        counts = ((18, 10, 10, 0, 0, 15, 1, 2),
                  (18, 10, 10, 0, 0, 16, 1, 1),
                  (18, 10, 10, 0, 0, 15, 2, 1))
    else:
        assert case == 'zero_calibration'
        total, h15, common, fit = 32, 17, 2, 2
        a, b, c, d, e, f, g = '8', '9', 'a', 'b', 'c', 'd', 'e'
        input_bytes, raw_bytes = 1536, 2560
        counts = ((2, 0, 0, 0, 0, 0, 0, 0),) * 3
    hidden = _Unreadable(attempts)
    identity = ReleaseInputIdentity('c17-release-prepared-input-package-v1', a * 64, b * 64, input_bytes)
    upstream = ReleaseMinutePackageIdentity('c17-release-minute-package-v1', c * 64, d * 64, raw_bytes)
    config = ReleasePreparationConfig(1, 'c17-release-log1p-mad-input-rules-v1',
        tuple(f'hand_feature_{i}' for i in range(13)), (15, 30), 30, 1e-6, 'P_U', 'AUDIT_ONLY')
    context = ReleaseInputContext(identity.profile_id, 'c17-release-91-v1',
        'NOT_AUTHENTICATED', 'SOURCE_WALL_CLOCK_COMPLETION_PROXY', upstream, config, e * 64, hidden, total)
    state = ReleasePreprocessState(hidden, hidden, fit, 30, 'P_U', f * 64, g * 64)
    histories = (ReleasePreparedHistory(15, hidden, _mask(h15, total), hidden),
                 ReleasePreparedHistory(30, hidden, _mask(common, total), hidden))
    minutes = ReleasePreparedMinutes(hidden, hidden, _mask(total, total), hidden,
        _mask(total, total), hidden, histories, _mask(common, total))
    qualifications = tuple(ReleasePolicyQualification(policy, *(_mask(n, total) for n in row))
                           for policy, row in zip(('P_U', 'P_B', 'P_A'), counts))
    labels = ReleaseInputLabels(hidden, hidden, hidden, hidden, qualifications)
    report = ReleaseInputLoadReport(identity.profile_id, 'INTERNAL_CONSISTENCY_CHECKED',
        'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY', identity, 'CHECKED', 'CHECKED',
        'NOT_PERFORMED', 'NOT_PERFORMED', 'NOT_REESTIMATED', 'NOT_AUTHENTICATED')
    saved = ReleasePreparedInputs(identity, context, state, minutes, labels, report)
    assert type(saved) is ReleasePreparedInputs
    return saved


def _fixture(case):
    return json.loads(_FIXTURE.read_text(encoding='utf-8'))['cases'][case]


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def _report_and_expected():
    # These identities deliberately differ from BOTH saved snapshots.
    upstream = ReleaseMinutePackageIdentity('c17-release-minute-package-v1', 'f' * 64, '0' * 64, 3072)
    identity = ReleaseInputIdentity('c17-release-prepared-input-package-v1', 'a' * 64, 'b' * 64, 4096)
    checks = ReleaseReplayChecks('MATCHED', 'MATCHED', 'MATCHED', 'MATCHED', 'MATCHED',
                                'MATCHED', 'NOT_REESTIMATED', 'NOT_AUTHENTICATED')
    report = ReleaseInputReplayReport('c17-release-input-replay-v1', 'MATCHED',
        'SAVED_PARAMETER_REPLAY_ONLY', upstream, identity, 9, 3, checks,
        ReleaseReplayTolerance(1e-7, 1e-9, 'SAVED_PARAMETERS'))
    expected = {
        'profile_id': 'c17-release-input-replay-v1', 'status': 'MATCHED',
        'scope': 'SAVED_PARAMETER_REPLAY_ONLY', 'minute_count': 9, 'fit_count': 3,
        'upstream_identity': {'profile_id': 'c17-release-minute-package-v1',
            'context_sha256': 'f' * 64, 'manifest_sha256': '0' * 64, 'manifest_byte_count': 3072},
        'input_identity': {'profile_id': 'c17-release-prepared-input-package-v1',
            'context_sha256': 'a' * 64, 'manifest_sha256': 'b' * 64, 'manifest_byte_count': 4096},
        'checks': {'byte_identity': 'MATCHED', 'upstream_fields': 'MATCHED', 'fit_selection': 'MATCHED',
            'saved_transform': 'MATCHED', 'history': 'MATCHED', 'labels_and_masks': 'MATCHED',
            'fit_parameters': 'NOT_REESTIMATED', 'source_authentication': 'NOT_AUTHENTICATED'},
        'numerical_tolerance': {'rtol': 1e-7, 'atol': 1e-9, 'reference': 'SAVED_PARAMETERS'},
    }
    return report, expected


def _stub_cli(monkeypatch, saved):
    cli = importlib.import_module('traffic_anomaly.release_input_cli')
    events = []
    upstream = SimpleNamespace(minutes=SimpleNamespace(feature_names=saved.context.configuration.feature_names))
    report, expected_replay = _report_and_expected()

    def raw_load(path):
        assert path == _RAW
        events.append('raw_load')
        return upstream

    def prepared_load(path):
        assert path == _PREPARED
        events.append('prepared_load')
        return saved

    def prepare(raw, config):
        assert raw is upstream and config == saved.context.configuration
        events.append('prepare_stub')
        return saved

    def save(value, path):
        assert value is saved and path == _OUTPUT
        events.append('save_stub')
        return saved.identity

    def verify(raw, value):
        assert raw is upstream and value is saved
        events.append('verify_stub')
        return report

    for name, function in (('load_release_minute_package', raw_load),
        ('load_release_input_package', prepared_load), ('prepare_release_inputs', prepare),
        ('save_release_input_package', save), ('verify_release_input_derivation', verify)):
        monkeypatch.setattr(cli, name, function)
    return cli, events, expected_replay


def _argv(command):
    if command == 'prepare':
        return ['prepare', '--raw-package', str(_RAW), '--output', str(_OUTPUT),
                '--epsilon', '1e-6', '--audit-fit-policy', 'P_U']
    if command == 'verify':
        return ['verify', '--raw-package', str(_RAW), '--prepared-package', str(_PREPARED)]
    return ['inspect', '--prepared-package', str(_PREPARED)]


@pytest.mark.parametrize('case', ['general', 'zero_calibration'])
@pytest.mark.parametrize('command', ['prepare', 'inspect', 'verify'])
def test_cli_pre_extraction_bytes(monkeypatch, capfdbinary, case, command):
    attempts = []
    saved = _handwritten_saved(case, attempts)
    cli, events, replay = _stub_cli(monkeypatch, saved)
    expected = _fixture(case)
    expected.update(command=command, status={'prepare': 'SAVED', 'inspect': 'INTERNAL_CONSISTENCY_CHECKED',
                                           'verify': 'MATCHED'}[command],
                    replay=replay if command == 'verify' else None)
    assert cli.main(_argv(command)) == 0
    out, err = capfdbinary.readouterr()
    assert out == _encoded(expected) and err == b''
    assert events == {'prepare': ['raw_load', 'prepare_stub', 'save_stub'],
                      'inspect': ['prepared_load'],
                      'verify': ['prepared_load', 'raw_load', 'verify_stub']}[command]
    assert attempts == []


def _projector():
    return importlib.import_module('traffic_anomaly.release_input_summary').summarize_release_inputs


@pytest.fixture(autouse=True)
def forbidden_product_actions(monkeypatch):
    """Patch actual entry points before any CLI alias is imported; stubs are explicit."""
    attempts = []

    def forbidden(name):
        def fail(*args, **kwargs):
            attempts.append(name)
            raise AssertionError('forbidden product action')
        return fail

    targets = {
        'traffic_anomaly.release_inputs': (
            'prepare_release_inputs', 'verify_release_input_derivation',
            'encode_release_input_package', 'decode_release_input_package',
            '_validate_content', '_snapshot', '_fit_statistics', '_fit_state',
            '_transform', '_history', '_fit_selection', '_qualifications',
        ),
        'traffic_anomaly.release_input_package': ('load_release_input_package', 'save_release_input_package'),
        'traffic_anomaly.release_minute_package': ('load_release_minute_package', 'save_release_minute_package'),
        'traffic_anomaly.release_minute_contract': ('encode_release_minute_package', 'decode_release_minute_package'),
    }
    for module_name, names in targets.items():
        module = importlib.import_module(module_name)
        for name in names:
            monkeypatch.setattr(module, name, forbidden(module_name + '.' + name))
    monkeypatch.setattr(ReleasePreparedInputs, 'joined', forbidden('joined'))
    yield attempts
    assert attempts == []


@pytest.mark.parametrize('case', ['general', 'zero_calibration'])
def test_shared_summary_matches_fixture(case):
    attempts = []
    saved = _handwritten_saved(case, attempts)
    assert _projector()(saved) == _fixture(case)['summary']
    assert attempts == []


def test_shared_summary_returns_fresh_nested_containers():
    attempts = []
    saved = _handwritten_saved('general', attempts)
    project = _projector()
    first, second = project(saved), project(saved)

    def mutable_ids(value):
        if type(value) is dict:
            return {id(value)}.union(*(mutable_ids(v) for v in value.values()))
        if type(value) is list:
            return {id(value)}.union(*(mutable_ids(v) for v in value))
        return set()

    assert not mutable_ids(first) & mutable_ids(second)
    first['identity']['context_sha256'] = 'changed'
    first['configuration']['windows'].append(99)
    first['qualification_counts']['P_U']['test_current_normal'] = 999
    first['package_checks']['status'] = 'changed'
    assert second == project(saved) == _fixture('general')['summary']
    assert saved.context.configuration.windows == (15, 30) and attempts == []


def test_shared_summary_projects_each_saved_field_without_new_validation():
    attempts = []
    saved = _handwritten_saved('general', attempts)
    expected = _fixture('general')['summary']
    identity = replace(saved.identity, profile_id='projected-input', context_sha256='a' * 64,
                       manifest_sha256='b' * 64, manifest_byte_count=51)
    upstream = replace(saved.context.upstream, context_sha256='c' * 64,
                       manifest_sha256='d' * 64, manifest_byte_count=52)
    config = replace(saved.context.configuration, schema_version=7, numeric_rules_id='projected-rules',
        feature_names=('one', 'two'), windows=(31, 47), fit_window=47, epsilon=0.25,
        audit_fit_policy='projected-policy', policy_status='projected-status')
    context = replace(saved.context, upstream=upstream, configuration=config,
        source_authentication='projected-auth', time_basis='projected-time',
        configuration_sha256='e' * 64, minute_count=14)
    minutes = replace(saved.minutes, raw_valid=_mask(12, 14), prepared_valid=_mask(11, 14),
        common_valid=_mask(8, 14), histories=(replace(saved.minutes.histories[0], valid=_mask(10, 14)),
                                           replace(saved.minutes.histories[1], valid=_mask(9, 14))))
    state = replace(saved.preprocessing, n_samples_seen=6, fit_mask_sha256='f' * 64, fit_rows_sha256='0' * 64)
    qualifications = tuple(ReleasePolicyQualification(policy, *(_mask(n, 14) for n in range(start, start + 8)))
                           for policy, start in (('P_U', 1), ('P_B', 2), ('P_A', 3)))
    check_names = ('status', 'scope', 'byte_integrity', 'structure', 'upstream_replay',
                   'transform_history_replay', 'fit_parameters')
    checks = {name: 'projected-' + name for name in check_names}
    changed = replace(saved, identity=identity, context=context, minutes=minutes, preprocessing=state,
        labels=replace(saved.labels, qualification_masks=qualifications),
        load_report=replace(saved.load_report, **checks))
    expected.update(
        identity=dict(profile_id='projected-input', context_sha256='a' * 64, manifest_sha256='b' * 64, manifest_byte_count=51),
        upstream_identity=dict(profile_id='c17-release-minute-package-v1', context_sha256='c' * 64,
                               manifest_sha256='d' * 64, manifest_byte_count=52),
        source_authentication='projected-auth', time_basis='projected-time',
        configuration=dict(schema_version=7, numeric_rules_id='projected-rules', feature_count=2,
            windows=[31, 47], fit_window=47, epsilon=0.25, audit_fit_policy='projected-policy', policy_status='projected-status'),
        configuration_sha256='e' * 64,
        minute_counts=dict(total=14, raw_valid=12, prepared_valid=11, common_valid=8,
                           history_h15_valid=10, history_h30_valid=9),
        fit=dict(count=6, mask_sha256='f' * 64, rows_sha256='0' * 64),
        qualification_counts={policy: dict(zip(_QUALIFICATIONS, range(start, start + 8)))
                              for policy, start in (('P_U', 1), ('P_B', 2), ('P_A', 3))},
        package_checks=checks,
    )
    assert _projector()(changed) == expected and attempts == []


def test_shared_summary_does_not_attempt_io_or_numerics(monkeypatch, forbidden_product_actions):
    import builtins
    project = _projector()
    attempts = []
    saved = _handwritten_saved('general', attempts)
    expected = _fixture('general')['summary']

    def forbidden(*args, **kwargs):
        forbidden_product_actions.append('io')
        raise AssertionError('projection attempted IO')

    core = importlib.import_module('traffic_anomaly.release_inputs')
    with monkeypatch.context() as scoped:
        scoped.setattr(builtins, 'open', forbidden)
        scoped.setattr(Path, 'open', forbidden)
        scoped.setattr(core, 'np', _Unreadable(forbidden_product_actions))
        assert project(saved) == expected
    assert attempts == [] and forbidden_product_actions == []


@pytest.mark.parametrize('case', ['general', 'zero_calibration'])
def test_cli_verify_keeps_report_identities(monkeypatch, capfdbinary, case):
    saved = _handwritten_saved(case, [])
    cli, events, replay = _stub_cli(monkeypatch, saved)
    assert cli.main(_argv('verify')) == 0
    out, err = capfdbinary.readouterr()
    result = json.loads(out)
    assert result['replay'] == replay
    assert result['replay']['input_identity'] != result['summary']['identity']
    assert result['replay']['upstream_identity'] != result['summary']['upstream_identity']
    assert err == b'' and events == ['prepared_load', 'raw_load', 'verify_stub']


@pytest.mark.parametrize('command', ['prepare', 'inspect', 'verify'])
def test_cli_calls_shared_projection_once_in_original_order(monkeypatch, capfdbinary, command):
    saved = _handwritten_saved('general', [])
    cli, events, replay = _stub_cli(monkeypatch, saved)
    project = _projector()

    def projection(value):
        assert value is saved
        events.append('summary')
        return project(value)

    monkeypatch.setattr(cli, 'summarize_release_inputs', projection)
    assert cli.main(_argv(command)) == 0
    out, err = capfdbinary.readouterr()
    assert err == b'' and json.loads(out)['summary'] == _fixture('general')['summary']
    assert events == {'prepare': ['raw_load', 'prepare_stub', 'summary', 'save_stub'],
                      'inspect': ['prepared_load', 'summary'],
                      'verify': ['prepared_load', 'raw_load', 'verify_stub', 'summary']}[command]


@pytest.mark.parametrize('command', ['prepare', 'inspect', 'verify'])
@pytest.mark.parametrize('fault', ['exception', 'nan', 'non-json', 'unicode', 'below', 'exact', 'over'])
def test_cli_projection_failures_and_full_output_limits(monkeypatch, capfdbinary, command, fault):
    saved = _handwritten_saved('general', [])
    cli, events, replay = _stub_cli(monkeypatch, saved)
    envelope = dict(version=1, command=command,
        status={'prepare': 'SAVED', 'inspect': 'INTERNAL_CONSISTENCY_CHECKED', 'verify': 'MATCHED'}[command],
        summary={'padding': ''}, replay=replay if command == 'verify' else None)
    sizes = {'below': 65535, 'exact': 65536, 'over': 65537}

    def projection(value):
        assert value is saved
        events.append('summary')
        if fault == 'exception':
            raise RuntimeError('private projection details')
        if fault in sizes:
            envelope['summary']['padding'] = '中' + 'x' * (sizes[fault] - len(_encoded(envelope)) - 3)
            return envelope['summary']
        return {'bad': {'nan': float('nan'), 'non-json': {1, 2}, 'unicode': '\ud800'}[fault]}

    monkeypatch.setattr(cli, 'summarize_release_inputs', projection)
    rc = cli.main(_argv(command))
    out, err = capfdbinary.readouterr()
    initial = {'prepare': ['raw_load', 'prepare_stub'], 'inspect': ['prepared_load'],
               'verify': ['prepared_load', 'raw_load', 'verify_stub']}[command]
    if fault in ('below', 'exact'):
        assert rc == 0 and err == b'' and out == _encoded(envelope) and len(out) == sizes[fault]
        assert events == initial + ['summary'] + (['save_stub'] if command == 'prepare' else [])
    else:
        code = 'INTERNAL_ERROR' if fault == 'exception' else 'RESOURCE_LIMIT' if fault == 'over' else 'INVALID_RESULT'
        assert rc == 2 and out == b'' and err == _encoded({'error': code})
        assert events == initial + ['summary']
