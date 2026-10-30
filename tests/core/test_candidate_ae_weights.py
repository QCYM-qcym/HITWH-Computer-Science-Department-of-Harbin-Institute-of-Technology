"""Strict JSON model state: artificial tensors, never external executable models."""
import copy
import json
import subprocess
import sys

import numpy as np
import pytest


def api():
    from traffic_anomaly import candidate_ae_weights
    return candidate_ae_weights


def binding(width=13):
    return dict(schema_version=1,run_id='toy-weights',model_profile_id='c17-i1-g13u-ae-synthetic-v1',
        evidence_kind='SYNTHETIC_ONLY',time_basis='synthetic_source_clock',policy_status='AUDIT_ONLY',
        scope='ENGINEERING_TOY_ONLY',selected_policy='P_U',score_direction='HIGHER_IS_MORE_ANOMALOUS',
        value_space='prepared',feature_names=[f'f{i}' for i in range(13)],qualification_windows=[15,30],
        configuration=dict(input_width=width,method='current_ae' if width==13 else 'history_ae',
                           history_window=None if width==13 else 15),configuration_sha256='a'*64,
        library_versions={'python':'toy','numpy':'toy','torch':'toy'},provenance={'toy':'b'*64},
        preprocessing_state={'toy':True},runtime={'device':'cpu'})


def document(width=13):
    shapes={'0.weight':[8,width],'0.bias':[8],'2.weight':[3,8],'2.bias':[3],
            '4.weight':[8,3],'4.bias':[8],'6.weight':[width,8],'6.bias':[width]}
    return {'schema_version':1,'format':'candidate-ae-json-weights-v1','binding':binding(width),
        'parameters':{k:{'dtype':'float32','shape':v,'values':[0.0]*int(np.prod(v))} for k,v in shapes.items()}}


@pytest.mark.parametrize('width',[13,26])
def test_json_roundtrip_reconstructs_exact_cpu_parameters_and_rng(width,monkeypatch):
    import torch
    m=api(); before=torch.random.get_rng_state().clone()
    threads=(torch.get_num_threads(),torch.get_num_interop_threads())
    def forbidden(*a,**kw):raise AssertionError('executable or accelerator route')
    monkeypatch.setattr(torch,'load',forbidden); monkeypatch.setattr(torch,'save',forbidden)
    monkeypatch.setattr(torch,'manual_seed',forbidden)
    monkeypatch.setattr(torch.accelerator,'current_accelerator',forbidden)
    network=m.build_candidate_ae_network(width)
    assert torch.equal(before,torch.random.get_rng_state())
    encoded=m.encode_candidate_ae_weights(network,binding(width))
    raw=json.dumps(encoded,allow_nan=False).encode()
    parsed=m.parse_candidate_ae_weights(raw,binding(width))
    arrays=m.validate_candidate_ae_weights(parsed,binding(width))
    restored=m.rebuild_candidate_ae_from_json(parsed,binding(width))
    assert sum(p.numel() for p in network.parameters())==({13:288,26:509}[width])
    for name,param in restored.named_parameters():
        assert param.device.type=='cpu' and param.dtype==torch.float32
        np.testing.assert_array_equal(param.detach().numpy().view(np.uint32),
                                      network.state_dict()[name].numpy().view(np.uint32))
        assert arrays[name].dtype==np.float32
    assert torch.equal(before,torch.random.get_rng_state())
    assert threads==(torch.get_num_threads(),torch.get_num_interop_threads())


@pytest.mark.parametrize('width',[True,False,0,12,14,25,27,13.0,'13',None])
def test_only_exact_supported_widths(width):
    with pytest.raises(api().CandidateAEWeightsError):api().build_candidate_ae_network(width)


@pytest.mark.parametrize('mutation',[
    lambda d:d.update(extra=True), lambda d:d.update(schema_version=True),lambda d:d.update(format='pickle'),
    lambda d:d['parameters'].pop('0.bias'),lambda d:d['parameters'].update(extra={}),
    lambda d:d['parameters']['0.bias'].update(dtype='float64'),
    lambda d:d['parameters']['0.bias'].update(shape=[True]),
    lambda d:d['parameters']['0.bias'].update(shape=[8.0]),
    lambda d:d['parameters']['0.bias'].update(shape=[-8]),
    lambda d:d['parameters']['0.bias'].update(shape=[1000000000]),
    lambda d:d['parameters']['0.bias'].update(shape=[1,8]),
    lambda d:d['parameters']['0.bias'].update(values=[0.0]*7),
    lambda d:d['parameters']['0.bias'].update(values=[0.0]*9),
    lambda d:d['parameters']['0.bias'].update(values=[False]*8),
    lambda d:d['parameters']['0.bias'].update(values=[float('nan')]*8),
    lambda d:d['parameters']['0.bias'].update(values=[float('inf')]*8),
    lambda d:d['parameters']['0.bias'].update(values=[1e100]*8),
    lambda d:d['parameters']['0.bias'].update(values=[0.1]*8),
    lambda d:d['parameters']['0.bias'].update(values=['0']*8),
    lambda d:d['parameters']['0.bias'].update(device='cuda'),
    lambda d:d['binding'].update(run_id='different'),
    lambda d:d['binding']['configuration'].update(input_width=26),
    lambda d:d['binding']['library_versions'].update(torch='different'),
    lambda d:d['binding'].update(scope='REAL_DATA'),
    lambda d:d['binding'].update(qualification_windows=[15.0,30]),
])
def test_tampering_rejected_before_tensor_allocation(mutation):
    m=api(); value=document(); mutation(value)
    with pytest.raises(m.CandidateAEWeightsError):m.validate_candidate_ae_weights(value,binding())


@pytest.mark.parametrize('payload',[b'{}',b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',
    b'{"x":1e999}',b'[]',b'null',b'\xff',b'['*1100+b']'*1100])
def test_strict_parser_rejects_invalid_json(payload):
    with pytest.raises(api().CandidateAEWeightsError):api().parse_candidate_ae_weights(payload,binding())


def test_parser_enforces_byte_limit_before_decode():
    m=api()
    with pytest.raises(m.CandidateAEWeightsError,match='RESOURCE_LIMIT'):
        m.parse_candidate_ae_weights(b' '*(1024*1024+1),binding())


def test_valid_plain_json_validation_imports_no_model_libraries():
    code="""import json,sys
from traffic_anomaly.candidate_ae_weights import validate_candidate_ae_weights,parse_candidate_ae_weights
d=json.loads(sys.stdin.read()); validate_candidate_ae_weights(d,d['binding']); parse_candidate_ae_weights(json.dumps(d).encode(),d['binding'])
assert not any(x in sys.modules for x in ('torch','sklearn','joblib'))
"""
    result=subprocess.run([sys.executable,'-X','utf8','-c',code],input=json.dumps(document()),
                          text=True,capture_output=True)
    assert result.returncode==0,result.stderr


def test_constructor_failure_restores_cpu_rng(monkeypatch):
    import torch
    m=api(); before=torch.random.get_rng_state().clone()
    def fail(*a,**kw):
        torch.rand(3,device='cpu'); raise RuntimeError('private path')
    monkeypatch.setattr(torch.nn,'Linear',fail)
    with pytest.raises(m.CandidateAEWeightsError,match='MODEL_BUILD_ERROR'):
        m.build_candidate_ae_network(13)
    assert torch.equal(before,torch.random.get_rng_state())


def test_rebuild_validates_before_constructing(monkeypatch):
    m=api(); value=document(); value['parameters']['0.bias']['values'][0]=False
    monkeypatch.setattr(m,'build_candidate_ae_network',lambda *a:pytest.fail('allocated'))
    with pytest.raises(m.CandidateAEWeightsError):m.rebuild_candidate_ae_from_json(value,binding())


def test_encoding_rejects_wrong_architecture_and_nonfinite():
    import torch
    m=api()
    with pytest.raises(m.CandidateAEWeightsError):m.encode_candidate_ae_weights(torch.nn.Linear(13,13),binding())
    model=m.build_candidate_ae_network(13)
    with torch.no_grad():model[0].bias[0]=float('nan')
    with pytest.raises(m.CandidateAEWeightsError):m.encode_candidate_ae_weights(model,binding())


def test_signed_zero_bits_survive_json():
    m=api(); value=document(); value['parameters']['0.bias']['values'][0]=-0.0
    parsed=m.parse_candidate_ae_weights(json.dumps(value).encode(),binding())
    restored=m.rebuild_candidate_ae_from_json(parsed,binding())
    assert np.signbit(restored[0].bias.detach().numpy()[0])


@pytest.mark.parametrize('duplicate',['schema_version','0.bias','dtype'])
def test_duplicate_keys_in_otherwise_valid_document_are_rejected(duplicate):
    value=document(); encoded=json.dumps(value)
    if duplicate=='schema_version':
        encoded=encoded.replace('"schema_version": 1','"schema_version": 1, "schema_version": 1',1)
    elif duplicate=='0.bias':
        pair='"0.bias": '+json.dumps(value['parameters']['0.bias'])
        encoded=encoded.replace(pair,pair+', '+pair,1)
    else:
        encoded=encoded.replace('"dtype": "float32"','"dtype": "float32", "dtype": "float32"',1)
    with pytest.raises(api().CandidateAEWeightsError):api().parse_candidate_ae_weights(encoded.encode(),binding())


def test_explicit_cpu_survives_caller_defaults_and_inference_mode():
    import torch
    m=api(); old_device=torch.get_default_device();old_dtype=torch.get_default_dtype()
    before=torch.random.get_rng_state().clone()
    try:
        torch.set_default_device('meta');torch.set_default_dtype(torch.float64)
        with torch.inference_mode():
            network=m.build_candidate_ae_network(26)
            state=m.encode_candidate_ae_weights(network,binding(26))
            restored=m.rebuild_candidate_ae_from_json(state,binding(26))
            assert torch.is_inference_mode_enabled()
            assert all(p.device.type=='cpu' and p.dtype==torch.float32 and not p.is_inference()
                       for p in restored.parameters())
        assert torch.get_default_device().type=='meta' and torch.get_default_dtype()==torch.float64
    finally:
        torch.set_default_device(old_device);torch.set_default_dtype(old_dtype)
    assert torch.equal(before,torch.random.get_rng_state())
