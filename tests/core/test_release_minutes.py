"""Invented full-91-column batches only; the history bridge is test-only.

No input here is a source receipt or authentication claim. Each generated row
is artificial and its changing id merely keeps the full lexical rows distinct.
"""
import builtins
import csv
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import importlib
import io
import json
from pathlib import Path
import random
import socket

import numpy as np
import pytest

from traffic_anomaly._release_csv import _parse_release_csv, ReleaseFixtureBudget

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tests/fixtures/release-91-artificial-v1.json').read_text(encoding='utf-8'))
HEADER = FIXTURE['header']
T = datetime(2026, 1, 1)
MINUTE = timedelta(minutes=1)


def mod():
    return importlib.import_module('traffic_anomaly._release_minutes')


def row(i=0, **changes):
    values = dict(zip(HEADER, FIXTURE['rows'][0]))
    values.update({'id': str(i), 'Timestamp': '2026-01-01 00:00:00.000001',
                   'Flow Duration': '0'})
    values.update(changes)
    return [values[name] for name in HEADER]


def encoded(rows):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    writer.writerows(rows)
    return buffer.getvalue().encode('utf-8')


def parsed(rows=(), *, sources=None):
    return _parse_release_csv(tuple(encoded(r) for r in sources) if sources is not None
                              else (encoded(rows),), budget=ReleaseFixtureBudget())


def segment(id='s', role='train', start=T, minutes=1):
    return mod().ReleaseSegment(id, role, start, start + minutes * MINUTE)


def aggregate(rows=(), segments=None, *, sources=None, max_minutes=10000):
    return mod()._aggregate_release_minutes(parsed(rows, sources=sources),
             (segment(),) if segments is None else segments, max_minutes=max_minutes)


def four_rows():
    return [row(i, **{'Protocol': str(p), 'Flow Duration': str(i * 1000000),
                     'Total Fwd Packet': str(i), 'Total Bwd packets': str(b),
                     'Total Length of Fwd Packet': str(i * 10),
                     'Total Length of Bwd Packet': str(b * 5), 'Label': label})
            for i, p, b, label in [(1, 6, 0, 'BENIGN'), (2, 17, 1, 'BENIGN'),
                                   (3, 1, 2, 'BENIGN'), (4, 0, 0, 'Portscan')]]


def test_four_hand_rows_and_old_pure_differential():
    r = aggregate(four_rows())
    assert r.values == ((4., 10., 3., 100., 15., 1., 1., 1., 1., 4., 2.5, 3.85, 2.),)
    assert r.source_valid == (True,)
    assert r.label_kinds == (('attack', 'attack', 'attack'),)
    assert (r.raw_records, r.eligible_records, r.excluded_records) == (4, 4, 0)
    assert r.bucket_counts[0].definite_attack_present
    from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
    from tools.data_audit.c17_g13u import aggregate_candidate_records
    assert r.feature_names == G13U_FEATURE_NAMES
    old = aggregate_candidate_records([dict(protocol=p, fwd_packets=i, bwd_packets=b,
        fwd_length=i*10, bwd_length=b*5, duration_us=i*1000000, label=label)
        for i, p, b, label in [(1,6,0,'BENIGN'),(2,17,1,'BENIGN'),
                               (3,1,2,'BENIGN'),(4,0,0,'Portscan')]])
    assert r.values[0] == pytest.approx(tuple(old['features'].values()), rel=1e-15)


@pytest.mark.parametrize('durations,median,p95', [
    ([1], Fraction(1, 1000000), Fraction(1, 1000000)),
    ([1, 2], Fraction(3, 2000000), Fraction(39, 20000000)),
    ([1, 2, 4], Fraction(2, 1000000), Fraction(38, 10000000)),
    ([0, 0, 1, 1], Fraction(1, 2000000), Fraction(1, 1000000)),
    ([1000000, 2000000, 3000000, 4000000], Fraction(5,2), Fraction(77,20)),
])
def test_exact_integer_microsecond_linear_quantiles(durations, median, p95):
    r = aggregate([row(i, **{'Flow Duration': str(d)}) for i, d in enumerate(durations)])
    assert r.values[0][9:12] == (float(Fraction(max(durations),1000000)), float(median), float(p95))


def test_permutations_and_late_earliest_completion_are_invariant():
    rows = [row(i, **{'Timestamp': (T + i % 3 * MINUTE).strftime('%Y-%m-%d %H:%M:%S.%f'),
                     'Flow Duration': str(i)}) for i in range(30)]
    expected = aggregate(rows, (segment(minutes=3),))
    for seed in range(4):
        shuffled = rows.copy()
        random.Random(seed).shuffle(shuffled)
        shuffled += [shuffled.pop(next(i for i,v in enumerate(shuffled) if v[0]=='0'))]
        actual = aggregate(shuffled, (segment(minutes=3),))
        assert replace(actual, source_sha256=()) == replace(expected, source_sha256=())


def test_full_lexical_duplicates_all_copies_cross_sources_and_outside():
    a = row(1)
    outside = row(3, Timestamp='2026-01-02 00:00:00.000000')
    different_unused = row(1, **{'Flow Bytes/s': 'Infinity'})
    numeric_spelling = row(1, **{'Total Fwd Packet': '2.0'})
    r = aggregate(sources=([a, outside], [a, different_unused, numeric_spelling, outside]))
    assert (r.raw_records, r.eligible_records, r.excluded_records, r.outside_records) == (6, 2, 4, 2)
    assert r.duplicate_groups == 2
    assert dict(r.reason_counts)['duplicate_record'] == 4
    assert r.bucket_counts[0].eligible_records == 2
    assert r.values == ((None,) * 13,)
    assert dict(r.bucket_counts[0].reason_counts)['duplicate_record'] == 2
    clean = aggregate([different_unused, numeric_spelling])
    assert clean.source_valid == (True,)
    assert clean.values[0][0] == 2
    outside_only = aggregate([row(7), outside, outside])
    assert outside_only.source_valid == (True,) and outside_only.eligible_records == 1
    assert outside_only.outside_records == 2


def test_protocol_zero_unknown_labels_unused_infinity_and_three_policies():
    r = aggregate([row(1, Protocol='0', Label='Portscan', **{'Flow Bytes/s':'Infinity'})])
    assert r.source_valid == (True,) and r.values[0][8] == 1
    assert r.label_kinds == (('attack',)*3,)
    attempted = aggregate([row(Label='Botnet - Attempted', **{'Attempted Category':'0'})])
    assert attempted.label_kinds == (('unknown','normal','attack'),)
    assert attempted.bucket_counts[0].attempted_present
    unknown = aggregate([row(Label='untrusted-private-label')])
    assert unknown.source_valid == (True,) and unknown.label_kinds == (('unknown',)*3,)
    assert 'untrusted-private-label' not in repr(unknown)
    assert dict(unknown.label_anomaly_counts)['unknown_label'] == 1
    priorities = aggregate([row(1, Label='Portscan'), row(2), row(3, Label='unknown')])
    assert priorities.source_valid == (True,) and priorities.label_kinds == (('unknown',)*3,)


def test_bad_protocol_taints_but_good_row_still_eligible_and_reason_overlap():
    bad = row(2, Protocol='200')
    r = aggregate([row(1), bad, bad])
    assert (r.raw_records, r.eligible_records, r.excluded_records) == (3,1,2)
    assert r.bucket_counts[0].raw_records == 3 and r.bucket_counts[0].eligible_records == 1
    assert dict(r.reason_counts)['duplicate_record'] == 2
    assert dict(r.reason_counts)['invalid_unsupported_protocol'] == 2
    assert sum(dict(r.reason_counts).values()) > r.excluded_records
    assert dict(r.raw_protocol_counts) == dict(tcp=1,udp=0,known_other=0,unresolved=0,excluded_protocol=2)
    assert sum(dict(r.eligible_protocol_counts).values()) == 1
    assert r.values == ((None,)*13,) and r.label_kinds == (('unknown',)*3,)


def test_completion_left_closed_edges_and_only_completion_bucket_tainted():
    segments = (segment(minutes=2), segment('v','validation',T+2*MINUTE,2))
    rows = [row(1, Timestamp='2026-01-01 00:00:59.000000', **{'Flow Duration':'1000000'}),
            row(2, Timestamp='2026-01-01 00:01:59.000000', **{'Flow Duration':'1000000'}),
            row(3, Timestamp='2026-01-01 00:02:00.000000'),
            row(4, Timestamp='2026-01-01 00:04:00.000000')]
    r = aggregate(rows, segments)
    assert r.timestamps == tuple(T+i*MINUTE for i in range(4))
    assert r.source_valid == (False, True, False, False)
    assert tuple(b.eligible_records for b in r.bucket_counts) == (0,1,1,0)
    assert dict(r.bucket_counts[2].reason_counts)['cross_partition'] == 1
    assert (r.outside_records,r.eligible_records,r.excluded_records) == (1,2,2)
    assert r.segment_ids == ('s','s','v','v') and r.roles == ('train','train','validation','validation')


def test_same_role_different_segments_start_outside_and_gap():
    segments=(segment('a','test',T,1),segment('b','test',T+2*MINUTE,1))
    r=aggregate([row(1, **{'Flow Duration':'120000000'}),
                 row(2, Timestamp='2026-01-01 00:01:00.000000', **{'Flow Duration':'60000000'}),
                 row(3, Timestamp='2026-01-01 00:01:00.000000'),
                 row(4, Timestamp='2025-12-31 23:59:59.000000', **{'Flow Duration':'1000000'})],segments)
    assert r.timestamps == (T,T+2*MINUTE)
    assert r.source_valid == (False,False)
    assert dict(r.reason_counts)['cross_partition'] == 3 and r.outside_records == 1
    assert tuple(dict(b.reason_counts)['cross_partition'] for b in r.bucket_counts) == (1,2)


@pytest.mark.parametrize('changes', [{'Timestamp':'bad'}, {'Flow Duration':'NaN'},
                                    {'Timestamp':'bad','Flow Duration':'0.5'}])
def test_unplaceable_global_taint_and_population_conservation(changes):
    r=aggregate([row(1), row(2,**changes), row(3,Timestamp='2026-01-02 00:00:00.000000')],
                (segment(minutes=3),))
    assert r.source_valid == (False,False,False)
    assert (r.raw_records,r.eligible_records,r.excluded_records,r.unplaced_invalid_rows,r.outside_records)==(3,1,2,1,1)
    assert all(dict(b.reason_counts)['unplaced_invalid_row']==1 for b in r.bucket_counts)
    assert sum(dict(r.raw_protocol_counts).values())==3
    assert sum(dict(r.eligible_protocol_counts).values())==1
    assert sum(b.raw_records for b in r.bucket_counts)==1


def test_empty_axis_buckets_remain_unknown_and_no_zero_fill():
    r=aggregate([], (segment(minutes=2),))
    assert r.values==((None,)*13,)*2 and r.source_valid==(False,False)
    assert r.label_kinds==(('unknown',)*3,)*2
    assert all(dict(b.reason_counts)['empty_unconfirmed']==1 for b in r.bucket_counts)
    with pytest.raises(FrozenInstanceError): r.raw_records=1
    with pytest.raises(FrozenInstanceError): r.bucket_counts[0].raw_records=1


@pytest.mark.parametrize('maximum', [0,-1,10001,True,1.0,None])
def test_invalid_max_minutes(maximum):
    with pytest.raises(ValueError,match='^invalid_max_minutes$'):
        aggregate(max_minutes=maximum)


@pytest.mark.parametrize('kind', ['empty','list','eight','duplicate_id','id_long','id_empty',
    'role','backward','overlap','reverse','aware','nonminute','zero','wrong_type','too_many_minutes'])
def test_segment_contract_is_bounded_and_chronological(kind):
    m=mod(); s=segment()
    cases={
        'empty':(), 'list':[s], 'eight':tuple(segment(str(i),start=T+i*MINUTE) for i in range(8)),
        'duplicate_id':(s,segment(start=T+MINUTE)),
        'id_long':(replace(s,id='x'*129),), 'id_empty':(replace(s,id=''),),
        'role':(replace(s,role='other'),),
        'backward':(replace(s,role='test'),segment('b',start=T+MINUTE)),
        'overlap':(s,segment('b')), 'reverse':(segment('b',start=T+MINUTE),s),
        'aware':(replace(s,start=T.replace(tzinfo=timezone.utc)),),
        'nonminute':(replace(s,end=s.end+timedelta(microseconds=1)),),
        'zero':(replace(s,end=s.start),), 'wrong_type':('s',),
        'too_many_minutes':(segment(minutes=2),)}
    with pytest.raises(ValueError): m._aggregate_release_minutes(parsed(),cases[kind],max_minutes=1)


def test_numeric_materialization_overflow_aborts_and_large_legal_count_rounds():
    r=aggregate([row(**{'Total Fwd Packet':'9007199254740993'})])
    assert r.eligible_records==1 and r.values[0][1]==9007199254740992.
    with pytest.raises(ValueError,match='^numeric_materialization_overflow$'):
        aggregate([row(**{'Total Fwd Packet':'1e400'})])


@pytest.mark.parametrize('kind', ['batch_type','schema','source_auth','time_basis','source_sizes',
    'hashes','rows_list','row_type','fingerprint','raw_fields','start','completion',
    'count','duration','channel','reason','labels','attempted','anomaly','unused','locator',
    'completion_array','unused_array','schema_array','authentication_array','time_basis_array'])
def test_supplied_dataclass_shapes_are_checked_without_authenticating(kind):
    p=parsed([row()]); r=p.rows[0]
    batches={'batch_type':object(), 'schema':replace(p,schema_id='other'),
        'source_auth':replace(p,source_authentication='AUTHENTICATED'),
        'time_basis':replace(p,time_basis='UTC'), 'source_sizes':replace(p,source_bytes=[2]),
        'hashes':replace(p,source_sha256=('private source',)), 'rows_list':replace(p,rows=[r]),
        'row_type':replace(p,rows=(object(),)),
        'schema_array':replace(p,schema_id=np.array(['x','y'])),
        'authentication_array':replace(p,source_authentication=np.array(['x','y'])),
        'time_basis_array':replace(p,time_basis=np.array(['x','y']))}
    rows={'fingerprint':replace(r,lexical_fingerprint=b'x'), 'raw_fields':replace(r,raw_fields=[]),
        'start':replace(r,start=T.replace(tzinfo=timezone.utc)),
        'completion':replace(r,completion=T+MINUTE), 'count':replace(r,fwd_packets=True),
        'duration':replace(r,duration_us=-1), 'channel':replace(r,protocol_channel='other'),
        'reason':replace(r,reasons=('private reason',)), 'labels':replace(r,label_kinds=('normal',)),
        'attempted':replace(r,attempted=1), 'anomaly':replace(r,label_anomaly='private'),
        'unused':replace(r,unused_field_issues=('private',)), 'locator':replace(r,source_ordinal=99),
        'completion_array':replace(r,completion=np.array([T,T])),
        'unused_array':replace(r,unused_field_issues=(np.array(['x','y']),))}
    p=batches[kind] if kind in batches else replace(p,rows=(rows[kind],))
    with pytest.raises(ValueError,match='^invalid_parsed_batch$'):
        mod()._aggregate_release_minutes(p,(segment(),),max_minutes=1)


def test_consistency_bindings_and_private_repr_do_not_claim_origin():
    p=parsed([row()])
    r=mod()._aggregate_release_minutes(p,(segment(),),max_minutes=1)
    assert (r.schema_id,r.source_sha256,r.source_bytes)==(p.schema_id,p.source_sha256,p.source_bytes)
    assert r.source_authentication=='NOT_AUTHENTICATED'
    assert r.time_basis=='SOURCE_WALL_CLOCK_COMPLETION_PROXY'
    assert p.rows[0].lexical_fingerprint.hex() not in repr(r)
    assert 'artificial-src' not in repr(r) and 'raw_fields' not in repr(r)


def test_pure_aggregate_has_no_file_network_tools_or_model_calls(monkeypatch):
    m=mod(); p=parsed(four_rows()); segments=(segment(),)
    real_import=builtins.__import__
    def guarded_import(name,*args,**kwargs):
        if name.startswith(('tools','sklearn','torch','tensorflow')): raise AssertionError(name)
        return real_import(name,*args,**kwargs)
    def forbidden(*args,**kwargs): raise AssertionError('external IO')
    with monkeypatch.context() as guard:
        guard.setattr(builtins,'open',forbidden); guard.setattr(io,'open',forbidden)
        guard.setattr(socket,'socket',forbidden); guard.setattr(builtins,'__import__',guarded_import)
        r=m._aggregate_release_minutes(p,segments,max_minutes=1)
    assert r.values[0][0]==4


def test_all_ten_thousand_samples_in_one_bucket_and_full_axis_limit():
    r=aggregate([row(i,**{'Flow Duration':str(i)}) for i in range(10000)],
                (segment(minutes=10000),),max_minutes=10000)
    assert len(r.timestamps)==10000 and sum(r.source_valid)==1
    assert r.values[0][0]==10000
    assert r.values[0][9:12]==(0.009999,0.0049995,0.00949905)
    assert (r.raw_records,r.eligible_records,r.excluded_records)==(10000,10000,0)
    with pytest.raises(ValueError,match='^invalid_parsed_batch$'):
        p=parsed([row()]); mod()._aggregate_release_minutes(replace(p,rows=p.rows*10001),(segment(),),max_minutes=1)


def artificial_history_bridge(r):
    """Only these freshly invented test rows receive the synthetic test marker."""
    from traffic_anomaly.candidate_inputs import CandidateMinuteBatch
    return CandidateMinuteBatch(np.array(r.timestamps,dtype='datetime64[us]'),
        np.array([[np.nan if v is None else v for v in values] for values in r.values]),
        np.array(r.source_valid,bool),np.array(r.segment_ids),np.array(r.roles))


def test_artificial_2439_minutes_seven_segments_history_resets_and_test_label_independence():
    from traffic_anomaly.candidate_inputs import prepare_candidate_inputs
    lengths=(40,40,40,580,580,580,579)
    roles=('train','validation','calibration','test','test','test','test')
    segments=[]; rows=[]; offset=0
    for j,(length,role) in enumerate(zip(lengths,roles)):
        start=T+offset*MINUTE
        segments.append(segment(str(j),role,start,length))
        for i in range(length):
            rows.append(row(offset+i,Timestamp=(start+i*MINUTE).strftime('%Y-%m-%d %H:%M:%S.%f')))
        offset+=length+1  # registration gaps retained, never zero-filled
    first=aggregate(rows,tuple(segments)); changed=[]
    for i,r in enumerate(rows):
        r=r.copy()
        if i>=120: r[HEADER.index('Label')]='BENIGN' if i%10==0 else 'Portscan' if i%2 else 'unknown'
        changed.append(r)
    second=aggregate(changed,tuple(segments))
    assert len(first.timestamps)==2439 and first.duplicate_groups==second.duplicate_groups==0
    assert first.source_valid==second.source_valid and first.values==second.values
    a=prepare_candidate_inputs(artificial_history_bridge(first),np.array([k[1]=='normal' for k in first.label_kinds]))
    b=prepare_candidate_inputs(artificial_history_bridge(second),np.array([k[1]=='normal' for k in second.label_kinds]))
    for w in (15,30):
        np.testing.assert_equal(a.histories[w].joined,b.histories[w].joined)
        assert a.histories[w].valid.sum()==2439-7*w
        index=0
        for length in lengths:
            assert not a.histories[w].valid[index:index+w].any()
            assert a.histories[w].valid[index+w:index+length].all()
            index+=length
    assert a.preprocessor.n_samples_seen==10
    # Each test segment loses exactly its first 30 minutes: 3*(580-30)+(579-30).
    # This selects common input-valid history and current normal truth only.
    assert a.test_normal.sum()==2199
    # Every tenth current minute stays normal despite attack/unknown history.
    # Each test segment contributes 55 such minutes after its 30-minute reset.
    assert b.test_normal.sum()==220


@pytest.mark.parametrize('field', ['Total Fwd Packet','Total Bwd packets',
                                  'Total Length of Fwd Packet','Total Length of Bwd Packet'])
def test_invalid_required_counts_taint_only_assigned_completion_bucket(field):
    r=aggregate([row(1,**{field:'0.5'}), row(2),
                 row(3,Timestamp='2026-01-01 00:01:00.000000')],(segment(minutes=2),))
    assert r.source_valid==(False,True) and r.eligible_records==2 and r.excluded_records==1
    assert tuple(b.eligible_records for b in r.bucket_counts)==(1,1)


def test_tiny_artificial_full91_profile_and_g13u_differential(tmp_path):
    """This test creates its own tiny index; no existing index can be selected."""
    from tools.data_audit.c17_payload import profile_csv
    from tools.data_audit.c17_g13u import audit_g13u
    cfg=dict(identity='SYNTHETIC_ONLY',expected_header=HEADER,
        numeric_columns=['Flow Duration','Protocol','Total Fwd Packet','Total Bwd packets',
                         'Total Length of Fwd Packet','Total Length of Bwd Packet','Flow Bytes/s'],
        columns=dict(start='Timestamp',duration='Flow Duration',label='Label',attempted='Attempted Category',
            protocol='Protocol',fwd_packets='Total Fwd Packet',bwd_packets='Total Bwd packets',
            fwd_length='Total Length of Fwd Packet',bwd_length='Total Length of Bwd Packet'),
        time=dict(formats=['%Y-%m-%d %H:%M:%S.%f'],duration_unit='us'),
        limits=dict(max_total_input_bytes=1000000,max_rows=10000,max_days=7,max_fields=100,
            max_field_chars=4096,max_label_values=100,max_category_values=32,max_minutes=10000,
            index_max_bytes=1048576,audit_max_bytes=2097152,max_duration_seconds=86400),
        supported_protocols=[1,2,6,17,132],unresolved_source_protocol=0,
        labels=dict(normal=['BENIGN'],attack=['Portscan'],attempted=['Botnet - Attempted'],
            attempted_empty=['-1'],attempted_categories=['0','1','2','3','4','5','6'],
            policy=dict(status='AUDIT_ONLY',attempted='unknown')),
        population='HASH_BOUND_RELEASED_CSV_RECORDS',feature_order=list(mod().G13U_FEATURE_NAMES),
        candidate_registration=dict(status='AUDIT_CANDIDATE_ONLY_NOT_APPROVED_PROTOCOL',
            label_values_seen_before_registration=False,model_results_seen=False,
            segments=[dict(id='s',role='train',start='2026-01-01 00:00:00',end='2026-01-01 00:05:00')]))
    duplicate=row(9,Timestamp='2026-01-01 00:03:00.000000')
    rows=[row(1,Protocol='0',Label='Portscan',**{'Flow Bytes/s':'Infinity'}),
          row(2,Timestamp='2026-01-01 00:01:00.000000',Label='Botnet - Attempted',**{'Attempted Category':'0'}),
          row(3,Timestamp='2026-01-01 00:02:00.000000',Protocol='200'),duplicate,duplicate,
          row(4,Timestamp='2026-01-01 00:05:00.000000')]
    path=tmp_path/'invented-91.csv'; path.write_bytes(encoded(rows))
    old=tmp_path/'old'; old.mkdir(); new=tmp_path/'new'; new.mkdir()
    profile=profile_csv([path],cfg,old)
    cfg['expected_inputs']=[dict(bytes=profile['files'][0]['bytes'],sha256=profile['files'][0]['sha256'])]
    old_result=audit_g13u([path],cfg,new,old/'profile-index.sqlite3')
    r=aggregate(rows,(segment(minutes=5),))
    assert (r.raw_records,r.eligible_records,r.excluded_records)==(6,2,4)
    assert old_result['all_source']['raw_records']==r.raw_records
    assert old_result['all_source']['eligible_completed_records']==r.eligible_records
    assert old_result['all_source']['excluded_records']==r.excluded_records
    assert old_result['all_source']['raw_protocol_channels']==dict(r.raw_protocol_counts)
    assert old_result['all_source']['eligible_protocol_channels']==dict(r.eligible_protocol_counts)
    for p,policy in enumerate(('P_U','P_B','P_A')):
        summary=old_result['policies'][policy]['segments'][0]
        assert summary['input_valid']==sum(r.source_valid)==2
        for kind in ('normal','attack','unknown'):
            assert summary[kind]==sum(k[p]==kind for k in r.label_kinds)
