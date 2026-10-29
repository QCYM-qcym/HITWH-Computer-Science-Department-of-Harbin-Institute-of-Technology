"""Bounded synthetic source-record adapter, not a real CSV/data-use profile.

Completion is start+duration_us on a declared artificial source clock. Unknown
physical protocol 0 has its own channel. Labels remain separate from values.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import re

import numpy as np

from .candidate_inputs import CandidateMinuteBatch, G13U_FEATURE_NAMES, MAX_MINUTES

RECORD_PROFILE_ID = 'c17-i1-g13u-record-adapter-v1'
POLICIES = ('P_U', 'P_B', 'P_A')
MAX_RECORDS = 10000
_MINUTE = timedelta(minutes=1)
_SYMBOL = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
_STAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?\Z')
_WORDS = re.compile(r'[A-Za-z0-9 _.\-]*\Z')
_MINUTE_FIELDS = {'timestamp','partition','segment_id','coverage','empty_label'}
_RECORD_FIELDS = {'record_key','start','duration_us','protocol','fwd_packets','bwd_packets',
                  'fwd_length','bwd_length','label','attempted_category'}
_COUNTS = ('fwd_packets','bwd_packets','fwd_length','bwd_length')
_ATTACK = frozenset(('FTP-Patator','SSH-Patator','DoS Slowloris','DoS Slowhttptest','DoS Hulk',
    'DoS GoldenEye','Heartbleed','Web Attack - Brute Force','Web Attack - XSS',
    'Web Attack - SQL Injection','Infiltration','Infiltration - Portscan','Portscan','Botnet','DDoS'))
_ATTEMPTED = frozenset(x+' - Attempted' for x in _ATTACK if x not in ('Infiltration - Portscan','Portscan'))


def _parse_time(value):
    if not isinstance(value,str) or not _STAMP.fullmatch(value):
        raise ValueError('synthetic_source_clock_required')
    return datetime.fromisoformat(value)


def _floor(value):
    return value.replace(second=0,microsecond=0)


def _symbol(value):
    return isinstance(value,str) and bool(_SYMBOL.fullmatch(value))


def _word(value):
    if value is not None and (not isinstance(value,str) or len(value)>128 or not _WORDS.fullmatch(value)):
        raise ValueError('bounded_synthetic_label_word_required')
    return value


def _channel(value):
    if type(value) is not int: return 'invalid'
    if value==0: return 'unresolved'
    if value==6: return 'tcp'
    if value==17: return 'udp'
    return 'known_other' if value in (1,2,132) else 'invalid'


def _kinds(label, category):
    known=label=='BENIGN' or label in _ATTACK or label in _ATTEMPTED
    attempted=label in _ATTEMPTED or category!='-1'
    category_known=category in ('-1','0','1','2','3','4','5','6')
    conflict=((label=='BENIGN' or label in _ATTACK) and attempted
              or label in _ATTEMPTED and category=='-1')
    if not known or not category_known or conflict: return ('unknown',)*3
    if attempted: return ('unknown','normal','attack')
    return ('attack',)*3 if label in _ATTACK else ('normal',)*3


def _counter_key(value):
    return '<MISSING>' if value is None else value


@dataclass(frozen=True)
class CandidateRecordResult:
    batch: CandidateMinuteBatch
    labels: dict[str,tuple[str,...]]
    normal_candidates: dict[str,np.ndarray]
    audit: dict

    def to_fixture(self, policy, *, epsilon=1e-6):
        if policy not in POLICIES or type(epsilon) not in (int,float) or not math.isfinite(epsilon) or epsilon<=0:
            raise ValueError('explicit_policy_and_positive_epsilon_required')
        b=self.batch
        return dict(schema_version=1,evidence_kind='SYNTHETIC_ONLY',time_basis='synthetic_source_clock',
            feature_names=list(G13U_FEATURE_NAMES),epsilon=epsilon,
            normal_candidates=self.normal_candidates[policy].tolist(),
            minutes=[dict(timestamp=str(t).removesuffix('.000000'),partition=str(b.partitions[i]),
                          segment_id=str(b.segment_ids[i]),valid=bool(b.row_valid[i]),
                          features=b.values[i].tolist() if b.row_valid[i] else [None]*13)
                     for i,t in enumerate(b.timestamps)])


def adapt_synthetic_records(minutes, records, *, evidence_kind='SYNTHETIC_ONLY'):
    if evidence_kind!='SYNTHETIC_ONLY' or not isinstance(minutes,(list,tuple)) or not 1<=len(minutes)<=MAX_MINUTES:
        raise ValueError('bounded_synthetic_minutes_required')
    stamps=[]
    for m in minutes:
        if (not isinstance(m,dict) or set(m)!=_MINUTE_FIELDS or not _symbol(m['segment_id'])
                or m['coverage'] not in ('observed','confirmed_empty','missing')
                or m['empty_label'] not in ('normal','unknown')
                or m['coverage']!='confirmed_empty' and m['empty_label']!='unknown'):
            raise ValueError('minute_contract')
        t=_parse_time(m['timestamp'])
        if _floor(t)!=t: raise ValueError('whole_minutes_required')
        stamps.append(t)
    n=len(minutes)
    # Reuse the candidate batch's dimension, time and chronological-role checks.
    skeleton=CandidateMinuteBatch(np.array(stamps,dtype='datetime64[us]'),np.zeros((n,13)),
        np.ones(n,bool),np.array([m['segment_id'] for m in minutes]),np.array([m['partition'] for m in minutes]))
    lookup={t:i for i,t in enumerate(stamps)}
    gap_prefix=[0]*n; segment_prefix=[0]*n; missing_prefix=[0]*(n+1)
    for i,m in enumerate(minutes):
        gap_prefix[i]=(gap_prefix[i-1] if i else 0)+int(i>0 and stamps[i]-stamps[i-1]!=_MINUTE)
        segment_prefix[i]=(segment_prefix[i-1] if i else 0)+int(i>0 and m['segment_id']!=minutes[i-1]['segment_id'])
        missing_prefix[i+1]=missing_prefix[i]+int(m['coverage']=='missing')
    rows=[]; keys=defaultdict(list)
    for raw in records:
        if len(rows)>=MAX_RECORDS: raise ValueError('record_cap')
        if not isinstance(raw,dict) or set(raw)!=_RECORD_FIELDS or not _symbol(raw['record_key']):
            raise ValueError('record_contract')
        label,category=_word(raw['label']),_word(raw['attempted_category'])
        start=_parse_time(raw['start']); duration=raw['duration_us']
        if type(duration) is not int or not 0<=duration<=86400000000:
            raise ValueError('bounded_integer_duration_required')
        try: end=start+timedelta(microseconds=duration)
        except OverflowError as exc: raise ValueError('completion_out_of_range') from exc
        index=lookup.get(_floor(end)); origin=lookup.get(_floor(start)); bad=set()
        channel=_channel(raw['protocol'])
        if channel=='invalid': bad.add('invalid_protocol')
        for field in _COUNTS:
            if type(raw[field]) is not int or not 0<=raw[field]<=1000000000:
                bad.add('invalid_'+field)
        if index is None:
            bad.add('outside_candidate_minutes')
        elif origin is None:
            bad.add('cross_candidate_boundary')
        else:
            if minutes[origin]['partition']!=minutes[index]['partition']: bad.add('cross_partition')
            if segment_prefix[index]!=segment_prefix[origin]: bad.add('cross_segment')
            if gap_prefix[index]!=gap_prefix[origin]: bad.add('cross_time_gap')
            if missing_prefix[index+1]!=missing_prefix[origin]: bad.add('cross_capture_missing')
        r=dict(raw=raw.copy(),label=label,category=category,index=index,channel=channel,
               bad=bad,kinds=_kinds(label,category))
        keys[raw['record_key']].append(len(rows)); rows.append(r)
    duplicate_groups=0
    for group in keys.values():
        if len(group)>1:
            duplicate_groups+=1
            reason='duplicate_record_key' if all(rows[i]['raw']==rows[group[0]]['raw'] for i in group) else 'conflicting_record_key'
            for i in group: rows[i]['bad'].add(reason)
    buckets=[[] for _ in minutes]
    raw_channels=Counter({k:0 for k in ('tcp','udp','known_other','unresolved','invalid')})
    eligible_channels=Counter({k:0 for k in ('tcp','udp','known_other','unresolved')})
    source_labels=Counter(); source_categories=Counter(); pairs=Counter(); record_reasons=Counter()
    eligible=outside=0
    for r in rows:
        raw_channels[r['channel']]+=1
        source_labels[_counter_key(r['label'])]+=1; source_categories[_counter_key(r['category'])]+=1
        pairs[(r['label'],r['category'])]+=1
        record_reasons.update(r['bad'])
        outside+=r['index'] is None
        if not r['bad']:
            eligible+=1; eligible_channels[r['channel']]+=1
        if r['index'] is not None: buckets[r['index']].append(r)
    features=np.full((n,13),np.nan); valid=np.zeros(n,bool)
    labels={p:[] for p in POLICIES}; reports=[]
    for i,(m,bucket) in enumerate(zip(minutes,buckets)):
        why={reason for r in bucket for reason in r['bad']}
        if m['coverage']=='missing': why.add('capture_missing')
        if m['coverage']=='confirmed_empty' and bucket: why.add('empty_evidence_conflict')
        if m['coverage']=='observed' and not bucket: why.add('empty_unconfirmed')
        valid[i]=not why
        good=[r for r in bucket if not r['bad']]
        if valid[i]:
            channels=Counter(r['channel'] for r in good)
            duration=np.array([r['raw']['duration_us']/1000000 for r in good])
            sums=[sum(r['raw'][f] for r in good) for f in _COUNTS]
            features[i]=[len(good),*sums,channels['tcp'],channels['udp'],channels['known_other'],channels['unresolved'],
                         float(duration.max()) if len(duration) else 0,
                         float(np.quantile(duration,.5,method='linear')) if len(duration) else 0,
                         float(np.quantile(duration,.95,method='linear')) if len(duration) else 0,
                         sum(r['raw']['bwd_packets']==0 for r in good)]
        kinds={}
        for k,p in enumerate(POLICIES):
            observed={r['kinds'][k] for r in good}
            if not valid[i] or 'unknown' in observed: kind='unknown'
            elif not good: kind=m['empty_label']
            else: kind='attack' if 'attack' in observed else 'normal'
            labels[p].append(kind); kinds[p]=kind
        reports.append(dict(timestamp=m['timestamp'],coverage=m['coverage'],
            raw_record_count=len(bucket),eligible_record_count=len(good),invalid_reasons=sorted(why),
            source_label_counts=dict(Counter(_counter_key(r['label']) for r in bucket)),
            source_category_counts=dict(Counter(_counter_key(r['category']) for r in bucket)),
            source_attack_label_present=any(r['label'] in _ATTACK for r in bucket),labels=kinds))
    final_labels={p:tuple(v) for p,v in labels.items()}
    masks={p:np.array([v=='normal' for v in values],dtype=bool) for p,values in final_labels.items()}
    for mask in masks.values(): mask.setflags(write=False)
    audit=dict(profile_id=RECORD_PROFILE_ID,evidence_kind='SYNTHETIC_ONLY',time_basis='synthetic_source_clock',
        policy_status='AUDIT_ONLY',input_records=len(rows),eligible_records=eligible,excluded_records=len(rows)-eligible,
        outside_records=int(outside),duplicate_key_groups=duplicate_groups,
        raw_protocol_channels=dict(raw_channels),eligible_protocol_channels=dict(eligible_channels),
        source_label_counts=dict(source_labels),source_category_counts=dict(source_categories),
        source_label_category_counts=[dict(label=l,attempted_category=c,records=count) for (l,c),count in pairs.items()],
        record_reason_counts=dict(record_reasons),reason_counts_may_overlap=True,
        record_conservation=len(rows)==eligible+(len(rows)-eligible),
        channel_conservation=sum(raw_channels.values())==len(rows) and sum(eligible_channels.values())==eligible,
        minute_reports=reports,policy_label_counts={p:dict(Counter(values)) for p,values in final_labels.items()})
    batch=CandidateMinuteBatch(skeleton.timestamps,features,valid,skeleton.segment_ids,skeleton.partitions)
    return CandidateRecordResult(batch,final_labels,masks,audit)
