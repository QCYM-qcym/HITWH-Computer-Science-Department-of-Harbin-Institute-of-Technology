"""One bounded report contract for the separate fixed AE capacity group.

This checks returned JSON structure, fixed configurations and saved-population
shapes. It never admits packages, authenticates provenance or replays models,
calibration, history or evaluation. Future consumers can reuse this contract.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from .candidate_ae_profiles import (MODEL_PROFILE_ID,CAPACITY492_MODEL_PROFILE_ID,
    CAPACITY492_SOURCE_SHA256,CAPACITY492_SOURCE_BYTE_COUNT,
    resolve_candidate_ae_configuration,strict_configuration_equal)
from .candidate_ae_run_artifacts import VERIFIER_PROFILE_ID,CAPACITY_VERIFIER_PROFILE_ID
from .candidate_evaluation import _UNDEFINED_REASONS
from .candidate_inputs import G13U_FEATURE_NAMES,PROFILE_ID,MAX_MINUTES
from .candidate_comparison import _execution_controls

COMPARISON_PROFILE_ID='c17-i1-g13u-ae-capacity-comparison-context-v1'
SLOT_ORDER=('current_ae13','current_ae13_capacity492','history_ae26_h15','history_ae26_h30')
SLOT_SPECS=((MODEL_PROFILE_ID,'current_ae',None,VERIFIER_PROFILE_ID),
    (CAPACITY492_MODEL_PROFILE_ID,'current_ae',None,CAPACITY_VERIFIER_PROFILE_ID),
    (MODEL_PROFILE_ID,'history_ae',15,VERIFIER_PROFILE_ID),
    (MODEL_PROFILE_ID,'history_ae',30,VERIFIER_PROFILE_ID))
POPULATION_KEYS=('calendar_test_minutes','scored_test_minutes','excluded_unscored_test_minutes',
    'normal_minutes','attack_minutes','unknown_minutes','unknown_source_attack_present')
COUNT_KEYS=('minute_count','score_valid_count','fit_count','calibration_count')
PROTOCOL_KEYS=('fit_scope','calibration_scope','quantile','quantile_method','alarm_comparison','preprocessing_fit_provenance')
PROVENANCE_KEYS=('record_manifest','input_manifest','source_fixture','minute_fixture','preprocess')
ARTIFACT_NAMES=('manifest.json','model-state.json','scores.json','evaluation.json','weights.json')
CHECKS=dict(byte_integrity='VERIFIED',upstream_lineage='VERIFIED',source_replay='VERIFIED',
    weights_json_structure='VERIFIED',stored_channel_score_relation='VERIFIED',
    stored_score_calibration='VERIFIED',strict_alarms='VERIFIED',evaluation='VERIFIED',
    model_deserialization='NOT_PERFORMED',network_reconstruction='NOT_PERFORMED',
    model_score_replay='NOT_CHECKED',training_execution='NOT_CHECKED',training_loss_replay='NOT_CHECKED',
    model_origin='NOT_AUTHENTICATED',library_versions='DECLARATION_CONSISTENT_ONLY')
LIMITATIONS=dict(capacity_control='NOT_COMPARABLE',history_causal_attribution='NOT_COMPARABLE',
    cross_model_score_scale='NOT_COMPARABLE',ranking='NOT_PERFORMED',statistical_significance='NOT_PERFORMED',
    model_execution='NOT_CHECKED',model_origin='NOT_AUTHENTICATED',
    capacity_control_reason='PARAMETER_COUNT_NEAR_MATCH_DOES_NOT_ESTABLISH_EQUAL_EFFECTIVE_CAPACITY')
SAFE_ERROR_CODES=frozenset(('INVALID_CAPACITY_COMPARISON','INVALID_CAPACITY_REPORT','INVALID_ARGUMENTS',
    'SOURCE_REQUIRED','FIXED_SOURCE_MISMATCH','INPUT_UNAVAILABLE','RESOURCE_LIMIT','INTEGRITY_MISMATCH',
    'INCOMPATIBLE_RUN','INVALID_RUN_ARTIFACTS','INCOMPATIBLE_PACKAGE','INVALID_PACKAGE','REPLAY_MISMATCH',
    'DUPLICATE_RUN_DIRECTORY','DUPLICATE_RUN_ID','DUPLICATE_RUN_SLOT','CHANGED_DURING_COMPARISON',
    'INCONSISTENT_VERIFICATION_SCOPE','INCOMPARABLE_UPSTREAM','INCOMPARABLE_QUALIFICATION',
    'REQUIRED_CAPACITY_CONTROLS_MISSING','OUTPUT_ERROR'))
_ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
_VERSION=re.compile(r'[A-Za-z0-9][A-Za-z0-9._+!-]{0,63}\Z')
_SHA=re.compile(r'[0-9a-f]{64}\Z')


class CandidateCapacityComparisonError(ValueError):
    def __init__(self,code):
        self.code=code if type(code) is str and code in SAFE_ERROR_CODES else 'INVALID_CAPACITY_COMPARISON'
        super().__init__(self.code)


def _need(condition,code='INVALID_CAPACITY_REPORT'):
    if not condition:raise CandidateCapacityComparisonError(code)


def _keys(value,keys):
    _need(type(value) is dict and set(value)==set(keys))


def _count(value,maximum=MAX_MINUTES,positive=False):
    _need(type(value) is int and int(positive)<=value<=maximum)


def _finite(value,minimum=0.,maximum=float('inf')):
    _need(type(value) in (int,float) and math.isfinite(value) and minimum<=value<=maximum)


def _identity(value,maximum=16*1024*1024):
    _keys(value,('sha256','byte_count'))
    _need(type(value['sha256']) is str and _SHA.fullmatch(value['sha256']) is not None)
    _count(value['byte_count'],maximum,positive=True)


def _bounded_json(value,depth=0,counter=None):
    if counter is None:counter=[0]
    counter[0]+=1
    _need(depth<=16 and counter[0]<=20000,'RESOURCE_LIMIT')
    kind=type(value)
    if kind is dict:
        _need(len(value)<=128,'RESOURCE_LIMIT')
        for key,item in value.items():
            _need(type(key) is str and len(key)<=128)
            _bounded_json(item,depth+1,counter)
    elif kind is list:
        _need(len(value)<=MAX_MINUTES,'RESOURCE_LIMIT')
        for item in value:_bounded_json(item,depth+1,counter)
    elif kind is str:_need(len(value)<=1024,'RESOURCE_LIMIT')
    elif kind is float:_need(math.isfinite(value))
    elif kind is int:_need(abs(value)<=2**53-1)
    else:_need(kind in (bool,type(None)))


def control_design_for_slots(slots):
    histories=[slot for slot in SLOT_ORDER[2:] if slot in slots]
    return dict(fixed_current_profile=CAPACITY492_MODEL_PROFILE_ID,reference_parameter_count=509,
        parameter_count_formula='SUM_LINEAR_WEIGHTS_AND_BIASES_V1',no_history_input=True,
        near_count=dict(absolute_difference=17,relative_difference=17/509,tolerance=.05,status='PREDEFINED_COUNT_ONLY'),
        same_hidden_width_pairs=[[SLOT_ORDER[0],slot] for slot in histories if SLOT_ORDER[0] in slots],
        near_parameter_count_pairs=[[SLOT_ORDER[1],slot] for slot in histories if SLOT_ORDER[1] in slots],
        same_hidden_width_control_present=bool(SLOT_ORDER[0] in slots and histories),
        controls_materials_complete=all(slot in slots for slot in SLOT_ORDER))


def _population(value,minute_count,score_count):
    _keys(value,POPULATION_KEYS)
    for count in value.values():_count(count)
    _need(value['calendar_test_minutes']<=minute_count and value['scored_test_minutes']<=score_count
        and value['calendar_test_minutes']==value['scored_test_minutes']+value['excluded_unscored_test_minutes']
        and value['normal_minutes']+value['attack_minutes']+value['unknown_minutes']==value['scored_test_minutes']
        and value['unknown_source_attack_present']<=value['unknown_minutes'])


def validate_capacity_report(report):
    """Validate the sole report shape without file IO or saved-score recompute."""
    _bounded_json(report)
    _keys(report,('schema_version','comparison_profile_id','status','evidence_kind','policy_status','scope',
        'included_slots','missing_slots','shared_context','runs','control_design','limitations'))
    fixed=dict(schema_version=1,comparison_profile_id=COMPARISON_PROFILE_ID,status='DATA_QUALIFICATION_ALIGNED',
        evidence_kind='SYNTHETIC_ONLY',policy_status='AUDIT_ONLY',scope='SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY')
    _need(strict_configuration_equal({key:report[key] for key in fixed},fixed))
    rows,slots=report['runs'],report['included_slots']
    _need(type(rows) is list and 2<=len(rows)<=4 and type(slots) is list
        and all(type(slot) is str for slot in slots) and len(set(slots))==len(slots)
        and slots==[slot for slot in SLOT_ORDER if slot in slots]
        and report['missing_slots']==[slot for slot in SLOT_ORDER if slot not in slots]
        and SLOT_ORDER[1] in slots and any(slot in slots for slot in SLOT_ORDER[2:]))
    _need(strict_configuration_equal(report['control_design'],control_design_for_slots(slots)))
    shared=report['shared_context']
    _keys(shared,('selected_policy','source_replay','feature_names','qualification_windows','five_provenance',
        'preprocessing_identity','preprocessing_state','qualification_protocol','qualification_axis_identity',
        *COUNT_KEYS,'test_denominators_by_policy'))
    _need(shared['selected_policy'] in ('P_U','P_B','P_A') and shared['source_replay']=='VERIFIED'
        and strict_configuration_equal(shared['feature_names'],list(G13U_FEATURE_NAMES))
        and strict_configuration_equal(shared['qualification_windows'],[15,30]))
    for key in COUNT_KEYS:_count(shared[key],positive=key!='score_valid_count')
    _need(shared['score_valid_count']<=shared['minute_count']
        and shared['fit_count']+shared['calibration_count']<=shared['score_valid_count'])
    _identity(shared['qualification_axis_identity'])
    _keys(shared['five_provenance'],PROVENANCE_KEYS)
    for value in shared['five_provenance'].values():_identity(value)
    _need(strict_configuration_equal(shared['five_provenance']['source_fixture'],
        dict(sha256=CAPACITY492_SOURCE_SHA256,byte_count=CAPACITY492_SOURCE_BYTE_COUNT)))
    _need(strict_configuration_equal(shared['preprocessing_identity'],shared['five_provenance']['preprocess']))
    default=resolve_candidate_ae_configuration('current_ae')
    _need(strict_configuration_equal(shared['qualification_protocol'],{key:default[key] for key in PROTOCOL_KEYS}))
    state=shared['preprocessing_state']
    _keys(state,('schema_version','profile_id','evidence_kind','transform','feature_names','mean','scale','n_samples_seen','fit_window'))
    _need(strict_configuration_equal({key:state[key] for key in ('schema_version','profile_id','evidence_kind','transform','feature_names')},
        dict(schema_version=1,profile_id=PROFILE_ID,evidence_kind='SYNTHETIC_ONLY',transform='log1p_standard_ddof0',feature_names=list(G13U_FEATURE_NAMES))))
    for key in ('mean','scale'):
        _need(type(state[key]) is list and len(state[key])==13)
        for value in state[key]:_finite(value,minimum=-float('inf') if key=='mean' else 0.)
    _need(all(value>0 for value in state['scale']))
    _count(state['n_samples_seen'],positive=True)
    _need(type(state['fit_window']) is int and state['fit_window']==30)
    populations=shared['test_denominators_by_policy']
    _keys(populations,('P_U','P_B','P_A'))
    for value in populations.values():_population(value,shared['minute_count'],shared['score_valid_count'])
    _need(len(rows)==len(slots) and all(type(row) is dict for row in rows)
        and [row.get('slot') for row in rows]==slots)
    ids=set()
    for row,slot in zip(rows,slots):
        _keys(row,('slot','run_id','model_profile_id','verifier_profile_id','configuration','configuration_sha256',
            'library_versions','runtime','architecture','parameter_count','parameter_count_reason','threshold','calibration',
            'policies','actual_five_artifacts','verification_checks','verification_scope'))
        profile,method,window,verifier=SLOT_SPECS[SLOT_ORDER.index(slot)]
        config=resolve_candidate_ae_configuration(method,window,model_profile_id=profile)
        _need(type(row['run_id']) is str and _ID.fullmatch(row['run_id']) is not None and row['run_id'] not in ids)
        ids.add(row['run_id'])
        _need(row['model_profile_id']==profile and row['verifier_profile_id']==verifier
            and strict_configuration_equal(row['configuration'],config)
            and strict_configuration_equal(row['architecture'],config['architecture'])
            and type(row['parameter_count']) is int and row['parameter_count']==config['parameter_count']
            and row['parameter_count_reason'] is None
            and row['verification_scope']=='STORED_ARTIFACT_CONSISTENCY_ONLY'
            and strict_configuration_equal(row['verification_checks'],CHECKS))
        canonical=json.dumps(config,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')
        _need(row['configuration_sha256']==hashlib.sha256(canonical).hexdigest())
        _keys(row['library_versions'],('python','numpy','torch'))
        _need(all(type(value) is str and _VERSION.fullmatch(value) is not None for value in row['library_versions'].values()))
        _keys(row['runtime'],('device','torch_num_threads','torch_num_interop_threads'))
        _need(row['runtime']['device']=='cpu')
        for key in ('torch_num_threads','torch_num_interop_threads'):_count(row['runtime'][key],2**31-1,positive=True)
        _keys(row['actual_five_artifacts'],ARTIFACT_NAMES)
        for name,value in row['actual_five_artifacts'].items():_identity(value,1024*1024 if name=='weights.json' else 16*1024*1024)
        _need(sum(value['byte_count'] for value in row['actual_five_artifacts'].values())<=32*1024*1024)
        _finite(row['threshold'])
        cal=row['calibration']
        _keys(cal,('sample_count','quantile','method','comparison','order_position_zero_based','strictly_above_count','equal_count'))
        _need(strict_configuration_equal({key:cal[key] for key in ('quantile','method','comparison')},
            dict(quantile=.99,method='linear',comparison='STRICT_GREATER')))
        _count(cal['sample_count'],positive=True)
        _need(cal['sample_count']==shared['calibration_count'])
        _finite(cal['order_position_zero_based'],maximum=cal['sample_count'])
        for key in ('strictly_above_count','equal_count'):_count(cal[key],cal['sample_count'])
        _need(cal['strictly_above_count']+cal['equal_count']<=cal['sample_count'])
        _keys(row['policies'],('P_U','P_B','P_A'))
        for policy,value in row['policies'].items():
            _keys(value,(*POPULATION_KEYS,'confusion_counts','metrics','undefined_reasons'))
            _need(strict_configuration_equal({key:value[key] for key in POPULATION_KEYS},populations[policy]))
            counts=value['confusion_counts'];_keys(counts,('tp','fp','tn','fn'))
            for count in counts.values():_count(count)
            _need(counts['tp']+counts['fn']==value['attack_minutes'] and counts['fp']+counts['tn']==value['normal_minutes'])
            metrics=value['metrics'];_keys(metrics,_UNDEFINED_REASONS)
            for metric in metrics.values():
                if metric is not None:_finite(metric,maximum=1.)
            # Only validate each saved metric's definition domain. Retain the
            # original numeric ratio; do not rerun evaluation or predictions.
            tp,fp,tn,fn=(counts[key] for key in ('tp','fp','tn','fn'))
            denominators=dict(precision=tp+fp,recall=tp+fn,f1=2*tp+fp+fn,fpr=fp+tn,fnr=tp+fn)
            _need(all((metrics[key] is None)==(denominator==0) for key,denominator in denominators.items()))
            undefined={key:reason for key,reason in _UNDEFINED_REASONS.items() if metrics[key] is None}
            _need(strict_configuration_equal(value['undefined_reasons'],undefined))
    limits=report['limitations']
    _keys(limits,(*LIMITATIONS,'execution_controls'))
    _need(strict_configuration_equal({key:limits[key] for key in LIMITATIONS},LIMITATIONS)
        and limits['execution_controls']==_execution_controls(rows))
