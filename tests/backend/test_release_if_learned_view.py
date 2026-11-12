"""Manual saved declarations; no preparation, estimator, scoring or replay."""
from dataclasses import asdict, fields, replace
from hashlib import sha256
from importlib import import_module
from io import BytesIO
from datetime import timedelta
import json

from fastapi.testclient import TestClient
import pytest


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode()


def hand_tuple():
    """Six native holders and actual codecs, with a manual sixteen-leaf forest."""
    from tests.core.release_if_result_cases import hand_pair, hand_result
    from tests.core.test_release_model_inputs import _case, _exact
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackage
    from traffic_anomaly.release_inputs import ReleaseInputContext, ReleasePreparedInputs
    from traffic_anomaly.release_if_result_contract import make_release_if_result_package
    from traffic_anomaly import release_if_learned_contract as learned
    from traffic_anomaly.iforest_numeric_state import IForestNumericNode, IForestNumericTree, IForestNumericState
    p = hand_pair()
    raw0, saved0 = _case()
    minutes = replace(raw0.minutes, timestamps=p.prepared_minutes.timestamps,
        segment_ids=p.segment_ids, roles=p.roles, values=p.raw_values,
        source_valid=p.prepared_minutes.raw_valid, label_kinds=p.labels.saved.label_kinds,
        bucket_counts=(raw0.minutes.bucket_counts[0],) * len(p.roles))
    raw = _exact(ReleaseMinutePackage, identity=p.raw_identity, minutes=minutes,
                 segments=p.segments, scope=p.raw_scope)
    context = ReleaseInputContext(saved0.context.profile_id, p.source_schema_id,
        p.source_authentication, p.time_basis, p.raw_identity, p.configuration,
        p.configuration_sha256, p.segments, len(p.roles))
    saved = ReleasePreparedInputs(p.prepared_identity, context, p.preprocessing,
        p.prepared_minutes, p.labels.saved, replace(saved0.load_report, identity=p.prepared_identity))
    ref = lambda i: learned.ReleaseIFLearnedReference(**asdict(i))
    values = [raw, saved]
    for view in ('current13', 'h30_26'):
        result = make_release_if_result_package(p, hand_result(p, view))
        config = learned.ReleaseIFLearnedConfiguration(**asdict(result.result.configuration))
        tree = IForestNumericTree((IForestNumericNode(None, None, None, None, 17),))
        state = IForestNumericState(1, 'iforest-numeric-state-v1',
            'iforest16-m32-f32route-f64path-numpy254-v1', config.input_width,
            tuple(range(config.input_width)), 17, (tree,) * 16)
        population = learned._population_sha256(minute_count=len(p.roles),
            **{k: getattr(result.result, k) for k in ('scored_mask', 'train_indices',
                'calibration_indices', 'preprocessing_fit_indices')})
        lc = learned.ReleaseIFLearnedContext(learned.LEARNED_PACKAGE_PROFILE_ID, view,
            ref(p.raw_identity), ref(p.prepared_identity), ref(result.identity),
            p.configuration_sha256, len(p.roles), 17, 4, 18, population,
            p.configuration.numeric_rules_id, learned._feature_columns(view), config,
            learned.LEARNED_FIT_RUNTIME_ID)
        values.extend((result, learned._make_release_if_learned_package(lc, state)))
    return tuple(values)


def api():
    return import_module('traffic_api.release_if_learned_view')


def build(monkeypatch, values=None, assets=None):
    m = api()
    payloads = [b'<html>learned</html>', b'export {}', b'body{}'] if assets is None else assets
    monkeypatch.setattr(m, '_read_assets', lambda: tuple((p, b, mime)
        for (p, _, mime), b in zip(m._ASSETS, payloads)))
    return m, m.create_release_if_learned_view_app(*(hand_tuple() if values is None else values))


def test_freeze_actual_summaries_snapshots_and_float_tokens(monkeypatch):
    m, app = build(monkeypatch)
    assert len(app.routes) == 9
    with TestClient(app) as client:
        response = client.get('/release-if-learned/v1/summary')
        body = response.json()
        assert body['result_snapshot_sha256'] == client.get('/release-if/v1/summary').json()['snapshot_sha256']
    expected = dict(body); expected.pop('snapshot_sha256')
    assert body['snapshot_sha256'] == sha256(canonical(expected)).hexdigest()
    assert canonical(expected).count(b'"max_features":1.0') == 2
    assert body['populations'] == dict(total=176, common=55, unscored=121,
        test_total=48, test_common=18, training=17, calibration=4, preprocessing_fit=18)
    assert body['replay'] is None
    assert body['views']['current13']['checks']['input_pair_binding'] == 'NOT_PERFORMED'


@pytest.mark.parametrize('index', range(6))
def test_every_top_slot_missing_has_initial_precedence(monkeypatch, index):
    values = list(hand_tuple())
    object.__delattr__(values[index], fields(values[index])[-1].name)
    with pytest.raises(api().ReleaseIFLearnedViewError, match='INVALID_VIEW_ARGUMENTS'):
        build(monkeypatch, values)


@pytest.mark.parametrize('field', ['raw_identity', 'prepared_identity', 'result_identity', 'population_sha256', 'configuration_sha256', 'feature_columns', 'fit_runtime_id', 'train_count'])
def test_native_invalid_stale_declaration_substitutions_fail(monkeypatch, field):
    from traffic_anomaly import release_if_learned_contract as c
    values = list(hand_tuple()); old = values[3].context
    value = getattr(old, field)
    if field.endswith('identity'): value = replace(value, manifest_sha256='f' * 64)
    elif field == 'feature_columns': value = value[::-1]
    elif field == 'train_count': value += 1
    elif field == 'fit_runtime_id': value = 'foreign'
    else: value = 'f' * 64
    values[3] = replace(values[3], context=replace(old, **{field: value}))
    with pytest.raises(api().ReleaseIFLearnedViewError, match='INPUT_BINDING_MISMATCH'):
        build(monkeypatch, values)


def test_native_range_precedence_and_nested_primitive(monkeypatch):
    for count, code in ((10001, 'RESOURCE_LIMIT'), (True, 'INPUT_BINDING_MISMATCH')):
        values = list(hand_tuple()); values[3] = replace(values[3], context=replace(values[3].context, minute_count=count))
        with pytest.raises(api().ReleaseIFLearnedViewError, match=code): build(monkeypatch, values)
    values = list(hand_tuple()); object.__delattr__(values[1].context.configuration, 'epsilon')
    with pytest.raises(api().ReleaseIFLearnedViewError, match='INPUT_BINDING_MISMATCH'): build(monkeypatch, values)


def test_real_lf_metadata_and_aggregate_edges(monkeypatch):
    m, app = build(monkeypatch)
    with TestClient(app) as client: size = len(client.get('/release-if-learned/v1/summary').content)
    monkeypatch.setattr(m, '_SUMMARY_LIMIT', size)
    build(monkeypatch)
    monkeypatch.setattr(m, '_SUMMARY_LIMIT', size - 1)
    with pytest.raises(m.ReleaseIFLearnedViewError, match='RESOURCE_LIMIT'): build(monkeypatch)
    monkeypatch.setattr(m, '_SUMMARY_LIMIT', 65536)
    total = size + sum(map(len, [b'<html>learned</html>', b'export {}', b'body{}'])) + sum(map(len, m._ERRORS.values()))
    monkeypatch.setattr(m, '_TOTAL_LIMIT', total); build(monkeypatch)
    monkeypatch.setattr(m, '_TOTAL_LIMIT', total - 1)
    with pytest.raises(m.ReleaseIFLearnedViewError, match='RESOURCE_LIMIT'): build(monkeypatch)


def test_first_repeated_nine_routes_are_frozen(monkeypatch):
    import builtins
    import io
    import os
    from pathlib import Path
    from traffic_api import release_if_result_view as old
    from traffic_anomaly import release_iforest, release_inputs, release_if_learned_summary
    from traffic_anomaly import iforest_numeric_state as p1, release_if_learned as learned_operation
    from traffic_anomaly import release_minute_package, release_input_package, release_if_result_package, release_if_learned_package
    from traffic_anomaly.evaluation import calibration
    from traffic_anomaly import release_if_learned_contract as lc, release_if_result_contract as rc, release_model_inputs as pair
    m, app = build(monkeypatch)
    def forbidden(*a, **kw): pytest.fail('request performed registration work')
    with TestClient(app) as client:
        with monkeypatch.context() as guard:
            for module, names in ((m, ('_read_assets', '_resource_files', '_json_bytes', 'sha256', 'pair_release_model_inputs', 'verify_release_if_result_pair', 'summarize_release_if_learned', '_population_sha256')),
                    (lc, ('encode_release_if_learned_package', 'decode_release_if_learned_package', '_population_sha256')),
                    (rc, ('verify_release_if_result_pair', 'encode_release_if_result_package', 'decode_release_if_result_package', 'calibrate')),
                    (pair, ('pair_release_model_inputs',)), (old, ('_json_bytes', 'sha256', '_read_assets')),
                    (release_iforest, ('_validated_inputs', '_compute')),
                    (release_inputs, ('prepare_release_inputs', 'verify_release_input_derivation', '_validate_content')),
                    (release_if_learned_summary, ('encode_release_if_learned_package', 'summarize_release_if_learned')),
                    (p1, ('score_iforest_numeric_state',)),
                    (learned_operation, ('replay_release_iforest_learned', 'fit_release_iforest_learned', '_p1_call', '_models')),
                    (release_minute_package, ('load_release_minute_package',)),
                    (release_input_package, ('load_release_input_package',)),
                    (release_if_result_package, ('load_release_if_result_package',)),
                    (release_if_learned_package, ('load_release_if_learned_package',)),
                    (calibration, ('calibrate',))):
                for name in names: guard.setattr(module, name, forbidden)
            guard.setattr(builtins, 'open', forbidden)
            guard.setattr(io, 'open', forbidden)
            guard.setattr(os, 'open', forbidden)
            guard.setattr(os, 'stat', forbidden)
            guard.setattr(os, 'lstat', forbidden)
            guard.setattr(Path, 'open', forbidden)
            guard.setattr(old.resources, 'files', forbidden)
            for _ in range(2):
                for route in app.routes:
                    assert client.get(route.path).status_code == 200
                    response = client.get(route.path + '?page=0')
                    assert response.status_code == (200 if route.path.endswith('/series') else 422)
                    assert client.head(route.path).content == b''
                    assert client.post(route.path).status_code == 405
                assert client.get('/missing').content == b'{"error":"NOT_FOUND"}\n'


@pytest.mark.parametrize('length,code', [(65536, None), (65537, 'RESOURCE_LIMIT'), (0, 'VIEW_UNAVAILABLE')])
def test_actual_asset_read_cap_scoped_to_new_alias(monkeypatch, length, code):
    m = api(); reads = []
    class Resource:
        def joinpath(self, name): return self
        def open(self, mode):
            assert mode == 'rb'
            class Stream(BytesIO):
                def read(self, size=-1): reads.append(size); return super().read(size)
            return Stream(b'x' * length)
    monkeypatch.setattr(m, '_resource_files', lambda name: Resource())
    if code:
        with pytest.raises(m.ReleaseIFLearnedViewError, match=code): m.create_release_if_learned_view_app(*hand_tuple())
    else:
        app = m.create_release_if_learned_view_app(*hand_tuple())
        with TestClient(app) as client:
            for path, _, _ in m._ASSETS: assert len(client.get(path).content) == 65536
        assert reads == [65537] * 3


@pytest.mark.parametrize('stage', ['pair', 'result', 'summary', 'population', 'old'])
def test_stage_specific_native_error_is_not_read_at_wrong_stage(monkeypatch, stage):
    from traffic_anomaly import release_if_learned_contract as lc, release_if_result_contract as rc
    from traffic_anomaly.release_model_inputs import ReleaseModelInputPairError
    m = api()
    names = dict(pair='pair_release_model_inputs', result='verify_release_if_result_pair',
        summary='summarize_release_if_learned', population='_population_sha256', old='create_release_if_result_view_app')
    wrong = rc.ReleaseIFResultPackageError('RESOURCE_LIMIT') if stage in ('pair', 'summary', 'population', 'old') else lc.ReleaseIFLearnedError('RESOURCE_LIMIT')
    def fail(*a, **kw): raise wrong
    monkeypatch.setattr(m, names[stage], fail)
    with pytest.raises(m.ReleaseIFLearnedViewError, match='VIEW_UNAVAILABLE'): build(monkeypatch)


@pytest.mark.parametrize('kind,code', [('attribute', 'VIEW_UNAVAILABLE'), ('memory', 'RESOURCE_LIMIT')])
def test_dependency_unexpected_attribute_is_not_owned_nested_error(monkeypatch, kind, code):
    m = api()
    def fail(*a): raise (AttributeError('private') if kind == 'attribute' else MemoryError())
    monkeypatch.setattr(m, 'pair_release_model_inputs', fail)
    with pytest.raises(m.ReleaseIFLearnedViewError, match=code): build(monkeypatch)


def test_registration_call_counts_and_actual_shared_source(monkeypatch):
    from traffic_anomaly import release_if_learned_summary as shared
    from pathlib import Path
    m = api(); calls = []
    for name in ('pair_release_model_inputs', 'verify_release_if_result_pair',
            'summarize_release_if_learned', '_population_sha256', 'create_release_if_result_view_app'):
        original = getattr(m, name)
        def wrap(*a, original=original, name=name, **kw):
            calls.append(name); return original(*a, **kw)
        monkeypatch.setattr(m, name, wrap)
    build(monkeypatch)
    assert calls == ['pair_release_model_inputs', 'verify_release_if_result_pair',
        'verify_release_if_result_pair', 'summarize_release_if_learned', 'summarize_release_if_learned',
        '_population_sha256', '_population_sha256', 'create_release_if_result_view_app']
    assert sha256(Path(shared.__file__).read_bytes()).hexdigest() == 'c84dd0a78a388feaaddc9b4498e36a8647b76ea2d0538a39af869c12be1006e4'


@pytest.mark.parametrize('fault,expected', [(RuntimeError(), 'VIEW_UNAVAILABLE'), (MemoryError(), 'RESOURCE_LIMIT'), (KeyboardInterrupt(), None)])
def test_owned_native_code_getter_once_and_precedence(monkeypatch, fault, expected):
    from traffic_anomaly.release_model_inputs import ReleaseModelInputPairError
    m = api(); native = ReleaseModelInputPairError('RESOURCE_LIMIT'); reads = []
    def code(error): reads.append(1); raise fault
    def fail(*a): raise native
    monkeypatch.setattr(ReleaseModelInputPairError, 'code', property(code), raising=False)
    monkeypatch.setattr(m, 'pair_release_model_inputs', fail)
    if expected is None:
        with pytest.raises(KeyboardInterrupt): build(monkeypatch)
    else:
        with pytest.raises(m.ReleaseIFLearnedViewError, match=expected): build(monkeypatch)
    assert reads == [1]


def test_all_top_level_slots_and_late_missing_precedence(monkeypatch):
    for index in range(6):
        for field in fields(hand_tuple()[index]):
            values = list(hand_tuple()); object.__delattr__(values[index], field.name)
            if index > 0: object.__setattr__(values[0], 'identity', None)
            with pytest.raises(api().ReleaseIFLearnedViewError, match='INVALID_VIEW_ARGUMENTS'):
                build(monkeypatch, values)


@pytest.mark.parametrize('stage', ['pair', 'old'])
@pytest.mark.parametrize('replacement', ['owned', 'native'])
def test_delta_owned_getter_replacements_are_unavailable(monkeypatch, stage, replacement):
    from traffic_anomaly.release_model_inputs import ReleaseModelInputPairError
    m = api(); values = hand_tuple(); reads = []
    cls = ReleaseModelInputPairError if stage == 'pair' else m.ReleaseIFResultViewError
    error = cls('RESOURCE_LIMIT')
    replaced = m.ReleaseIFLearnedViewError('RESOURCE_LIMIT') if replacement == 'owned' else cls('RESOURCE_LIMIT')
    def getter(self): reads.append(1); raise replaced
    def fail(*a): raise error
    monkeypatch.setattr(cls, 'code', property(getter), raising=False)
    monkeypatch.setattr(m, 'pair_release_model_inputs' if stage == 'pair' else 'create_release_if_result_view_app', fail)
    with pytest.raises(m.ReleaseIFLearnedViewError) as caught: build(monkeypatch, values)
    assert caught.value.args == ('VIEW_UNAVAILABLE',) and reads == [1]


def test_delta_wrong_stage_owned_view_error_from_old_composition(monkeypatch):
    m = api()
    def fail(*a): raise m.ReleaseIFLearnedViewError('RESOURCE_LIMIT')
    monkeypatch.setattr(m, 'create_release_if_result_view_app', fail)
    with pytest.raises(m.ReleaseIFLearnedViewError, match='VIEW_UNAVAILABLE'): build(monkeypatch)


def test_delta_view_foreign_class_probe_is_never_read(monkeypatch):
    m = api(); probes = []
    class Foreign(Exception):
        @property
        def __class__(self): probes.append(1); return MemoryError
    def fail(*a): raise Foreign()
    monkeypatch.setattr(m, 'pair_release_model_inputs', fail)
    with pytest.raises(m.ReleaseIFLearnedViewError, match='VIEW_UNAVAILABLE'): build(monkeypatch)
    assert probes == []


@pytest.mark.parametrize('change', ['raw', 'prepared', 'result', 'population', 'configuration'])
def test_delta_coherent_cross_tuple_mismatch_rejected_before_composition(monkeypatch, change):
    from traffic_anomaly import release_if_learned_contract as lc
    from traffic_anomaly.release_if_learned_summary import summarize_release_if_learned
    m = api(); values = list(hand_tuple()); learned = values[3]; context = learned.context
    if change in ('raw', 'prepared', 'result'):
        name = change + '_identity'
        context = replace(context, **{name: replace(getattr(context, name), manifest_sha256='f' * 64)})
    elif change == 'configuration': context = replace(context, configuration_sha256='f' * 64)
    else:
        result = values[2].result
        # Use an alternate valid same-count calibration set, leaving the train/fit relation intact.
        digest = lc._population_sha256(minute_count=176, scored_mask=result.scored_mask,
            train_indices=result.train_indices, calibration_indices=(123, 124, 125, 126),
            preprocessing_fit_indices=result.preprocessing_fit_indices)
        assert digest != context.population_sha256
        context = replace(context, population_sha256=digest)
    values[3] = lc._make_release_if_learned_package(context, learned.state)
    summary = summarize_release_if_learned(values[3])
    assert summary['counts'] == summarize_release_if_learned(learned)['counts']
    assert summary['learned_identity'] != summarize_release_if_learned(learned)['learned_identity']
    def forbidden(*a): pytest.fail('old composition reached before cross binding')
    monkeypatch.setattr(m, 'create_release_if_result_view_app', forbidden)
    with pytest.raises(m.ReleaseIFLearnedViewError, match='INPUT_BINDING_MISMATCH'): build(monkeypatch, values)


@pytest.mark.parametrize('swap', ['results', 'learned', 'both'])
def test_delta_swapped_native_views_rejected_before_composition(monkeypatch, swap):
    m = api(); values = list(hand_tuple())
    if swap in ('results', 'both'): values[2], values[4] = values[4], values[2]
    if swap in ('learned', 'both'): values[3], values[5] = values[5], values[3]
    monkeypatch.setattr(m, 'create_release_if_result_view_app', lambda *a: pytest.fail('composed swapped tuple'))
    with pytest.raises(m.ReleaseIFLearnedViewError, match='INPUT_BINDING_MISMATCH'): build(monkeypatch, values)


def test_later_mutation_cannot_change_frozen_bytes(monkeypatch):
    values = hand_tuple(); m, app = build(monkeypatch, values)
    with TestClient(app) as client:
        before = [client.get(r.path).content for r in app.routes]
        object.__setattr__(values[3].context, 'view', 'foreign')
        object.__setattr__(values[2].result, 'scores', ())
        monkeypatch.setattr(m, '_read_assets', lambda: (_ for _ in ()).throw(AssertionError()))
        assert before == [client.get(r.path).content for r in app.routes]


def test_delta_separate_wholly_unscored_test_segment_can_exceed_common(monkeypatch):
    from traffic_anomaly.release_model_inputs import pair_release_model_inputs
    from traffic_anomaly.release_if_result_contract import make_release_if_result_package
    from traffic_anomaly import release_if_learned_contract as lc
    values = list(hand_tuple()); raw, prepared = values[:2]; extra = 100
    segment = replace(raw.segments[-1], id='unscored-test', start=raw.segments[-1].end,
        end=raw.segments[-1].end + timedelta(minutes=extra))
    segments = (*raw.segments, segment)
    stamps = tuple(raw.minutes.timestamps[-1] + timedelta(minutes=i + 1) for i in range(extra))
    kinds = (('unknown',) * 3,) * extra; false = (False,) * extra; null = ((None,) * 13,) * extra
    raw_minutes = replace(raw.minutes, timestamps=raw.minutes.timestamps + stamps,
        segment_ids=raw.minutes.segment_ids + (segment.id,) * extra,
        roles=raw.minutes.roles + ('test',) * extra, values=raw.minutes.values + null,
        source_valid=raw.minutes.source_valid + false, label_kinds=raw.minutes.label_kinds + kinds,
        bucket_counts=raw.minutes.bucket_counts + (raw.minutes.bucket_counts[0],) * extra)
    object.__setattr__(raw, 'minutes', raw_minutes); object.__setattr__(raw, 'segments', segments)
    minutes = prepared.minutes
    minutes = replace(minutes, timestamps=minutes.timestamps + stamps,
        segment_ordinals=minutes.segment_ordinals + (4,) * extra, raw_valid=minutes.raw_valid + false,
        current_values=minutes.current_values + null, prepared_valid=minutes.prepared_valid + false,
        prepared_reason=minutes.prepared_reason + ('source_invalid',) * extra,
        common_valid=minutes.common_valid + false, histories=tuple(replace(h,
            residual=h.residual + null, valid=h.valid + false,
            invalid_reason=h.invalid_reason + ('invalid_input',) * extra) for h in minutes.histories))
    quals = tuple(replace(q, **{f.name: getattr(q, f.name) + false for f in fields(q) if f.name != 'policy'})
        for q in prepared.labels.qualification_masks)
    labels = replace(prepared.labels, label_kinds=prepared.labels.label_kinds + kinds,
        fit_mask=prepared.labels.fit_mask + false, qualification_masks=quals)
    prepared = replace(prepared, context=replace(prepared.context, segments=segments, minute_count=276),
        minutes=minutes, labels=labels, preprocessing=replace(prepared.preprocessing,
            fit_mask_sha256=sha256(canonical(dict(schema_version=1, minute_count=276, mask=labels.fit_mask))).hexdigest()))
    values[1] = prepared
    pair = pair_release_model_inputs(raw, prepared)
    for index in (2, 4):
        old = values[index]; result = replace(old.result, scores=old.result.scores + (None,) * extra,
            predictions=old.result.predictions + (None,) * extra, scored_mask=old.result.scored_mask + false)
        saved_result = make_release_if_result_package(pair, result)
        learned = values[index + 1]
        population = lc._population_sha256(minute_count=276, **{k: getattr(result, k) for k in
            ('scored_mask', 'train_indices', 'calibration_indices', 'preprocessing_fit_indices')})
        context = replace(learned.context, minute_count=276, population_sha256=population,
            result_identity=lc.ReleaseIFLearnedReference(**asdict(saved_result.identity)))
        values[index] = saved_result
        values[index + 1] = lc._make_release_if_learned_package(context, learned.state)
    _, app = build(monkeypatch, values)
    with TestClient(app) as client:
        counts = client.get('/release-if-learned/v1/summary').json()['populations']
        old = client.get('/release-if/v1/summary').json()
    assert counts['test_total'] == 148 > counts['common'] == 55
    assert counts['test_common'] == 18
    assert old['axis']['segments'][-1]['id'] == 'unscored-test'
    assert old['axis']['segments'][-1]['minute_count'] == 100
    assert old['axis']['segments'][-1]['scored_count'] == 0
    assert old['axis']['scored_count'] == counts['common']


def test_delta_exact_new_route_errors_and_security_headers(monkeypatch):
    m, app = build(monkeypatch)
    with TestClient(app) as client:
        for path in ('/release-if-learned/v1/summary', *(p for p, _, _ in m._ASSETS)):
            success = client.get(path)
            assert success.headers['cache-control'] == 'no-store'
            assert success.headers['x-content-type-options'] == 'nosniff'
            assert 'access-control-allow-origin' not in success.headers
            if path == '/release/learned': assert success.headers['content-security-policy'] == m._CSP
            else: assert 'content-security-policy' not in success.headers
            for method, status, code in (('GET', 422, 'INVALID_QUERY'), ('POST', 405, 'METHOD_NOT_ALLOWED'), ('HEAD', 405, 'METHOD_NOT_ALLOWED')):
                response = client.request(method, path + '?x=1')
                assert response.status_code == status
                assert response.content == (b'' if method == 'HEAD' else canonical(dict(error=code)))
                assert response.headers['content-type'] == 'application/json'
                assert response.headers['cache-control'] == 'no-store'
                assert response.headers['x-content-type-options'] == 'nosniff'
                assert 'access-control-allow-origin' not in response.headers
                if status == 405: assert response.headers['allow'] == 'GET'
