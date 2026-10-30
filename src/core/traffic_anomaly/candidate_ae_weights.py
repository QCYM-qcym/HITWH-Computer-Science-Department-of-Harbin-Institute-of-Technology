"""Bounded non-executable JSON weights for the fixed synthetic candidate AE."""
from __future__ import annotations

import json
import math

import numpy as np

MAX_WEIGHTS_BYTES = 1024 * 1024
FORMAT = 'candidate-ae-json-weights-v1'
_BINDING_KEYS = frozenset(('schema_version','run_id','model_profile_id','evidence_kind','time_basis',
    'policy_status','scope','selected_policy','score_direction','value_space','feature_names',
    'qualification_windows','configuration','configuration_sha256','library_versions','provenance',
    'preprocessing_state','runtime'))


class CandidateAEWeightsError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code='INVALID_WEIGHTS'):
    if not condition:
        raise CandidateAEWeightsError(code)


def _shapes(width):
    _require(type(width) is int and width in (13,26))
    return {'0.weight':(8,width),'0.bias':(8,), '2.weight':(3,8),'2.bias':(3,),
            '4.weight':(8,3),'4.bias':(8,), '6.weight':(width,8),'6.bias':(width,)}


def _canonical(value):
    return json.dumps(value,allow_nan=False,sort_keys=True,separators=(',',':'))


def _binding(value):
    _require(type(value) is dict and value.keys()==_BINDING_KEYS)
    _require(type(value['schema_version']) is int and value['schema_version']==1
             and value['model_profile_id']=='c17-i1-g13u-ae-synthetic-v1'
             and value['evidence_kind']=='SYNTHETIC_ONLY' and value['policy_status']=='AUDIT_ONLY'
             and value['scope']=='ENGINEERING_TOY_ONLY'
             and value['time_basis']=='synthetic_source_clock'
             and value['value_space']=='prepared'
             and value['score_direction']=='HIGHER_IS_MORE_ANOMALOUS'
             and value['selected_policy'] in ('P_U','P_B','P_A'))
    config=value['configuration']; width=config['input_width']; _shapes(width)
    _require((width==13 and config['method']=='current_ae' and config['history_window'] is None)
             or (width==26 and config['method']=='history_ae'
                 and type(config['history_window']) is int and config['history_window'] in (15,30)))
    # Comparing serialized values also distinguishes bools from numbers and integer fields from floats.
    encoded=_canonical(value)
    return width,encoded


def validate_candidate_ae_weights(document, expected_binding):
    """Validate before tensor allocation; expected binding is caller-owned run identity."""
    try:
        width,expected=_binding(expected_binding)
        _require(type(document) is dict and set(document)=={'schema_version','format','binding','parameters'})
        _require(type(document['schema_version']) is int and document['schema_version']==1
                 and document['format']==FORMAT and _binding(document['binding'])==(width,expected))
        shapes=_shapes(width); parameters=document['parameters']
        _require(type(parameters) is dict and parameters.keys()==shapes.keys())
        result={}
        for name,shape in shapes.items():
            entry=parameters[name]
            _require(type(entry) is dict and set(entry)=={'dtype','shape','values'}
                     and entry['dtype']=='float32' and type(entry['shape']) is list
                     and all(type(v) is int for v in entry['shape']) and entry['shape']==list(shape))
            values=entry['values']
            _require(type(values) is list and len(values)==math.prod(shape))
            _require(all(type(v) in (int,float) and math.isfinite(v) for v in values))
            with np.errstate(over='ignore',invalid='ignore'):
                array=np.asarray(values,dtype=np.float32)
            _require(np.isfinite(array).all() and all(float(x)==v for x,v in zip(array,values)))
            result[name]=array.reshape(shape)
        return result
    except CandidateAEWeightsError:
        raise
    except (KeyError,TypeError,ValueError,OverflowError,RecursionError) as exc:
        raise CandidateAEWeightsError('INVALID_WEIGHTS') from exc


def _pairs(pairs):
    result={}
    for key,value in pairs:
        _require(key not in result)
        result[key]=value
    return result


def _number(value):
    result=float(value)
    _require(math.isfinite(result))
    return result


def parse_candidate_ae_weights(payload, expected_binding):
    """Strict parse with a byte cap; returns a validated plain JSON document."""
    try:
        _require(type(payload) is bytes)
        _require(0<len(payload)<=MAX_WEIGHTS_BYTES,'RESOURCE_LIMIT')
        value=json.loads(payload.decode('utf-8'),object_pairs_hook=_pairs,
                         parse_float=_number,parse_constant=lambda _: _require(False))
        validate_candidate_ae_weights(value,expected_binding)
        return value
    except CandidateAEWeightsError:
        raise
    except (UnicodeError,ValueError,TypeError,OverflowError,RecursionError) as exc:
        raise CandidateAEWeightsError('INVALID_WEIGHTS') from exc


def build_candidate_ae_network(input_width):
    """Hardcoded CPU network. Save/restore only CPU RNG, including constructor failures."""
    _shapes(input_width)
    import torch
    saved=torch.random.get_rng_state().clone()
    try:
        torch.random.default_generator.manual_seed(42)
        with torch.inference_mode(False),torch.enable_grad():
            widths=(input_width,8,3,8,input_width); layers=[]
            for index,(left,right) in enumerate(zip(widths,widths[1:])):
                layers.append(torch.nn.Linear(left,right,device='cpu',dtype=torch.float32))
                if index<3:
                    layers.append(torch.nn.ReLU())
            return torch.nn.Sequential(*layers)
    except (RuntimeError,ValueError,TypeError) as exc:
        raise CandidateAEWeightsError('MODEL_BUILD_ERROR') from exc
    finally:
        torch.random.set_rng_state(saved)


def encode_candidate_ae_weights(network, binding):
    """Encode only the fixed topology, no architecture or arbitrary class serialization."""
    try:
        width,_=_binding(binding)
        import torch
        _require(type(network) is torch.nn.Sequential and len(network)==7)
        for index,layer in enumerate(network):
            _require(type(layer) is (torch.nn.Linear if index%2==0 else torch.nn.ReLU))
        parameters={}
        for name,tensor in network.state_dict().items():
            _require(tensor.device.type=='cpu' and tensor.dtype==torch.float32 and tensor.layout==torch.strided)
            array=tensor.detach().numpy()
            parameters[name]={'dtype':'float32','shape':list(array.shape),'values':array.ravel().tolist()}
        document={'schema_version':1,'format':FORMAT,'binding':json.loads(_canonical(binding)),
                  'parameters':parameters}
        validate_candidate_ae_weights(document,binding)
        return document
    except CandidateAEWeightsError:
        raise
    except (KeyError,TypeError,ValueError,RuntimeError,AttributeError,OverflowError,RecursionError) as exc:
        raise CandidateAEWeightsError('INVALID_WEIGHTS') from exc


def rebuild_candidate_ae_from_json(document, expected_binding):
    """Copy checked arrays into a fresh fixed CPU topology; never executes a payload."""
    arrays=validate_candidate_ae_weights(document,expected_binding)
    network=build_candidate_ae_network(expected_binding['configuration']['input_width'])
    import torch
    try:
        with torch.no_grad():
            for name,parameter in network.named_parameters():
                parameter.copy_(torch.tensor(arrays[name],device='cpu',dtype=torch.float32))
                _require(parameter.detach().numpy().tobytes()==arrays[name].tobytes(),'WEIGHTS_REPLAY_MISMATCH')
        return network
    except CandidateAEWeightsError:
        raise
    except (KeyError,RuntimeError,TypeError,ValueError) as exc:
        raise CandidateAEWeightsError('WEIGHTS_REPLAY_MISMATCH') from exc
