"""Raw13 package structure and necessary relationships, not source authentication."""
from collections import UserDict
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path

import pytest

from traffic_anomaly._release_minutes import ReleaseSegment
from .release_minute_package_cases import make_result, plain_members, documents, reseal, replace_member, canonical

NAMES=('minutes.json','labels.json','diagnostics.json','manifest.json','COMPLETE.json')


def api():return importlib.import_module('traffic_anomaly.release_minute_contract')


@pytest.fixture
def sample():
    segments=(ReleaseSegment('人工段','train',datetime(2026,1,1),datetime(2026,1,1,0,4)),)
    rows=(({'id':'1','Timestamp':'2026-01-01 00:00:00.000000','Flow Duration':'1000000'},
        {'id':'2','Timestamp':'2026-01-01 00:01:00.000000','Label':'FTP-Patator - Attempted','Attempted Category':'0'},
        {'id':'3','Timestamp':'2026-01-01 00:02:00.000000','Label':'unrecognized-artificial'}),)
    return make_result(rows,segments),segments


def reject(call,code=None):
    with pytest.raises(api().ReleaseMinutePackageError) as caught:call()
    assert str(caught.value)==caught.value.code
    if code is not None:assert caught.value.code==code
    assert '/' not in str(caught.value) and '\\' not in str(caught.value)
    return caught.value.code


def test_protocol_and_five_members_roundtrip(sample):
    result,segments=sample;m=api()
    encoded=m.encode_release_minute_package(result,segments)
    assert type(encoded) is tuple and tuple(name for name,_ in encoded)==NAMES
    assert all(type(pair) is tuple and type(pair[1]) is bytes and pair[1].endswith(b'\n') and not pair[1].endswith(b'\n\n') for pair in encoded)
    members=dict(encoded);package=m.decode_release_minute_package(members)
    assert package.minutes==result and package.segments==segments
    assert package.scope=='PACKAGE_INTERNAL_CONSISTENCY_ONLY'
    assert package.identity.profile_id=='c17-release-minute-package-v1'
    assert type(package.identity.manifest_byte_count) is int
    assert package.identity.manifest_byte_count==len(members['manifest.json'])
    assert package.minutes.source_authentication=='NOT_AUTHENTICATED'
    assert package.minutes.time_basis=='SOURCE_WALL_CLOCK_COMPLETION_PROXY'
    minute_doc=json.loads(members['minutes.json'])
    assert set(minute_doc)=={'schema_version','profile_id','context_sha256','timestamps','segment_ordinals','source_valid','values'}
    assert minute_doc['values'][3]==[None]*13
    expected=json.loads((Path(__file__).parents[1]/'fixtures/release-minute-protocol-v1.json').read_bytes())
    assert json.loads(members['manifest.json'])['context']['protocol']==expected


def test_duration_constant_11_digits_roundtrips(sample):
    result,segments=sample;members=plain_members(result,segments)
    assert b'86400000000' in members['manifest.json']
    assert api().decode_release_minute_package(members).minutes==result


def test_rejects_12_digit_integer_token(sample):
    docs=documents(plain_members(*sample))
    docs['manifest.json']['context']['protocol']['duration_max_us']=100000000000
    reject(lambda:api().decode_release_minute_package(reseal(docs)))


def test_frozen_result_has_no_aliases(sample):
    members=plain_members(*sample);package=api().decode_release_minute_package(members)
    original=package.minutes;members.clear()
    assert package.minutes==original
    with pytest.raises((FrozenInstanceError,AttributeError)):package.scope='changed'
    with pytest.raises((FrozenInstanceError,AttributeError)):package.identity.manifest_byte_count=0
    with pytest.raises(TypeError):package.minutes.values[0][0]=1.
    reject(lambda:api().encode_release_minute_package(replace(original,values=list(original.values)),sample[1]))


def test_pure_codec_opens_no_paths(sample,monkeypatch):
    m=api();result,segments=sample;attempts=[]
    def blocked(*a,**k):attempts.append(True);raise AssertionError('codec opened a path')
    monkeypatch.setattr('builtins.open',blocked);monkeypatch.setattr(Path,'open',blocked)
    members=dict(m.encode_release_minute_package(result,segments))
    assert m.decode_release_minute_package(members).minutes==result
    assert attempts==[]


@pytest.mark.parametrize('kind',['mapping','subclass','nonstring-key','bytearray','missing','extra'],ids=['mapping','dict-subclass','key-type','mutable-bytes','missing','sixth'])
def test_rejects_custom_mapping_and_bool_scalars(sample,kind):
    members=plain_members(*sample)
    class Subdict(dict):pass
    if kind=='mapping':members=UserDict(members)
    elif kind=='subclass':members=Subdict(members)
    elif kind=='nonstring-key':members[True]=members.pop('minutes.json')
    elif kind=='bytearray':members['minutes.json']=bytearray(members['minutes.json'])
    elif kind=='missing':members.pop('COMPLETE.json')
    else:members['extra.json']=b'{}\n'
    reject(lambda:api().decode_release_minute_package(members),'INVALID_PACKAGE_ARGUMENTS')


@pytest.mark.parametrize('member',NAMES,ids=['minutes','labels','diagnostics','manifest','complete'])
@pytest.mark.parametrize('kind',['bool-version','unknown-version','unknown-profile','extra-key'],ids=['bool','version','profile','key'])
def test_every_document_has_strict_header_and_keys(sample,member,kind):
    docs=documents(plain_members(*sample))
    if kind=='bool-version':docs[member]['schema_version']=True
    elif kind=='unknown-version':docs[member]['schema_version']=2
    elif kind=='unknown-profile':docs[member]['profile_id']='unknown'
    else:docs[member]['unexpected']=True
    reject(lambda:api().decode_release_minute_package(reseal(docs)))


@pytest.mark.parametrize('kind',['duplicate','bom','trailing-space','two-documents','invalid-utf8','nan','infinity'],ids=['duplicate','bom','whitespace','multidoc','utf8','nan','inf'])
def test_rejects_duplicate_keys_noncanonical_and_unknown_version(sample,kind):
    members=plain_members(*sample);payload=members['minutes.json']
    if kind=='duplicate':payload=payload.replace(b'"schema_version":1',b'"schema_version":1,"schema_version":1')
    elif kind=='bom':payload=b'\xef\xbb\xbf'+payload
    elif kind=='trailing-space':payload+=b' '
    elif kind=='two-documents':payload+=b'{}\n'
    elif kind=='invalid-utf8':payload=b'\xff'+payload
    elif kind=='nan':payload=payload.replace(b'1.0',b'NaN',1)
    else:payload=payload.replace(b'1.0',b'Infinity',1)
    assert payload!=members['minutes.json']
    reject(lambda:api().decode_release_minute_package(replace_member(members,'minutes.json',payload)))


def test_schema_error_class_never_exposes_arbitrary_input():
    m=api();error=m.ReleaseMinutePackageError('private-path/label-data')
    assert str(error)==error.code and '/' not in str(error)


@pytest.mark.parametrize('field,value',[('raw_records',True),('source_bytes',(True,)),('source_sha256',('A'*64,)),('schema_id','unknown')],ids=['bool-count','bool-source','uppercase-sha','schema'])
def test_encode_refuses_untyped_input_fields(sample,field,value):
    result,segments=sample
    reject(lambda:api().encode_release_minute_package(replace(result,**{field:value}),segments))


AXIS_CASES=['duplicate-time','reverse-time','seconds','timezone','short-axis','short-width','long-width',
    'ordinal','missing-valid','bool-mask','valid-null','invalid-zero','invalid-partial','count-value','channel-value',
    'fraction-packet','duration-order','duration-cap','no-backward-cap','no-backward-fraction','minute-label',
    'role','empty-id','long-id','control-id','feature-order','source-ordinal','source-size-type','source-hash']


@pytest.mark.parametrize('kind',AXIS_CASES,ids=AXIS_CASES)
def test_rejects_axis_mask_and_feature_contradictions(sample,kind):
    docs=documents(plain_members(*sample));minutes=docs['minutes.json'];context=docs['manifest.json']['context']
    if kind=='duplicate-time':minutes['timestamps'][1]=minutes['timestamps'][0]
    elif kind=='reverse-time':minutes['timestamps'][0],minutes['timestamps'][1]=minutes['timestamps'][1],minutes['timestamps'][0]
    elif kind=='seconds':minutes['timestamps'][0]='2026-01-01T00:00:01'
    elif kind=='timezone':minutes['timestamps'][0]+='Z'
    elif kind=='short-axis':minutes['timestamps'].pop()
    elif kind=='short-width':minutes['values'][0].pop()
    elif kind=='long-width':minutes['values'][0].append(1.)
    elif kind=='ordinal':minutes['segment_ordinals'][0]=1
    elif kind=='missing-valid':minutes['source_valid'].pop()
    elif kind=='bool-mask':minutes['source_valid'][0]=1
    elif kind=='valid-null':minutes['values'][0][0]=None
    elif kind=='invalid-zero':minutes['values'][3]=[0.]*13
    elif kind=='invalid-partial':minutes['values'][3][0]=0.
    elif kind=='count-value':minutes['values'][0][0]=2.
    elif kind=='channel-value':minutes['values'][0][6]=1.
    elif kind=='fraction-packet':minutes['values'][0][1]=2.5
    elif kind=='duration-order':minutes['values'][0][10]=2.
    elif kind=='duration-cap':minutes['values'][0][9]=86401.
    elif kind=='no-backward-cap':minutes['values'][0][12]=2.
    elif kind=='no-backward-fraction':minutes['values'][0][12]=0.5
    elif kind=='minute-label':docs['labels.json']['label_kinds'][1]=['normal']*3
    elif kind=='role':context['segments'][0]['role']='future'
    elif kind=='empty-id':context['segments'][0]['id']=''
    elif kind=='long-id':context['segments'][0]['id']='x'*129
    elif kind=='control-id':context['segments'][0]['id']='a\x7fb'
    elif kind=='feature-order':context['protocol']['feature_names'].reverse()
    elif kind=='source-ordinal':context['sources'][0]['ordinal']=True
    elif kind=='source-size-type':context['sources'][0]['byte_count']=1.
    else:context['sources'][0]['sha256']='A'*64
    reject(lambda:api().decode_release_minute_package(reseal(docs)))


@pytest.mark.parametrize('value',[0,-1.,-0.,float('nan'),float('inf')],ids=['int','negative','negative-zero','nan','inf'])
def test_valid_values_are_exact_nonnegative_finite_float(sample,value):
    result,segments=sample;row=list(result.values[0]);row[1]=value
    result=replace(result,values=(tuple(row),*result.values[1:]))
    reject(lambda:api().encode_release_minute_package(result,segments))


@pytest.mark.parametrize('kind',['surrogate','wrong-result-id','wrong-result-role','tz-segment','reversed','nonminute'],ids=['surrogate','id-owner','role-owner','tz','reversed','nonminute'])
def test_segment_and_result_scalar_types_are_checked_before_encoding(sample,kind):
    result,segments=sample;segment=segments[0]
    if kind=='surrogate':segments=(replace(segment,id='\ud800'),)
    elif kind=='wrong-result-id':result=replace(result,segment_ids=('wrong',)*4)
    elif kind=='wrong-result-role':result=replace(result,roles=('test',)*4)
    elif kind=='tz-segment':segments=(replace(segment,start=segment.start.replace(tzinfo=timezone.utc)),)
    elif kind=='reversed':segments=(replace(segment,end=segment.start),)
    else:segments=(replace(segment,start=segment.start+timedelta(seconds=1)),)
    reject(lambda:api().encode_release_minute_package(result,segments))


def test_keeps_eligible_records_when_whole_minute_invalid():
    segments=(ReleaseSegment('tainted','train',datetime(2026,1,1),datetime(2026,1,1,0,4)),)
    result=make_result((({'id':'1','Timestamp':'2026-01-01 00:00:00.000000'},
        {'id':'2','Timestamp':'invalid-time'}),),segments)
    actual=api().decode_release_minute_package(plain_members(result,segments)).minutes
    assert (actual.raw_records,actual.eligible_records,actual.excluded_records,actual.unplaced_invalid_rows)==(2,1,1,1)
    assert actual.source_valid==(False,False,False,False)
    assert all(row==(None,)*13 for row in actual.values)
    assert actual.bucket_counts[0].eligible_records==1
    assert dict(actual.reason_counts)['unplaced_invalid_row']==1
    assert [dict(b.reason_counts)['unplaced_invalid_row'] for b in actual.bucket_counts]==[1]*4
    assert [dict(b.reason_counts)['empty_unconfirmed'] for b in actual.bucket_counts]==[0,1,1,1]


def test_empty_sources_with_headers_keep_identity_order_and_empty_buckets():
    segments=(ReleaseSegment('empty','train',datetime(2026,1,1),datetime(2026,1,1,0,2)),)
    result=make_result(((),()),segments)
    package=api().decode_release_minute_package(plain_members(result,segments))
    assert package.minutes.raw_records==0
    assert len(package.minutes.source_sha256)==2 and len(set(package.minutes.source_sha256))==1
    assert dict(package.minutes.reason_counts)['empty_unconfirmed']==0
    assert all(dict(b.reason_counts)['empty_unconfirmed']==1 for b in package.minutes.bucket_counts)


GLOBAL_CASES=['raw','eligible','excluded','outside','unplaced','raw-protocol','eligible-protocol',
    'outside-reason','unplaced-reason','global-empty','invalid-time-domain','assigned-global','cross-global',
    'excluded-protocol','duplicate-groups','label-normal','label-anomaly','policy-T','policy-unknown',
    'bucket-raw','bucket-eligible','bucket-excluded','bucket-raw-protocol','bucket-eligible-protocol',
    'bucket-outside','bucket-unplaced','bucket-empty','bucket-duration','bucket-assigned','unused-cap',
    'bucket-label-sum','bucket-anomaly','attempted-flag-type','attempted-flag','valid-iff-reasons']


@pytest.mark.parametrize('kind',GLOBAL_CASES,ids=GLOBAL_CASES)
def test_rejects_record_protocol_and_label_conservation_mismatch(sample,kind):
    docs=documents(plain_members(*sample));diag=docs['diagnostics.json'];g=diag['global'];b=diag['buckets'][0];labels=docs['labels.json']
    if kind in ('raw','eligible','excluded','outside','unplaced'):
        name={'raw':'raw_records','eligible':'eligible_records','excluded':'excluded_records','outside':'outside_records','unplaced':'unplaced_invalid_rows'}[kind];g[name]+=1
    elif kind=='raw-protocol':g['raw_protocol_counts'][0]+=1
    elif kind=='eligible-protocol':g['eligible_protocol_counts'][0]+=1
    elif kind=='outside-reason':g['reason_counts'][10]=1
    elif kind=='unplaced-reason':g['reason_counts'][11]=1
    elif kind=='global-empty':g['reason_counts'][12]=1
    elif kind=='invalid-time-domain':g['reason_counts'][7]=1
    elif kind=='assigned-global':g['reason_counts'][2]=1
    elif kind=='cross-global':g['reason_counts'][9]=1
    elif kind=='excluded-protocol':g['reason_counts'][1]=1
    elif kind=='duplicate-groups':g['duplicate_groups']=1
    elif kind=='label-normal':labels['global_label_kind_counts'][0][0]+=1
    elif kind=='label-anomaly':labels['global_label_anomaly_counts'][0]=0
    elif kind=='policy-T':labels['bucket_label_kind_counts'][1][1]=[0,1,0]
    elif kind=='policy-unknown':labels['global_label_kind_counts'][1][2]=0
    elif kind=='bucket-raw':b['raw_records']+=1
    elif kind=='bucket-eligible':b['eligible_records']+=1
    elif kind=='bucket-excluded':b['excluded_records']+=1
    elif kind=='bucket-raw-protocol':b['raw_protocol_counts'][0]=0;b['raw_protocol_counts'][1]=1
    elif kind=='bucket-eligible-protocol':b['eligible_protocol_counts'][0]=0;b['eligible_protocol_counts'][1]=1
    elif kind=='bucket-outside':b['reason_counts'][10]=1
    elif kind=='bucket-unplaced':b['reason_counts'][11]=1
    elif kind=='bucket-empty':b['reason_counts'][12]=1
    elif kind=='bucket-duration':b['reason_counts'][0]=1
    elif kind=='bucket-assigned':b['reason_counts'][2]=1
    elif kind=='unused-cap':b['unused_field_issue_records']=2
    elif kind=='bucket-label-sum':labels['bucket_label_kind_counts'][0][0][0]=0
    elif kind=='bucket-anomaly':labels['bucket_label_anomaly_counts'][0][0]=2
    elif kind=='attempted-flag-type':labels['attempted_present'][0]=1
    elif kind=='attempted-flag':labels['attempted_present'][1]=False
    else:docs['minutes.json']['source_valid'][0]=False
    reject(lambda:api().decode_release_minute_package(reseal(docs)))


def test_overlap_reasons_duplicates_and_outside_descriptions_are_not_dropped():
    segments=(ReleaseSegment('overlap','train',datetime(2026,1,1),datetime(2026,1,1,0,2)),)
    repeated={'id':'1','Timestamp':'2026-01-01 00:00:00.000000'}
    rows=((repeated,{'id':'2','Timestamp':'2026-01-01 00:01:00.000000','Protocol':'4','Total Fwd Packet':'bad','Total Length of Bwd Packet':'bad'}),
          (dict(repeated),{'id':'3','Timestamp':'2026-01-01 00:08:00.000000','Label':'Portscan'}))
    result=make_result(rows,segments);actual=api().decode_release_minute_package(plain_members(result,segments)).minutes
    assert actual.duplicate_groups==1 and dict(actual.reason_counts)['duplicate_record']==2
    assert actual.outside_records==1
    assert sum(value for _,value in actual.bucket_counts[1].reason_counts)>actual.bucket_counts[1].excluded_records
    assert actual.label_kind_counts[0][1]==1


def test_unused_descriptor_and_reverse_flags_do_not_falsely_invalidate(sample):
    result,segments=sample;buckets=list(result.bucket_counts)
    buckets[0]=replace(buckets[0],unused_field_issue_records=1,definite_attack_present=True)
    changed=replace(result,bucket_counts=tuple(buckets))
    actual=api().decode_release_minute_package(plain_members(changed,segments)).minutes
    assert actual.source_valid[0] is True and actual.bucket_counts[0].definite_attack_present is True


def test_adjacent_segments_and_gaps_are_not_filled():
    segments=(ReleaseSegment('a','train',datetime(2026,1,1),datetime(2026,1,1,0,2)),
        ReleaseSegment('b','validation',datetime(2026,1,1,0,2),datetime(2026,1,1,0,4)),
        ReleaseSegment('c','test',datetime(2026,1,1,0,6),datetime(2026,1,1,0,8)))
    result=make_result((({'id':'1','Timestamp':'2026-01-01 00:06:00.000000'},),),segments)
    members=plain_members(result,segments);package=api().decode_release_minute_package(members)
    assert [stamp.minute for stamp in package.minutes.timestamps]==[0,1,2,3,6,7]
    assert package.minutes.segment_ids==('a','a','b','b','c','c')
    docs=documents(members);docs['minutes.json']['timestamps'][4]='2026-01-01T00:04:00'
    reject(lambda:api().decode_release_minute_package(reseal(docs)))
    reject(lambda:api().encode_release_minute_package(result,(segments[1],segments[0],segments[2])))


def test_binding_changes_need_all_members(sample):
    members=plain_members(*sample);docs=documents(members)
    docs['manifest.json']['context']['sources'][0]['sha256']='b'*64
    payload=canonical(docs['manifest.json'])
    reject(lambda:api().decode_release_minute_package(replace_member(members,'manifest.json',payload)),'INTEGRITY_MISMATCH')


def test_self_consistent_rewrite_has_new_identity_not_trust(sample):
    members=plain_members(*sample);before=api().decode_release_minute_package(members);docs=documents(members)
    docs['manifest.json']['context']['sources'][0]['sha256']='b'*64
    after=api().decode_release_minute_package(reseal(docs))
    assert before.identity!=after.identity
    assert after.minutes.source_authentication=='NOT_AUTHENTICATED'
    assert before.minutes.values==after.minutes.values


@pytest.mark.parametrize('member,limit',[(NAMES[0],8388608),(NAMES[1],8388608),(NAMES[2],8388608),(NAMES[3],65536),(NAMES[4],4096)],ids=['minutes','labels','diagnostics','manifest','complete'])
def test_member_and_total_limits_before_parse(sample,monkeypatch,member,limit):
    m=api();members=plain_members(*sample)
    over=dict(members);over[member]=b' '*(limit+1)
    with monkeypatch.context() as context:
        context.setattr(m.json,'loads',lambda *a,**k:pytest.fail('parsed before byte budget'))
        reject(lambda:m.decode_release_minute_package(over),'RESOURCE_LIMIT')
    exact=dict(members);exact[member]=b' '*limit
    assert reject(lambda:m.decode_release_minute_package(exact))!='RESOURCE_LIMIT'


def test_total_byte_limit_counts_all_five_members(sample,monkeypatch):
    m=api();members=plain_members(*sample)
    members['minutes.json']=b' '*8388608;members['labels.json']=b' '*8388608
    remaining=20971520-sum(len(payload) for name,payload in members.items() if name!='diagnostics.json')
    members['diagnostics.json']=b' '*(remaining+1)
    with monkeypatch.context() as context:
        context.setattr(m.json,'loads',lambda *a,**k:pytest.fail('parsed before total byte budget'))
        reject(lambda:m.decode_release_minute_package(members),'RESOURCE_LIMIT')
    members['diagnostics.json']=b' '*remaining
    assert reject(lambda:m.decode_release_minute_package(members))!='RESOURCE_LIMIT'


def _maximum_object(valid):
    """Finite value-domain probe; no 2.5 million CSV rows or source file I/O."""
    segments=[];start=datetime(2026,1,1)
    for i,role in enumerate(('train','train','validation','validation','calibration','calibration','test')):
        end=start+timedelta(minutes=1428 if i<6 else 1432)
        segments.append(ReleaseSegment(chr(0x1d11e+i)*128,role,start,end));start=end
    segments=tuple(segments)
    template=make_result(((),),segments)
    total=2500000;count=250 if valid else 0;unplaced=0 if valid else total
    reasons=tuple((key,unplaced if key=='unplaced_invalid_row' else int(not valid) if key=='empty_unconfirmed' else 0)
                  for key,_ in template.bucket_counts[0].reason_counts)
    global_reasons=tuple((key,unplaced if key in ('invalid_timestamp','unplaced_invalid_row') else 0)
                         for key,_ in template.reason_counts)
    def protocol(pairs,number):return tuple((key,number if key=='tcp' else 0) for key,_ in pairs)
    bucket=replace(template.bucket_counts[0],raw_records=count,eligible_records=count,excluded_records=0,
        reason_counts=reasons,raw_protocol_counts=protocol(template.raw_protocol_counts,count),
        eligible_protocol_counts=protocol(template.eligible_protocol_counts,count),
        label_kind_counts=((count,0,0),)*3,unused_field_issue_records=count)
    large=float.fromhex('0x1.fffffffffffffp+1023')
    row=(250.,large,large,large,large,250.,0.,0.,0.,86400.,86400.,86400.,250.) if valid else (None,)*13
    result=replace(template,source_bytes=(429496729,429496729,429496729,429496729,429496732),
        source_sha256=tuple(str(i)*64 for i in range(5)),
        values=(row,)*10000,source_valid=(valid,)*10000,
        label_kinds=(('normal',)*3 if valid else ('unknown',)*3,)*10000,bucket_counts=(bucket,)*10000,
        raw_records=total,eligible_records=total if valid else 0,excluded_records=0 if valid else total,
        unplaced_invalid_rows=unplaced,reason_counts=global_reasons,
        raw_protocol_counts=protocol(template.raw_protocol_counts,total),
        eligible_protocol_counts=protocol(template.eligible_protocol_counts,total if valid else 0),
        label_kind_counts=((total,0,0),)*3)
    return result,segments


@pytest.mark.parametrize('valid',[True,False],ids=['valid-10000','unplaced-10000'])
def test_maximum_legal_shapes_and_bytes(valid):
    result,segments=_maximum_object(valid);m=api()
    encoded=m.encode_release_minute_package(result,segments)
    sizes={name:len(payload) for name,payload in encoded}
    assert tuple(sizes)==NAMES
    assert all(sizes[name]<=limit for name,limit in m.PACKAGE_MEMBER_BYTE_LIMITS)
    assert sum(sizes.values())<=m.PACKAGE_TOTAL_BYTE_LIMIT
    package=m.decode_release_minute_package(dict(encoded))
    assert package.minutes==result and package.segments==segments
    assert len(package.minutes.timestamps)==10000
    print(json.dumps({'maximum_valid':valid,'members':sizes,'total_bytes':sum(sizes.values())},sort_keys=True))


@pytest.mark.parametrize('kind',['source-zero','source-total','six-sources','no-sources','no-segments','eight-segments',
    'minute-over','record-over','negative-record','duplicate-id','overlap','reverse-role'],ids=str)
def test_structural_domain_bounds(sample,kind):
    result,segments=sample;segment=segments[0]
    if kind=='source-zero':result=replace(result,source_bytes=(0,))
    elif kind=='source-total':result=replace(result,source_bytes=(2**31,1),source_sha256=('a'*64,)*2)
    elif kind=='six-sources':result=replace(result,source_bytes=(1,)*6,source_sha256=('a'*64,)*6)
    elif kind=='no-sources':result=replace(result,source_bytes=(),source_sha256=())
    elif kind=='no-segments':segments=()
    elif kind=='eight-segments':segments=(segment,)*8
    elif kind=='minute-over':segments=(replace(segment,end=segment.start+timedelta(minutes=10001)),)
    elif kind=='record-over':result=replace(result,raw_records=2500001)
    elif kind=='negative-record':result=replace(result,raw_records=-1)
    elif kind=='duplicate-id':segments=(segment,replace(segment,start=segment.end,end=segment.end+timedelta(minutes=1)))
    elif kind=='overlap':segments=(segment,replace(segment,id='other',start=segment.start+timedelta(minutes=1)))
    else:segments=(replace(segment,role='test'),replace(segment,id='other',start=segment.end,end=segment.end+timedelta(minutes=1)))
    reject(lambda:api().encode_release_minute_package(result,segments))


@pytest.mark.parametrize('kind',['outer-list','row-list','bucket-list','reason-list','pair-list','kind-list',
    'anomaly-bool','flag-int','role-subclass','datetime-subclass'],ids=str)
def test_deep_exact_types_are_required_even_for_frozen_objects(sample,kind):
    result,segments=sample;bucket=result.bucket_counts[0]
    if kind=='outer-list':result=replace(result,values=list(result.values))
    elif kind=='row-list':result=replace(result,values=(list(result.values[0]),*result.values[1:]))
    elif kind=='bucket-list':result=replace(result,bucket_counts=list(result.bucket_counts))
    elif kind=='reason-list':bucket=replace(bucket,reason_counts=list(bucket.reason_counts))
    elif kind=='pair-list':bucket=replace(bucket,reason_counts=(list(bucket.reason_counts[0]),*bucket.reason_counts[1:]))
    elif kind=='kind-list':bucket=replace(bucket,label_kind_counts=(list(bucket.label_kind_counts[0]),*bucket.label_kind_counts[1:]))
    elif kind=='anomaly-bool':bucket=replace(bucket,label_anomaly_counts=((bucket.label_anomaly_counts[0][0],False),*bucket.label_anomaly_counts[1:]))
    elif kind=='flag-int':bucket=replace(bucket,definite_attack_present=0)
    elif kind=='role-subclass':
        class Role(str):pass
        segments=(replace(segments[0],role=Role('train')),)
    else:
        class Stamp(datetime):pass
        result=replace(result,timestamps=(Stamp(2026,1,1),*result.timestamps[1:]))
    if bucket is not sample[0].bucket_counts[0]:result=replace(result,bucket_counts=(bucket,*result.bucket_counts[1:]))
    reject(lambda:api().encode_release_minute_package(result,segments))


@pytest.mark.parametrize('payload',[b'['*1100+b'0'+b']'*1100+b'\n',b'1e999\n'],ids=['recursion','overflow'])
def test_parser_failures_are_safe_codes(sample,payload):
    members=plain_members(*sample)
    reject(lambda:api().decode_release_minute_package(replace_member(members,'minutes.json',payload)),'INVALID_PACKAGE')


def test_all_declared_safe_error_codes_and_public_value_guards(sample):
    m=api()
    codes=('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
        'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE',
        'OUTPUT_EXISTS','PACKAGE_CHANGED','OUTPUT_ERROR')
    assert all(str(m.ReleaseMinutePackageError(code))==code for code in codes)
    package=m.decode_release_minute_package(plain_members(*sample))
    reject(lambda:replace(package,scope='AUTHENTICATED'))
    reject(lambda:replace(package,identity=None))
    reject(lambda:replace(package.identity,manifest_byte_count=True))
