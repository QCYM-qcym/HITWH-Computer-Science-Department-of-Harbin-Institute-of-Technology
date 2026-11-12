"""Learned metadata composes manual P1 state without importing model code."""
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


P = 'c17-release-iforest-learned-package-v1'
RUNTIME = 'python314-numpy254-sklearn191-joblib160-serial-wm1024-v1'
RULES = 'c17-release-log1p-mad-input-rules-v1'
NAMES = ('completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
    'duration_p95_s', 'no_backward_packet_source_record_count')
CODES = ('INVALID_LEARNED_ARGUMENTS INVALID_LEARNED_PACKAGE INCOMPATIBLE_LEARNED_PACKAGE '
    'RESOURCE_LIMIT INTEGRITY_MISMATCH INPUT_BINDING_MISMATCH NO_TRAINING_NORMAL '
    'NO_CALIBRATION_NORMAL INVALID_INPUT_NUMERIC MODEL_UNAVAILABLE MODEL_ERROR '
    'INVALID_MODEL_STATE INVALID_MODEL_SCORES SCORE_MISMATCH CALIBRATION_MISMATCH '
    'PREDICTION_MISMATCH INCOMPATIBLE_RUNTIME INVALID_PACKAGE_PATH INPUT_UNAVAILABLE '
    'OUTPUT_EXISTS PACKAGE_CHANGED OUTPUT_ERROR LEARNED_ERROR').split()


def api():
    name = 'traffic_anomaly.release_if_learned_contract'
    assert importlib.util.find_spec(name) is not None, 'learned contract module is missing'
    return importlib.import_module(name)


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def digest(payload):
    return {'byte_count': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


def manual(*, view='current13', m=2, train=None):
    c = api()
    from traffic_anomaly.iforest_numeric_state import (
        IForestNumericNode as Node, IForestNumericTree as Tree, IForestNumericState)
    width = 13 if view == 'current13' else 26
    # Two leaves retain a signed-zero threshold without any numerical scoring.
    nodes = ((Node(1, 2, 0, -0.0, m), Node(None, None, None, None, 1),
        Node(None, None, None, None, m - 1)) if m > 1 else
        (Node(None, None, None, None, 1),))
    state = IForestNumericState(1, 'iforest-numeric-state-v1',
        'iforest16-m32-f32route-f64path-numpy254-v1', width, tuple(range(width)),
        m, tuple(Tree(nodes) for _ in range(16)))
    ref = lambda p: c.ReleaseIFLearnedReference(p, 'a' * 64, 'b' * 64, 1)
    columns = tuple('current:' + n for n in NAMES)
    if width == 26:
        columns += tuple('residual_h30:' + n for n in NAMES)
    config = c.ReleaseIFLearnedConfiguration(width, 16, m, 1., False, 'auto', 42, 1)
    context = c.ReleaseIFLearnedContext(P, view,
        ref('c17-release-minute-package-v1'), ref('c17-release-prepared-input-package-v1'),
        ref('c17-release-iforest-result-package-v1'), 'c' * 64, 100,
        m if train is None else train, 1, 40, 'd' * 64, RULES, columns, config, RUNTIME)
    return context, state


def package(**kwargs):
    c = api()
    return c._make_release_if_learned_package(*manual(**kwargs))


def members(**kwargs):
    c = api()
    return dict(c.encode_release_if_learned_package(package(**kwargs)))


def rejection(call, code):
    c = api()
    with pytest.raises(c.ReleaseIFLearnedError) as caught:
        call()
    assert type(caught.value) is c.ReleaseIFLearnedError
    assert caught.value.code == code
    assert caught.value.args == (code,)
    assert str(caught.value) == code
    assert caught.value.__cause__ is None


def reseal(original, *, context_change=None, manifest_change=None, state_bytes=None):
    result = dict(original)
    manifest = json.loads(result['manifest.json'])
    if context_change:
        context_change(manifest['context'])
    if state_bytes is not None:
        result['numeric-state.json'] = state_bytes
    manifest['context_sha256'] = hashlib.sha256(canonical(manifest['context'])).hexdigest()
    manifest['members'] = {'numeric-state.json': digest(result['numeric-state.json'])}
    if manifest_change:
        manifest_change(manifest)
    result['manifest.json'] = canonical(manifest)
    result['COMPLETE.json'] = canonical({'schema_version': 1, 'profile_id': P,
        'status': 'COMPLETE', 'manifest': digest(result['manifest.json'])})
    return result


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
@pytest.mark.parametrize('m', [1, 2, 32])
def test_manual_state_three_members_and_identity(view, m):
    c = api()
    p = package(view=view, m=m)
    encoded = c.encode_release_if_learned_package(p)
    assert tuple(name for name, _ in encoded) == ('numeric-state.json', 'manifest.json', 'COMPLETE.json')
    saved = dict(encoded)
    ref = lambda profile: {'profile_id': profile, 'context_sha256': 'a' * 64,
        'manifest_sha256': 'b' * 64, 'manifest_byte_count': 1}
    columns = ['current:' + name for name in NAMES]
    if view == 'h30_26':
        columns += ['residual_h30:' + name for name in NAMES]
    expected_context = {'profile_id': P, 'view': view,
        'raw_identity': ref('c17-release-minute-package-v1'),
        'prepared_identity': ref('c17-release-prepared-input-package-v1'),
        'result_identity': ref('c17-release-iforest-result-package-v1'),
        'configuration_sha256': 'c' * 64, 'minute_count': 100, 'train_count': m,
        'calibration_count': 1, 'preprocessing_fit_count': 40, 'population_sha256': 'd' * 64,
        'input_rules_id': RULES, 'feature_columns': columns, 'fit_runtime_id': RUNTIME,
        'model_configuration': {'input_width': len(columns), 'n_estimators': 16,
            'max_samples': m, 'max_features': 1., 'bootstrap': False,
            'contamination': 'auto', 'random_state': 42, 'n_jobs': 1}}
    from traffic_anomaly.iforest_numeric_state import encode_iforest_numeric_state
    expected_state = encode_iforest_numeric_state(p.state)
    expected_manifest = canonical({'schema_version': 1, 'profile_id': P,
        'context_sha256': hashlib.sha256(canonical(expected_context)).hexdigest(),
        'context': expected_context, 'members': {'numeric-state.json': digest(expected_state)}})
    assert saved == {'numeric-state.json': expected_state, 'manifest.json': expected_manifest,
        'COMPLETE.json': canonical({'schema_version': 1, 'profile_id': P,
            'status': 'COMPLETE', 'manifest': digest(expected_manifest)})}
    manifest = json.loads(saved['manifest.json'])
    assert set(manifest) == {'schema_version', 'profile_id', 'context_sha256', 'context', 'members'}
    assert len(manifest['context']) == 15
    assert manifest['members'] == {'numeric-state.json': digest(saved['numeric-state.json'])}
    assert manifest['context_sha256'] == hashlib.sha256(canonical(manifest['context'])).hexdigest()
    assert json.loads(saved['COMPLETE.json']) == {'schema_version': 1, 'profile_id': P,
        'status': 'COMPLETE', 'manifest': digest(saved['manifest.json'])}
    assert p.identity == c.ReleaseIFLearnedReference(P, manifest['context_sha256'],
        hashlib.sha256(saved['manifest.json']).hexdigest(), len(saved['manifest.json']))
    assert p.load_report == c.ReleaseIFLearnedLoadReport(P,
        'SAVED_LEARNED_INTERNAL_CONSISTENCY_ONLY', 'MATCHED', 'MATCHED', 'NOT_RUN',
        'NOT_AUTHENTICATED', 'NOT_AUTHENTICATED')
    loaded = c.decode_release_if_learned_package(saved)
    assert loaded == p
    assert c.encode_release_if_learned_package(loaded) == encoded
    assert all(payload.endswith(b'\n') and not payload.endswith(b'\n\n')
        and len(payload) <= limit for (name, payload), limit in zip(encoded, (262144, 8192, 4096)))
    if m > 1:
        assert math.copysign(1., loaded.state.trees[0].nodes[0].threshold) == -1.


def test_contract_exact_classes_slots_missing_slots_and_report_integrity():
    c = api()
    p = package()
    expected = [('ReleaseIFLearnedReference', 'profile_id context_sha256 manifest_sha256 manifest_byte_count'),
        ('ReleaseIFLearnedConfiguration', 'input_width n_estimators max_samples max_features bootstrap contamination random_state n_jobs'),
        ('ReleaseIFLearnedContext', 'profile_id view raw_identity prepared_identity result_identity configuration_sha256 minute_count train_count calibration_count preprocessing_fit_count population_sha256 input_rules_id feature_columns model_configuration fit_runtime_id'),
        ('ReleaseIFLearnedLoadReport', 'profile_id scope byte_integrity structure numerical_replay source_authentication model_origin'),
        ('ReleaseIFLearnedPackage', 'identity context state load_report')]
    objects = [p.identity, p.context.model_configuration, p.context, p.load_report, p]
    for (name, names), obj in zip(expected, objects):
        kind = getattr(c, name)
        assert tuple(f.name for f in fields(kind)) == tuple(names.split())
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError):
            setattr(obj, names.split()[0], None)
        missing = object.__new__(kind)
        changed = (replace(p, identity=missing) if obj is p.identity else
            replace(p, context=replace(p.context, model_configuration=missing))
            if obj is p.context.model_configuration else replace(p, context=missing)
            if obj is p.context else replace(p, load_report=missing)
            if obj is p.load_report else missing)
        rejection(lambda: c.encode_release_if_learned_package(changed), 'INVALID_LEARNED_PACKAGE')
    rejection(lambda: c.encode_release_if_learned_package(replace(p,
        identity=replace(p.identity, manifest_sha256='e' * 64))), 'INTEGRITY_MISMATCH')
    rejection(lambda: c.encode_release_if_learned_package(replace(p,
        load_report=replace(p.load_report, numerical_replay='MATCHED'))), 'INTEGRITY_MISMATCH')


@pytest.mark.parametrize('code', CODES)
def test_only_finite_error_codes_escape(code):
    c = api()
    assert c.ReleaseIFLearnedError(code).args == (code,)


def test_top_level_shapes_subclasses_and_unknown_constructor_values():
    c = api()
    class Text(str):
        def __eq__(self, other):
            raise AssertionError('foreign comparison')
        __hash__ = str.__hash__
    class Tuple(tuple):
        def __iter__(self):
            raise AssertionError('foreign iteration')
    class Package(c.ReleaseIFLearnedPackage):
        pass
    for value in ('foreign', Text('RESOURCE_LIMIT'), None, 1, []):
        assert c.ReleaseIFLearnedError(value).args == ('LEARNED_ERROR',)
    p = package()
    rejection(lambda: c.encode_release_if_learned_package(Package(
        p.identity, p.context, p.state, p.load_report)), 'INVALID_LEARNED_ARGUMENTS')
    for value in (None, [], {}, {'x': b''}, dict(members(), **{'COMPLETE.json': bytearray()})):
        rejection(lambda: c.decode_release_if_learned_package(value), 'INVALID_LEARNED_ARGUMENTS')
    rejection(lambda: c._make_release_if_learned_package(replace(p.context,
        feature_columns=Tuple(p.context.feature_columns)), p.state), 'INVALID_LEARNED_PACKAGE')


@pytest.mark.parametrize('field,value,code', [
    ('minute_count', True, 'INVALID_LEARNED_PACKAGE'),
    ('minute_count', 0, 'INVALID_LEARNED_PACKAGE'),
    ('minute_count', 10001, 'RESOURCE_LIMIT'),
    ('train_count', 41, 'INPUT_BINDING_MISMATCH'),
    ('calibration_count', 99, 'INPUT_BINDING_MISMATCH'),
    ('preprocessing_fit_count', 101, 'INPUT_BINDING_MISMATCH'),
    ('population_sha256', 'D' * 64, 'INVALID_LEARNED_PACKAGE'),
    ('configuration_sha256', 'g' * 64, 'INVALID_LEARNED_PACKAGE'),
    ('profile_id', 'unknown', 'INCOMPATIBLE_LEARNED_PACKAGE'),
    ('view', 'h15_26', 'INCOMPATIBLE_LEARNED_PACKAGE'),
    ('input_rules_id', 'unknown', 'INCOMPATIBLE_LEARNED_PACKAGE'),
    ('fit_runtime_id', 'unknown', 'INCOMPATIBLE_LEARNED_PACKAGE'),
    ('feature_columns', (), 'INCOMPATIBLE_LEARNED_PACKAGE'),
    ('feature_columns', ('x',) * 27, 'RESOURCE_LIMIT'),
    ('feature_columns', (True,) * 13, 'INVALID_LEARNED_PACKAGE')])
def test_context_primitives_limits_fixed_values_and_relations(field, value, code):
    c = api()
    context, state = manual()
    rejection(lambda: c._make_release_if_learned_package(replace(context, **{field: value}), state), code)


@pytest.mark.parametrize('field,value,code', [
    ('input_width', True, 'INVALID_LEARNED_PACKAGE'), ('input_width', 26, 'INCOMPATIBLE_LEARNED_PACKAGE'),
    ('n_estimators', 15, 'INCOMPATIBLE_LEARNED_PACKAGE'), ('max_samples', 0, 'INVALID_LEARNED_PACKAGE'),
    ('max_samples', 33, 'RESOURCE_LIMIT'), ('max_samples', 1, 'INPUT_BINDING_MISMATCH'),
    ('max_features', 1, 'INVALID_LEARNED_PACKAGE'), ('max_features', float('nan'), 'INVALID_LEARNED_PACKAGE'),
    ('max_features', .5, 'INCOMPATIBLE_LEARNED_PACKAGE'), ('bootstrap', 0, 'INVALID_LEARNED_PACKAGE'),
    ('bootstrap', True, 'INCOMPATIBLE_LEARNED_PACKAGE'), ('contamination', 'x', 'INCOMPATIBLE_LEARNED_PACKAGE'),
    ('random_state', 0, 'INCOMPATIBLE_LEARNED_PACKAGE'), ('n_jobs', 2, 'INCOMPATIBLE_LEARNED_PACKAGE')])
def test_configuration_exact_types_caps_fixed_values_and_train_binding(field, value, code):
    c = api()
    context, state = manual()
    changed = replace(context.model_configuration, **{field: value})
    rejection(lambda: c._make_release_if_learned_package(replace(context, model_configuration=changed), state), code)


def test_reference_profiles_caps_semantic_order_and_valid_p1_binding():
    c = api()
    context, state = manual()
    for field in ('raw_identity', 'prepared_identity', 'result_identity'):
        ref = getattr(context, field)
        for change, code in [({'profile_id': P}, 'INCOMPATIBLE_LEARNED_PACKAGE'),
                ({'manifest_byte_count': True}, 'INVALID_LEARNED_PACKAGE'),
                ({'manifest_byte_count': 0}, 'INVALID_LEARNED_PACKAGE'),
                ({'manifest_byte_count': 65537}, 'RESOURCE_LIMIT'),
                ({'context_sha256': 'A' * 64}, 'INVALID_LEARNED_PACKAGE')]:
            rejection(lambda: c._make_release_if_learned_package(replace(context,
                **{field: replace(ref, **change)}), state), code)
    rejection(lambda: c._make_release_if_learned_package(replace(context,
        feature_columns=tuple(reversed(context.feature_columns))), state), 'INCOMPATIBLE_LEARNED_PACKAGE')
    other_context, other_state = manual(view='h30_26')
    rejection(lambda: c._make_release_if_learned_package(context, other_state), 'INPUT_BINDING_MISMATCH')
    rejection(lambda: c._make_release_if_learned_package(context, manual(m=1)[1]), 'INPUT_BINDING_MISMATCH')
    from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
    assert NAMES == G13U_FEATURE_NAMES
    assert c._feature_columns('current13') == context.feature_columns
    assert c._feature_columns('h30_26') == other_context.feature_columns
    rejection(lambda: c._feature_columns('h15_26'), 'INCOMPATIBLE_LEARNED_PACKAGE')


@pytest.mark.parametrize('change,code', [
    (lambda x: x.update(extra=1), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.pop('view'), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.update(view='h15_26'), 'INCOMPATIBLE_LEARNED_PACKAGE'),
    (lambda x: x.update(minute_count=True), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.update(feature_columns=['x'] * 27), 'RESOURCE_LIMIT'),
    (lambda x: x['model_configuration'].update(extra=1), 'INVALID_LEARNED_PACKAGE')])
def test_resealed_context_cannot_bypass_typed_validation(change, code):
    c = api()
    rejection(lambda: c.decode_release_if_learned_package(reseal(members(), context_change=change)), code)


@pytest.mark.parametrize('payload', [b'\xef\xbb\xbf{}\n', b'\xff', b'{}', b'{}\n\n',
    b'{"x":1,"x":1}\n', b'{"x":NaN}\n', b'{"x":Infinity}\n',
    b'{"x":123456789}\n', b'{"x":0.123456789012345678901234567890123}\n', b'[]\n'])
def test_complete_parser_rejects_noncanonical_or_malformed_metadata(payload):
    c = api()
    saved = members()
    saved['COMPLETE.json'] = payload
    rejection(lambda: c.decode_release_if_learned_package(saved), 'INVALID_LEARNED_PACKAGE')


def test_precedence_and_all_member_budgets_before_json_or_p1():
    c = api()
    for name, limit in [('numeric-state.json', 262144), ('manifest.json', 8192), ('COMPLETE.json', 4096)]:
        saved = members()
        saved['COMPLETE.json'] = b'\xff'
        saved[name] = b'\xff' * (limit + 1)
        rejection(lambda: c.decode_release_if_learned_package(saved), 'RESOURCE_LIMIT')
    saved = members()
    saved['numeric-state.json'] = b'not json'
    saved['manifest.json'] = b'not json'
    rejection(lambda: c.decode_release_if_learned_package(saved), 'INTEGRITY_MISMATCH')
    saved = reseal(members(), context_change=lambda x: x.update(minute_count=True), state_bytes=b'bad')
    rejection(lambda: c.decode_release_if_learned_package(saved), 'INVALID_LEARNED_PACKAGE')
    saved = reseal(members(), manifest_change=lambda x: x['members']['numeric-state.json'].update(byte_count=262145))
    rejection(lambda: c.decode_release_if_learned_package(saved), 'RESOURCE_LIMIT')


@pytest.mark.parametrize('change,code', [
    (lambda x: x.update(extra=1), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.update(schema_version=True), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.update(schema_version=2), 'INCOMPATIBLE_LEARNED_PACKAGE'),
    (lambda x: x.update(profile_id='unknown'), 'INCOMPATIBLE_LEARNED_PACKAGE'),
    (lambda x: x.update(status='PENDING'), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x['manifest'].update(byte_count=True), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x['manifest'].update(byte_count=0), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x['manifest'].update(byte_count=8193), 'RESOURCE_LIMIT'),
    (lambda x: x['manifest'].update(byte_count=1), 'INTEGRITY_MISMATCH'),
    (lambda x: x['manifest'].update(sha256='A' * 64), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x['manifest'].update(sha256='e' * 64), 'INTEGRITY_MISMATCH')])
def test_complete_schema_and_declared_manifest_binding(change, code):
    c = api()
    saved = members()
    complete = json.loads(saved['COMPLETE.json'])
    change(complete)
    saved['COMPLETE.json'] = canonical(complete)
    rejection(lambda: c.decode_release_if_learned_package(saved), code)


@pytest.mark.parametrize('change,code', [
    (lambda x: x.update(extra=1), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.update(schema_version=True), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.update(schema_version=2), 'INCOMPATIBLE_LEARNED_PACKAGE'),
    (lambda x: x.update(profile_id='unknown'), 'INCOMPATIBLE_LEARNED_PACKAGE'),
    (lambda x: x.update(context_sha256='g' * 64), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x.update(context_sha256='e' * 64), 'INTEGRITY_MISMATCH'),
    (lambda x: x['members'].update(extra={}), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x['members']['numeric-state.json'].update(byte_count=True), 'INVALID_LEARNED_PACKAGE'),
    (lambda x: x['members']['numeric-state.json'].update(sha256='e' * 64), 'INTEGRITY_MISMATCH')])
def test_resealed_manifest_schema_and_state_binding(change, code):
    c = api()
    rejection(lambda: c.decode_release_if_learned_package(
        reseal(members(), manifest_change=change)), code)


def test_state_codec_remains_the_validation_authority():
    c = api()
    context, state = manual()
    rejection(lambda: c._make_release_if_learned_package(context,
        replace(state, version=2)), 'INCOMPATIBLE_LEARNED_PACKAGE')
    rejection(lambda: c._make_release_if_learned_package(context,
        replace(state, max_samples=True)), 'INVALID_LEARNED_PACKAGE')
    rejection(lambda: c._make_release_if_learned_package(context,
        replace(state, trees=state.trees + state.trees[:1])), 'RESOURCE_LIMIT')
    raw = json.loads(members()['numeric-state.json'])
    raw['version'] = 2
    rejection(lambda: c.decode_release_if_learned_package(
        reseal(members(), state_bytes=canonical(raw))), 'INCOMPATIBLE_LEARNED_PACKAGE')
    rejection(lambda: c.decode_release_if_learned_package(
        reseal(members(), state_bytes=b'not JSON')), 'INVALID_LEARNED_PACKAGE')


def populations():
    return dict(minute_count=4, scored_mask=(True, True, True, False),
        train_indices=(0, 1), calibration_indices=(2,), preprocessing_fit_indices=(0, 1, 3))


def test_population_digest_uses_exact_six_fields_and_allows_unscored_preprocessing():
    c = api()
    values = populations()
    expected = {'schema_version': 1, 'minute_count': 4, 'scored_mask': [True, True, True, False],
        'train_indices': [0, 1], 'calibration_indices': [2], 'preprocessing_fit_indices': [0, 1, 3]}
    assert c._population_sha256(**values) == hashlib.sha256(canonical(expected)).hexdigest()


@pytest.mark.parametrize('field,value,code', [
    ('minute_count', True, 'INVALID_LEARNED_PACKAGE'), ('minute_count', 10001, 'RESOURCE_LIMIT'),
    ('scored_mask', (True,) * 3, 'INVALID_LEARNED_PACKAGE'),
    ('scored_mask', (1, True, True, False), 'INVALID_LEARNED_PACKAGE'),
    ('train_indices', (), 'INVALID_LEARNED_PACKAGE'),
    ('train_indices', (1, 0), 'INVALID_LEARNED_PACKAGE'),
    ('train_indices', (0, 0), 'INVALID_LEARNED_PACKAGE'),
    ('train_indices', (False,), 'INVALID_LEARNED_PACKAGE'),
    ('train_indices', (4,), 'INVALID_LEARNED_PACKAGE'),
    ('calibration_indices', (0,), 'INPUT_BINDING_MISMATCH'),
    ('calibration_indices', (3,), 'INPUT_BINDING_MISMATCH'),
    ('preprocessing_fit_indices', (0,), 'INPUT_BINDING_MISMATCH'),
    ('preprocessing_fit_indices', (0,) * 5, 'RESOURCE_LIMIT')])
def test_population_shapes_ranges_and_relations(field, value, code):
    c = api()
    values = populations()
    values[field] = value
    rejection(lambda: c._population_sha256(**values), code)


def test_sibling_limits_precede_element_validation():
    c = api()
    values = populations()
    values['train_indices'] = (object(),)
    values['preprocessing_fit_indices'] = (0,) * 5
    rejection(lambda: c._population_sha256(**values), 'RESOURCE_LIMIT')
    context, state = manual()
    rejection(lambda: c._make_release_if_learned_package(replace(context,
        feature_columns=(object(),), train_count=10001), state), 'RESOURCE_LIMIT')


def test_decoded_primitive_shape_precedes_sibling_container_cap():
    c = api()
    saved = reseal(members(), context_change=lambda x: x.update(
        minute_count=True, feature_columns=['x'] * 27))
    rejection(lambda: c.decode_release_if_learned_package(saved), 'INVALID_LEARNED_PACKAGE')


def test_maximum_population_axis_and_train_above_sample_cap_remain_valid():
    c = api()
    assert package(m=32, train=33).context.train_count == 33
    values = {'minute_count': 10000, 'scored_mask': (True,) * 10000,
        'train_indices': tuple(range(5000)), 'calibration_indices': tuple(range(5000, 10000)),
        'preprocessing_fit_indices': tuple(range(10000))}
    expected = {'schema_version': 1, **{name: list(value) if type(value) is tuple else value
        for name, value in values.items()}}
    assert len(canonical(expected)) <= 262144
    assert c._population_sha256(**values) == hashlib.sha256(canonical(expected)).hexdigest()


@pytest.mark.parametrize('entry', ['maker', 'encode', 'decode'])
@pytest.mark.parametrize('failure,code', [('ordinary', 'LEARNED_ERROR'),
    ('foreign', 'LEARNED_ERROR'), ('memory', 'RESOURCE_LIMIT'), ('recursion', 'INVALID_LEARNED_PACKAGE')])
def test_metadata_parser_known_errors_and_unknown_domain_subclasses(monkeypatch, entry, failure, code):
    c = api()
    p = package()
    saved = dict(c.encode_release_if_learned_package(p))
    class Foreign(c.ReleaseIFLearnedError):
        def __init__(self):
            ValueError.__init__(self, 'private')
        @property
        def code(self):
            raise AssertionError('foreign getter')
    error = {'ordinary': TypeError('private'), 'foreign': Foreign(),
        'memory': MemoryError(), 'recursion': RecursionError()}[failure]
    def broken(*args, **kwargs):
        raise error
    # Parser errors belong to decode; unrelated failures on content encode do not.
    if entry == 'decode':
        monkeypatch.setattr(c.json, 'loads', broken)
    else:
        monkeypatch.setattr(c, 'encode_iforest_numeric_state', broken)
        if failure == 'recursion':
            code = 'LEARNED_ERROR'
    call = {'maker': lambda: c._make_release_if_learned_package(p.context, p.state),
        'encode': lambda: c.encode_release_if_learned_package(p),
        'decode': lambda: c.decode_release_if_learned_package(saved)}[entry]
    rejection(call, code)


@pytest.mark.parametrize('interrupt', [KeyboardInterrupt, SystemExit])
def test_control_flow_interrupts_propagate(monkeypatch, interrupt):
    c = api()
    context, state = manual()
    def broken(*args, **kwargs):
        raise interrupt
    monkeypatch.setattr(c, 'encode_iforest_numeric_state', broken)
    with pytest.raises(interrupt):
        c._make_release_if_learned_package(context, state)


@pytest.mark.parametrize('kind,code', [('memory', 'RESOURCE_LIMIT'), ('foreign', 'LEARNED_ERROR'),
    ('ordinary', 'LEARNED_ERROR'), ('upstream', 'INCOMPATIBLE_LEARNED_PACKAGE')])
def test_p1_codec_error_mapping_without_foreign_attribute_reads(monkeypatch, kind, code):
    c = api()
    from traffic_anomaly.iforest_numeric_state import IForestNumericStateError
    class Foreign(IForestNumericStateError):
        def __init__(self):
            ValueError.__init__(self, 'private')
        @property
        def code(self):
            raise AssertionError('foreign getter')
    error = {'memory': MemoryError(), 'foreign': Foreign(), 'ordinary': RuntimeError('private'),
        'upstream': IForestNumericStateError('INCOMPATIBLE_STATE')}[kind]
    context, state = manual()
    def broken(*args, **kwargs):
        raise error
    monkeypatch.setattr(c, 'encode_iforest_numeric_state', broken)
    rejection(lambda: c._make_release_if_learned_package(context, state), code)


def test_fresh_process_codec_imports_no_numerical_model_or_pickle_root():
    c = api()
    saved = members()
    script = textwrap.dedent('''
        import builtins, json, sys
        denied = {'numpy', 'sklearn', 'joblib', 'torch', 'pickle', 'cloudpickle'}
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.split('.')[0] in denied:
                raise AssertionError('forbidden dependency import: ' + name)
            return original(name, *args, **kwargs)
        builtins.__import__ = guarded
        from traffic_anomaly import release_if_learned_contract as c
        raw = json.loads(sys.stdin.read())
        payloads = {name: bytes.fromhex(value) for name, value in raw.items()}
        loaded = c.decode_release_if_learned_package(payloads)
        assert dict(c.encode_release_if_learned_package(loaded)) == payloads
        assert not any(name.split('.')[0] in denied for name in sys.modules)
        print('COLD_CODEC_PASS')
    ''')
    done = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', script],
        input=json.dumps({name: value.hex() for name, value in saved.items()}),
        capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    assert done.stdout == 'COLD_CODEC_PASS\n'
