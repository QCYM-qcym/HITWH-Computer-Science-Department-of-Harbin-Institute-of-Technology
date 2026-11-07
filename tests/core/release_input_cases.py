"""Small artificial value objects and named mutations, never mathematical oracles.

No import-time calculation. Maximum shapes are opt-in, never pytest fixtures.
"""
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json


def make_upstream(*, lengths=(48,40,40,48), roles=('train','validation','calibration','test'),
                  label_overrides=None, value_overrides=None, invalid_indices=(), continuous=False):
    """Create at most 240 synthetic minutes directly, not from a data file."""
    from traffic_anomaly._release_minutes import (ReleaseSegment,ReleaseMinuteResult,ReleaseBucketCounts,
        REASON_CODES,PROTOCOL_CHANNELS,ELIGIBLE_CHANNELS,LABEL_ANOMALIES)
    from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
    from traffic_anomaly.release_minute_contract import encode_release_minute_package,decode_release_minute_package
    if not 1<=sum(lengths)<=240 or len(lengths)!=len(roles):raise ValueError('bounded_artificial_axis_required')
    label_overrides=label_overrides or {};value_overrides=value_overrides or {}
    segments=[];times=[];ids=[];role_axis=[];values=[];valid=[];labels=[];buckets=[]
    epoch=datetime(2026,1,1);cursor=epoch
    def pairs(names,amount=0):return tuple((key,amount if key=='tcp' else 0) for key in names)
    for j,(length,role) in enumerate(zip(lengths,roles)):
        start=cursor if continuous else epoch+timedelta(hours=j)
        end=start+timedelta(minutes=length);cursor=end
        segment=ReleaseSegment(f'artificial-{j}',role,start,end);segments.append(segment)
        for local in range(length):
            i=len(times);p=float(1+local%3);ok=i not in invalid_indices
            label=label_overrides.get(i,('normal',)*3) if ok else ('unknown',)*3
            row=value_overrides.get(i,(1.,p,1.,10*p,10.,1.,0.,0.,0.,p,p,p,0.)) if ok else (None,)*13
            reasons=tuple((key,int(not ok) if key=='empty_unconfirmed' else 0) for key in REASON_CODES)
            kinds=tuple(tuple(int(ok and value==kind) for kind in ('normal','attack','unknown')) for value in label)
            unknown=ok and label==('unknown',)*3
            anomalies=tuple((key,int(unknown and key=='unknown_label')) for key in LABEL_ANOMALIES)
            buckets.append(ReleaseBucketCounts(int(ok),int(ok),0,reasons,pairs(PROTOCOL_CHANNELS,int(ok)),
                pairs(ELIGIBLE_CHANNELS,int(ok)),kinds,anomalies,ok and label==('attack',)*3,
                ok and label==('unknown','normal','attack'),0))
            times.append(start+timedelta(minutes=local));ids.append(segment.id);role_axis.append(role)
            values.append(row);valid.append(ok);labels.append(label)
    count=sum(valid)
    global_kinds=tuple(tuple(sum(b.label_kind_counts[p][k] for b in buckets) for k in range(3)) for p in range(3))
    global_anomalies=tuple((key,sum(dict(b.label_anomaly_counts)[key] for b in buckets)) for key in LABEL_ANOMALIES)
    result=ReleaseMinuteResult('c17-release-91-v1',(1,),('a'*64,),'NOT_AUTHENTICATED',
        'SOURCE_WALL_CLOCK_COMPLETION_PROXY',G13U_FEATURE_NAMES,tuple(times),tuple(ids),tuple(role_axis),
        tuple(values),tuple(valid),tuple(labels),tuple(buckets),count,count,0,0,0,0,
        tuple((key,0) for key in REASON_CODES),pairs(PROTOCOL_CHANNELS,count),pairs(ELIGIBLE_CHANNELS,count),
        global_kinds,global_anomalies)
    return decode_release_minute_package(dict(encode_release_minute_package(result,tuple(segments))))


def make_config(*, policy='P_U', epsilon=1e-6):
    from traffic_anomaly.release_inputs import ReleasePreparationConfig
    from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
    return ReleasePreparationConfig(1,'c17-release-log1p-mad-input-rules-v1',G13U_FEATURE_NAMES,
                                    (15,30),30,epsilon,policy,'AUDIT_ONLY')


def prepared_case():
    from traffic_anomaly.release_inputs import prepare_release_inputs
    upstream=make_upstream()
    return upstream,prepare_release_inputs(upstream,make_config())


def canonical(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')+b'\n'


def digest(payload):return {'byte_count':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}


def documents(members):return {name:json.loads(payload) for name,payload in members.items()}


def reseal(docs):
    """Rebind bytes, not semantic mask/row claims; never produces expected numerics."""
    context=docs['manifest.json']['context']
    config_sha=hashlib.sha256(canonical(context['configuration'])).hexdigest()
    context['configuration_sha256']=config_sha;docs['preprocess.json']['configuration_sha256']=config_sha
    context_sha=hashlib.sha256(canonical(context)).hexdigest()
    docs['manifest.json']['context_sha256']=context_sha;members={}
    for name in ('preprocess.json','inputs.json','labels.json'):
        docs[name]['context_sha256']=context_sha
        if name=='inputs.json':docs[name]['preprocess']=digest(members['preprocess.json'])
        members[name]=canonical(docs[name])
    docs['manifest.json']['members']={name:digest(payload) for name,payload in members.items()}
    members['manifest.json']=canonical(docs['manifest.json'])
    docs['COMPLETE.json']['manifest']=digest(members['manifest.json'])
    members['COMPLETE.json']=canonical(docs['COMPLETE.json'])
    return members


def replace_member(members,name,payload):
    result=dict(members);result[name]=payload
    manifest=json.loads(result['manifest.json'])
    if name=='preprocess.json':
        inputs=json.loads(result['inputs.json']);inputs['preprocess']=digest(payload)
        result['inputs.json']=canonical(inputs);manifest['members']['inputs.json']=digest(result['inputs.json'])
    if name in ('preprocess.json','inputs.json','labels.json'):
        manifest['members'][name]=digest(payload);result['manifest.json']=canonical(manifest)
    if name!='COMPLETE.json':
        complete=json.loads(result['COMPLETE.json']);complete['manifest']=digest(result['manifest.json'])
        result['COMPLETE.json']=canonical(complete)
    return result


def exercise_maximum_shape(case_name: str) -> dict[str,int]:
    """A9 codec-only probe, for the controller's separate bounded process ONLY.

    No prepare, fit, logarithm, median, MAD, CSV, path or model operation. Values
    are deliberate structural claims and do not constitute replay evidence.
    """
    if type(case_name) is not str or case_name not in ('M1','M2','M3'):raise ValueError('unknown_maximum_case')
    from traffic_anomaly import release_inputs as m
    from traffic_anomaly._release_minutes import (ReleaseSegment,ReleaseMinuteResult,ReleaseBucketCounts,
        REASON_CODES,PROTOCOL_CHANNELS,ELIGIBLE_CHANNELS,LABEL_ANOMALIES)
    from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
    from traffic_anomaly.release_minute_contract import encode_release_minute_package,decode_release_minute_package
    lengths=(31,1661,1661,1661,1661,1661,1664) if case_name=='M3' else (10000,)
    roles=('train','validation','validation','calibration','calibration','test','test') if case_name=='M3' else ('train',)
    segments=[];times=[];ordinals=[];local_indices=[];role_axis=[];ids=[];cursor=datetime(2026,1,1)
    for j,(length,role) in enumerate(zip(lengths,roles)):
        name='\U0001f642'*127+str(j) if case_name=='M3' else '\U0001f642'*128
        segment=ReleaseSegment(name,role,cursor,cursor+timedelta(minutes=length));segments.append(segment)
        for local in range(length):
            times.append(cursor+timedelta(minutes=local));ordinals.append(j);local_indices.append(local)
            role_axis.append(role);ids.append(name)
        cursor=segment.end
    times=tuple(times);ordinals=tuple(ordinals);segments=tuple(segments)
    source_valid=tuple(not(case_name=='M3' and j>0 and local==40) for j,local in zip(ordinals,local_indices))
    raw_row=(1.,1.,1.,10.,10.,1.,0.,0.,0.,1.,1.,1.,0.)
    def pairs(names,count):return tuple((name,count if name=='tcp' else 0) for name in names)
    buckets=[]
    for valid in source_valid:
        count=int(valid)
        buckets.append(ReleaseBucketCounts(count,count,0,tuple((name,int(not valid) if name=='empty_unconfirmed' else 0) for name in REASON_CODES),
            pairs(PROTOCOL_CHANNELS,count),pairs(ELIGIBLE_CHANNELS,count),((count,0,0),)*3,
            tuple((name,0) for name in LABEL_ANOMALIES),False,False,0))
    count=sum(source_valid);sources=5 if case_name=='M3' else 1
    raw=ReleaseMinuteResult('c17-release-91-v1',(1,)*sources,('a'*64,)*sources,'NOT_AUTHENTICATED',
        'SOURCE_WALL_CLOCK_COMPLETION_PROXY',G13U_FEATURE_NAMES,times,tuple(ids),tuple(role_axis),
        tuple(raw_row if valid else (None,)*13 for valid in source_valid),source_valid,
        tuple(('normal',)*3 if valid else ('unknown',)*3 for valid in source_valid),tuple(buckets),count,count,0,0,0,0,
        tuple((name,0) for name in REASON_CODES),pairs(PROTOCOL_CHANNELS,count),pairs(ELIGIBLE_CHANNELS,count),
        ((count,0,0),)*3,tuple((name,0) for name in LABEL_ANOMALIES))
    upstream=decode_release_minute_package(dict(encode_release_minute_package(raw,segments)))
    config=make_config();context=m.ReleaseInputContext('c17-release-prepared-input-package-v1','c17-release-91-v1',
        'NOT_AUTHENTICATED','SOURCE_WALL_CLOCK_COMPLETION_PROXY',upstream.identity,config,m._config_sha(config),segments,10000)
    valid=tuple(source and not(case_name=='M3' and j>0 and local==80) for source,j,local in zip(source_valid,ordinals,local_indices))
    pattern=(1.7976931348623157e308,-1.7976931348623157e308,1.2345678901234567,-1.2345678901234567,0.,-0.)
    row=tuple(pattern[i%6] for i in range(13)) if case_name=='M1' else (0.,)*13
    values=tuple(row if ok else (None,)*13 for ok in valid)
    reasons=tuple(None if ok else 'source_invalid' if not source else 'nonfinite_transform' for source,ok in zip(source_valid,valid))
    histories=[]
    for window in (15,30):
        start=0;pending='warmup';residual=[];flags=[];why=[]
        for i,ok in enumerate(valid):
            if i and ordinals[i]!=ordinals[i-1]:start,pending=i,'boundary'
            success=False
            if not ok:reason='invalid_input';start,pending=i+1,reason
            elif i-start<window:reason=pending
            elif case_name=='M2' or (case_name=='M3' and ordinals[i]>0 and local_indices[i]==120):
                reason='nonfinite_history';start,pending=i+1,reason
            else:success=True;reason=None
            residual.append(row if success else (None,)*13);flags.append(success);why.append(reason)
        histories.append(m.ReleasePreparedHistory(window,tuple(residual),tuple(flags),tuple(why)))
    common=tuple(ok and a and b for ok,a,b in zip(valid,histories[0].valid,histories[1].valid))
    minutes=m.ReleasePreparedMinutes(times,ordinals,source_valid,values,valid,reasons,tuple(histories),common)
    mask=m._fit_selection(context,minutes,raw.label_kinds);indices=tuple(i for i,ok in enumerate(mask) if ok)
    assert len(indices)==(1 if case_name=='M3' else 9970)
    state=m.ReleasePreprocessState((0.,)*13,(1.,)*13,len(indices),30,'P_U',m._mask_sha(mask),m._rows_sha(raw,indices))
    labels=m.ReleaseInputLabels(('P_U','P_B','P_A'),raw.label_kinds,mask,indices,m._qualifications(context,minutes,raw.label_kinds))
    saved=m._snapshot(context,state,minutes,labels)
    encoded=m.encode_release_input_package(saved);loaded=m.decode_release_input_package(dict(encoded))
    assert loaded==saved and m.encode_release_input_package(loaded)==encoded
    assert loaded.load_report.transform_history_replay=='NOT_PERFORMED'
    if case_name=='M2':assert not any(common) and not any(loaded.minutes.histories[0].valid) and not any(loaded.minutes.histories[1].valid)
    result={name:len(payload) for name,payload in encoded};result['total_bytes']=sum(result.values())
    assert set(result)==set(m.PACKAGE_MEMBER_NAMES)|{'total_bytes'} and all(type(n) is int for n in result.values())
    return result
