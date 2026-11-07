"""Independent raw-release input preparation, bounded codec and explicit replay.

Loading checks internal structure only. Replay uses saved parameters, never refits.
No model, source file, filesystem or research-policy approval belongs here.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
import hashlib
import json
import math
import re

import numpy as np

from .candidate_inputs import G13U_FEATURE_NAMES
from ._release_minutes import ReleaseSegment
from .release_minute_contract import (ReleaseMinutePackage,ReleaseMinutePackageIdentity,
    ReleaseMinutePackageError,encode_release_minute_package)

PACKAGE_MEMBER_NAMES: tuple[str,...]=('preprocess.json','inputs.json','labels.json','manifest.json','COMPLETE.json')
PACKAGE_MEMBER_BYTE_LIMITS: tuple[tuple[str,int],...]=tuple(zip(PACKAGE_MEMBER_NAMES,(16384,16777216,2097152,65536,4096)))
PACKAGE_TOTAL_BYTE_LIMIT: int=20971520
_LIMITS=dict(PACKAGE_MEMBER_BYTE_LIMITS)
_P='c17-release-prepared-input-package-v1'
_R='c17-release-log1p-mad-input-rules-v1'
_V='c17-release-input-replay-v1'
_RAW='c17-release-minute-package-v1'
_SOURCE='c17-release-91-v1'
_AUTH='NOT_AUTHENTICATED'
_TIME='SOURCE_WALL_CLOCK_COMPLETION_PROXY'
_SCOPE='SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY'
_POLS=('P_U','P_B','P_A')
_KINDS=('normal','attack','unknown')
_ROLES=('train','validation','calibration','test')
_QUAL=('train_full_history_normal','calibration_full_history_normal',
    'validation_current_normal','validation_current_attack','validation_current_unknown',
    'test_current_normal','test_current_attack','test_current_unknown')
_SHA=re.compile(r'[0-9a-f]{64}\Z')
_STAMP=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00\Z')
_CODES=frozenset(('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE','OUTPUT_EXISTS',
    'PACKAGE_CHANGED','OUTPUT_ERROR','INVALID_PREPARATION_CONFIG','UPSTREAM_IDENTITY_MISMATCH',
    'NO_TRAINING_NORMAL_MINUTES','NONFINITE_FIT_STATE','DERIVATION_MISMATCH'))


class ReleaseInputPreparationError(ValueError):
    code: str

    def __init__(self,code):
        self.code=code if type(code) is str and code in _CODES else 'INVALID_PACKAGE'
        super().__init__(self.code)


@dataclass(frozen=True,slots=True)
class ReleasePreparationConfig:
    schema_version: int
    numeric_rules_id: str
    feature_names: tuple[str,...]
    windows: tuple[int,...]
    fit_window: int
    epsilon: float
    audit_fit_policy: str
    policy_status: str


@dataclass(frozen=True,slots=True)
class ReleaseInputIdentity:
    profile_id: str
    context_sha256: str
    manifest_sha256: str
    manifest_byte_count: int


@dataclass(frozen=True,slots=True)
class ReleaseInputContext:
    profile_id: str
    source_schema_id: str
    source_authentication: str
    time_basis: str
    upstream: ReleaseMinutePackageIdentity
    configuration: ReleasePreparationConfig
    configuration_sha256: str
    segments: tuple[ReleaseSegment,...]
    minute_count: int


@dataclass(frozen=True,slots=True)
class ReleasePreprocessState:
    mean: tuple[float,...]
    scale: tuple[float,...]
    n_samples_seen: int
    fit_window: int
    audit_fit_policy: str
    fit_mask_sha256: str
    fit_rows_sha256: str


@dataclass(frozen=True,slots=True)
class ReleasePreparedHistory:
    window: int
    residual: tuple[tuple[float|None,...],...]
    valid: tuple[bool,...]
    invalid_reason: tuple[str|None,...]


@dataclass(frozen=True,slots=True)
class ReleasePreparedMinutes:
    timestamps: tuple[datetime,...]
    segment_ordinals: tuple[int,...]
    raw_valid: tuple[bool,...]
    current_values: tuple[tuple[float|None,...],...]
    prepared_valid: tuple[bool,...]
    prepared_reason: tuple[str|None,...]
    histories: tuple[ReleasePreparedHistory,ReleasePreparedHistory]
    common_valid: tuple[bool,...]


@dataclass(frozen=True,slots=True)
class ReleasePolicyQualification:
    policy: str
    train_full_history_normal: tuple[bool,...]
    calibration_full_history_normal: tuple[bool,...]
    validation_current_normal: tuple[bool,...]
    validation_current_attack: tuple[bool,...]
    validation_current_unknown: tuple[bool,...]
    test_current_normal: tuple[bool,...]
    test_current_attack: tuple[bool,...]
    test_current_unknown: tuple[bool,...]


@dataclass(frozen=True,slots=True)
class ReleaseInputLabels:
    policies: tuple[str,...]
    label_kinds: tuple[tuple[str,str,str],...]
    fit_mask: tuple[bool,...]
    fit_indices: tuple[int,...]
    qualification_masks: tuple[ReleasePolicyQualification,...]


@dataclass(frozen=True,slots=True)
class ReleaseInputLoadReport:
    profile_id: str
    status: str
    scope: str
    identity: ReleaseInputIdentity
    byte_integrity: str
    structure: str
    upstream_replay: str
    transform_history_replay: str
    fit_parameters: str
    source_authentication: str


@dataclass(frozen=True,slots=True)
class ReleasePreparedInputs:
    identity: ReleaseInputIdentity
    context: ReleaseInputContext
    preprocessing: ReleasePreprocessState
    minutes: ReleasePreparedMinutes
    labels: ReleaseInputLabels
    load_report: ReleaseInputLoadReport

    def joined(self,window: int) -> tuple[tuple[float|None,...],...]:
        _need(type(window) is int and window in (15,30),'INVALID_PACKAGE_ARGUMENTS')
        _validate_content(self.context,self.preprocessing,self.minutes,self.labels)
        history=self.minutes.histories[(15,30).index(window)]
        return tuple(current+residual if valid else (None,)*26
            for current,residual,valid in zip(self.minutes.current_values,history.residual,history.valid))


@dataclass(frozen=True,slots=True)
class ReleaseReplayChecks:
    byte_identity: str
    upstream_fields: str
    fit_selection: str
    saved_transform: str
    history: str
    labels_and_masks: str
    fit_parameters: str
    source_authentication: str


@dataclass(frozen=True,slots=True)
class ReleaseReplayTolerance:
    rtol: float
    atol: float
    reference: str


@dataclass(frozen=True,slots=True)
class ReleaseInputReplayReport:
    profile_id: str
    status: str
    scope: str
    upstream_identity: ReleaseMinutePackageIdentity
    input_identity: ReleaseInputIdentity
    minute_count: int
    fit_count: int
    checks: ReleaseReplayChecks
    numerical_tolerance: ReleaseReplayTolerance


def _need(condition,code='INCONSISTENT_PACKAGE'):
    if not condition:raise ReleaseInputPreparationError(code)


def _exact(value,kind):_need(type(value) is kind,'INVALID_PACKAGE')


def _tuple(value,n):
    _need(type(value) is tuple and len(value)==n,'INVALID_PACKAGE');return value


def _int(value,lo,hi):
    _need(type(value) is int and value>=lo,'INVALID_PACKAGE')
    _need(value<=hi,'RESOURCE_LIMIT');return value


def _sha(value):_need(type(value) is str and _SHA.fullmatch(value) is not None,'INVALID_PACKAGE')


def _same(a,b):
    if type(a) is not type(b):return False
    if type(a) in (tuple,list):return len(a)==len(b) and all(_same(x,y) for x,y in zip(a,b))
    if type(a) is dict:return a.keys()==b.keys() and all(_same(a[key],b[key]) for key in a)
    if hasattr(type(a),'__dataclass_fields__'):return all(_same(getattr(a,f.name),getattr(b,f.name)) for f in fields(a))
    return a==b


def _config(config):
    code='INVALID_PREPARATION_CONFIG'
    _need(type(config) is ReleasePreparationConfig,code)
    _need(type(config.schema_version) is int and type(config.numeric_rules_id) is str,code)
    _need(config.schema_version==1 and config.numeric_rules_id==_R,'INCOMPATIBLE_PACKAGE')
    _need(_same(config.feature_names,G13U_FEATURE_NAMES) and _same(config.windows,(15,30))
        and type(config.fit_window) is int and config.fit_window==30,code)
    _need(type(config.epsilon) is float and math.isfinite(config.epsilon) and config.epsilon>0,code)
    _need(type(config.audit_fit_policy) is str and config.audit_fit_policy in _POLS
        and type(config.policy_status) is str and config.policy_status=='AUDIT_ONLY',code)


def _identity(value,kind,profile):
    _exact(value,kind);_need(type(value.profile_id) is str and value.profile_id==profile,'INCOMPATIBLE_PACKAGE')
    _sha(value.context_sha256);_sha(value.manifest_sha256);_int(value.manifest_byte_count,1,65536)


def _axis(segments):
    _need(type(segments) is tuple and 1<=len(segments)<=7,'INVALID_PACKAGE')
    times=[];ordinals=[];roles=[];seen=set();last_end=None;last_role=-1
    for j,segment in enumerate(segments):
        _exact(segment,ReleaseSegment)
        _need(type(segment.id) is str and 1<=len(segment.id)<=128 and all(32<=ord(c)!=127 and not 0xd800<=ord(c)<=0xdfff for c in segment.id),'INVALID_PACKAGE')
        _need(segment.id not in seen,'INVALID_PACKAGE');seen.add(segment.id)
        _need(type(segment.role) is str and segment.role in _ROLES,'INVALID_PACKAGE')
        for stamp in (segment.start,segment.end):
            _need(type(stamp) is datetime and stamp.tzinfo is None and stamp.second==stamp.microsecond==0,'INVALID_PACKAGE')
        rank=_ROLES.index(segment.role)
        _need(segment.start<segment.end and (last_end is None or last_end<=segment.start) and last_role<=rank)
        count=(segment.end-segment.start)//timedelta(minutes=1)
        _need(len(times)+count<=10000,'RESOURCE_LIMIT')
        times.extend(segment.start+timedelta(minutes=i) for i in range(count))
        ordinals.extend([j]*count);roles.extend([segment.role]*count)
        last_end=segment.end;last_role=rank
    return tuple(times),tuple(ordinals),tuple(roles)


def _eligible(times,ordinals,valid,normal,window=30):
    result=[];start=0
    for i in range(len(times)):
        if i and (ordinals[i]!=ordinals[i-1] or times[i]-times[i-1]!=timedelta(minutes=1)):start=i
        if not valid[i]:start=i+1
        result.append(bool(valid[i] and i-start>=window and all(normal[i-window:i+1])))
    return tuple(result)


def _fit_selection(context,minutes,label_kinds):
    q=_POLS.index(context.configuration.audit_fit_policy)
    eligible=_eligible(minutes.timestamps,minutes.segment_ordinals,minutes.raw_valid,tuple(row[q]=='normal' for row in label_kinds))
    return tuple(ok and context.segments[j].role=='train' for ok,j in zip(eligible,minutes.segment_ordinals))


def _qualifications(context,minutes,label_kinds):
    roles=tuple(context.segments[j].role for j in minutes.segment_ordinals);result=[]
    for q,policy in enumerate(_POLS):
        normal=tuple(row[q]=='normal' for row in label_kinds)
        whole=_eligible(minutes.timestamps,minutes.segment_ordinals,minutes.prepared_valid,normal)
        masks=[tuple(common and full and role==wanted for common,full,role in zip(minutes.common_valid,whole,roles)) for wanted in ('train','calibration')]
        masks.extend(tuple(common and role==wanted and row[q]==kind for common,role,row in zip(minutes.common_valid,roles,label_kinds))
                     for wanted in ('validation','test') for kind in _KINDS)
        result.append(ReleasePolicyQualification(policy,*masks))
    return tuple(result)


def _canonical(value,limit):
    buffer=bytearray()
    try:
        for chunk in json.JSONEncoder(ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).iterencode(value):
            encoded=chunk.encode('utf-8');_need(len(buffer)+len(encoded)+1<=limit,'RESOURCE_LIMIT');buffer.extend(encoded)
    except ReleaseInputPreparationError:raise
    except (ValueError,TypeError,UnicodeError,OverflowError,RecursionError):raise ReleaseInputPreparationError('INVALID_PACKAGE') from None
    return bytes(buffer)+b'\n'


def _plain(value):
    if hasattr(type(value),'__dataclass_fields__'):return {f.name:_plain(getattr(value,f.name)) for f in fields(value)}
    if type(value) is tuple:return [_plain(item) for item in value]
    if type(value) is datetime:return value.isoformat()
    return value


def _digest(payload):return dict(byte_count=len(payload),sha256=hashlib.sha256(payload).hexdigest())


def _config_sha(config):return hashlib.sha256(_canonical(_plain(config),16384)).hexdigest()


def _mask_sha(mask):
    return hashlib.sha256(_canonical(dict(schema_version=1,minute_count=len(mask),mask=mask),131072)).hexdigest()


def _rows_sha(raw,indices):
    return hashlib.sha256(_canonical(dict(schema_version=1,rows=[dict(index=i,timestamp=raw.timestamps[i].isoformat(),values=raw.values[i]) for i in indices]),8388608)).hexdigest()


def _bind_upstream(upstream):
    _need(type(upstream) is ReleaseMinutePackage,'INVALID_PACKAGE_ARGUMENTS')
    _need(type(upstream.scope) is str and upstream.scope=='PACKAGE_INTERNAL_CONSISTENCY_ONLY','INVALID_PACKAGE')
    try:members=dict(encode_release_minute_package(upstream.minutes,upstream.segments))
    except ReleaseMinutePackageError as error:raise ReleaseInputPreparationError(error.code) from None
    manifest=members['manifest.json'];context_sha=json.loads(manifest)['context_sha256']
    actual=ReleaseMinutePackageIdentity(_RAW,context_sha,hashlib.sha256(manifest).hexdigest(),len(manifest))
    _need(_same(upstream.identity,actual),'UPSTREAM_IDENTITY_MISMATCH')
    return upstream


def _fit_statistics(z):
    """Separate reduction boundary permits explicit fault-injection evidence."""
    return z.mean(axis=0),z.std(axis=0,ddof=0)


def _fit_state(raw,indices,config,mask):
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        z=np.log1p(np.asarray([raw.values[i] for i in indices],dtype=np.float64))
        mean,scale=_fit_statistics(z)
        constant=(z==z[0]).all(axis=0)
        mean[constant],scale[constant]=z[0,constant],1.
        scale[scale==0]=1.
    _need(mean.shape==(13,) and scale.shape==(13,) and np.isfinite(mean).all()
        and np.isfinite(scale).all() and (scale>0).all(),'NONFINITE_FIT_STATE')
    return ReleasePreprocessState(tuple(map(float,mean)),tuple(map(float,scale)),len(indices),30,
        config.audit_fit_policy,_mask_sha(mask),_rows_sha(raw,indices))


def _transform(raw,state):
    valid=np.asarray(raw.source_valid,dtype=bool).copy();x=np.full((len(valid),13),np.nan)
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        x[valid]=(np.log1p(np.asarray(raw.values,dtype=np.float64)[valid])-state.mean)/state.scale
    valid &= np.isfinite(x).all(axis=1)
    values=tuple(tuple(map(float,row)) if ok else (None,)*13 for row,ok in zip(x,valid))
    reasons=tuple(None if ok else 'source_invalid' if not source else 'nonfinite_transform' for ok,source in zip(valid,raw.source_valid))
    return values,tuple(map(bool,valid)),reasons


def _reset(times,ordinals,i):
    if i and ordinals[i]!=ordinals[i-1]:return 'boundary'
    if i and times[i]-times[i-1]!=timedelta(minutes=1):return 'gap'
    return None


def _history(times,ordinals,values,valid,window,epsilon):
    x=np.asarray(values,dtype=np.float64);residual=[];good=[];reasons=[];start=0;pending='warmup'
    for i,ok in enumerate(valid):
        reset=_reset(times,ordinals,i)
        if reset:start,pending=i,reset
        value=(None,)*13;success=False
        if not ok:reason='invalid_input';start,pending=i+1,reason
        elif i-start<window:reason=pending
        else:
            with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
                median=np.median(x[i-window:i],axis=0)
                mad=np.median(np.abs(x[i-window:i]-median),axis=0)
                numerator=x[i]-median;denominator=mad+epsilon;result=numerator/denominator
            success=all(np.isfinite(v).all() for v in (median,mad,numerator,denominator,result))
            if success:value=tuple(map(float,result));reason=None
            else:reason='nonfinite_history';start,pending=i+1,reason
        residual.append(value);good.append(success);reasons.append(reason)
    return ReleasePreparedHistory(window,tuple(residual),tuple(good),tuple(reasons))


def _report(identity):
    return ReleaseInputLoadReport(_P,'INTERNAL_CONSISTENCY_CHECKED',_SCOPE,identity,'CHECKED','CHECKED',
        'NOT_PERFORMED','NOT_PERFORMED','NOT_REESTIMATED',_AUTH)


def prepare_release_inputs(upstream: ReleaseMinutePackage,config: ReleasePreparationConfig) -> ReleasePreparedInputs:
    upstream=_bind_upstream(upstream);_config(config);raw=upstream.minutes
    context=ReleaseInputContext(_P,_SOURCE,_AUTH,_TIME,upstream.identity,config,_config_sha(config),upstream.segments,len(raw.timestamps))
    ordinals=_axis(upstream.segments)[1]
    base=ReleasePreparedMinutes(raw.timestamps,ordinals,raw.source_valid,(),(),(),(),())
    mask=_fit_selection(context,base,raw.label_kinds);indices=tuple(i for i,ok in enumerate(mask) if ok)
    _need(bool(indices),'NO_TRAINING_NORMAL_MINUTES')
    state=_fit_state(raw,indices,config,mask)
    values,valid,reasons=_transform(raw,state)
    histories=tuple(_history(raw.timestamps,ordinals,values,valid,w,config.epsilon) for w in (15,30))
    common=tuple(v and a and b for v,a,b in zip(valid,histories[0].valid,histories[1].valid))
    minutes=ReleasePreparedMinutes(raw.timestamps,ordinals,raw.source_valid,values,valid,reasons,histories,common)
    labels=ReleaseInputLabels(_POLS,raw.label_kinds,mask,indices,_qualifications(context,minutes,raw.label_kinds))
    return _snapshot(context,state,minutes,labels)


def _bools(value,n):
    _tuple(value,n);_need(all(type(item) is bool for item in value),'INVALID_PACKAGE')


def _finite_vector(value,n,*,positive=False):
    _tuple(value,n)
    _need(all(type(item) is float and math.isfinite(item) and (not positive or item>0) for item in value),'INVALID_PACKAGE')


def _value_rows(rows,valid,n):
    _tuple(rows,n)
    for row,ok in zip(rows,valid):
        _tuple(row,13)
        if ok:_finite_vector(row,13)
        else:_need(all(item is None for item in row))


def _history_structure(history,minutes,window):
    _exact(history,ReleasePreparedHistory);_need(type(history.window) is int and history.window==window,'INVALID_PACKAGE')
    n=len(minutes.timestamps);_bools(history.valid,n);_tuple(history.invalid_reason,n)
    _value_rows(history.residual,history.valid,n)
    start=0;pending='warmup'
    for i,ok in enumerate(minutes.prepared_valid):
        reset=_reset(minutes.timestamps,minutes.segment_ordinals,i)
        if reset:start,pending=i,reset
        if not ok:
            _need(not history.valid[i] and _same(history.invalid_reason[i],'invalid_input'))
            start,pending=i+1,'invalid_input'
        elif i-start<window:_need(not history.valid[i] and _same(history.invalid_reason[i],pending))
        elif history.valid[i]:_need(history.invalid_reason[i] is None)
        else:
            _need(_same(history.invalid_reason[i],'nonfinite_history'))
            start,pending=i+1,'nonfinite_history'


def _validate_content(context,state,minutes,labels):
    for value,kind in ((context,ReleaseInputContext),(state,ReleasePreprocessState),
            (minutes,ReleasePreparedMinutes),(labels,ReleaseInputLabels)):_exact(value,kind)
    _need(type(context.profile_id) is str and context.profile_id==_P and type(context.source_schema_id) is str
        and context.source_schema_id==_SOURCE,'INCOMPATIBLE_PACKAGE')
    _need(_same(context.source_authentication,_AUTH) and _same(context.time_basis,_TIME))
    _identity(context.upstream,ReleaseMinutePackageIdentity,_RAW);_config(context.configuration)
    _sha(context.configuration_sha256)
    _need(context.configuration_sha256==_config_sha(context.configuration),'INTEGRITY_MISMATCH')
    n=_int(context.minute_count,1,10000);times,ordinals,roles=_axis(context.segments)
    _need(n==len(times))
    _tuple(minutes.segment_ordinals,n)
    _need(all(type(index) is int and 0<=index<len(context.segments) for index in minutes.segment_ordinals),'INVALID_PACKAGE')
    _need(_same(minutes.timestamps,times) and _same(minutes.segment_ordinals,ordinals))
    for mask in (minutes.raw_valid,minutes.prepared_valid,minutes.common_valid):_bools(mask,n)
    _tuple(minutes.prepared_reason,n);_value_rows(minutes.current_values,minutes.prepared_valid,n)
    for raw,valid,reason in zip(minutes.raw_valid,minutes.prepared_valid,minutes.prepared_reason):
        _need(not valid or raw)
        expected=None if valid else 'source_invalid' if not raw else 'nonfinite_transform'
        _need(_same(reason,expected))
    _tuple(minutes.histories,2)
    for history,window in zip(minutes.histories,(15,30)):_history_structure(history,minutes,window)
    common=tuple(v and a and b for v,a,b in zip(minutes.prepared_valid,minutes.histories[0].valid,minutes.histories[1].valid))
    _need(_same(minutes.common_valid,common))
    _need(_same(labels.policies,_POLS),'INVALID_PACKAGE');_tuple(labels.label_kinds,n)
    for raw,row in zip(minutes.raw_valid,labels.label_kinds):
        _tuple(row,3);_need(all(type(kind) is str and kind in _KINDS for kind in row),'INVALID_PACKAGE')
        _need(raw or row==('unknown',)*3)
    _bools(labels.fit_mask,n)
    _need(type(labels.fit_indices) is tuple and all(type(index) is int and 0<=index<n for index in labels.fit_indices),'INVALID_PACKAGE')
    expected_mask=_fit_selection(context,minutes,labels.label_kinds)
    indices=tuple(i for i,ok in enumerate(expected_mask) if ok)
    _need(bool(indices) and _same(labels.fit_mask,expected_mask) and _same(labels.fit_indices,indices))
    _finite_vector(state.mean,13);_finite_vector(state.scale,13,positive=True)
    _int(state.n_samples_seen,1,n)
    _need(state.n_samples_seen==len(indices) and _same(state.fit_window,30)
        and _same(state.audit_fit_policy,context.configuration.audit_fit_policy))
    _sha(state.fit_mask_sha256);_sha(state.fit_rows_sha256)
    _need(state.fit_mask_sha256==_mask_sha(labels.fit_mask),'INTEGRITY_MISMATCH')
    _tuple(labels.qualification_masks,3)
    for qualification in labels.qualification_masks:
        _exact(qualification,ReleasePolicyQualification)
        _need(type(qualification.policy) is str and qualification.policy in _POLS,'INVALID_PACKAGE')
        for name in _QUAL:_bools(getattr(qualification,name),n)
    _need(_same(labels.qualification_masks,_qualifications(context,minutes,labels.label_kinds)))


def _context_doc(context):
    doc=_plain(context)
    doc['segments']=[dict(ordinal=i,**_plain(segment)) for i,segment in enumerate(context.segments)]
    return doc


def _encode_content(context,state,minutes,labels):
    """Validate logical content and derive identity without a placeholder/self hash."""
    _validate_content(context,state,minutes,labels)
    context_doc=_context_doc(context);context_sha=hashlib.sha256(_canonical(context_doc,65536)).hexdigest()
    envelope=dict(schema_version=1,profile_id=_P,context_sha256=context_sha)
    members=[];total=0
    def append(name,doc):
        nonlocal total
        payload=_canonical(doc,min(_LIMITS[name],PACKAGE_TOTAL_BYTE_LIMIT-total))
        members.append((name,payload));total+=len(payload);return payload
    state_payload=append('preprocess.json',dict(envelope,configuration_sha256=context.configuration_sha256,state=_plain(state)))
    inputs=_plain(minutes);inputs['histories']={str(h.window):_plain(h) for h in minutes.histories}
    append('inputs.json',dict(envelope,preprocess=_digest(state_payload),**inputs))
    label_doc=_plain(labels)
    label_doc['qualification_masks']={q.policy:{name:_plain(getattr(q,name)) for name in _QUAL} for q in labels.qualification_masks}
    append('labels.json',dict(envelope,**label_doc))
    manifest=append('manifest.json',dict(envelope,context=context_doc,members={name:_digest(payload) for name,payload in members}))
    append('COMPLETE.json',dict(schema_version=1,profile_id=_P,status='COMPLETE',manifest=_digest(manifest)))
    identity=ReleaseInputIdentity(_P,context_sha,hashlib.sha256(manifest).hexdigest(),len(manifest))
    return tuple(members),identity


def _snapshot(context,state,minutes,labels):
    _,identity=_encode_content(context,state,minutes,labels)
    return ReleasePreparedInputs(identity,context,state,minutes,labels,_report(identity))


def encode_release_input_package(saved: ReleasePreparedInputs) -> tuple[tuple[str,bytes],...]:
    _need(type(saved) is ReleasePreparedInputs,'INVALID_PACKAGE_ARGUMENTS')
    members,actual=_encode_content(saved.context,saved.preprocessing,saved.minutes,saved.labels)
    _need(_same(saved.identity,actual),'INTEGRITY_MISMATCH')
    _need(_same(saved.load_report,_report(actual)))
    return members


def _keys(doc,keys):
    _need(type(doc) is dict and all(type(key) is str for key in doc) and set(doc)==set(keys),'INVALID_PACKAGE')


def _array(value,n):
    _need(type(value) is list and len(value)==n,'INVALID_PACKAGE');return value


def _json_int(token):
    _need(token.isascii() and token.isdecimal() and len(token)<=8,'INVALID_PACKAGE');return int(token)


def _json_float(token):
    _need(len(token)<=32,'INVALID_PACKAGE');value=float(token)
    _need(math.isfinite(value),'INVALID_PACKAGE');return value


def _bad_constant(_):raise ReleaseInputPreparationError('INVALID_PACKAGE')


def _json_object(pairs):
    result={}
    for key,value in pairs:
        _need(key not in result,'INVALID_PACKAGE');result[key]=value
    return result


def _parse(payload,limit):
    try:
        doc=json.loads(payload.decode('utf-8'),parse_int=_json_int,parse_float=_json_float,
            parse_constant=_bad_constant,object_pairs_hook=_json_object)
        _need(_canonical(doc,limit)==payload,'INVALID_PACKAGE');return doc
    except ReleaseInputPreparationError:raise
    except (UnicodeError,TypeError,ValueError,OverflowError,RecursionError):raise ReleaseInputPreparationError('INVALID_PACKAGE') from None


def _header(doc,extra,*,bound=True):
    _keys(doc,('schema_version','profile_id',*(('context_sha256',) if bound else ()),*extra))
    _need(type(doc['schema_version']) is int and type(doc['profile_id']) is str,'INVALID_PACKAGE')
    _need(doc['schema_version']==1 and doc['profile_id']==_P,'INCOMPATIBLE_PACKAGE')
    if bound:_sha(doc['context_sha256'])


def _binding(ref,payload,limit):
    _keys(ref,('byte_count','sha256'));_int(ref['byte_count'],1,limit);_sha(ref['sha256'])
    _need(_same(ref,_digest(payload)),'INTEGRITY_MISMATCH')


def _stamp(value):
    _need(type(value) is str and _STAMP.fullmatch(value) is not None,'INVALID_PACKAGE')
    try:return datetime.fromisoformat(value)
    except ValueError:raise ReleaseInputPreparationError('INVALID_PACKAGE') from None


def _decode_context(doc):
    _keys(doc,tuple(f.name for f in fields(ReleaseInputContext)))
    raw_identity=doc['upstream'];_keys(raw_identity,tuple(f.name for f in fields(ReleaseInputIdentity)))
    _need(_same(raw_identity['profile_id'],_RAW),'INCOMPATIBLE_PACKAGE')
    _sha(raw_identity['context_sha256']);_sha(raw_identity['manifest_sha256']);_int(raw_identity['manifest_byte_count'],1,65536)
    upstream=ReleaseMinutePackageIdentity(**raw_identity)
    config_doc=doc['configuration'];_keys(config_doc,tuple(f.name for f in fields(ReleasePreparationConfig)))
    _need(type(config_doc['feature_names']) is list and type(config_doc['windows']) is list,'INVALID_PACKAGE')
    config=ReleasePreparationConfig(**dict(config_doc,feature_names=tuple(config_doc['feature_names']),windows=tuple(config_doc['windows'])))
    segments=[];raw_segments=doc['segments']
    _need(type(raw_segments) is list and 1<=len(raw_segments)<=7,'INVALID_PACKAGE')
    for i,segment in enumerate(raw_segments):
        _keys(segment,('ordinal','id','role','start','end'))
        _need(type(segment['ordinal']) is int and segment['ordinal']==i,'INVALID_PACKAGE')
        segments.append(ReleaseSegment(segment['id'],segment['role'],_stamp(segment['start']),_stamp(segment['end'])))
    return ReleaseInputContext(**dict(doc,upstream=upstream,configuration=config,segments=tuple(segments)))


def _decode_rows(rows,n):return tuple(tuple(_array(row,13)) for row in _array(rows,n))


def decode_release_input_package(members: dict[str,bytes]) -> ReleasePreparedInputs:
    _need(type(members) is dict and all(type(key) is str for key in members) and set(members)==set(PACKAGE_MEMBER_NAMES)
        and all(type(payload) is bytes for payload in members.values()),'INVALID_PACKAGE_ARGUMENTS')
    _need(all(len(members[name])<=limit for name,limit in PACKAGE_MEMBER_BYTE_LIMITS)
        and sum(map(len,members.values()))<=PACKAGE_TOTAL_BYTE_LIMIT,'RESOURCE_LIMIT')
    complete=_parse(members['COMPLETE.json'],4096);_header(complete,('status','manifest'),bound=False)
    _need(_same(complete['status'],'COMPLETE'),'INVALID_PACKAGE');_binding(complete['manifest'],members['manifest.json'],65536)
    manifest=_parse(members['manifest.json'],65536);_header(manifest,('context','members'))
    _keys(manifest['members'],PACKAGE_MEMBER_NAMES[:3])
    for name in PACKAGE_MEMBER_NAMES[:3]:_binding(manifest['members'][name],members[name],_LIMITS[name])
    context_doc=manifest['context'];context=_decode_context(context_doc)
    context_sha=hashlib.sha256(_canonical(context_doc,65536)).hexdigest()
    _need(manifest['context_sha256']==context_sha,'INTEGRITY_MISMATCH')
    n=_int(context.minute_count,1,10000)
    state_doc=_parse(members['preprocess.json'],16384);_header(state_doc,('configuration_sha256','state'))
    inputs=_parse(members['inputs.json'],16777216);_header(inputs,('preprocess',*(f.name for f in fields(ReleasePreparedMinutes))))
    label_doc=_parse(members['labels.json'],2097152);_header(label_doc,tuple(f.name for f in fields(ReleaseInputLabels)))
    for doc in (state_doc,inputs,label_doc):_need(doc['context_sha256']==context_sha,'INTEGRITY_MISMATCH')
    _need(_same(state_doc['configuration_sha256'],context.configuration_sha256),'INTEGRITY_MISMATCH')
    _binding(inputs['preprocess'],members['preprocess.json'],16384)
    state=state_doc['state'];_keys(state,tuple(f.name for f in fields(ReleasePreprocessState)))
    state=ReleasePreprocessState(**dict(state,mean=tuple(_array(state['mean'],13)),scale=tuple(_array(state['scale'],13))))
    _keys(inputs['histories'],('15','30'));histories=[]
    for window in (15,30):
        h=inputs['histories'][str(window)];_keys(h,tuple(f.name for f in fields(ReleasePreparedHistory)))
        histories.append(ReleasePreparedHistory(h['window'],_decode_rows(h['residual'],n),tuple(_array(h['valid'],n)),tuple(_array(h['invalid_reason'],n))))
    minutes=ReleasePreparedMinutes(tuple(_stamp(stamp) for stamp in _array(inputs['timestamps'],n)),
        tuple(_array(inputs['segment_ordinals'],n)),tuple(_array(inputs['raw_valid'],n)),_decode_rows(inputs['current_values'],n),
        tuple(_array(inputs['prepared_valid'],n)),tuple(_array(inputs['prepared_reason'],n)),tuple(histories),tuple(_array(inputs['common_valid'],n)))
    quals=label_doc['qualification_masks'];_keys(quals,_POLS);qualifications=[]
    for policy in _POLS:
        _keys(quals[policy],_QUAL)
        qualifications.append(ReleasePolicyQualification(policy,*(tuple(_array(quals[policy][name],n)) for name in _QUAL)))
    _need(type(label_doc['fit_indices']) is list,'INVALID_PACKAGE')
    labels=ReleaseInputLabels(tuple(_array(label_doc['policies'],3)),
        tuple(tuple(_array(row,3)) for row in _array(label_doc['label_kinds'],n)),tuple(_array(label_doc['fit_mask'],n)),
        tuple(label_doc['fit_indices']),tuple(qualifications))
    _validate_content(context,state,minutes,labels)
    identity=ReleaseInputIdentity(_P,context_sha,hashlib.sha256(members['manifest.json']).hexdigest(),len(members['manifest.json']))
    return ReleasePreparedInputs(identity,context,state,minutes,labels,_report(identity))


def _close(saved,replayed):
    if saved is None or replayed is None:return saved is replayed
    if type(saved) is not float or type(replayed) is not float or not math.isfinite(saved) or not math.isfinite(replayed):return False
    difference=abs(saved-replayed)
    return math.isfinite(difference) and difference<=1e-12+1e-12*abs(replayed)


def _close_rows(saved,replayed):
    return len(saved)==len(replayed) and all(len(a)==len(b) and all(_close(x,y) for x,y in zip(a,b)) for a,b in zip(saved,replayed))


def verify_release_input_derivation(upstream: ReleaseMinutePackage,saved: ReleasePreparedInputs) -> ReleaseInputReplayReport:
    upstream=_bind_upstream(upstream);encode_release_input_package(saved)
    _need(_same(upstream.identity,saved.context.upstream),'UPSTREAM_IDENTITY_MISMATCH')
    raw=upstream.minutes;m=saved.minutes;state=saved.preprocessing
    _need(_same(upstream.segments,saved.context.segments) and _same(raw.timestamps,m.timestamps)
        and _same(raw.source_valid,m.raw_valid) and _same(raw.label_kinds,saved.labels.label_kinds),'DERIVATION_MISMATCH')
    mask=_fit_selection(saved.context,m,raw.label_kinds)
    _need(_same(mask,saved.labels.fit_mask) and _rows_sha(raw,saved.labels.fit_indices)==state.fit_rows_sha256,'DERIVATION_MISMATCH')
    values,valid,reasons=_transform(raw,state)
    _need(_same(valid,m.prepared_valid) and _same(reasons,m.prepared_reason) and _close_rows(m.current_values,values),'DERIVATION_MISMATCH')
    histories=tuple(_history(m.timestamps,m.segment_ordinals,values,valid,w,saved.context.configuration.epsilon) for w in (15,30))
    for actual,expected in zip(m.histories,histories):
        _need(_same(actual.valid,expected.valid) and _same(actual.invalid_reason,expected.invalid_reason)
            and _close_rows(actual.residual,expected.residual),'DERIVATION_MISMATCH')
    # Exact mask relationships were already derived from the exact replayed flags
    # by shared content validation; no train-statistics estimation happens here.
    checks=ReleaseReplayChecks(*('MATCHED',)*6,'NOT_REESTIMATED',_AUTH)
    tolerance=ReleaseReplayTolerance(1e-12,1e-12,'REPLAYED')
    return ReleaseInputReplayReport(_V,'MATCHED','SAVED_PARAMETER_DERIVATION_REPLAY',upstream.identity,
        saved.identity,saved.context.minute_count,state.n_samples_seen,checks,tolerance)
