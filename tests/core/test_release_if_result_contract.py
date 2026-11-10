"""Saved results check bounded internal consistency, never estimator execution."""
from dataclasses import asdict, fields, replace, FrozenInstanceError
from datetime import datetime, timedelta
import builtins
import hashlib
import importlib
import json
import math

import pytest

from traffic_anomaly import release_if_result_contract as contract
from tests.core.release_if_result_cases import hand_pair, hand_result, canonical, reference_members


def api():
    # Initial missing-module RED is retained in the private execution log. Once
    # implemented, exercise the normal import path rather than a missing API shim.
    return contract


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_hand_written_dual_view_canonical_codec_and_pair_binding(view):
    c = api()
    pair = hand_pair()
    result = hand_result(pair, view)
    package = c.make_release_if_result_package(pair, result)
    expected = reference_members(pair, view)
    assert dict(c.encode_release_if_result_package(package)) == expected
    loaded = c.decode_release_if_result_package(expected)
    assert loaded == package
    assert loaded.result.threshold == 2.9699999999999998
    assert loaded.result.scores[0] is None
    assert loaded.result.scored_mask[30] is False
    assert loaded.result.scores[31] == 0.
    assert math.copysign(1., loaded.result.scores[31]) == -1.
    assert loaded.result.predictions[31] is False
    assert loaded.result.preprocessing_fit_indices == tuple(range(30, 48))
    assert loaded.result.calibration_indices == (124, 125, 126, 127)
    assert c.verify_release_if_result_pair(loaded, pair) is None
    assert len(fields(loaded.context)) == 16
    assert len(fields(loaded.context.segments[0])) == 4
    for obj, name in ((loaded, 'result'), (loaded.context, 'view'),
                      (loaded.context.calibration, 'quantile')):
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, None)


def reseal(members, *, result_change=None, context_change=None):
    """Recompute refs with stdlib only; changes remain subject to product validation."""
    result = json.loads(members['result.json'])
    manifest = json.loads(members['manifest.json'])
    if result_change:
        result_change(result)
    if context_change:
        context_change(manifest['context'])
    digest = hashlib.sha256(canonical(manifest['context'])).hexdigest()
    result['context_sha256'] = manifest['context_sha256'] = digest
    payload = canonical(result)
    manifest['members'] = {'result.json': {'byte_count': len(payload),
                                         'sha256': hashlib.sha256(payload).hexdigest()}}
    manifest_payload = canonical(manifest)
    complete = json.loads(members['COMPLETE.json'])
    complete['manifest'] = {'byte_count': len(manifest_payload),
                            'sha256': hashlib.sha256(manifest_payload).hexdigest()}
    return {'result.json': payload, 'manifest.json': manifest_payload,
            'COMPLETE.json': canonical(complete)}


def rejection(call, code):
    c = api()
    with pytest.raises(c.ReleaseIFResultPackageError) as caught:
        call()
    assert caught.value.code == code
    assert str(caught.value) == code


@pytest.mark.parametrize('threshold', [2.97, 2.969])
def test_unchanged_predictions_do_not_make_wrong_q99_valid(threshold):
    c = api()
    pair = hand_pair()
    rejection(lambda: c.make_release_if_result_package(pair,
        replace(hand_result(pair), threshold=threshold)), 'INCONSISTENT_PACKAGE')
    changed = reseal(reference_members(), result_change=lambda r: r.update(threshold=threshold))
    rejection(lambda: c.decode_release_if_result_package(changed), 'INCONSISTENT_PACKAGE')


@pytest.mark.parametrize(('change', 'code'), [
    (lambda r: r.update(extra=None), 'INVALID_PACKAGE'),
    (lambda r: r.update(schema_version=True), 'INVALID_PACKAGE'),
    (lambda r: r.update(schema_version=2), 'INCOMPATIBLE_PACKAGE'),
    (lambda r: r.update(profile_id='unknown'), 'INCOMPATIBLE_PACKAGE'),
    (lambda r: r.update(threshold=3), 'INVALID_PACKAGE'),
    (lambda r: r['scored_mask'].__setitem__(0, 0), 'INVALID_PACKAGE'),
    (lambda r: r['scores'].__setitem__(31, False), 'INVALID_PACKAGE'),
    (lambda r: r['scores'].__setitem__(31, None), 'INCONSISTENT_PACKAGE'),
    (lambda r: r['scores'].__setitem__(0, 0.), 'INCONSISTENT_PACKAGE'),
    (lambda r: r['predictions'].__setitem__(31, 0), 'INVALID_PACKAGE'),
    (lambda r: r['predictions'].__setitem__(31, True), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(train_indices=[31, 31]), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(train_indices=[True]), 'INVALID_PACKAGE'),
    (lambda r: r.update(train_indices=[]), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(calibration_indices=[31]), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(preprocessing_fit_indices=[31]), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(preprocessing_fit_indices=[78, *range(31, 48)]), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(preprocessing_fit_indices=list(range(31, 48)) + [78]), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(train_indices=[10000]), 'INCONSISTENT_PACKAGE'),
    (lambda r: r.update(train_indices=[31] * 10001), 'RESOURCE_LIMIT'),
    (lambda r: (r['scores'].__setitem__(0, 0.), r['predictions'].__setitem__(0, False),
                r['scored_mask'].__setitem__(0, True)), 'INCONSISTENT_PACKAGE'),
])
def test_resealed_result_types_and_semantics_still_validate(change, code):
    c = api()
    members = reseal(reference_members(), result_change=change)
    rejection(lambda: c.decode_release_if_result_package(members), code)


@pytest.mark.parametrize(('change', 'code'), [
    (lambda x: x.update(extra=False), 'INVALID_PACKAGE'),
    (lambda x: x.update(profile_id='unknown'), 'INCOMPATIBLE_PACKAGE'),
    (lambda x: x.update(result_profile_id='unknown'), 'INCOMPATIBLE_PACKAGE'),
    (lambda x: x.update(view='h15_26'), 'INCOMPATIBLE_PACKAGE'),
    (lambda x: x.update(source_authentication='VERIFIED'), 'INCONSISTENT_PACKAGE'),
    (lambda x: x.update(time_basis='UTC'), 'INCONSISTENT_PACKAGE'),
    (lambda x: x.update(policy_status='ACTIVE'), 'INCONSISTENT_PACKAGE'),
    (lambda x: x.update(audit_fit_policy='P_X'), 'INVALID_PACKAGE'),
    (lambda x: x.update(score_direction='SCORE_SAMPLES'), 'INCONSISTENT_PACKAGE'),
    (lambda x: x.update(minute_count=True), 'INVALID_PACKAGE'),
    (lambda x: x.update(minute_count=175), 'INCONSISTENT_PACKAGE'),
    (lambda x: x.update(minute_count=10001), 'RESOURCE_LIMIT'),
    (lambda x: x['calibration'].update(quantile=1), 'INVALID_PACKAGE'),
    (lambda x: x['calibration'].update(method='nearest'), 'INCONSISTENT_PACKAGE'),
    (lambda x: x['model_configuration'].update(bootstrap=0), 'INVALID_PACKAGE'),
    (lambda x: x['model_configuration'].update(max_samples=18), 'INCONSISTENT_PACKAGE'),
    (lambda x: x['raw_identity'].update(context_sha256='G' * 64), 'INVALID_PACKAGE'),
    (lambda x: x['prepared_identity'].update(manifest_byte_count=True), 'INVALID_PACKAGE'),
    (lambda x: x['prepared_identity'].update(manifest_byte_count=65537), 'RESOURCE_LIMIT'),
    (lambda x: x['segments'][0].update(ordinal=True), 'INVALID_PACKAGE'),
    (lambda x: x['segments'][0].update(ordinal=1), 'INCONSISTENT_PACKAGE'),
    (lambda x: x['segments'][0].update(id='x' * 129), 'RESOURCE_LIMIT'),
    (lambda x: x['segments'][0].update(id='a\x7f'), 'INVALID_PACKAGE'),
    (lambda x: x['segments'][1].update(id='s0'), 'INCONSISTENT_PACKAGE'),
    (lambda x: x['segments'][1].update(role='test'), 'INCONSISTENT_PACKAGE'),
    (lambda x: x['segments'][0].update(start='2026-01-01T00:00:01'), 'INVALID_PACKAGE'),
    (lambda x: x['segments'][0].update(start='2026-02-30T00:00:00'), 'INVALID_PACKAGE'),
    (lambda x: x.update(segments=x['segments'] * 2), 'RESOURCE_LIMIT'),
])
def test_resealed_context_fields_roles_and_types(change, code):
    c = api()
    rejection(lambda: c.decode_release_if_result_package(
        reseal(reference_members(), context_change=change)), code)


def test_byte_refs_and_declared_identity_or_report_cannot_lie():
    c = api()
    members = reference_members()
    members['result.json'] = members['result.json'].replace(b'4.0', b'5.0')
    rejection(lambda: c.decode_release_if_result_package(members), 'INTEGRITY_MISMATCH')
    package = c.decode_release_if_result_package(reference_members())
    rejection(lambda: c.encode_release_if_result_package(replace(package,
        identity=replace(package.identity, manifest_sha256='f' * 64))), 'INTEGRITY_MISMATCH')
    rejection(lambda: c.encode_release_if_result_package(replace(package,
        load_report=replace(package.load_report, model_execution='MATCHED'))), 'INCONSISTENT_PACKAGE')
    rejection(lambda: c.encode_release_if_result_package(replace(package,
        identity=asdict(package.identity))), 'INVALID_PACKAGE')


def test_internal_consistency_is_distinct_from_explicit_pair_binding():
    c = api()
    pair = hand_pair()
    members = reseal(reference_members(), context_change=lambda x:
        x['raw_identity'].update(manifest_sha256='f' * 64))
    package = c.decode_release_if_result_package(members)
    assert dict(c.encode_release_if_result_package(package)) == members
    rejection(lambda: c.verify_release_if_result_pair(package, pair), 'INPUT_BINDING_MISMATCH')
    def unscore(r):
        r['scores'][78] = r['predictions'][78] = None
        r['scored_mask'][78] = False
    package = c.decode_release_if_result_package(reseal(reference_members(), result_change=unscore))
    rejection(lambda: c.verify_release_if_result_pair(package, pair), 'INPUT_BINDING_MISMATCH')
    rejection(lambda: c.make_release_if_result_package(pair, package.result), 'INPUT_BINDING_MISMATCH')
    shifted = replace(pair, segments=tuple(replace(s, start=s.start + timedelta(days=1),
        end=s.end + timedelta(days=1)) for s in pair.segments), prepared_minutes=replace(
            pair.prepared_minutes, timestamps=tuple(t + timedelta(days=1)
                for t in pair.prepared_minutes.timestamps)))
    package = c.make_release_if_result_package(pair, hand_result(pair))
    rejection(lambda: c.verify_release_if_result_pair(package, shifted), 'INPUT_BINDING_MISMATCH')
    rejection(lambda: c.verify_release_if_result_pair(package, object()), 'INVALID_PACKAGE')


@pytest.mark.parametrize('cal_scores', [(0.,), (1.,) * 4, (-0.,) * 4])
def test_single_all_equal_and_zero_q99_strict_greater(cal_scores):
    c = api()
    members = reference_members()
    def change(r):
        indices = [124] if len(cal_scores) == 1 else [124, 125, 126, 127]
        r['calibration_indices'] = indices
        for i, score in zip(indices, cal_scores):
            r['scores'][i] = score
        r['threshold'] = cal_scores[0]
        r['predictions'] = [None if score is None else score > cal_scores[0] for score in r['scores']]
    package = c.decode_release_if_result_package(reseal(members, result_change=change))
    assert package.result.threshold == cal_scores[0]
    assert all(package.result.predictions[i] is False for i in package.result.calibration_indices)
    assert package.result.predictions[158] is True


def test_q99_overflow_safely_rejected_and_nonfinite_never_parsed():
    c = api()
    def overflow(r):
        r['scores'][124:128] = [-1.7e308, -1.7e308, -1.7e308, 1.7e308]
        r['predictions'][124:128] = [False, False, False, True]
    rejection(lambda: c.decode_release_if_result_package(
        reseal(reference_members(), result_change=overflow)), 'INCONSISTENT_PACKAGE')
    for score in (math.nan, math.inf, -math.inf):
        pair = hand_pair()
        result = hand_result(pair)
        rejection(lambda: c.make_release_if_result_package(pair,
            replace(result, scores=result.scores[:31] + (score,) + result.scores[32:])), 'INVALID_PACKAGE')


def test_pure_codec_and_binding_do_not_prepare_fit_score_or_open_sources(monkeypatch):
    c = api()
    pair = hand_pair()
    result = hand_result(pair)
    def forbidden(*args, **kwargs):
        raise AssertionError('external execution forbidden')
    model = importlib.import_module('traffic_anomaly.release_iforest')
    inputs = importlib.import_module('traffic_anomaly.release_inputs')
    monkeypatch.setattr(model, '_compute', forbidden)
    monkeypatch.setattr(model, 'fit_release_iforest', forbidden)
    for name in ('prepare_release_inputs', '_fit_state', '_fit_statistics', '_transform',
                 '_history', 'verify_release_input_derivation'):
        monkeypatch.setattr(inputs, name, forbidden)
    original_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name == 'sklearn' or name.startswith('sklearn.'):
            return forbidden()
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(builtins, 'open', forbidden)
    package = c.make_release_if_result_package(pair, result)
    assert c.verify_release_if_result_pair(c.decode_release_if_result_package(
        dict(c.encode_release_if_result_package(package))), pair) is None


@pytest.mark.parametrize('payload', [b'{}', b'{}\n\n', b'\xef\xbb\xbf{}\n', b'\xff\n',
    b'{"a":1,"a":1}\n', b'{"a":NaN}\n', b'{"a":Infinity}\n', b'{"a":123456789}\n',
    b'{"a":0.123456789012345678901234567890123}\n', b'[' * 1100 + b']' * 1100 + b'\n'])
def test_invalid_complete_json_is_safely_rejected(payload):
    c = api()
    members = reference_members()
    members['COMPLETE.json'] = payload
    rejection(lambda: c.decode_release_if_result_package(members), 'INVALID_PACKAGE')


def test_member_budget_precedes_json_parsing_and_exact_argument_types():
    c = api()
    for name, limit in c.PACKAGE_MEMBER_BYTE_LIMITS:
        members = reference_members()
        members[name] = b'x' * (limit + 1)
        rejection(lambda: c.decode_release_if_result_package(members), 'RESOURCE_LIMIT')
    for members in ([], {}, {**reference_members(), 'extra.json': b'{}\n'},
                    {**reference_members(), 'result.json': bytearray(b'{}\n')}):
        rejection(lambda: c.decode_release_if_result_package(members), 'INVALID_PACKAGE_ARGUMENTS')
    assert str(c.ReleaseIFResultPackageError('private-data')) == 'INVALID_PACKAGE'


@pytest.mark.parametrize('index', [0, 29])
def test_preprocessing_fit_rejects_segment_prefix_but_offset30_unscored_stays_legal(index):
    c = api()
    members = reseal(reference_members(), result_change=lambda r:
        r.update(preprocessing_fit_indices=[index, *range(30, 48)]))
    rejection(lambda: c.decode_release_if_result_package(members), 'INCONSISTENT_PACKAGE')
    good = c.decode_release_if_result_package(reference_members())
    assert good.result.preprocessing_fit_indices[0] == 30
    assert good.result.scored_mask[30] is False


def maximal_members():
    """10000 minutes, seven ordered roles, gaps, 128 Unicode codepoints and
    longest finite binary64 token. Independent documents, no estimator."""
    members = reference_members()
    counts = (1430, 1430, 1430, 1430, 1430, 1430, 1420)
    roles = ('train', 'train', 'validation', 'validation', 'calibration', 'test', 'test')
    start = datetime(2026, 1, 1)
    segments = []
    mask = []
    for ordinal, (count, role) in enumerate(zip(counts, roles)):
        end = start + timedelta(minutes=count)
        segments.append(dict(ordinal=ordinal, id=chr(0x1F600 + ordinal) * 128,
            role=role, start=start.isoformat(), end=end.isoformat()))
        mask.extend([False] * 30 + [True] * (count - 30))
        start = end + timedelta(minutes=7)
    # All scores equal: shared Q99 must preserve the extreme finite value.
    extreme = -1.7976931348623157e308
    def change_result(r):
        r.update(scores=[extreme if ok else None for ok in mask],
            predictions=[False if ok else None for ok in mask], scored_mask=mask,
            threshold=extreme, train_indices=list(range(30, 1430)),
            calibration_indices=list(range(5750, 7150)),
            preprocessing_fit_indices=list(range(30, 2860)))
        # The first30 of secondtrain segment must stay excluded from fit too.
        r['preprocessing_fit_indices'] = list(range(30, 1430)) + list(range(1460, 2860))
    def change_context(x):
        x.update(segments=segments, minute_count=10000)
        x['model_configuration']['max_samples'] = 32
    return reseal(members, result_change=change_result, context_change=change_context)


def test_actual_maximum_axis_unicode_ids_extreme_floats_and_all_three_bytes_roundtrip():
    c = api()
    expected = maximal_members()
    package = c.decode_release_if_result_package(expected)
    assert package.context.minute_count == 10000
    assert len(package.context.segments) == 7
    assert len(package.context.segments[0].id) == 128
    assert len(package.context.segments[0].id.encode('utf-8')) == 512
    assert sum(package.result.scored_mask) == 9790
    assert len(package.result.train_indices) == 1400
    assert len(package.result.calibration_indices) == 1400
    assert len(package.result.preprocessing_fit_indices) == 2800
    assert package.result.threshold == -1.7976931348623157e308
    assert dict(c.encode_release_if_result_package(package)) == expected
    for name, limit in c.PACKAGE_MEMBER_BYTE_LIMITS:
        assert len(expected[name]) <= limit
    assert sum(map(len, expected.values())) <= 1118208
    assert len(canonical(json.loads(expected['manifest.json'])['context'])) <= 16384


def test_context_limit_plus_one_precedes_context_field_traversal():
    c = api()
    base = reference_members()
    context = json.loads(base['manifest.json'])['context']
    original_length = len(canonical(context))
    padding = 16385 - original_length
    over = reseal(base, context_change=lambda x:
        x.update(time_basis=x['time_basis'] + 'x' * padding))
    assert len(canonical(json.loads(over['manifest.json'])['context'])) == 16385
    rejection(lambda: c.decode_release_if_result_package(over), 'RESOURCE_LIMIT')


def test_supplied_container_types_and_lengths_are_checked_before_entries():
    c = api()
    package = c.decode_release_if_result_package(reference_members())
    class Untouchable:
        def __eq__(self, other):
            raise AssertionError('entries traversed before length bound')
    rejection(lambda: c.encode_release_if_result_package(replace(package, result=replace(
        package.result, train_indices=(Untouchable(),) * 177))), 'RESOURCE_LIMIT')
    rejection(lambda: c.encode_release_if_result_package(replace(package, result=replace(
        package.result, scored_mask=(Untouchable(),) * 10001))), 'RESOURCE_LIMIT')
    rejection(lambda: c.encode_release_if_result_package(replace(package,
        context=replace(package.context, segments=(Untouchable(),) * 8))), 'RESOURCE_LIMIT')
    rejection(lambda: c.encode_release_if_result_package(replace(package,
        context=replace(package.context, calibration={'quantile': .99, 'method': 'linear',
                                                     'comparison': 'STRICT_GREATER'}))), 'INVALID_PACKAGE')


def test_missing_dataclass_storage_is_a_safe_invalid_package():
    c = api()
    package = c.decode_release_if_result_package(reference_members())
    broken = object.__new__(c.ReleaseIFResultContext)
    rejection(lambda: c.encode_release_if_result_package(replace(package, context=broken)), 'INVALID_PACKAGE')


def test_negative_zero_canonical_float_and_valid_self_consistent_score_rewrite():
    c = api()
    base = reference_members()
    def change(r):
        r['scores'][158] = 99.
    changed = reseal(base, result_change=change)
    package = c.decode_release_if_result_package(changed)
    assert package.result.scores[158] == 99.
    assert package.result.predictions[158] is True
    assert package.result.threshold == 2.9699999999999998
    assert c.verify_release_if_result_pair(package, hand_pair()) is None
    assert b'-0.0' in base['result.json']
    noncanonical = base['result.json'].replace(b'-0.0', b'-0e0', 1)
    bad = dict(base, **{'result.json': noncanonical})
    # Bind the noncanonical member's actual bytes to isolate canonicality.
    manifest = json.loads(base['manifest.json'])
    manifest['members']['result.json'] = dict(byte_count=len(noncanonical),
        sha256=hashlib.sha256(noncanonical).hexdigest())
    bad['manifest.json'] = canonical(manifest)
    complete = json.loads(base['COMPLETE.json'])
    complete['manifest'] = dict(byte_count=len(bad['manifest.json']),
        sha256=hashlib.sha256(bad['manifest.json']).hexdigest())
    bad['COMPLETE.json'] = canonical(complete)
    rejection(lambda: c.decode_release_if_result_package(bad), 'INVALID_PACKAGE')


@pytest.mark.parametrize(('change', 'code'), [
    (dict(profile_id='unknown'), 'INCOMPATIBLE_PACKAGE'),
    (dict(view='unknown'), 'INCOMPATIBLE_PACKAGE'),
    (dict(threshold=float('nan')), 'INVALID_PACKAGE'),
    (dict(scores=()), 'INCONSISTENT_PACKAGE'),
    (dict(scored_mask=(False,) * 10001), 'RESOURCE_LIMIT'),
])
def test_make_validates_result_before_allocating_pair_numbers(monkeypatch, change, code):
    c = api()
    pair = hand_pair()
    result = replace(hand_result(pair), **change)
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid result reached pair numeric validation')
    monkeypatch.setattr(c, '_validated_inputs', forbidden)
    rejection(lambda: c.make_release_if_result_package(pair, result), code)


def test_declared_identity_context_hash_and_manifest_length_are_all_bound():
    c = api()
    package = c.decode_release_if_result_package(reference_members())
    for change in (dict(context_sha256='f' * 64), dict(manifest_byte_count=1)):
        rejection(lambda: c.encode_release_if_result_package(replace(package,
            identity=replace(package.identity, **change))), 'INTEGRITY_MISMATCH')
    members = reference_members()
    manifest = json.loads(members['manifest.json'])
    manifest['context_sha256'] = 'f' * 64
    members['manifest.json'] = canonical(manifest)
    complete = json.loads(members['COMPLETE.json'])
    complete['manifest'] = dict(byte_count=len(members['manifest.json']),
        sha256=hashlib.sha256(members['manifest.json']).hexdigest())
    members['COMPLETE.json'] = canonical(complete)
    rejection(lambda: c.decode_release_if_result_package(members), 'INTEGRITY_MISMATCH')


def test_keyboard_interrupt_in_pure_pair_validation_propagates(monkeypatch):
    c = api()
    pair = hand_pair()
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(c, '_validated_inputs', interrupted)
    with pytest.raises(KeyboardInterrupt):
        c.make_release_if_result_package(pair, hand_result(pair))


@pytest.mark.parametrize('view', ['current13', 'h30_26'])
def test_make_binds_independently_valid_175_result_before_joint_176_axis_validation(view):
    c = api()
    pair = hand_pair()
    def shorten_result(r):
        for name in ('scores', 'predictions', 'scored_mask'):
            r[name] = r[name][:-1]
    def shorten_context(x):
        x['minute_count'] = 175
        x['segments'][-1]['end'] = '2026-01-01T02:55:00'
    members = reseal(reference_members(view=view), result_change=shorten_result,
                     context_change=shorten_context)
    shortened = c.decode_release_if_result_package(members)
    assert shortened.context.minute_count == 175
    assert len(shortened.result.scores) == len(shortened.result.predictions) == 175
    assert len(shortened.result.scored_mask) == 175
    assert shortened.result.train_indices == tuple(range(31, 48))
    assert shortened.result.calibration_indices == (124, 125, 126, 127)
    assert shortened.result.threshold == 2.9699999999999998
    # Each operand is independently legal: the original pair binds its original
    # result, and the shortened result passed the full independent saved codec.
    original = c.make_release_if_result_package(pair, hand_result(pair, view))
    assert original.context.minute_count == 176
    rejection(lambda: c.make_release_if_result_package(pair, shortened.result),
              'INPUT_BINDING_MISMATCH')
