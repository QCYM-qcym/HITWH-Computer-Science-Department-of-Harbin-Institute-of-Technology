"""Pure bounded raw13 package codec; consistency never authenticates a source.

No paths, source replay, aggregation execution, preprocessing or model bridge.
All hashes bind actual canonical bytes in this package only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import math
import re
from types import MappingProxyType

from ._release_csv import (EXPECTED_HEADER, _NORMAL_LABELS, _ATTACK_LABELS,
    _ATTEMPTED_LABELS, _EMPTY_CATEGORIES, _ATTEMPTED_CATEGORIES)
from ._release_minutes import (ReleaseMinuteResult, ReleaseBucketCounts, ReleaseSegment,
    POLICIES, LABEL_KINDS, REASON_CODES, PROTOCOL_CHANNELS, ELIGIBLE_CHANNELS, LABEL_ANOMALIES)
from .candidate_inputs import G13U_FEATURE_NAMES

PACKAGE_MEMBER_NAMES: tuple[str,...]=('minutes.json','labels.json','diagnostics.json','manifest.json','COMPLETE.json')
PACKAGE_MEMBER_BYTE_LIMITS: tuple[tuple[str,int],...]=tuple(zip(PACKAGE_MEMBER_NAMES,(8388608,8388608,8388608,65536,4096)))
PACKAGE_TOTAL_BYTE_LIMIT: int=20971520
_LIMITS=dict(PACKAGE_MEMBER_BYTE_LIMITS)
_PROFILE='c17-release-minute-package-v1'
_SOURCE='c17-release-91-v1'
_SCOPE='PACKAGE_INTERNAL_CONSISTENCY_ONLY'
_AUTH='NOT_AUTHENTICATED'
_TIME='SOURCE_WALL_CLOCK_COMPLETION_PROXY'
_MAX_RECORDS=2500000
_SHA=re.compile('[0-9a-f]{64}\\Z')
_STAMP=re.compile('[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00\\Z')
_ROLES=('train','validation','calibration','test')
_SPECIAL=frozenset(('invalid_timestamp','invalid_duration','outside_registered_minutes','unplaced_invalid_row','empty_unconfirmed'))
_ASSIGNED=tuple(key for key in REASON_CODES if key not in _SPECIAL)
_CODES=frozenset(('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE',
    'OUTPUT_EXISTS','PACKAGE_CHANGED','OUTPUT_ERROR'))


class ReleaseMinutePackageError(ValueError):
    code: str

    def __init__(self,code):
        self.code=code if type(code) is str and code in _CODES else 'INVALID_PACKAGE'
        super().__init__(self.code)


def _need(value,code='INCONSISTENT_PACKAGE'):
    if not value:raise ReleaseMinutePackageError(code)


def _uint(value,maximum=_MAX_RECORDS,*,positive=False):
    _need(type(value) is int and value>=int(positive),'INVALID_PACKAGE')
    _need(value<=maximum,'RESOURCE_LIMIT')
    return value


def _sha(value):
    _need(type(value) is str and _SHA.fullmatch(value) is not None,'INVALID_PACKAGE')


def _keys(value,keys):
    _need(type(value) is dict and all(type(key) is str for key in value) and set(value)==set(keys),'INVALID_PACKAGE')


def _tuple(value,length):
    _need(type(value) is tuple and len(value)==length,'INVALID_PACKAGE')
    return value


def _list(value,length):
    _need(type(value) is list and len(value)==length,'INVALID_PACKAGE')
    return value


def _same(actual,expected):
    if type(actual) is not type(expected):return False
    if type(expected) is dict:
        return actual.keys()==expected.keys() and all(_same(actual[key],value) for key,value in expected.items())
    if type(expected) in (list,tuple):return len(actual)==len(expected) and all(_same(a,b) for a,b in zip(actual,expected))
    return actual==expected


def _freeze(value):
    if type(value) is dict:return MappingProxyType({key:_freeze(item) for key,item in value.items()})
    if type(value) in (tuple,list):return tuple(_freeze(item) for item in value)
    return value


def _plain(value):
    if type(value) is MappingProxyType:return {key:_plain(item) for key,item in value.items()}
    if type(value) is tuple:return [_plain(item) for item in value]
    return value


_PROTOCOL=_freeze(dict(profile_id='c17-release-raw13-rules-v1',header=EXPECTED_HEADER,
    feature_names=G13U_FEATURE_NAMES,policies=POLICIES,label_kind_order=LABEL_KINDS,reason_order=REASON_CODES,
    raw_protocol_order=PROTOCOL_CHANNELS,eligible_protocol_order=ELIGIBLE_CHANNELS,label_anomaly_order=LABEL_ANOMALIES,
    minute_seconds=60,minute_interval='LEFT_CLOSED_RIGHT_OPEN',completion_rule='SOURCE_START_PLUS_DURATION_US',
    assignment_rule='FLOOR_COMPLETION_TO_SOURCE_MINUTE',source_timestamp_profile='STRPTIME_YMD_HMS_FRACTION_NAIVE_V1',
    integer_parse_profile='RELEASE_DECIMAL_NONNEGATIVE_INTEGRAL_4096_DIGITS_V1',duration_max_us=86400000000,
    duration_output_unit='SECONDS',quantile_rule='LINEAR_RATIONAL_MICROSECONDS_THEN_FLOAT64',
    duplicate_rule='EXCLUDE_ALL_FULL91_LENGTH_PREFIXED_UTF8_LEXICAL_COPIES_GLOBAL',
    cross_segment_rule='EXCLUDE_IF_START_NOT_IN_COMPLETION_SEGMENT',unplaced_rule='INVALIDATE_ALL_REGISTERED_MINUTES',
    empty_rule='UNCONFIRMED_INVALID_NULL_NOT_ZERO',minute_label_rule='INVALID_UNKNOWN_ELSE_UNKNOWN_THEN_ATTACK_THEN_NORMAL',
    protocol_codes=dict(tcp=(6,),udp=(17,),known_other=(1,2,132),unresolved=(0,)),
    other_protocol_rule='EXCLUDE_INVALID_OR_UNSUPPORTED_CODE',label_rules=dict(
        profile_id='c17-release-attempted-three-policy-v1',normal_labels=_NORMAL_LABELS,attack_labels=_ATTACK_LABELS,
        attempted_labels=_ATTEMPTED_LABELS,empty_categories=_EMPTY_CATEGORIES,attempted_categories=_ATTEMPTED_CATEGORIES,
        attempted_policy_kinds=('unknown','normal','attack'))))


def _valid_id(value):
    return (type(value) is str and 1<=len(value)<=128
        and all(ord(c)>=32 and ord(c)!=127 and not 0xD800<=ord(c)<=0xDFFF for c in value))


def _axis(segments):
    _need(type(segments) is tuple and 1<=len(segments)<=7,'INVALID_PACKAGE_ARGUMENTS')
    times,ids,roles,ordinals=[],[],[],[]
    previous_end=None;previous_role=-1;seen=set()
    for ordinal,segment in enumerate(segments):
        _need(type(segment) is ReleaseSegment and _valid_id(segment.id),'INVALID_PACKAGE')
        _need(segment.id not in seen and type(segment.role) is str and segment.role in _ROLES,'INVALID_PACKAGE')
        seen.add(segment.id)
        for stamp in (segment.start,segment.end):
            _need(type(stamp) is datetime and stamp.tzinfo is None and stamp.second==stamp.microsecond==0,'INVALID_PACKAGE')
        _need(segment.start<segment.end and (previous_end is None or previous_end<=segment.start))
        role=_ROLES.index(segment.role);_need(role>=previous_role)
        count=(segment.end-segment.start)//timedelta(minutes=1)
        _need(len(times)+count<=10000,'RESOURCE_LIMIT')
        times.extend(segment.start+timedelta(minutes=i) for i in range(count))
        ids.extend([segment.id]*count);roles.extend([segment.role]*count);ordinals.extend([ordinal]*count)
        previous_end,previous_role=segment.end,role
    _need(bool(times),'INVALID_PACKAGE')
    return tuple(times),tuple(ids),tuple(roles),tuple(ordinals)


def _pairs(value,names):
    _tuple(value,len(names))
    result={}
    for pair,name in zip(value,names):
        _tuple(pair,2);_need(type(pair[0]) is str and pair[0]==name,'INVALID_PACKAGE')
        result[name]=_uint(pair[1])
    return result


def _kinds(value):
    _tuple(value,3)
    for row in value:
        _tuple(row,3)
        for count in row:_uint(count)
    return value


def _level(raw,eligible,excluded,reasons,protocol,good,kinds,anomalies):
    for value in (raw,eligible,excluded):_uint(value)
    _need(raw==eligible+excluded and sum(protocol.values())==raw and sum(good.values())==eligible)
    _need(all(good[key]<=protocol[key] for key in ELIGIBLE_CHANNELS))
    _need(reasons['invalid_protocol']+reasons['invalid_unsupported_protocol']==protocol['excluded_protocol'])
    _kinds(kinds);_need(all(sum(row)==raw for row in kinds))
    _need(sum(anomalies.values())<=raw)
    pu,pb,pa=kinds;abnormal=sum(anomalies.values())
    attempted=pb[0]-pu[0]
    _need(pu[0]==pa[0] and pu[1]==pb[1] and pb[2]==pa[2]==abnormal
        and attempted>=0 and attempted==pa[1]-pu[1]==pu[2]-pa[2])
    return attempted


def _validate_result(minutes,segments):
    _need(type(minutes) is ReleaseMinuteResult,'INVALID_PACKAGE_ARGUMENTS')
    times,ids,roles,ordinals=_axis(segments);n=len(times)
    _need(type(minutes.schema_id) is str and minutes.schema_id==_SOURCE,'INCOMPATIBLE_PACKAGE')
    _need(type(minutes.source_authentication) is str and minutes.source_authentication==_AUTH
        and type(minutes.time_basis) is str and minutes.time_basis==_TIME)
    _need(type(minutes.source_bytes) is tuple and 1<=len(minutes.source_bytes)<=5,'INVALID_PACKAGE')
    for size in minutes.source_bytes:_uint(size,2**31,positive=True)
    _need(sum(minutes.source_bytes)<=2**31,'RESOURCE_LIMIT')
    _tuple(minutes.source_sha256,len(minutes.source_bytes))
    for sha in minutes.source_sha256:_sha(sha)
    _need(_same(minutes.feature_names,G13U_FEATURE_NAMES),'INVALID_PACKAGE')
    for value in (minutes.timestamps,minutes.segment_ids,minutes.roles,minutes.values,
            minutes.source_valid,minutes.label_kinds,minutes.bucket_counts):_tuple(value,n)
    _need(all(type(t) is datetime and t.tzinfo is None and t.second==t.microsecond==0 for t in minutes.timestamps),'INVALID_PACKAGE')
    _need(_same(minutes.timestamps,times) and _same(minutes.segment_ids,ids) and _same(minutes.roles,roles))
    r,e,x,o,u=(getattr(minutes,name) for name in ('raw_records','eligible_records','excluded_records','outside_records','unplaced_invalid_rows'))
    for count in (r,e,x,o,u,minutes.duplicate_groups):_uint(count)
    reasons=_pairs(minutes.reason_counts,REASON_CODES);raw=_pairs(minutes.raw_protocol_counts,PROTOCOL_CHANNELS)
    good=_pairs(minutes.eligible_protocol_counts,ELIGIBLE_CHANNELS);anomalies=_pairs(minutes.label_anomaly_counts,LABEL_ANOMALIES)
    _level(r,e,x,reasons,raw,good,minutes.label_kind_counts,anomalies)
    _need(reasons['outside_registered_minutes']==o and reasons['unplaced_invalid_row']==u and reasons['empty_unconfirmed']==0)
    _need(max(reasons['invalid_timestamp'],reasons['invalid_duration'])<=u<=reasons['invalid_timestamp']+reasons['invalid_duration'])
    _need(all(reasons[key]<=x for key in _ASSIGNED))
    duplicates=reasons['duplicate_record'];groups=minutes.duplicate_groups
    _need((duplicates==0)==(groups==0) and groups<=r//2 and (not groups or 2*groups<=duplicates<=r))
    reports=[]
    for i,bucket in enumerate(minutes.bucket_counts):
        _need(type(bucket) is ReleaseBucketCounts,'INVALID_PACKAGE')
        br,be,bx=bucket.raw_records,bucket.eligible_records,bucket.excluded_records
        why=_pairs(bucket.reason_counts,REASON_CODES);bp=_pairs(bucket.raw_protocol_counts,PROTOCOL_CHANNELS)
        bg=_pairs(bucket.eligible_protocol_counts,ELIGIBLE_CHANNELS);ba=_pairs(bucket.label_anomaly_counts,LABEL_ANOMALIES)
        attempted=_level(br,be,bx,why,bp,bg,bucket.label_kind_counts,ba)
        _uint(bucket.unused_field_issue_records);_need(bucket.unused_field_issue_records<=br)
        _need(type(bucket.definite_attack_present) is bool and type(bucket.attempted_present) is bool,'INVALID_PACKAGE')
        _need(br!=0 or not(bucket.definite_attack_present or bucket.attempted_present))
        _need(bucket.label_kind_counts[0][1]==0 or bucket.definite_attack_present)
        _need(not(attempted or ba['unknown_attempted_category'] or ba['label_category_conflict']) or bucket.attempted_present)
        _need(why['outside_registered_minutes']==0 and why['unplaced_invalid_row']==u
            and why['empty_unconfirmed']==int(br==0) and why['invalid_timestamp']==why['invalid_duration']==0)
        _need(all(why[key]<=bx for key in _ASSIGNED) and (bx>0)==any(why[key]>0 for key in _ASSIGNED))
        valid=minutes.source_valid[i];_need(type(valid) is bool,'INVALID_PACKAGE')
        _need(valid==all(value==0 for value in why.values()))
        row=minutes.values[i];_tuple(row,13)
        if valid:
            _need(br==be>0 and bx==0)
            _need(all(type(value) is float and math.isfinite(value) and value>=0
                and not(value==0 and math.copysign(1.,value)<0) for value in row),'INVALID_PACKAGE')
            _need(row[0]==float(be) and tuple(row[5:9])==tuple(float(bg[key]) for key in ELIGIBLE_CHANNELS)
                and sum(row[5:9])==row[0])
            _need(all(value.is_integer() for value in row[1:5]) and row[12].is_integer() and 0<=row[12]<=be)
            _need(0<=row[10]<=row[11]<=row[9]<=86400.)
        else:_need(all(value is None for value in row))
        label=minutes.label_kinds[i];_tuple(label,3)
        _need(all(type(value) is str and value in LABEL_KINDS for value in label),'INVALID_PACKAGE')
        expected=tuple('unknown' if not valid or counts[2] else 'attack' if counts[1] else 'normal'
                       for counts in bucket.label_kind_counts)
        _need(label==expected)
        reports.append((bucket,why,bp,bg,ba))
    _need(sum(b.raw_records for b,_,_,_,_ in reports)+o+u==r
        and sum(b.eligible_records for b,_,_,_,_ in reports)==e
        and sum(b.excluded_records for b,_,_,_,_ in reports)+o+u==x)
    for key in ELIGIBLE_CHANNELS:_need(good[key]==sum(bg[key] for _,_,_,bg,_ in reports))
    raw_differences=[raw[key]-sum(bp[key] for _,_,bp,_,_ in reports) for key in PROTOCOL_CHANNELS]
    _need(all(value>=0 for value in raw_differences) and sum(raw_differences)==o+u)
    for key in _ASSIGNED:
        difference=reasons[key]-sum(why[key] for _,why,_,_,_ in reports)
        _need(difference==0 if key=='cross_partition' else 0<=difference<=o+u)
    for policy in range(3):
        differences=[minutes.label_kind_counts[policy][kind]-sum(b.label_kind_counts[policy][kind] for b,_,_,_,_ in reports) for kind in range(3)]
        _need(all(value>=0 for value in differences) and sum(differences)==o+u)
    anomaly_differences=[anomalies[key]-sum(ba[key] for _,_,_,_,ba in reports) for key in LABEL_ANOMALIES]
    _need(all(value>=0 for value in anomaly_differences) and sum(anomaly_differences)<=o+u)
    return ordinals


@dataclass(frozen=True,slots=True)
class ReleaseMinutePackageIdentity:
    profile_id: str
    context_sha256: str
    manifest_sha256: str
    manifest_byte_count: int

    def __post_init__(self):
        _need(type(self.profile_id) is str and self.profile_id==_PROFILE,'INCOMPATIBLE_PACKAGE')
        _sha(self.context_sha256);_sha(self.manifest_sha256)
        _uint(self.manifest_byte_count,65536,positive=True)


@dataclass(frozen=True,slots=True)
class ReleaseMinutePackage:
    identity: ReleaseMinutePackageIdentity
    minutes: ReleaseMinuteResult
    segments: tuple[ReleaseSegment,...]
    scope: str

    def __post_init__(self):
        _need(type(self.identity) is ReleaseMinutePackageIdentity and type(self.scope) is str and self.scope==_SCOPE,'INVALID_PACKAGE')
        _validate_result(self.minutes,self.segments)


def _canonical(value,limit):
    result=bytearray()
    try:
        for chunk in json.JSONEncoder(ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).iterencode(value):
            encoded=chunk.encode('utf-8')
            _need(len(result)+len(encoded)+1<=limit,'RESOURCE_LIMIT')
            result.extend(encoded)
    except ReleaseMinutePackageError:raise
    except (UnicodeError,TypeError,ValueError,OverflowError,RecursionError):
        raise ReleaseMinutePackageError('INVALID_PACKAGE') from None
    return bytes(result)+b'\n'


def _digest(payload):return dict(byte_count=len(payload),sha256=hashlib.sha256(payload).hexdigest())


def _base(context_sha):return dict(schema_version=1,profile_id=_PROFILE,context_sha256=context_sha)


def _count_values(pairs):return [value for _,value in pairs]


def encode_release_minute_package(minutes: ReleaseMinuteResult,
        segments: tuple[ReleaseSegment,...]) -> tuple[tuple[str,bytes],...]:
    """Encode an already materialized result without opening or replaying sources."""
    ordinals=_validate_result(minutes,segments)
    context=dict(source_schema_id=_SOURCE,source_authentication=_AUTH,time_basis=_TIME,
        sources=[dict(ordinal=i,byte_count=size,sha256=sha) for i,(size,sha) in enumerate(zip(minutes.source_bytes,minutes.source_sha256))],
        segments=[dict(ordinal=i,id=segment.id,role=segment.role,start=segment.start.isoformat(),end=segment.end.isoformat()) for i,segment in enumerate(segments)],
        minute_count=len(minutes.timestamps),protocol=_plain(_PROTOCOL))
    context_sha=hashlib.sha256(_canonical(context,65536)).hexdigest()
    values=dict(_base(context_sha),timestamps=[stamp.isoformat() for stamp in minutes.timestamps],
        segment_ordinals=ordinals,source_valid=minutes.source_valid,values=minutes.values)
    labels=dict(_base(context_sha),label_kinds=minutes.label_kinds,
        bucket_label_kind_counts=[b.label_kind_counts for b in minutes.bucket_counts],
        bucket_label_anomaly_counts=[_count_values(b.label_anomaly_counts) for b in minutes.bucket_counts],
        definite_attack_present=[b.definite_attack_present for b in minutes.bucket_counts],
        attempted_present=[b.attempted_present for b in minutes.bucket_counts],
        global_label_kind_counts=minutes.label_kind_counts,global_label_anomaly_counts=_count_values(minutes.label_anomaly_counts))
    global_counts={key:getattr(minutes,key) for key in ('raw_records','eligible_records','excluded_records','outside_records','unplaced_invalid_rows','duplicate_groups')}
    for key in ('reason_counts','raw_protocol_counts','eligible_protocol_counts'):global_counts[key]=_count_values(getattr(minutes,key))
    buckets=[]
    for bucket in minutes.bucket_counts:
        value={key:getattr(bucket,key) for key in ('raw_records','eligible_records','excluded_records','unused_field_issue_records')}
        for key in ('reason_counts','raw_protocol_counts','eligible_protocol_counts'):value[key]=_count_values(getattr(bucket,key))
        buckets.append(value)
    diagnostics=dict(_base(context_sha),**{'global':global_counts,'buckets':buckets})
    members=[];total=0
    def append(name,doc):
        nonlocal total
        payload=_canonical(doc,min(_LIMITS[name],PACKAGE_TOTAL_BYTE_LIMIT-total))
        total+=len(payload);members.append((name,payload))
        return payload
    for name,doc in zip(PACKAGE_MEMBER_NAMES[:3],(values,labels,diagnostics)):append(name,doc)
    manifest=append('manifest.json',dict(_base(context_sha),context=context,members={name:_digest(payload) for name,payload in members}))
    append('COMPLETE.json',dict(schema_version=1,profile_id=_PROFILE,status='COMPLETE',manifest=_digest(manifest)))
    return tuple(members)


def _json_int(token):
    _need(len(token.lstrip('-'))<=11,'INVALID_PACKAGE')
    return int(token)


def _json_float(token):
    value=float(token);_need(math.isfinite(value),'INVALID_PACKAGE');return value


def _json_object(pairs):
    result={}
    for key,value in pairs:
        _need(key not in result,'INVALID_PACKAGE');result[key]=value
    return result


def _bad_constant(_):raise ReleaseMinutePackageError('INVALID_PACKAGE')


def _parse(payload,limit):
    try:
        result=json.loads(payload.decode('utf-8'),object_pairs_hook=_json_object,
            parse_int=_json_int,parse_float=_json_float,parse_constant=_bad_constant)
        _need(_canonical(result,limit)==payload,'INVALID_PACKAGE')
        return result
    except ReleaseMinutePackageError:raise
    except (UnicodeError,TypeError,ValueError,OverflowError,RecursionError):
        raise ReleaseMinutePackageError('INVALID_PACKAGE') from None


def _header(doc,keys,*,bound=True):
    _keys(doc,keys)
    _need(type(doc['schema_version']) is int,'INVALID_PACKAGE')
    _need(doc['schema_version']==1 and type(doc['profile_id']) is str and doc['profile_id']==_PROFILE,'INCOMPATIBLE_PACKAGE')
    if bound:_sha(doc['context_sha256'])


def _binding(value,payload):
    _keys(value,('byte_count','sha256'));_uint(value['byte_count'],PACKAGE_TOTAL_BYTE_LIMIT,positive=True);_sha(value['sha256'])
    _need(_same(value,_digest(payload)),'INTEGRITY_MISMATCH')


def _stamp(value):
    _need(type(value) is str and _STAMP.fullmatch(value) is not None,'INVALID_PACKAGE')
    try:return datetime.fromisoformat(value)
    except ValueError:raise ReleaseMinutePackageError('INVALID_PACKAGE') from None


def _pairs_from_list(values,names):return tuple(zip(names,_list(values,len(names))))


def _kinds_from_list(values):return tuple(tuple(_list(row,3)) for row in _list(values,3))


def decode_release_minute_package(members: dict[str,bytes]) -> ReleaseMinutePackage:
    """Validate exactly five bounded payloads and return a detached frozen value."""
    _need(type(members) is dict and all(type(key) is str for key in members)
        and set(members)==set(PACKAGE_MEMBER_NAMES)
        and all(type(payload) is bytes for payload in members.values()),'INVALID_PACKAGE_ARGUMENTS')
    _need(all(len(members[name])<=limit for name,limit in PACKAGE_MEMBER_BYTE_LIMITS)
        and sum(map(len,members.values()))<=PACKAGE_TOTAL_BYTE_LIMIT,'RESOURCE_LIMIT')
    complete=_parse(members['COMPLETE.json'],4096)
    _header(complete,('schema_version','profile_id','status','manifest'),bound=False)
    _need(type(complete['status']) is str and complete['status']=='COMPLETE','INVALID_PACKAGE')
    _binding(complete['manifest'],members['manifest.json'])
    manifest=_parse(members['manifest.json'],65536)
    _header(manifest,('schema_version','profile_id','context_sha256','context','members'))
    _keys(manifest['members'],PACKAGE_MEMBER_NAMES[:3])
    for name in PACKAGE_MEMBER_NAMES[:3]:_binding(manifest['members'][name],members[name])
    context=manifest['context']
    _keys(context,('source_schema_id','source_authentication','time_basis','sources','segments','minute_count','protocol'))
    _need(hashlib.sha256(_canonical(context,65536)).hexdigest()==manifest['context_sha256'],'INTEGRITY_MISMATCH')
    _need(type(context['source_schema_id']) is str and context['source_schema_id']==_SOURCE,'INCOMPATIBLE_PACKAGE')
    _need(type(context['source_authentication']) is str and context['source_authentication']==_AUTH
        and type(context['time_basis']) is str and context['time_basis']==_TIME)
    _need(_same(context['protocol'],_plain(_PROTOCOL)),'INCOMPATIBLE_PACKAGE')
    sources=context['sources'];_need(type(sources) is list and 1<=len(sources)<=5,'INVALID_PACKAGE')
    for i,source in enumerate(sources):
        _keys(source,('ordinal','byte_count','sha256'))
        _need(type(source['ordinal']) is int and source['ordinal']==i,'INVALID_PACKAGE')
        _uint(source['byte_count'],2**31,positive=True);_sha(source['sha256'])
    raw_segments=context['segments'];_need(type(raw_segments) is list and 1<=len(raw_segments)<=7,'INVALID_PACKAGE')
    segments=[]
    for i,segment in enumerate(raw_segments):
        _keys(segment,('ordinal','id','role','start','end'))
        _need(type(segment['ordinal']) is int and segment['ordinal']==i,'INVALID_PACKAGE')
        segments.append(ReleaseSegment(segment['id'],segment['role'],_stamp(segment['start']),_stamp(segment['end'])))
    segments=tuple(segments);times,ids,roles,ordinals=_axis(segments)
    n=_uint(context['minute_count'],10000,positive=True);_need(n==len(times))
    data={name:_parse(members[name],_LIMITS[name]) for name in PACKAGE_MEMBER_NAMES[:3]}
    for doc in data.values():
        _need(type(doc) is dict and type(doc.get('context_sha256')) is str
            and doc['context_sha256']==manifest['context_sha256'],'INTEGRITY_MISMATCH')
    minute=data['minutes.json'];label=data['labels.json'];diag=data['diagnostics.json']
    _header(minute,('schema_version','profile_id','context_sha256','timestamps','segment_ordinals','source_valid','values'))
    _header(label,('schema_version','profile_id','context_sha256','label_kinds','bucket_label_kind_counts',
        'bucket_label_anomaly_counts','definite_attack_present','attempted_present','global_label_kind_counts','global_label_anomaly_counts'))
    _header(diag,('schema_version','profile_id','context_sha256','global','buckets'))
    _need(_same(tuple(_list(minute['segment_ordinals'],n)),ordinals))
    stamps=tuple(_stamp(stamp) for stamp in _list(minute['timestamps'],n))
    values=tuple(tuple(_list(row,13)) for row in _list(minute['values'],n))
    valid=tuple(_list(minute['source_valid'],n))
    label_kinds=tuple(tuple(_list(row,3)) for row in _list(label['label_kinds'],n))
    kinds=_list(label['bucket_label_kind_counts'],n);anomalies=_list(label['bucket_label_anomaly_counts'],n)
    definite=_list(label['definite_attack_present'],n);attempted=_list(label['attempted_present'],n)
    buckets=[]
    for i,bucket in enumerate(_list(diag['buckets'],n)):
        _keys(bucket,('raw_records','eligible_records','excluded_records','reason_counts','raw_protocol_counts','eligible_protocol_counts','unused_field_issue_records'))
        buckets.append(ReleaseBucketCounts(bucket['raw_records'],bucket['eligible_records'],bucket['excluded_records'],
            _pairs_from_list(bucket['reason_counts'],REASON_CODES),_pairs_from_list(bucket['raw_protocol_counts'],PROTOCOL_CHANNELS),
            _pairs_from_list(bucket['eligible_protocol_counts'],ELIGIBLE_CHANNELS),_kinds_from_list(kinds[i]),
            _pairs_from_list(anomalies[i],LABEL_ANOMALIES),definite[i],attempted[i],bucket['unused_field_issue_records']))
    g=diag['global']
    _keys(g,('raw_records','eligible_records','excluded_records','outside_records','unplaced_invalid_rows','duplicate_groups',
        'reason_counts','raw_protocol_counts','eligible_protocol_counts'))
    result=ReleaseMinuteResult(_SOURCE,tuple(source['byte_count'] for source in sources),tuple(source['sha256'] for source in sources),
        _AUTH,_TIME,G13U_FEATURE_NAMES,stamps,ids,roles,values,valid,label_kinds,tuple(buckets),g['raw_records'],g['eligible_records'],
        g['excluded_records'],g['outside_records'],g['unplaced_invalid_rows'],g['duplicate_groups'],
        _pairs_from_list(g['reason_counts'],REASON_CODES),_pairs_from_list(g['raw_protocol_counts'],PROTOCOL_CHANNELS),
        _pairs_from_list(g['eligible_protocol_counts'],ELIGIBLE_CHANNELS),_kinds_from_list(label['global_label_kind_counts']),
        _pairs_from_list(label['global_label_anomaly_counts'],LABEL_ANOMALIES))
    identity=ReleaseMinutePackageIdentity(_PROFILE,manifest['context_sha256'],hashlib.sha256(members['manifest.json']).hexdigest(),len(members['manifest.json']))
    return ReleaseMinutePackage(identity,result,segments,_SCOPE)
