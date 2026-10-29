"""Synthetic completed-record adapter behavior, separate from real payload audit."""
from datetime import datetime, timedelta
import importlib
import numpy as np
import pytest


def mod():
    return importlib.import_module('traffic_anomaly.candidate_records')


def minute_specs(n=3):
    origin=datetime(2026,1,1)
    return [dict(timestamp=(origin+timedelta(minutes=i)).isoformat(timespec='minutes'),
                 partition='train',segment_id='a',coverage='observed',empty_label='unknown') for i in range(n)]


def record(key='r0', **changes):
    return dict(record_key=key,start='2026-01-01T00:00:01',duration_us=1000000,protocol=6,
                fwd_packets=1,bwd_packets=0,fwd_length=10,bwd_length=0,
                label='BENIGN',attempted_category='-1')|changes


def test_four_records_match_hand_checked_thirteen_features_and_channels():
    records=[record('a',protocol=6,fwd_packets=1,bwd_packets=0,fwd_length=10,bwd_length=0,duration_us=1000000),
             record('b',protocol=17,fwd_packets=2,bwd_packets=1,fwd_length=20,bwd_length=5,duration_us=2000000),
             record('c',protocol=1,fwd_packets=3,bwd_packets=2,fwd_length=30,bwd_length=10,duration_us=3000000),
             record('d',protocol=0,fwd_packets=4,bwd_packets=0,fwd_length=40,bwd_length=0,duration_us=4000000,label='Portscan')]
    r=mod().adapt_synthetic_records(minute_specs(1),records)
    np.testing.assert_allclose(r.batch.values[0],[4,10,3,100,15,1,1,1,1,4,2.5,3.85,2])
    assert r.audit['raw_protocol_channels']==dict(tcp=1,udp=1,known_other=1,unresolved=1,invalid=0)
    assert r.audit['source_label_counts']=={'BENIGN':3,'Portscan':1}
    assert r.audit['input_records']==r.audit['eligible_records']==4
    assert all(r.labels[p]==('attack',) for p in ('P_U','P_B','P_A'))


def test_end_at_exact_minute_boundary_enters_next_bucket():
    r=mod().adapt_synthetic_records(minute_specs(2),[record(start='2026-01-01T00:00:59')])
    assert r.audit['minute_reports'][0]['raw_record_count']==0
    assert r.audit['minute_reports'][1]['raw_record_count']==1
    assert r.batch.row_valid.tolist()==[False,True]
    assert r.batch.values[1,0]==1


@pytest.mark.parametrize('kind',['partition','segment','gap','missing'])
def test_cross_boundary_record_taints_completion_bucket(kind):
    minutes=minute_specs(3)
    if kind=='partition': minutes[1]['partition']=minutes[2]['partition']='validation'
    if kind=='segment': minutes[1]['segment_id']=minutes[2]['segment_id']='b'
    if kind=='gap': minutes.pop(1)
    if kind=='missing': minutes[1]['coverage']='missing'
    r=mod().adapt_synthetic_records(minutes,[record(duration_us=120000000)])
    assert not r.batch.row_valid[-1]
    assert r.audit['eligible_records']==0 and r.audit['excluded_records']==1
    assert r.audit['minute_reports'][-1]['invalid_reasons']


def test_observed_empty_missing_and_confirmed_empty_remain_distinct():
    minutes=minute_specs(4)
    minutes[1]['coverage']='missing'
    minutes[2].update(coverage='confirmed_empty',empty_label='normal')
    minutes[3].update(coverage='confirmed_empty',empty_label='unknown')
    r=mod().adapt_synthetic_records(minutes,[])
    assert r.batch.row_valid.tolist()==[False,False,True,True]
    assert r.labels['P_U']==('unknown','unknown','normal','unknown')
    np.testing.assert_array_equal(r.batch.values[2],[0]*13)
    f=r.to_fixture('P_U')
    assert f['minutes'][0]['features']==[None]*13
    assert f['minutes'][0]['valid'] is False
    assert f['normal_candidates']==[False,False,True,False]


def test_records_do_not_repair_missing_or_empty_evidence():
    for coverage in ('missing','confirmed_empty'):
        minutes=minute_specs(1); minutes[0]['coverage']=coverage
        r=mod().adapt_synthetic_records(minutes,[record()])
        assert not r.batch.row_valid[0] and r.labels['P_U']==('unknown',)
        assert r.audit['source_label_counts']=={'BENIGN':1}


def test_reused_segment_name_does_not_hide_intervening_boundary():
    minutes=minute_specs(3)
    minutes[1]['segment_id']='other'
    r=mod().adapt_synthetic_records(minutes,[record(duration_us=120000000)])
    assert not r.batch.row_valid[-1]
    assert r.audit['eligible_records']==0


def test_unknown_protocol_is_invalid_but_zero_keeps_original_attack_label():
    r=mod().adapt_synthetic_records(minute_specs(1),[record(protocol=0,label='Portscan')])
    assert r.batch.row_valid[0] and r.batch.values[0,8]==1
    assert r.batch.values[0,7]==0 and r.labels['P_U']==('attack',)
    r=mod().adapt_synthetic_records(minute_specs(1),[record(protocol=200,label='Portscan')])
    assert not r.batch.row_valid[0]
    assert r.audit['raw_protocol_channels']['invalid']==1
    assert r.audit['source_label_counts']=={'Portscan':1}


@pytest.mark.parametrize('other_label,want',[('BENIGN',('unknown','normal','attack')),('Portscan',('unknown','attack','attack'))])
def test_attempted_policies_keep_unknown_precedence_and_separate_labels(other_label,want):
    records=[record('plain',label=other_label),record('attempt',protocol=0,label='SSH-Patator - Attempted',attempted_category='0')]
    r=mod().adapt_synthetic_records(minute_specs(1),records)
    assert tuple(r.labels[p][0] for p in ('P_U','P_B','P_A'))==want
    assert r.audit['source_label_counts']=={other_label:1,'SSH-Patator - Attempted':1}
    changed=[record('plain',label='BENIGN'),record('attempt',protocol=0)]
    q=mod().adapt_synthetic_records(minute_specs(1),changed)
    np.testing.assert_array_equal(r.batch.values,q.batch.values)
    np.testing.assert_array_equal(r.batch.row_valid,q.batch.row_valid)


@pytest.mark.parametrize('changes',[dict(label=None),dict(label='mystery'),dict(attempted_category='9'),dict(attempted_category='0')])
def test_missing_unknown_or_conflicting_labels_never_become_normal(changes):
    r=mod().adapt_synthetic_records(minute_specs(1),[record(**changes)])
    assert r.batch.row_valid[0]
    assert all(r.labels[p]==('unknown',) for p in ('P_U','P_B','P_A'))


def test_identical_statistics_with_distinct_keys_are_not_deduplicated():
    r=mod().adapt_synthetic_records(minute_specs(1),[record('one'),record('two')])
    assert r.batch.row_valid[0] and r.batch.values[0,0]==2
    for records in ([record(),record()], [record(),record(fwd_packets=2)]):
        r=mod().adapt_synthetic_records(minute_specs(1),records)
        assert not r.batch.row_valid[0] and r.audit['eligible_records']==0
        assert r.audit['input_records']==r.audit['excluded_records']==2


def test_bad_count_taints_whole_bucket_without_losing_other_records():
    r=mod().adapt_synthetic_records(minute_specs(1),[record('one'),record('two',fwd_packets=-1)])
    assert not r.batch.row_valid[0] and np.isnan(r.batch.values[0]).all()
    assert r.audit['input_records']==2 and r.audit['eligible_records']==1 and r.audit['excluded_records']==1
    assert r.audit['source_label_counts']=={'BENIGN':2}


def test_outside_records_remain_in_global_conservation_and_labels():
    r=mod().adapt_synthetic_records(minute_specs(1),[record('inside'),record('outside',start='2026-01-01T00:02:00',label='Portscan',protocol=0)])
    assert r.audit['input_records']==2 and r.audit['outside_records']==1
    assert r.audit['eligible_records']+r.audit['excluded_records']==2
    assert r.audit['source_label_counts']=={'BENIGN':1,'Portscan':1}
    assert sum(r.audit['eligible_protocol_channels'].values())==r.audit['eligible_records']


@pytest.mark.parametrize('changes',[dict(start='not-time'),dict(start='2026-01-01T00:00:00Z'),dict(duration_us=-1),dict(duration_us=True),dict(duration_us=1.5),dict(duration_us=86400000001)])
def test_unplaceable_or_unbounded_time_fails_without_silent_drop(changes):
    with pytest.raises(ValueError): mod().adapt_synthetic_records(minute_specs(1),[record(**changes)])


def test_scope_extra_fields_and_record_cap_are_enforced():
    with pytest.raises(ValueError): mod().adapt_synthetic_records(minute_specs(1),[record()],evidence_kind='REAL')
    with pytest.raises(ValueError): mod().adapt_synthetic_records(minute_specs(1),[record(ip='private')])
    with pytest.raises(ValueError): mod().adapt_synthetic_records(minute_specs(1),(record(str(i)) for i in range(10001)))
