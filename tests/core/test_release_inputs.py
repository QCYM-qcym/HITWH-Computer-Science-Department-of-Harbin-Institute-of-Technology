"""Artificial unit evidence only; no models, files or maximum-shape auto-runs."""
from dataclasses import FrozenInstanceError,replace
from collections import UserDict
import importlib
import math
from pathlib import Path

import pytest

from .release_input_cases import make_upstream,make_config,prepared_case,documents,reseal,replace_member


def api():return importlib.import_module('traffic_anomaly.release_inputs')


def reject(call,code=None):
    with pytest.raises(api().ReleaseInputPreparationError) as caught:call()
    assert str(caught.value)==caught.value.code
    if code is not None:assert caught.value.code==code
    return caught.value.code


@pytest.mark.parametrize('field,value',[('epsilon',True),('epsilon',1),('epsilon',0.),('epsilon',-0.),
    ('epsilon',float('nan')),('epsilon',float('inf')),('audit_fit_policy',''),('windows',(30,)),
    ('fit_window',True),('policy_status','APPROVED'),('numeric_rules_id','old')],ids=['bool','int','zero','negzero','nan','inf','policy','window','fit-bool','status','rule'])
def test_config_requires_explicit_policy_epsilon_and_exact_types(field,value):
    m=api();config=make_config()
    reject(lambda:m.prepare_release_inputs(make_upstream(),replace(config,**{field:value})))
    with pytest.raises(TypeError):m.ReleasePreparationConfig()


def test_upstream_identity_rebound_before_prepare():
    m=api();upstream=make_upstream()
    forged=replace(upstream,identity=replace(upstream.identity,manifest_sha256='b'*64))
    reject(lambda:m.prepare_release_inputs(forged,make_config()),'UPSTREAM_IDENTITY_MISMATCH')


def test_fit_uses_each_eligible_current_row_once():
    m=api();upstream=make_upstream();saved=m.prepare_release_inputs(upstream,make_config())
    assert saved.labels.fit_indices==tuple(range(30,48))
    assert saved.preprocessing.n_samples_seen==18
    logs=[math.log1p(p) for p in (1.,2.,3.)];mean=sum(logs)/3
    scale=math.sqrt(sum((z-mean)**2 for z in logs)/3)
    assert saved.preprocessing.mean[1]==pytest.approx(mean,rel=1e-12)
    assert saved.preprocessing.scale[1]==pytest.approx(scale,rel=1e-12)
    assert sum(saved.minutes.common_valid)==56
    assert sum(saved.labels.qualification_masks[0].train_full_history_normal)==18


def test_constant_columns_use_first_mean_and_unit_scale():
    _,saved=prepared_case()
    assert saved.preprocessing.mean[0]==math.log1p(1.)
    assert saved.preprocessing.scale[0]==1.
    assert all(row[0]==0. for row in saved.minutes.current_values)


def test_empty_fit_population_rejected():
    reject(lambda:api().prepare_release_inputs(make_upstream(lengths=(30,),roles=('train',)),make_config()),'NO_TRAINING_NORMAL_MINUTES')


def test_raw_fit_population_is_not_final_common_population():
    overrides={i:(1.,1.,1.,10.,10.,1.,0.,0.,0.,1.,1.,1.,0.) for i in range(80)}
    overrides[33]=(1.,2.,1.,10.,10.,1.,0.,0.,0.,1.,1.,1.,0.)
    saved=api().prepare_release_inputs(make_upstream(lengths=(80,),roles=('train',),value_overrides=overrides),make_config(epsilon=1e-320))
    assert saved.preprocessing.n_samples_seen==50
    assert sum(saved.minutes.common_valid)==19
    assert sum(saved.labels.qualification_masks[0].train_full_history_normal)==19
    for history,first in zip(saved.minutes.histories,(49,64)):
        assert history.invalid_reason[33]=='nonfinite_history'
        assert all(not history.valid[i] and history.invalid_reason[i]=='nonfinite_history' for i in range(34,first))
        assert history.valid[first] and not history.valid[first-1]


def test_adjacent_segments_reset_even_with_same_role():
    saved=api().prepare_release_inputs(make_upstream(lengths=(48,48),roles=('train','train'),continuous=True),make_config())
    for history,first in zip(saved.minutes.histories,(63,78)):
        assert history.invalid_reason[48]=='boundary'
        assert not history.valid[first-1] and history.valid[first]


def test_test_label_changes_do_not_change_numeric_history():
    m=api();_,a=prepared_case()
    b=m.prepare_release_inputs(make_upstream(label_overrides={133:('attack',)*3}),make_config())
    assert a.minutes==b.minutes
    assert a.preprocessing==b.preprocessing
    assert a.identity!=b.identity


def test_held_out_changes_keep_training_state_and_training_digests():
    m=api();_,a=prepared_case()
    b=m.prepare_release_inputs(make_upstream(value_overrides={83:(1.,4.,1.,40.,10.,1.,0.,0.,0.,4.,4.,4.,0.)}),make_config())
    assert a.preprocessing==b.preprocessing and a.labels.fit_mask==b.labels.fit_mask
    assert a.minutes.current_values[:83]==b.minutes.current_values[:83]
    assert a.identity!=b.identity


def test_exact_five_member_schema_and_digest_dag():
    m=api();upstream,saved=prepared_case();members=m.encode_release_input_package(saved)
    assert tuple(name for name,_ in members)==('preprocess.json','inputs.json','labels.json','manifest.json','COMPLETE.json')
    loaded=m.decode_release_input_package(dict(members));assert loaded==saved
    docs=documents(dict(members))
    assert set(docs['preprocess.json'])=={'schema_version','profile_id','context_sha256','configuration_sha256','state'}
    assert not {'labels','fit_mask','joined','raw_values'} & set(docs['inputs.json'])
    assert 'identity' not in docs['manifest.json'] and 'load_report' not in docs['manifest.json']
    assert loaded.load_report.upstream_replay=='NOT_PERFORMED'
    assert m.verify_release_input_derivation(upstream,loaded).checks.fit_parameters=='NOT_REESTIMATED'
    assert all(payload.endswith(b'\n') and not payload.endswith(b'\n\n') for _,payload in members)


def test_public_encode_rejects_forged_identity_or_load_report():
    m=api();_,saved=prepared_case()
    reject(lambda:m.encode_release_input_package(replace(saved,identity=replace(saved.identity,manifest_sha256='b'*64))),'INTEGRITY_MISMATCH')
    reject(lambda:m.encode_release_input_package(replace(saved,load_report=replace(saved.load_report,upstream_replay='MATCHED'))))


@pytest.mark.parametrize('window',[True,15.,14,31],ids=['bool','float','14','31'])
def test_joined_requires_exact_window_and_nulls_whole_invalid_row(window):
    _,saved=prepared_case();reject(lambda:saved.joined(window))


def test_frozen_detached_values_and_joined():
    _,saved=prepared_case();joined=saved.joined(15)
    assert type(joined) is tuple and all(type(row) is tuple and len(row)==26 for row in joined)
    assert joined[0]==(None,)*26
    assert joined[15]==saved.minutes.current_values[15]+saved.minutes.histories[0].residual[15]
    assert saved.joined(15) is not joined
    with pytest.raises((FrozenInstanceError,AttributeError)):saved.minutes=()
    with pytest.raises(TypeError):saved.minutes.current_values[0][0]=1.


def test_nonfinite_fit_state_is_explicit_reduction_fault_injection(monkeypatch):
    m=api();actual=m._fit_statistics
    def faulty(z):
        mean,scale=actual(z);mean[1]=float('inf');return mean,scale
    monkeypatch.setattr(m,'_fit_statistics',faulty)
    reject(lambda:m.prepare_release_inputs(make_upstream(),make_config()),'NONFINITE_FIT_STATE')


@pytest.fixture
def packed():
    upstream,saved=prepared_case()
    return upstream,saved,dict(api().encode_release_input_package(saved))


@pytest.mark.parametrize('kind',['mapping','subclass','key','value','missing','extra'])
def test_exact_member_argument_types(packed,kind):
    members=dict(packed[2])
    class Subdict(dict):pass
    if kind=='mapping':members=UserDict(members)
    elif kind=='subclass':members=Subdict(members)
    elif kind=='key':members[True]=members.pop('inputs.json')
    elif kind=='value':members['inputs.json']=bytearray(members['inputs.json'])
    elif kind=='missing':members.pop('COMPLETE.json')
    else:members['sixth.json']=b'{}\n'
    reject(lambda:api().decode_release_input_package(members),'INVALID_PACKAGE_ARGUMENTS')


@pytest.mark.parametrize('member',('preprocess.json','inputs.json','labels.json','manifest.json','COMPLETE.json'),ids=['state','inputs','labels','manifest','complete'])
@pytest.mark.parametrize('kind',['bool-version','version','profile','extra'])
def test_strict_envelopes(packed,member,kind):
    docs=documents(packed[2])
    if kind=='bool-version':docs[member]['schema_version']=True
    elif kind=='version':docs[member]['schema_version']=2
    elif kind=='profile':docs[member]['profile_id']='unknown'
    else:docs[member]['unknown']=None
    reject(lambda:api().decode_release_input_package(reseal(docs)))


@pytest.mark.parametrize('kind',['duplicate','bom','space','multidoc','utf8','nan','inf','negative-int','negative-zero-int',
    'nine-digit-int','long-float','recursion','integer-float'],ids=str)
def test_canonical_and_numeric_token_rejections(packed,kind):
    members=packed[2];payload=members['inputs.json']
    if kind=='duplicate':payload=payload.replace(b'"schema_version":1',b'"schema_version":1,"schema_version":1')
    elif kind=='bom':payload=b'\xef\xbb\xbf'+payload
    elif kind=='space':payload+=b' '
    elif kind=='multidoc':payload+=b'{}\n'
    elif kind=='utf8':payload=b'\xff'+payload
    elif kind=='nan':payload=b'NaN\n'
    elif kind=='inf':payload=b'1e999\n'
    elif kind=='negative-int':payload=b'-1\n'
    elif kind=='negative-zero-int':payload=b'-0\n'
    elif kind=='nine-digit-int':payload=b'100000000\n'
    elif kind=='long-float':payload=b'0.'+b'1'*32+b'\n'
    elif kind=='recursion':payload=b'['*1100+b'0'+b']'*1100+b'\n'
    else:
        docs=documents(members);docs['inputs.json']['current_values'][0][0]=0
        reject(lambda:api().decode_release_input_package(reseal(docs)),'INVALID_PACKAGE');return
    reject(lambda:api().decode_release_input_package(replace_member(members,'inputs.json',payload)),'INVALID_PACKAGE')


RELATIONS=('axis','ordinal-bool','raw-bool','prepared-bool','invalid-source','invalid-partial','valid-null','prepared-reason',
    'history-early','history-ready','history-null','history-reason','history-bool-window','common','fit-mask','fit-indices',
    'fit-count','fit-sha','state-policy','state-window','scale-zero','mean-int','qualification','raw-label','policy-order',
    'context-count','segment-extra','segment-overlap','segment-id','configuration-sha','state-extra','history-extra','label-extra')


@pytest.mark.parametrize('kind',RELATIONS,ids=RELATIONS)
def test_load_recomputes_masks_and_reachable_history_state_only(packed,kind):
    docs=documents(packed[2]);inputs=docs['inputs.json'];labels=docs['labels.json'];state=docs['preprocess.json']['state'];context=docs['manifest.json']['context'];h=inputs['histories']['15']
    if kind=='axis':inputs['timestamps'][1]=inputs['timestamps'][0]
    elif kind=='ordinal-bool':inputs['segment_ordinals'][0]=False
    elif kind=='raw-bool':inputs['raw_valid'][0]=1
    elif kind=='prepared-bool':inputs['prepared_valid'][0]=1
    elif kind=='invalid-source':inputs['raw_valid'][0]=False
    elif kind=='invalid-partial':inputs['prepared_valid'][0]=False;inputs['prepared_reason'][0]='nonfinite_transform';inputs['current_values'][0][0]=None
    elif kind=='valid-null':inputs['current_values'][0]=[None]*13
    elif kind=='prepared-reason':inputs['prepared_reason'][0]='nonfinite_transform'
    elif kind=='history-early':h['valid'][0]=True;h['invalid_reason'][0]=None;h['residual'][0]=[0.]*13
    elif kind=='history-ready':h['valid'][15]=False;h['invalid_reason'][15]='warmup';h['residual'][15]=[None]*13
    elif kind=='history-null':h['residual'][15]=[None]*13
    elif kind=='history-reason':h['invalid_reason'][0]='gap'
    elif kind=='history-bool-window':h['window']=True
    elif kind=='common':inputs['common_valid'][15]=True
    elif kind=='fit-mask':labels['fit_mask'][0]=True
    elif kind=='fit-indices':labels['fit_indices'][0]=True
    elif kind=='fit-count':state['n_samples_seen']+=1
    elif kind=='fit-sha':state['fit_mask_sha256']='b'*64
    elif kind=='state-policy':state['audit_fit_policy']='P_A'
    elif kind=='state-window':state['fit_window']=15
    elif kind=='scale-zero':state['scale'][0]=0.
    elif kind=='mean-int':state['mean'][0]=0
    elif kind=='qualification':labels['qualification_masks']['P_U']['test_current_normal'][0]=True
    elif kind=='raw-label':inputs['raw_valid'][0]=False;inputs['prepared_valid'][0]=False;inputs['prepared_reason'][0]='source_invalid';inputs['current_values'][0]=[None]*13
    elif kind=='policy-order':labels['policies'].reverse()
    elif kind=='context-count':context['minute_count']+=1
    elif kind=='segment-extra':context['segments'][0]['extra']=0
    elif kind=='segment-overlap':context['segments'][1]['start']=context['segments'][0]['start']
    elif kind=='segment-id':context['segments'][0]['id']='\ud800'
    elif kind=='configuration-sha':
        docs['preprocess.json']['configuration_sha256']='b'*64
        # Bind only bytes, preserving the intentional cross-document contradiction.
        from .release_input_cases import canonical
        reject(lambda:api().decode_release_input_package(replace_member(packed[2],'preprocess.json',canonical(docs['preprocess.json']))));return
    elif kind=='state-extra':state['extra']=0
    elif kind=='history-extra':h['extra']=0
    else:labels['extra']=0
    if kind=='segment-id':
        # Lone surrogate cannot be canonical UTF-8; direct frozen object covers it.
        saved=packed[1];segments=(replace(saved.context.segments[0],id='\ud800'),*saved.context.segments[1:])
        reject(lambda:api().encode_release_input_package(replace(saved,context=replace(saved.context,segments=segments))));return
    reject(lambda:api().decode_release_input_package(reseal(docs)))


def test_load_does_not_fit_transform_or_calculate_history(packed,monkeypatch):
    m=api();attempts=[]
    def blocked(*a,**k):attempts.append(True);raise AssertionError('forbidden numerical or path operation')
    for name in ('prepare_release_inputs','verify_release_input_derivation','_fit_statistics','_fit_state','_transform','_history'):
        monkeypatch.setattr(m,name,blocked)
    monkeypatch.setattr(m.np,'log1p',blocked);monkeypatch.setattr(m.np,'median',blocked)
    monkeypatch.setattr('builtins.open',blocked);monkeypatch.setattr(Path,'open',blocked)
    loaded=m.decode_release_input_package(dict(packed[2]))
    assert loaded==packed[1] and loaded.joined(30)==packed[1].joined(30)
    assert m.encode_release_input_package(loaded)==tuple(packed[2].items()) and attempts==[]


def test_verify_replays_saved_parameters_without_refitting(packed,monkeypatch):
    m=api();counts={'transform':0,'history':0};transform=m._transform;history=m._history
    def nofit(*a,**k):pytest.fail('verify refitted')
    def transform_spy(*a,**k):counts['transform']+=1;return transform(*a,**k)
    def history_spy(*a,**k):counts['history']+=1;return history(*a,**k)
    monkeypatch.setattr(m,'_fit_state',nofit);monkeypatch.setattr(m,'_fit_statistics',nofit)
    monkeypatch.setattr(m,'_transform',transform_spy);monkeypatch.setattr(m,'_history',history_spy)
    report=m.verify_release_input_derivation(packed[0],packed[1])
    assert counts=={'transform':1,'history':2} and report.status=='MATCHED'
    assert report.numerical_tolerance.reference=='REPLAYED' and report.checks.fit_parameters=='NOT_REESTIMATED'


@pytest.mark.parametrize('member,path',[('inputs.json','current'),('inputs.json','residual'),('preprocess.json','mean'),('preprocess.json','rows-sha')],ids=['current','residual','parameters','raw-row-digest'])
def test_replay_rejects_consistent_value_tampering(packed,member,path):
    m=api();docs=documents(packed[2])
    if path=='current':docs[member]['current_values'][35][1]+=1.
    elif path=='residual':docs[member]['histories']['30']['residual'][35][1]+=1.
    elif path=='mean':docs[member]['state']['mean'][1]+=1.
    else:docs[member]['state']['fit_rows_sha256']='b'*64
    loaded=m.decode_release_input_package(reseal(docs))
    assert loaded.identity!=packed[1].identity and loaded.load_report.transform_history_replay=='NOT_PERFORMED'
    reject(lambda:m.verify_release_input_derivation(packed[0],loaded),'DERIVATION_MISMATCH')


def test_directional_tolerance_and_overflow_difference():
    m=api()
    assert m._close(1e12+1.,1e12)
    assert not m._close(1e12+1.01,1e12)
    assert m._close(-0.,0.) and m._close(None,None)
    assert not m._close(None,0.) and not m._close(float('inf'),float('inf'))
    assert not m._close(1.7976931348623157e308,-1.7976931348623157e308)
    # At zero the saved-centered tolerance would allow a slightly larger error.
    assert not m._close(1e-12+5e-25,0.)


@pytest.mark.parametrize('name,limit',[('preprocess.json',16384),('inputs.json',16777216),('labels.json',2097152),('manifest.json',65536),('COMPLETE.json',4096)],ids=['state','inputs','labels','manifest','complete'])
def test_member_limits_precede_parsing(packed,monkeypatch,name,limit):
    m=api();members=dict(packed[2]);members[name]=b' '*(limit+1)
    with monkeypatch.context() as patch:
        patch.setattr(m.json,'loads',lambda *a,**k:pytest.fail('parse before byte limit'))
        reject(lambda:m.decode_release_input_package(members),'RESOURCE_LIMIT')
    members[name]=b' '*limit
    assert reject(lambda:m.decode_release_input_package(members))!='RESOURCE_LIMIT'


def test_declared_member_reference_has_its_own_bound(packed):
    docs=documents(packed[2]);docs['manifest.json']['members']['preprocess.json']['byte_count']=16385
    from .release_input_cases import canonical
    members=replace_member(packed[2],'manifest.json',canonical(docs['manifest.json']))
    reject(lambda:api().decode_release_input_package(members),'RESOURCE_LIMIT')


@pytest.mark.parametrize('limit',[16384,65536,131072,8388608],ids=['config','context','fit-mask','fit-rows'])
def test_intermediate_accumulator_caps_and_reserved_lf(limit):
    m=api();text='x'*(limit-3)
    assert len(m._canonical(text,limit))==limit
    reject(lambda:m._canonical(text+'x',limit),'RESOURCE_LIMIT')


def test_total_budget_is_retained_without_impossible_public_counterexample():
    m=api();assert sum(limit for _,limit in m.PACKAGE_MEMBER_BYTE_LIMITS)==18960384<20971520
    assert m.PACKAGE_TOTAL_BYTE_LIMIT==20971520
    assert m._canonical(None,5)==b'null\n'
    reject(lambda:m._canonical(None,4),'RESOURCE_LIMIT')


def test_history_uses_only_past_and_excludes_current_and_future():
    m=api();raw=make_upstream(lengths=(40,),roles=('train',)).minutes
    values=tuple((float(i),)*13 if i!=30 else (100.,)*13 for i in range(40))
    changed=values[:31]+((1e6,)*13,)*9
    for window,expected in ((15,78./5.),(30,85.5/8.5)):
        a=m._history(raw.timestamps,(0,)*40,values,(True,)*40,window,1.)
        b=m._history(raw.timestamps,(0,)*40,changed,(True,)*40,window,1.)
        assert a.residual[30]==(expected,)*13
        assert a.residual[:31]==b.residual[:31]


def test_h30_valid_does_not_imply_h15_valid():
    m=api();raw=make_upstream(lengths=(31,),roles=('train',)).minutes
    values=tuple((float(i+1),)*13 for i in range(15))+((0.,)*13,)*15+((1.,)*13,)
    a=m._history(raw.timestamps,(0,)*31,values,(True,)*31,15,1e-320)
    b=m._history(raw.timestamps,(0,)*31,values,(True,)*31,30,1e-320)
    assert not a.valid[30] and a.invalid_reason[30]=='nonfinite_history'
    assert b.valid[30] and b.residual[30]==(1.,)*13


def test_structurally_reachable_failure_is_loadable_without_claiming_replay(packed):
    m=api();saved=packed[1];history=saved.minutes.histories[1]
    history=replace(history,valid=history.valid[:30]+(False,)*18+history.valid[48:],
        residual=history.residual[:30]+((None,)*13,)*18+history.residual[48:],
        invalid_reason=history.invalid_reason[:30]+('nonfinite_history',)*18+history.invalid_reason[48:])
    common=tuple(v and a and b for v,a,b in zip(saved.minutes.prepared_valid,saved.minutes.histories[0].valid,history.valid))
    minutes=replace(saved.minutes,histories=(saved.minutes.histories[0],history),common_valid=common)
    labels=replace(saved.labels,qualification_masks=m._qualifications(saved.context,minutes,saved.labels.label_kinds))
    rewritten=m._snapshot(saved.context,saved.preprocessing,minutes,labels)
    loaded=m.decode_release_input_package(dict(m.encode_release_input_package(rewritten)))
    assert loaded.preprocessing.n_samples_seen==18
    assert not any(loaded.labels.qualification_masks[0].train_full_history_normal)
    assert loaded.load_report.transform_history_replay=='NOT_PERFORMED'
    reject(lambda:m.verify_release_input_derivation(packed[0],loaded),'DERIVATION_MISMATCH')


def test_saved_parameter_transform_failure_is_not_natural_fit_evidence(packed,monkeypatch):
    m=api();upstream,saved,_=packed
    state=replace(saved.preprocessing,mean=(0.,)*13,scale=(5e-324,)*13)
    values,valid,reasons=m._transform(upstream.minutes,state)
    assert not any(valid) and set(reasons)=={'nonfinite_transform'}
    histories=tuple(m._history(saved.minutes.timestamps,saved.minutes.segment_ordinals,values,valid,w,1e-6) for w in (15,30))
    minutes=replace(saved.minutes,current_values=values,prepared_valid=valid,prepared_reason=reasons,
        histories=histories,common_valid=(False,)*saved.context.minute_count)
    labels=replace(saved.labels,qualification_masks=m._qualifications(saved.context,minutes,saved.labels.label_kinds))
    rewritten=m._snapshot(saved.context,state,minutes,labels)
    def blocked(*a,**k):pytest.fail('saved-parameter verification re-estimated fit')
    monkeypatch.setattr(m,'_fit_state',blocked);monkeypatch.setattr(m,'_fit_statistics',blocked)
    assert rewritten.labels.label_kinds==saved.labels.label_kinds
    assert m.verify_release_input_derivation(upstream,rewritten).checks.fit_parameters=='NOT_REESTIMATED'


def test_negative_zero_has_distinct_bytes_but_can_match_numerical_replay(packed):
    m=api();docs=documents(packed[2]);assert docs['inputs.json']['current_values'][0][0]==0.
    docs['inputs.json']['current_values'][0][0]=-0.
    loaded=m.decode_release_input_package(reseal(docs))
    assert loaded.identity!=packed[1].identity
    assert math.copysign(1.,loaded.minutes.current_values[0][0])==-1.
    assert m.verify_release_input_derivation(packed[0],loaded).status=='MATCHED'


@pytest.mark.parametrize('policy,count',[('P_U',7),('P_B',18),('P_A',7)],ids=['unknown-policy','benign-policy','attack-policy'])
def test_explicit_audit_policy_changes_only_its_raw_fit_selection(policy,count):
    upstream=make_upstream(lengths=(48,),roles=('train',),label_overrides={10:('unknown','normal','attack')})
    saved=api().prepare_release_inputs(upstream,make_config(policy=policy))
    assert saved.preprocessing.n_samples_seen==count
    assert saved.labels.fit_indices==tuple(range(30 if policy=='P_B' else 41,48))
    assert saved.labels.label_kinds==upstream.minutes.label_kinds
    assert len(saved.labels.qualification_masks)==3
    assert sum(len(getattr(q,name)) for q in saved.labels.qualification_masks for name in api()._QUAL)==24*48


@pytest.mark.parametrize('kind',['mean-list','row-list','history-list','segment-list','qualification-list','mask-int','label-subclass'],ids=str)
def test_public_encoder_rejects_mutable_or_nonexact_nested_values(packed,kind):
    saved=packed[1]
    if kind=='mean-list':saved=replace(saved,preprocessing=replace(saved.preprocessing,mean=list(saved.preprocessing.mean)))
    elif kind=='row-list':saved=replace(saved,minutes=replace(saved.minutes,current_values=(list(saved.minutes.current_values[0]),*saved.minutes.current_values[1:])))
    elif kind=='history-list':saved=replace(saved,minutes=replace(saved.minutes,histories=list(saved.minutes.histories)))
    elif kind=='segment-list':saved=replace(saved,context=replace(saved.context,segments=list(saved.context.segments)))
    elif kind=='qualification-list':saved=replace(saved,labels=replace(saved.labels,qualification_masks=list(saved.labels.qualification_masks)))
    elif kind=='mask-int':saved=replace(saved,minutes=replace(saved.minutes,prepared_valid=(1,*saved.minutes.prepared_valid[1:])))
    else:
        class Label(str):pass
        saved=replace(saved,labels=replace(saved.labels,label_kinds=((Label('normal'),'normal','normal'),*saved.labels.label_kinds[1:])))
    reject(lambda:api().encode_release_input_package(saved))


@pytest.mark.parametrize('rule',[0,None,False],ids=['integer','none','bool'])
def test_rule_type_errors_are_configuration_errors(rule):
    reject(lambda:api().prepare_release_inputs(make_upstream(),replace(make_config(),numeric_rules_id=rule)),
           'INVALID_PREPARATION_CONFIG')


def test_unknown_string_rule_remains_incompatible_version():
    reject(lambda:api().prepare_release_inputs(make_upstream(),replace(make_config(),numeric_rules_id='unknown-rules-v2')),
           'INCOMPATIBLE_PACKAGE')


@pytest.mark.parametrize('kind',['bool','string','float','none','negative','out-of-domain','mutable'],ids=str)
def test_fit_index_shape_or_scalar_errors_precede_relation_checks(packed,kind):
    saved=packed[1];indices=saved.labels.fit_indices
    value={'bool':True,'string':'30','float':30.,'none':None,'negative':-1,'out-of-domain':saved.context.minute_count}.get(kind)
    indices=list(indices) if kind=='mutable' else (value,*indices[1:])
    invalid=replace(saved,labels=replace(saved.labels,fit_indices=indices))
    reject(lambda:api().encode_release_input_package(invalid),'INVALID_PACKAGE')


@pytest.mark.parametrize('kind',['bool','string','negative','out-of-domain'],ids=str)
def test_fit_index_decoder_checks_scalar_domain_before_relations(packed,kind):
    docs=documents(packed[2]);docs['labels.json']['fit_indices'][0]={
        'bool':True,'string':'30','negative':-1,'out-of-domain':packed[1].context.minute_count}[kind]
    reject(lambda:api().decode_release_input_package(reseal(docs)),'INVALID_PACKAGE')


@pytest.mark.parametrize('kind',['wrong-valid-index','wrong-count','reverse'],ids=str)
def test_legal_fit_indices_conflicting_with_mask_are_relationship_errors(packed,kind):
    saved=packed[1];indices=saved.labels.fit_indices
    if kind=='wrong-valid-index':indices=(29,*indices[1:])
    elif kind=='wrong-count':indices=indices[:-1]
    else:indices=tuple(reversed(indices))
    reject(lambda:api().encode_release_input_package(replace(saved,labels=replace(saved.labels,fit_indices=indices))),
           'INCONSISTENT_PACKAGE')


@pytest.mark.parametrize('value',[True,'0',-1,4],ids=['bool','string','negative','out-of-domain'])
def test_segment_index_scalars_follow_the_same_invalid_package_class(packed,value):
    saved=packed[1]
    minutes=replace(saved.minutes,segment_ordinals=(value,*saved.minutes.segment_ordinals[1:]))
    reject(lambda:api().encode_release_input_package(replace(saved,minutes=minutes)),'INVALID_PACKAGE')


def test_legal_segment_index_conflict_is_a_relationship_error(packed):
    saved=packed[1];minutes=replace(saved.minutes,segment_ordinals=(1,*saved.minutes.segment_ordinals[1:]))
    reject(lambda:api().encode_release_input_package(replace(saved,minutes=minutes)),'INCONSISTENT_PACKAGE')
