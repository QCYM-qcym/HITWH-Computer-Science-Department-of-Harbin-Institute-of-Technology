"""Predefined AE492 numerical/JSON seam; all snapshots and weights are artificial."""
import builtins
import copy
from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from traffic_anomaly.candidate_artifacts import _array_mapping
from .test_candidate_autoencoder import snapshot, changed_arrays

OLD = 'c17-i1-g13u-ae-synthetic-v1'
NEW = 'c17-i1-g13u-ae-current-capacity492-synthetic-v1'

# Complete prescribed old default, independently retained as compatibility input.
OLD_CONFIG = dict(model_profile_id=OLD, parameter_status='ENGINEERING_TOY_ONLY',
    method='current_ae',input_width=13,history_window=None,architecture=[13,8,3,8,13],parameter_count=288,
    activation='RELU_HIDDEN_LINEAR_OUTPUT',device='cpu',training_dtype='float32',score_dtype='float64',
    score_rule='FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT',epochs=5,batch_strategy='FULL_BATCH',shuffle=False,
    optimizer='Adam',optimizer_cpu_guard='INSTANCE_LOCAL_HEALTH_CHECK_V1',
    optimizer_healthcheck_api='_accelerator_graph_capture_health_check',learning_rate=.001,
    adam_betas=[.9,.999],adam_epsilon=1e-8,weight_decay=0.,amsgrad=False,random_state=42,
    fit_scope='TRAIN_NORMAL_COMMON',calibration_scope='CALIBRATION_NORMAL_COMMON',quantile=.99,
    quantile_method='linear',alarm_comparison='STRICT_GREATER',preprocessing_fit_provenance='NOT_REESTIMATED')


def expected(profile=NEW):
    config=copy.deepcopy(OLD_CONFIG)
    if profile==NEW:
        config.update(model_profile_id=NEW,architecture=[13,14,3,14,13],parameter_count=492)
    return config


def profiles():
    return importlib.import_module('traffic_anomaly.candidate_ae_profiles')


def weights():
    return importlib.import_module('traffic_anomaly.candidate_ae_weights')


def compute(snapshot,profile=NEW):
    from traffic_anomaly.candidate_autoencoder import compute_synthetic_candidate_ae
    return compute_synthetic_candidate_ae(snapshot,method='current_ae',model_profile_id=profile)


def binding(profile=NEW):
    config=expected(profile)
    canonical=json.dumps(config,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
    return dict(schema_version=1,run_id='invented-capacity',model_profile_id=profile,
        evidence_kind='SYNTHETIC_ONLY',time_basis='synthetic_source_clock',policy_status='AUDIT_ONLY',
        scope='ENGINEERING_TOY_ONLY',selected_policy='P_U',score_direction='HIGHER_IS_MORE_ANOMALOUS',
        value_space='prepared',feature_names=[f'f{i}' for i in range(13)],qualification_windows=[15,30],
        configuration=config,configuration_sha256=hashlib.sha256(canonical).hexdigest(),
        library_versions={'python':'toy','numpy':'toy','torch':'toy'},provenance={'toy':'b'*64},
        preprocessing_state={'toy':True},runtime={'device':'cpu'})


def document(profile=NEW):
    hidden=14 if profile==NEW else 8
    shapes={'0.weight':[hidden,13],'0.bias':[hidden],'2.weight':[3,hidden],'2.bias':[3],
        '4.weight':[hidden,3],'4.bias':[hidden],'6.weight':[13,hidden],'6.bias':[13]}
    return dict(schema_version=1,format='candidate-ae-json-weights-v1',binding=binding(profile),
        parameters={key:dict(dtype='float32',shape=shape,values=[0.0]*int(np.prod(shape))) for key,shape in shapes.items()})


def no_torch(monkeypatch):
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name.split('.')[0]=='torch': pytest.fail('torch imported before rejection')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)


def test_fixed_resolver_preserves_complete_old_default_and_fresh_values():
    p=profiles()
    assert p.MODEL_PROFILE_ID==OLD and p.CAPACITY492_MODEL_PROFILE_ID==NEW
    old=p.resolve_candidate_ae_configuration('current_ae')
    assert p.strict_configuration_equal(old,OLD_CONFIG)
    config=p.resolve_candidate_ae_configuration('current_ae',model_profile_id=NEW)
    assert p.strict_configuration_equal(config,expected())
    config['architecture'][1]=99
    config['adam_betas'][0]=0.
    assert p.strict_configuration_equal(p.resolve_candidate_ae_configuration('current_ae',model_profile_id=NEW),expected())
    for window in (15,30):
        history=copy.deepcopy(OLD_CONFIG)
        history.update(method='history_ae',history_window=window,input_width=26,
                       architecture=[26,8,3,8,26],parameter_count=509)
        assert p.strict_configuration_equal(p.resolve_candidate_ae_configuration('history_ae',window),history)


@pytest.mark.parametrize('key,value',[('epochs',5.0),('parameter_count',288.0),('shuffle',0),
    ('weight_decay',0),('weight_decay',-0.0),('architecture',[13.,8,3,8,13]),('adam_betas',(.9,.999)),('extra',1)])
def test_configuration_equality_is_type_sensitive(key,value):
    actual=copy.deepcopy(OLD_CONFIG)
    actual[key]=value
    assert not profiles().strict_configuration_equal(actual,OLD_CONFIG)


@pytest.mark.parametrize('profile,method,window',[(NEW,'history_ae',15),(NEW,'history_ae',30),
    (NEW,'current_ae',15),('unknown','current_ae',None),(True,'current_ae',None),
    (13.,'current_ae',None),([],'current_ae',None),({},'current_ae',None),
    (None,'current_ae',None),(NEW,True,None),(NEW,'current_ae',False)])
def test_profile_and_method_rejected_before_torch_import(snapshot,monkeypatch,profile,method,window):
    from traffic_anomaly.candidate_autoencoder import compute_synthetic_candidate_ae,CandidateAEError
    no_torch(monkeypatch)
    with pytest.raises(CandidateAEError):
        compute_synthetic_candidate_ae(snapshot,method=method,history_window=window,model_profile_id=profile)


def test_new_model_actual_named_parameters_and_independent_layer_arithmetic():
    import torch
    state=torch.random.get_rng_state().clone()
    threads=torch.get_num_threads(),torch.get_num_interop_threads()
    model=weights().build_candidate_ae_network(13,model_profile_id=NEW)
    expected_shapes={'0.weight':(14,13),'0.bias':(14,),'2.weight':(3,14),'2.bias':(3,),
        '4.weight':(14,3),'4.bias':(14,),'6.weight':(13,14),'6.bias':(13,)}
    assert {name:tuple(value.shape) for name,value in model.named_parameters()}==expected_shapes
    assert 13*14+14 + 14*3+3 + 3*14+14 + 14*13+13 == 492
    assert sum(value.numel() for value in model.parameters())==492
    assert all(value.device.type=='cpu' and value.dtype==torch.float32 for value in model.parameters())
    assert all(type(model[i]) is torch.nn.ReLU for i in (1,3,5))
    assert type(model[6]) is torch.nn.Linear and model[6].bias is not None
    assert torch.equal(state,torch.random.get_rng_state())
    assert threads==(torch.get_num_threads(),torch.get_num_interop_threads())


def test_five_training_batches_current_only_and_independent_mse_q99(snapshot,monkeypatch):
    import torch
    from traffic_anomaly.candidate_inputs import CandidatePreprocessor
    m=weights()
    original=m.build_candidate_ae_network
    observed=[]
    def build(width,**kwargs):
        network=original(width,**kwargs)
        network.register_forward_pre_hook(lambda model,args: observed.append(args[0].detach().numpy().copy()) if model.training else None)
        return network
    monkeypatch.setattr(m,'build_candidate_ae_network',build)
    def forbidden(*args,**kwargs): pytest.fail('pure compute read/fit/accelerator attempt')
    state=torch.random.get_rng_state().clone()
    threads=torch.get_num_threads(),torch.get_num_interop_threads()
    with monkeypatch.context() as guards:
        guards.setattr(Path,'open',forbidden)
        guards.setattr(CandidatePreprocessor,'fit',forbidden)
        guards.setattr(torch.accelerator,'current_accelerator',forbidden)
        result=compute(snapshot)
    assert len(observed)==5
    train=snapshot.current_values[snapshot.training_normal].astype(np.float32)
    assert all(value.shape==(6,13) and np.array_equal(value,train) for value in observed)
    assert result.fit_indices==(30,31,32,33,34,35)
    assert result.calibration_indices==(102,103,104,105,106,107)
    assert np.array_equal(result.score_valid,snapshot.common_valid)
    matrix=snapshot.current_values[result.score_valid].astype(np.float32)
    with torch.inference_mode(): recovered=result.model(torch.from_numpy(matrix.copy())).numpy()
    independent=np.sum((matrix.astype(np.float64)-recovered.astype(np.float64))**2,axis=1)/13
    np.testing.assert_allclose(result.scores[result.score_valid],independent,rtol=0,atol=0)
    np.testing.assert_array_equal(result.current_reconstruction_mse[result.score_valid],independent)
    assert np.isnan(result.history_deviation_reconstruction_mse).all()
    ordered=sorted(float(result.scores[i]) for i in (102,103,104,105,106,107))
    # Six calibration values: zero-based Q99 rank4.95; fixed independent interpolation.
    threshold=ordered[4]+(ordered[5]-ordered[4])*.95
    assert result.threshold==pytest.approx(threshold,rel=1e-15)
    assert np.array_equal(result.alarms[result.score_valid],independent>result.threshold)
    assert result.configuration==expected()
    assert torch.equal(state,torch.random.get_rng_state())
    assert threads==(torch.get_num_threads(),torch.get_num_interop_threads())


def test_test_labels_and_values_do_not_train_new_current_model(snapshot):
    import torch
    original=compute(snapshot)
    test=snapshot.partitions=='test'
    labels={policy:tuple('attack' if test[i] else value for i,value in enumerate(values)) for policy,values in snapshot.labels.items()}
    normal=_array_mapping({policy:np.array([value=='normal' for value in values],bool) for policy,values in labels.items()})
    changed=compute(replace(snapshot,labels=labels,normal_candidates=normal))
    assert original.training_losses==changed.training_losses and original.threshold==changed.threshold
    np.testing.assert_array_equal(original.scores,changed.scores)
    assert all(torch.equal(a,b) for a,b in zip(original.model.parameters(),changed.model.parameters()))
    values=snapshot.current_values.copy()
    values[test]+=1.
    changed=compute(changed_arrays(snapshot,current_values=values))
    assert original.training_losses==changed.training_losses and original.threshold==changed.threshold
    assert all(torch.equal(a,b) for a,b in zip(original.model.parameters(),changed.model.parameters()))
    assert not np.array_equal(original.scores[test&original.score_valid],changed.scores[test&original.score_valid])


def test_old_optional_profile_and_omitted_default_identical(snapshot):
    import torch
    from traffic_anomaly.candidate_autoencoder import compute_synthetic_candidate_ae
    default=compute_synthetic_candidate_ae(snapshot,method='current_ae')
    explicit=compute(snapshot,OLD)
    assert default.configuration==explicit.configuration==OLD_CONFIG
    assert default.training_losses==explicit.training_losses and default.threshold==explicit.threshold
    np.testing.assert_array_equal(default.scores,explicit.scores)
    assert all(torch.equal(a,b) for a,b in zip(default.model.parameters(),explicit.model.parameters()))


@pytest.mark.parametrize('profile',[OLD,NEW])
def test_json_encode_rebuild_and_replay_carries_exact_profile(snapshot,monkeypatch,profile):
    import torch
    from traffic_anomaly.candidate_autoencoder import replay_candidate_ae
    result=compute(snapshot,profile)
    m=weights()
    encoded=m.encode_candidate_ae_weights(result.model,binding(profile))
    parsed=m.parse_candidate_ae_weights(json.dumps(encoded,allow_nan=False).encode(),binding(profile))
    rebuilt=m.rebuild_candidate_ae_from_json(parsed,binding(profile))
    assert encoded['binding']['configuration']==expected(profile)
    assert sum(value.numel() for value in rebuilt.parameters())==(288 if profile==OLD else 492)
    monkeypatch.setattr(torch.optim.Adam,'step',lambda *a,**k:pytest.fail('replay trained'))
    replay_candidate_ae(snapshot,result,rebuilt)
    for name,value in rebuilt.named_parameters():
        assert value.detach().numpy().tobytes()==result.model.state_dict()[name].numpy().tobytes()


@pytest.mark.parametrize('profile,mutation',[(OLD,'old_hidden14'),(NEW,'new_hidden8'),
    (NEW,'new_history'),(NEW,'outer_mismatch'),(NEW,'unknown'),(NEW,'epochs_float'),
    (NEW,'parameter_float'),(NEW,'architecture_float'),(NEW,'shuffle_int'),(NEW,'hash'),
    (NEW,'missing_config'),(NEW,'extra_config'),(OLD,'old_optimizer'),(OLD,'old_three_fields')])
def test_self_consistent_forged_binding_rejected_before_torch(monkeypatch,profile,mutation):
    m=weights(); value=document(profile); config=value['binding']['configuration']
    if mutation=='old_hidden14': config.update(architecture=[13,14,3,14,13],parameter_count=492)
    elif mutation=='new_hidden8': config.update(architecture=[13,8,3,8,13],parameter_count=288)
    elif mutation=='new_history': config.update(method='history_ae',history_window=15,input_width=26,architecture=[26,14,3,14,26])
    elif mutation=='outer_mismatch': value['binding']['model_profile_id']=OLD
    elif mutation=='unknown': config['model_profile_id']=value['binding']['model_profile_id']='unknown'
    elif mutation=='epochs_float': config['epochs']=5.
    elif mutation=='parameter_float': config['parameter_count']=492.
    elif mutation=='architecture_float': config['architecture'][0]=13.
    elif mutation=='shuffle_int': config['shuffle']=0
    elif mutation=='hash': value['binding']['configuration_sha256']='0'*64
    elif mutation=='missing_config': config.pop('optimizer')
    elif mutation=='extra_config': config['extra']=True
    elif mutation=='old_optimizer': config['learning_rate']=.1
    else: value['binding']['configuration']={key:config[key] for key in ('input_width','method','history_window')}
    if mutation!='hash':
        canonical=json.dumps(value['binding']['configuration'],allow_nan=False,sort_keys=True,separators=(',',':')).encode()
        value['binding']['configuration_sha256']=hashlib.sha256(canonical).hexdigest()
    expected_binding=copy.deepcopy(value['binding'])
    no_torch(monkeypatch)
    with pytest.raises(m.CandidateAEWeightsError): m.validate_candidate_ae_weights(value,expected_binding)
    with pytest.raises(m.CandidateAEWeightsError): m.rebuild_candidate_ae_from_json(value,expected_binding)


@pytest.mark.parametrize('width,profile',[(26,NEW),(13,True),(13,'unknown'),(13.,NEW)])
def test_bad_network_profile_width_rejected_before_torch(monkeypatch,width,profile):
    m=weights(); no_torch(monkeypatch)
    with pytest.raises(m.CandidateAEWeightsError): m.build_candidate_ae_network(width,model_profile_id=profile)


def test_new_plain_json_shape_rejects_before_torch_and_validates_without_torch(monkeypatch):
    m=weights(); no_torch(monkeypatch)
    value=document()
    assert m.validate_candidate_ae_weights(value,binding())['0.weight'].shape==(14,13)
    value['parameters']['0.weight']['shape']=[8,13]
    with pytest.raises(m.CandidateAEWeightsError): m.rebuild_candidate_ae_from_json(value,binding())


def test_configuration_signed_zero_cannot_forge_prescribed_hash(monkeypatch):
    m=weights(); value=document()
    # The supplied hash describes +0.0, while the self-consistent caller binding
    # contains -0.0. An exact fixed configuration must reject the discrepancy.
    value['binding']['configuration']['weight_decay']=-0.0
    no_torch(monkeypatch)
    with pytest.raises(m.CandidateAEWeightsError):
        m.validate_candidate_ae_weights(value,copy.deepcopy(value['binding']))


@pytest.mark.parametrize('kind',['old_id_new_arch','new_id_old_arch','unknown','float_epochs'])
def test_replay_rejects_profile_or_complete_configuration_before_inputs_and_torch(monkeypatch,kind):
    from traffic_anomaly import candidate_autoencoder as ae
    configuration=expected()
    if kind=='old_id_new_arch': configuration['model_profile_id']=OLD
    elif kind=='new_id_old_arch': configuration.update(architecture=[13,8,3,8,13],parameter_count=288)
    elif kind=='unknown': configuration['model_profile_id']='unknown'
    else: configuration['epochs']=5.
    result=ae.CandidateAEResult(None,None,None,None,0.,{}, {},configuration,(),(),None,None,(),{})
    monkeypatch.setattr(ae,'_inputs',lambda *a:pytest.fail('invalid config reached input preparation'))
    no_torch(monkeypatch)
    with pytest.raises(ae.CandidateAEError): ae.replay_candidate_ae(object(),result,None)


def test_wrong_old_network_cannot_train_as_new_profile(snapshot,monkeypatch):
    import torch
    from traffic_anomaly.candidate_autoencoder import CandidateAEError
    m=weights(); original=m.build_candidate_ae_network
    monkeypatch.setattr(m,'build_candidate_ae_network',lambda width,**kwargs:original(width))
    monkeypatch.setattr(torch.optim.Adam,'step',lambda *a,**k:pytest.fail('wrong topology trained'))
    with pytest.raises(CandidateAEError,match='INCOMPATIBLE_AE_NETWORK'): compute(snapshot)
