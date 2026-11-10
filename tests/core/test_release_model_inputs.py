"""Hand-written exact values, not evidence of loading or numeric derivation."""
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
import builtins
import importlib
import io
import os
import pickle
import socket

import pytest

from traffic_anomaly._release_minutes import (
    ReleaseBucketCounts, ReleaseMinuteResult, ReleaseSegment,
)
from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
from traffic_anomaly.release_minute_contract import ReleaseMinutePackage, ReleaseMinutePackageIdentity
from traffic_anomaly.release_inputs import (
    ReleaseInputContext, ReleaseInputIdentity, ReleaseInputLabels, ReleaseInputLoadReport,
    ReleasePolicyQualification, ReleasePreparationConfig, ReleasePreparedHistory,
    ReleasePreparedInputs, ReleasePreparedMinutes, ReleasePreprocessState,
)
from traffic_anomaly.release_model_inputs import (
    ReleaseModelInputPairError, pair_release_model_inputs, summarize_release_model_inputs,
)

RAW_ROW = (0., 1., 2., 3., 4., 5., 6., 7., 8., 9., 10., 11., 12.)
CURRENT = (-6., -5., -4., -3., -2., -1., 0., 1., 2., 3., 4., 5., 6.)
RESIDUAL = (13., 14., 15., 16., 17., 18., 19., 20., 21., 22., 23., 24., 25.)
JOINED = (-6., -5., -4., -3., -2., -1., 0., 1., 2., 3., 4., 5., 6.,
          13., 14., 15., 16., 17., 18., 19., 20., 21., 22., 23., 24., 25.)
NULL13 = (None,) * 13
NULL26 = (None,) * 26
FALSE6 = (False,) * 6
QUAL_NAMES = ('train_full_history_normal', 'calibration_full_history_normal',
              'validation_current_normal', 'validation_current_attack', 'validation_current_unknown',
              'test_current_normal', 'test_current_attack', 'test_current_unknown')


def _exact(kind, **values):
    """Avoid raw package __post_init__ validation, only in this hand-built fixture."""
    instance = object.__new__(kind)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


def _raw_replace(raw, **values):
    return _exact(ReleaseMinutePackage, **{field.name: values.get(field.name, getattr(raw, field.name))
                                         for field in fields(raw)})


def _case(policy='P_U'):
    start = datetime(2026, 1, 1)
    stamps = tuple(start + timedelta(minutes=i) for i in range(6))
    segments = (ReleaseSegment('train', 'train', stamps[0], stamps[3]),
                ReleaseSegment('validation', 'validation', stamps[3], stamps[4]),
                ReleaseSegment('calibration', 'calibration', stamps[4], stamps[5]),
                ReleaseSegment('test', 'test', stamps[5], start + timedelta(minutes=6)))
    identity = ReleaseMinutePackageIdentity('c17-release-minute-package-v1', 'a' * 64, 'b' * 64, 123)
    raw_valid = (True, True, True, True, False, True)
    kinds = (('normal',) * 3, ('normal',) * 3, ('unknown', 'normal', 'attack'),
             ('unknown',) * 3, ('unknown',) * 3, ('attack',) * 3)
    # Diagnostics are deliberately unrelated to fixture labels; pair borrows none of them.
    bucket = ReleaseBucketCounts(0, 0, 0, (), (), (), (), (), False, False, 0)
    buckets = (bucket, bucket, bucket, bucket,
               replace(bucket, definite_attack_present=True), replace(bucket, definite_attack_present=True))
    result = ReleaseMinuteResult('c17-release-91-v1', (1,), ('0' * 64,), 'NOT_AUTHENTICATED',
        'SOURCE_WALL_CLOCK_COMPLETION_PROXY', G13U_FEATURE_NAMES, stamps,
        ('train', 'train', 'train', 'validation', 'calibration', 'test'),
        ('train', 'train', 'train', 'validation', 'calibration', 'test'),
        (RAW_ROW, RAW_ROW, RAW_ROW, RAW_ROW, NULL13, RAW_ROW), raw_valid, kinds, buckets,
        0, 0, 0, 0, 0, 0, (), (), (), (), ())
    raw = _exact(ReleaseMinutePackage, identity=identity, minutes=result, segments=segments,
                 scope='PACKAGE_INTERNAL_CONSISTENCY_ONLY')
    config = ReleasePreparationConfig(1, 'c17-release-log1p-mad-input-rules-v1', G13U_FEATURE_NAMES,
                                     (15, 30), 30, 1e-6, policy, 'AUDIT_ONLY')
    context = ReleaseInputContext('c17-release-prepared-input-package-v1', 'c17-release-91-v1',
        'NOT_AUTHENTICATED', 'SOURCE_WALL_CLOCK_COMPLETION_PROXY', identity, config, 'c' * 64, segments, 6)
    state = ReleasePreprocessState((0.,) * 13, (1.,) * 13, 2, 30, policy, 'd' * 64, 'e' * 64)
    h15 = ReleasePreparedHistory(15, (NULL13, RESIDUAL, RESIDUAL, RESIDUAL, NULL13, RESIDUAL),
                                (False, True, True, True, False, True),
                                ('warmup', None, None, None, 'invalid_input', None))
    h30 = ReleasePreparedHistory(30, (NULL13, RESIDUAL, NULL13, RESIDUAL, NULL13, RESIDUAL),
                                (False, True, False, True, False, True),
                                ('warmup', None, 'warmup', None, 'invalid_input', None))
    minutes = ReleasePreparedMinutes(stamps, (0, 0, 0, 1, 2, 3), raw_valid,
        (CURRENT, CURRENT, CURRENT, CURRENT, NULL13, CURRENT), raw_valid,
        (None, None, None, None, 'source_invalid', None), (h15, h30),
        (False, True, False, True, False, True))
    qualifications = tuple(ReleasePolicyQualification(p,
        (False, True, False, False, False, False) if p != 'P_B' else FALSE6,
        FALSE6, FALSE6, FALSE6, (False, False, False, True, False, False),
        FALSE6, (False, False, False, False, False, True), FALSE6) for p in ('P_U', 'P_B', 'P_A'))
    labels = ReleaseInputLabels(('P_U', 'P_B', 'P_A'), kinds,
                               (True, True, False, False, False, False), (0, 1), qualifications)
    saved_identity = ReleaseInputIdentity('c17-release-prepared-input-package-v1', 'f' * 64, '1' * 64, 456)
    report = ReleaseInputLoadReport('c17-release-prepared-input-package-v1', 'INTERNAL_CONSISTENCY_CHECKED',
        'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY', saved_identity, 'CHECKED', 'CHECKED',
        'NOT_PERFORMED', 'NOT_PERFORMED', 'NOT_REESTIMATED', 'NOT_AUTHENTICATED')
    return raw, ReleasePreparedInputs(saved_identity, context, state, minutes, labels, report)


def test_saved_pair_full_axis_and_populations():
    # Catches row filtering, wrong concat order, common-mask filtering, and fit/model conflation.
    raw, saved = _case()
    pair = pair_release_model_inputs(raw, saved)
    assert pair.profile_id == 'c17-release-model-input-pair-v1'
    assert pair.raw_identity is raw.identity
    assert pair.prepared_identity is saved.identity
    assert pair.raw_values == (RAW_ROW, RAW_ROW, RAW_ROW, RAW_ROW, NULL13, RAW_ROW)
    assert pair.raw_values is raw.minutes.values
    assert pair.prepared_minutes is saved.minutes
    assert pair.joined_h15 == (NULL26, JOINED, JOINED, JOINED, NULL26, JOINED)
    assert pair.joined_h30 == (NULL26, JOINED, NULL26, JOINED, NULL26, JOINED)
    assert pair.labels.saved is saved.labels
    assert pair.labels.definite_attack_present == (False, False, False, False, True, True)
    assert pair.population.preprocessing_fit_indices == (0, 1)
    assert pair.population.train_indices == (1,)
    assert pair.population.calibration_indices == ()
    assert pair.population.train_mask is saved.labels.qualification_masks[0].train_full_history_normal
    assert pair.raw_scope == 'PACKAGE_INTERNAL_CONSISTENCY_ONLY'
    assert pair.prepared_scope == 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY'
    assert pair.segments is raw.segments
    assert pair.segment_ids is raw.minutes.segment_ids
    assert pair.roles is raw.minutes.roles


def _mutation(raw, saved, name):
    r, m, c = raw.minutes, saved.minutes, saved.context
    if name == 'top': return None, saved
    if name == 'nested': return _raw_replace(raw, minutes=None), saved
    if name == 'identity': return raw, replace(saved, context=replace(c, upstream=replace(raw.identity, context_sha256='2' * 64)))
    if name == 'report': return raw, replace(saved, load_report=replace(saved.load_report, identity=replace(saved.identity, manifest_sha256='2' * 64)))
    if name == 'axis': return _raw_replace(raw, minutes=replace(r, timestamps=r.timestamps[:-1])), saved
    if name == 'timestamp': return _raw_replace(raw, minutes=replace(r, timestamps=(r.timestamps[1],) + r.timestamps[1:])), saved
    if name == 'segment': return _raw_replace(raw, segments=(replace(raw.segments[0], id='other'),) + raw.segments[1:]), saved
    if name == 'role': return _raw_replace(raw, minutes=replace(r, roles=('test',) + r.roles[1:])), saved
    if name == 'ordinal': return raw, replace(saved, minutes=replace(m, segment_ordinals=(True,) + m.segment_ordinals[1:]))
    if name == 'valid': return _raw_replace(raw, minutes=replace(r, source_valid=(False,) + r.source_valid[1:])), saved
    if name == 'label': return _raw_replace(raw, minutes=replace(r, label_kinds=(('attack',) * 3,) + r.label_kinds[1:])), saved
    if name == 'columns': return _raw_replace(raw, minutes=replace(r, feature_names=r.feature_names[::-1])), saved
    if name == 'windows': return raw, replace(saved, context=replace(c, configuration=replace(c.configuration, windows=(30, 15))))
    if name == 'source': return _raw_replace(raw, minutes=replace(r, source_authentication='AUTHENTICATED')), saved
    if name == 'nan': return raw, replace(saved, minutes=replace(m, current_values=((float('nan'),) + CURRENT[1:],) + m.current_values[1:]))
    if name == 'raw_negative': return _raw_replace(raw, minutes=replace(r, values=((-1.,) + RAW_ROW[1:],) + r.values[1:])), saved
    if name == 'raw_int': return _raw_replace(raw, minutes=replace(r, values=((0,) + RAW_ROW[1:],) + r.values[1:])), saved
    if name == 'width': return raw, replace(saved, minutes=replace(m, current_values=(CURRENT[:-1],) + m.current_values[1:]))
    if name == 'null': return raw, replace(saved, minutes=replace(m, current_values=m.current_values[:4] + (CURRENT,) + m.current_values[5:]))
    if name == 'mask_bool': return raw, replace(saved, minutes=replace(m, common_valid=(0,) + m.common_valid[1:]))
    if name == 'common': return raw, replace(saved, minutes=replace(m, common_valid=(True,) + m.common_valid[1:]))
    if name == 'reason': return raw, replace(saved, minutes=replace(m, prepared_reason=('secret',) + m.prepared_reason[1:]))
    if name == 'scale': return raw, replace(saved, preprocessing=replace(saved.preprocessing, scale=(0.,) * 13))
    if name == 'fit_indices': return raw, replace(saved, labels=replace(saved.labels, fit_indices=(1, 0)))
    if name == 'fit_count': return raw, replace(saved, preprocessing=replace(saved.preprocessing, n_samples_seen=1))
    if name == 'qualification':
        q = replace(saved.labels.qualification_masks[0], train_full_history_normal=(True,) + FALSE6[1:])
        return raw, replace(saved, labels=replace(saved.labels, qualification_masks=(q,) + saved.labels.qualification_masks[1:]))
    if name == 'attack_bool':
        b = replace(r.bucket_counts[0], definite_attack_present=1)
        return _raw_replace(raw, minutes=replace(r, bucket_counts=(b,) + r.bucket_counts[1:])), saved
    if name == 'n_bool': return raw, replace(saved, context=replace(c, minute_count=True))
    if name == 'n_zero': return raw, replace(saved, context=replace(c, minute_count=0))
    if name == 'n_limit': return raw, replace(saved, context=replace(c, minute_count=10001))
    if name == 'segment_limit': return _raw_replace(raw, segments=raw.segments * 2), saved
    if name == 'empty_segments': return _raw_replace(raw, segments=()), saved
    raise AssertionError(name)


@pytest.mark.parametrize(('name', 'code'), [
    ('top', 'INVALID_PAIR_ARGUMENTS'), ('nested', 'INVALID_PAIR_STRUCTURE'),
    ('identity', 'UPSTREAM_IDENTITY_MISMATCH'), ('report', 'PAIR_ALIGNMENT_MISMATCH'),
    ('axis', 'PAIR_ALIGNMENT_MISMATCH'), ('timestamp', 'PAIR_ALIGNMENT_MISMATCH'),
    ('segment', 'PAIR_ALIGNMENT_MISMATCH'), ('role', 'PAIR_ALIGNMENT_MISMATCH'),
    ('ordinal', 'INVALID_PAIR_STRUCTURE'), ('valid', 'PAIR_ALIGNMENT_MISMATCH'),
    ('label', 'PAIR_ALIGNMENT_MISMATCH'), ('columns', 'INCOMPATIBLE_PAIR'),
    ('windows', 'INCOMPATIBLE_PAIR'), ('source', 'INCOMPATIBLE_PAIR'),
    ('nan', 'INVALID_PAIR_STRUCTURE'), ('raw_negative', 'INVALID_PAIR_STRUCTURE'),
    ('raw_int', 'INVALID_PAIR_STRUCTURE'), ('width', 'INVALID_PAIR_STRUCTURE'),
    ('null', 'INVALID_PAIR_STRUCTURE'), ('mask_bool', 'INVALID_PAIR_STRUCTURE'),
    ('common', 'INVALID_PAIR_STRUCTURE'), ('reason', 'INVALID_PAIR_STRUCTURE'),
    ('scale', 'INVALID_PAIR_STRUCTURE'), ('fit_indices', 'INVALID_PAIR_STRUCTURE'),
    ('fit_count', 'INVALID_PAIR_STRUCTURE'), ('qualification', 'INVALID_PAIR_STRUCTURE'),
    ('attack_bool', 'INVALID_PAIR_STRUCTURE'), ('n_bool', 'INVALID_PAIR_STRUCTURE'),
    ('n_zero', 'INVALID_PAIR_STRUCTURE'), ('n_limit', 'RESOURCE_LIMIT'),
    ('segment_limit', 'RESOURCE_LIMIT'), ('empty_segments', 'INVALID_PAIR_STRUCTURE'),
])
def test_pair_rejects_named_mutations(name, code):
    # Each mutation targets a required validation branch, not old codec behavior.
    raw, saved = _mutation(*_case(), name)
    with pytest.raises(ReleaseModelInputPairError) as captured:
        pair_release_model_inputs(raw, saved)
    assert captured.value.code == code
    assert str(captured.value) == code


@pytest.mark.parametrize(('policy', 'expected'), [('P_U', (1,)), ('P_B', ()), ('P_A', (1,))])
def test_policy_population_and_attack_sidecar(policy, expected):
    raw, saved = _case(policy)
    pair = pair_release_model_inputs(raw, saved)
    assert pair.population.policy == policy
    assert pair.population.train_indices == expected
    assert pair.population.calibration_indices == ()
    assert pair.population.preprocessing_fit_indices == (0, 1)
    assert pair.labels.saved.qualification_masks is saved.labels.qualification_masks
    assert pair.labels.definite_attack_present[3:5] == (False, True)


def test_label_changes_keep_numeric_slots():
    raw, saved = _case()
    first = pair_release_model_inputs(raw, saved)
    kinds = saved.labels.label_kinds[:3] + (('attack',) * 3,) + saved.labels.label_kinds[4:]
    changed_raw = _raw_replace(raw, minutes=replace(raw.minutes, label_kinds=kinds))
    changed_saved = replace(saved, labels=replace(saved.labels, label_kinds=kinds))
    second = pair_release_model_inputs(changed_raw, changed_saved)
    assert first.raw_values == second.raw_values
    assert first.prepared_minutes == second.prepared_minutes
    assert first.joined_h15 == second.joined_h15
    assert first.joined_h30 == second.joined_h30
    assert second.labels.saved.label_kinds[3] == ('attack',) * 3


def test_pair_nested_immutable():
    pair = pair_release_model_inputs(*_case())
    for obj, attribute in ((pair, 'profile_id'), (pair.population, 'policy'),
                           (pair.labels, 'saved'), (pair.configuration, 'epsilon'),
                           (pair.preprocessing, 'mean'), (pair.prepared_minutes, 'raw_valid'),
                           (pair.labels.saved, 'fit_mask'), (pair.segments[0], 'id')):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attribute, None)
    with pytest.raises(TypeError):
        pair.joined_h15[1][0] = 0.


def test_summary_whitelist():
    pair = pair_release_model_inputs(*_case())
    summary = summarize_release_model_inputs(pair)
    assert set(summary) == {'version', 'profile_id', 'status', 'raw_identity', 'prepared_identity',
        'configuration', 'configuration_sha256', 'source', 'scopes', 'checks', 'feature_columns',
        'minute_counts', 'preprocessing_fit', 'model_population', 'qualification_counts'}
    assert summary['version'] == 1
    assert summary['status'] == 'INPUTS_PAIRED'
    assert summary['minute_counts'] == dict(total=6, raw_valid=5, prepared_valid=5,
        history_h15_valid=4, history_h30_valid=3, common_valid=3, definite_attack_present=2)
    assert summary['preprocessing_fit'] == dict(count=2, mask_sha256='d' * 64, rows_sha256='e' * 64)
    assert summary['model_population'] == dict(policy='P_U', train_count=1, calibration_count=0)
    assert summary['source'] == dict(schema_id='c17-release-91-v1', authentication='NOT_AUTHENTICATED',
                                    time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY')
    assert summary['checks'] == dict(derivation_replay='DERIVATION_REPLAY_NOT_PERFORMED',
        fit_parameters='NOT_REESTIMATED', model='MODEL_NOT_LOADED', execution='EXECUTION_NOT_GRANTED',
        external_case_evidence='NOT_ESTABLISHED')
    assert summary['scopes'] == dict(pair='READ_ONLY_MODEL_INPUT_PAIR',
        raw='PACKAGE_INTERNAL_CONSISTENCY_ONLY', prepared='SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY')
    assert summary['feature_columns']['raw13'] == list(G13U_FEATURE_NAMES)
    assert summary['feature_columns']['current13'] == list(G13U_FEATURE_NAMES)
    for window in (15, 30):
        assert summary['feature_columns'][f'h{window}_26'] == [
            *('current:' + name for name in G13U_FEATURE_NAMES),
            *(f'residual_h{window}:' + name for name in G13U_FEATURE_NAMES)]
    assert summary['qualification_counts'] == {
        'P_U': dict(zip(QUAL_NAMES, (1, 0, 0, 0, 1, 0, 1, 0))),
        'P_B': dict(zip(QUAL_NAMES, (0, 0, 0, 0, 1, 0, 1, 0))),
        'P_A': dict(zip(QUAL_NAMES, (1, 0, 0, 0, 1, 0, 1, 0)))}
    assert summary['configuration'] == dict(schema_version=1, numeric_rules_id='c17-release-log1p-mad-input-rules-v1',
        windows=[15, 30], fit_window=30, epsilon=1e-6, audit_fit_policy='P_U', policy_status='AUDIT_ONLY')
    assert summary['raw_identity'] == dict(profile_id='c17-release-minute-package-v1',
        context_sha256='a' * 64, manifest_sha256='b' * 64, manifest_byte_count=123)
    assert summary['prepared_identity'] == dict(profile_id='c17-release-prepared-input-package-v1',
        context_sha256='f' * 64, manifest_sha256='1' * 64, manifest_byte_count=456)
    assert summary['configuration_sha256'] == 'c' * 64
    assert summary['profile_id'] == 'c17-release-model-input-pair-v1'
    summary['feature_columns']['raw13'][0] = 'changed'
    summary['qualification_counts']['P_U']['train_full_history_normal'] = 99
    assert summarize_release_model_inputs(pair)['feature_columns']['raw13'][0] == 'completed_source_record_count'
    assert pair.labels.saved.qualification_masks[0].train_full_history_normal[1] is True


@pytest.mark.parametrize('n', [1, 10000])
def test_bounded_full_axis_accepts_structural_endpoints(n):
    # Pair deliberately does not reconstruct the history that these saved flags claim.
    raw, saved = _case()
    start = datetime(2026, 1, 1)
    stamps = tuple(start + timedelta(minutes=i) for i in range(n))
    segments = (ReleaseSegment('only', 'train', start, start + timedelta(minutes=n)),)
    valid, empty = (True,) * n, (False,) * n
    kinds = (('normal',) * 3,) * n
    r = replace(raw.minutes, timestamps=stamps, segment_ids=('only',) * n, roles=('train',) * n,
                values=(RAW_ROW,) * n, source_valid=valid, label_kinds=kinds,
                bucket_counts=(raw.minutes.bucket_counts[0],) * n)
    raw = _raw_replace(raw, minutes=r, segments=segments)
    histories = tuple(ReleasePreparedHistory(w, (RESIDUAL,) * n, valid, (None,) * n) for w in (15, 30))
    minutes = ReleasePreparedMinutes(stamps, (0,) * n, valid, (CURRENT,) * n, valid,
                                     (None,) * n, histories, valid)
    labels = ReleaseInputLabels(('P_U', 'P_B', 'P_A'), kinds, (True,) + empty[1:], (0,),
        tuple(ReleasePolicyQualification(p, *(empty for _ in range(8))) for p in ('P_U', 'P_B', 'P_A')))
    saved = replace(saved, context=replace(saved.context, segments=segments, minute_count=n),
                    minutes=minutes, labels=labels, preprocessing=replace(saved.preprocessing, n_samples_seen=1))
    pair = pair_release_model_inputs(raw, saved)
    assert len(pair.joined_h15) == n
    assert pair.joined_h15[0] == JOINED
    assert pair.joined_h30[-1] == JOINED
    assert pair.population.preprocessing_fit_indices == (0,)
    assert pair.population.train_indices == ()
    assert summarize_release_model_inputs(pair)['minute_counts']['total'] == n


def test_pair_and_summary_do_not_replay_or_perform_external_actions(monkeypatch):
    raw, saved = _case()
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('forbidden')
        raise AssertionError('forbidden action attempted')
    # Patch both aliases and defining modules, after fixture construction/imports.
    targets = {
        'traffic_anomaly.release_inputs': ('_validate_content', '_eligible', '_axis', '_config_sha',
            '_mask_sha', '_fit_selection', '_qualifications', '_fit_state', '_fit_statistics',
            '_transform', '_history', 'prepare_release_inputs', 'verify_release_input_derivation',
            'encode_release_input_package', 'decode_release_input_package'),
        'traffic_anomaly.release_minute_contract': ('_validate_result',
            'encode_release_minute_package', 'decode_release_minute_package'),
        'traffic_anomaly.release_input_package': ('load_release_input_package', 'save_release_input_package',
            'encode_release_input_package', 'decode_release_input_package'),
        'traffic_anomaly.release_minute_package': ('load_release_minute_package', 'save_release_minute_package',
            'encode_release_minute_package', 'decode_release_minute_package'),
    }
    modules = [(importlib.import_module(name), names) for name, names in targets.items()]
    # The product is called under guards; pytest's own capture/logging is outside this block.
    with monkeypatch.context() as guard:
        for module, names in modules:
            for name in names:
                guard.setattr(module, name, forbidden)
        guard.setattr(ReleasePreparedInputs, 'joined', forbidden)
        for module, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                             (socket, 'socket'), (pickle, 'load'), (pickle, 'loads'),
                             (builtins, '__import__')):
            guard.setattr(module, name, forbidden)
        pair = pair_release_model_inputs(raw, saved)
        summary = summarize_release_model_inputs(pair)
    assert attempts == []
    assert summary['minute_counts']['definite_attack_present'] == 2


def test_error_code_and_summary_argument_are_safe():
    assert ReleaseModelInputPairError('private details').code == 'INVALID_PAIR_STRUCTURE'
    assert ReleaseModelInputPairError([]).code == 'INVALID_PAIR_STRUCTURE'
    with pytest.raises(ReleaseModelInputPairError) as captured:
        summarize_release_model_inputs(object())
    assert captured.value.code == 'INVALID_PAIR_ARGUMENTS'


def test_joint_cli_uses_real_pair_summary(monkeypatch, capsysbinary):
    """Only loaders are stubs; observe real pair/summary frames and exact output."""
    import json
    from pathlib import Path
    import sys
    from traffic_anomaly import release_model_input_cli as cli
    raw, saved = _case()
    events, seen, returned = [], [], []
    def raw_load(path):
        events.append(('raw', path))
        return raw
    def prepared_load(path):
        events.append(('prepared', path))
        return saved
    monkeypatch.setattr(cli, 'load_release_minute_package', raw_load)
    monkeypatch.setattr(cli, 'load_release_input_package', prepared_load)
    def observe(frame, event, arg):
        if frame.f_code is pair_release_model_inputs.__code__:
            if event == 'call':
                events.append(('pair',))
                seen.append((frame.f_locals['raw'] is raw, frame.f_locals['saved'] is saved))
            elif event == 'return':
                returned.append(arg)
        elif frame.f_code is summarize_release_model_inputs.__code__ and event == 'call':
            events.append(('summary',))
            seen.append((frame.f_locals['pair'] is returned[0],))
    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        status = cli.main(['--raw-package', 'raw/run=@daily', '--prepared-package=saved/paired'])
    finally:
        sys.setprofile(previous)
    output = capsysbinary.readouterr()
    assert status == 0 and output.err == b''
    assert events == [('raw', Path('raw/run=@daily')), ('prepared', Path('saved/paired')),
                      ('pair',), ('summary',)]
    assert seen == [(True, True), (True,)]
    columns = ['completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
        'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
        'udp_source_record_count', 'known_other_source_protocol_record_count',
        'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
        'duration_p95_s', 'no_backward_packet_source_record_count']
    expected = {
        'version': 1, 'profile_id': 'c17-release-model-input-pair-v1', 'status': 'INPUTS_PAIRED',
        'raw_identity': {'profile_id': 'c17-release-minute-package-v1', 'context_sha256': 'a' * 64,
                         'manifest_sha256': 'b' * 64, 'manifest_byte_count': 123},
        'prepared_identity': {'profile_id': 'c17-release-prepared-input-package-v1',
            'context_sha256': 'f' * 64, 'manifest_sha256': '1' * 64, 'manifest_byte_count': 456},
        'configuration': {'schema_version': 1, 'numeric_rules_id': 'c17-release-log1p-mad-input-rules-v1',
            'windows': [15, 30], 'fit_window': 30, 'epsilon': 1e-6, 'audit_fit_policy': 'P_U',
            'policy_status': 'AUDIT_ONLY'},
        'configuration_sha256': 'c' * 64,
        'source': {'schema_id': 'c17-release-91-v1', 'authentication': 'NOT_AUTHENTICATED',
                   'time_basis': 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'},
        'scopes': {'pair': 'READ_ONLY_MODEL_INPUT_PAIR', 'raw': 'PACKAGE_INTERNAL_CONSISTENCY_ONLY',
                   'prepared': 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY'},
        'checks': {'derivation_replay': 'DERIVATION_REPLAY_NOT_PERFORMED', 'fit_parameters': 'NOT_REESTIMATED',
            'model': 'MODEL_NOT_LOADED', 'execution': 'EXECUTION_NOT_GRANTED',
            'external_case_evidence': 'NOT_ESTABLISHED'},
        'feature_columns': {'raw13': columns, 'current13': columns,
            'h15_26': ['current:' + name for name in columns] + ['residual_h15:' + name for name in columns],
            'h30_26': ['current:' + name for name in columns] + ['residual_h30:' + name for name in columns]},
        'minute_counts': {'total': 6, 'raw_valid': 5, 'prepared_valid': 5, 'history_h15_valid': 4,
            'history_h30_valid': 3, 'common_valid': 3, 'definite_attack_present': 2},
        'preprocessing_fit': {'count': 2, 'mask_sha256': 'd' * 64, 'rows_sha256': 'e' * 64},
        'model_population': {'policy': 'P_U', 'train_count': 1, 'calibration_count': 0},
        'qualification_counts': {
            'P_U': {'train_full_history_normal': 1, 'calibration_full_history_normal': 0,
                'validation_current_normal': 0, 'validation_current_attack': 0, 'validation_current_unknown': 1,
                'test_current_normal': 0, 'test_current_attack': 1, 'test_current_unknown': 0},
            'P_B': {'train_full_history_normal': 0, 'calibration_full_history_normal': 0,
                'validation_current_normal': 0, 'validation_current_attack': 0, 'validation_current_unknown': 1,
                'test_current_normal': 0, 'test_current_attack': 1, 'test_current_unknown': 0},
            'P_A': {'train_full_history_normal': 1, 'calibration_full_history_normal': 0,
                'validation_current_normal': 0, 'validation_current_attack': 0, 'validation_current_unknown': 1,
                'test_current_normal': 0, 'test_current_attack': 1, 'test_current_unknown': 0}},
    }
    assert output.out == (json.dumps(expected, ensure_ascii=False, allow_nan=False,
                                    sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def test_joint_cli_rejects_real_pair_wrong_upstream(monkeypatch, capsysbinary):
    from pathlib import Path
    import sys
    from traffic_anomaly import release_model_input_cli as cli
    raw, saved = _case()
    saved = replace(saved, context=replace(saved.context,
        upstream=replace(raw.identity, context_sha256='2' * 64)))
    events, seen = [], []
    def raw_load(path):
        events.append(('raw', path))
        return raw
    def prepared_load(path):
        events.append(('prepared', path))
        return saved
    monkeypatch.setattr(cli, 'load_release_minute_package', raw_load)
    monkeypatch.setattr(cli, 'load_release_input_package', prepared_load)
    def observe(frame, event, arg):
        if event == 'call' and frame.f_code is pair_release_model_inputs.__code__:
            events.append(('pair',))
            seen.append((frame.f_locals['raw'] is raw, frame.f_locals['saved'] is saved))
        elif event == 'call' and frame.f_code is summarize_release_model_inputs.__code__:
            events.append(('summary',))
    previous = sys.getprofile()
    try:
        sys.setprofile(observe)
        status = cli.main(['--raw-package', 'raw/run=@daily', '--prepared-package=saved/wrong'])
    finally:
        sys.setprofile(previous)
    output = capsysbinary.readouterr()
    assert status == 2
    assert output.out == b''
    assert output.err == b'{"error":"UPSTREAM_IDENTITY_MISMATCH"}\n'
    assert events == [('raw', Path('raw/run=@daily')), ('prepared', Path('saved/wrong')), ('pair',)]
    assert seen == [(True, True)]
