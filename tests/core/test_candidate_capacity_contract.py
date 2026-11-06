"""Pure declared-report consistency; hand values do not certify admission."""
from copy import deepcopy
import hashlib
import json

import pytest

from traffic_anomaly import candidate_capacity_contract as c

REASONS={
    'precision':'No positive predictions on scored normal or attack test minutes.',
    'recall':'No scored attack test minutes.',
    'f1':'No scored attack test minutes or positive predictions on scored labeled test minutes.',
    'fpr':'No scored normal test minutes.',
    'fnr':'No scored attack test minutes.',
}


@pytest.fixture
def report():
    identity=dict(sha256='0'*64,byte_count=1)
    slots=list(c.SLOT_ORDER[1:3])
    population=dict(calendar_test_minutes=6,scored_test_minutes=6,excluded_unscored_test_minutes=0,
        normal_minutes=4,attack_minutes=1,unknown_minutes=1,unknown_source_attack_present=1)
    policy=dict(**population,confusion_counts=dict(tp=1,fp=1,tn=3,fn=0),
        metrics=dict(precision=.5,recall=1.,f1=2/3,fpr=.25,fnr=0.),undefined_reasons={})
    default=c.resolve_candidate_ae_configuration('current_ae')
    provenance={key:deepcopy(identity) for key in c.PROVENANCE_KEYS}
    provenance['source_fixture']=dict(sha256=c.CAPACITY492_SOURCE_SHA256,byte_count=c.CAPACITY492_SOURCE_BYTE_COUNT)
    shared=dict(selected_policy='P_U',source_replay='VERIFIED',feature_names=list(c.G13U_FEATURE_NAMES),
        qualification_windows=[15,30],five_provenance=provenance,preprocessing_identity=deepcopy(identity),
        preprocessing_state=dict(schema_version=1,profile_id=c.PROFILE_ID,evidence_kind='SYNTHETIC_ONLY',
            transform='log1p_standard_ddof0',feature_names=list(c.G13U_FEATURE_NAMES),mean=[0.]*13,scale=[1.]*13,
            n_samples_seen=6,fit_window=30),qualification_protocol={key:default[key] for key in c.PROTOCOL_KEYS},
        qualification_axis_identity=deepcopy(identity),minute_count=144,score_valid_count=24,fit_count=6,calibration_count=6,
        test_denominators_by_policy={key:deepcopy(population) for key in ('P_U','P_B','P_A')})
    rows=[]
    for slot in slots:
        profile,method,window,verifier=c.SLOT_SPECS[c.SLOT_ORDER.index(slot)]
        config=c.resolve_candidate_ae_configuration(method,window,model_profile_id=profile)
        digest=hashlib.sha256(json.dumps(config,allow_nan=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        rows.append(dict(slot=slot,run_id=slot,model_profile_id=profile,verifier_profile_id=verifier,
            configuration=config,configuration_sha256=digest,library_versions=dict(python='3.14',numpy='2.5',torch='2.14'),
            runtime=dict(device='cpu',torch_num_threads=1,torch_num_interop_threads=1),architecture=config['architecture'],
            parameter_count=config['parameter_count'],parameter_count_reason=None,threshold=1.,
            calibration=dict(sample_count=6,quantile=.99,method='linear',comparison='STRICT_GREATER',
                order_position_zero_based=4.95,strictly_above_count=1,equal_count=0),
            policies={key:deepcopy(policy) for key in ('P_U','P_B','P_A')},
            actual_five_artifacts={key:deepcopy(identity) for key in c.ARTIFACT_NAMES},
            verification_checks=deepcopy(c.CHECKS),verification_scope='STORED_ARTIFACT_CONSISTENCY_ONLY'))
    return dict(schema_version=1,comparison_profile_id=c.COMPARISON_PROFILE_ID,status='DATA_QUALIFICATION_ALIGNED',
        evidence_kind='SYNTHETIC_ONLY',policy_status='AUDIT_ONLY',scope='SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY',
        included_slots=slots,missing_slots=[slot for slot in c.SLOT_ORDER if slot not in slots],shared_context=shared,runs=rows,
        control_design=c.control_design_for_slots(slots),limitations=dict(c.LIMITATIONS,execution_controls='SHARED_DECLARATIONS_CONSISTENT_ONLY'))


@pytest.mark.parametrize('window,valid',[(30,True),(15,False),(30.,False),(True,False),('30',False),(None,False)])
def test_preprocessing_fit_window_is_exact_admitted_30(report,window,valid):
    report['shared_context']['preprocessing_state']['fit_window']=window
    if valid:c.validate_capacity_report(report)
    else:
        with pytest.raises(c.CandidateCapacityComparisonError):c.validate_capacity_report(report)


@pytest.mark.parametrize('change,status,valid',[
    ('none','SHARED_DECLARATIONS_CONSISTENT_ONLY',True),
    ('none','DECLARED_EXECUTION_CONTROLS_DIFFER',False),
    ('threads','SHARED_DECLARATIONS_CONSISTENT_ONLY',False),
    ('threads','DECLARED_EXECUTION_CONTROLS_DIFFER',True),
    ('versions','SHARED_DECLARATIONS_CONSISTENT_ONLY',False),
    ('versions','DECLARED_EXECUTION_CONTROLS_DIFFER',True),
    ('both_same_threads','SHARED_DECLARATIONS_CONSISTENT_ONLY',True),
    ('both_same_threads','DECLARED_EXECUTION_CONTROLS_DIFFER',False)])
def test_execution_controls_status_matches_only_declared_rows(report,change,status,valid):
    if change=='threads':report['runs'][1]['runtime']['torch_num_threads']=2
    elif change=='versions':report['runs'][1]['library_versions']['torch']='2.14-different'
    elif change=='both_same_threads':
        for row in report['runs']:row['runtime']['torch_num_threads']=2
    report['limitations']['execution_controls']=status
    if valid:c.validate_capacity_report(report)
    else:
        with pytest.raises(c.CandidateCapacityComparisonError):c.validate_capacity_report(report)


# Literal domains from the existing project definitions, not production scoring.
DOMAINS=[
    ('precision',dict(tp=0,fp=0,tn=4,fn=1),dict(precision=None,recall=0.,f1=0.,fpr=0.,fnr=1.)),
    ('recall',dict(tp=0,fp=1,tn=3,fn=0),dict(precision=0.,recall=None,f1=0.,fpr=.25,fnr=None)),
    ('fnr',dict(tp=0,fp=1,tn=3,fn=0),dict(precision=0.,recall=None,f1=0.,fpr=.25,fnr=None)),
    ('f1',dict(tp=0,fp=0,tn=4,fn=0),dict(precision=None,recall=None,f1=None,fpr=0.,fnr=None)),
    ('fpr',dict(tp=1,fp=0,tn=0,fn=1),dict(precision=1.,recall=.5,f1=2/3,fpr=None,fnr=.5)),
]


def set_population_and_metrics(report,counts,metrics):
    normal,attack=counts['fp']+counts['tn'],counts['tp']+counts['fn']
    population=dict(calendar_test_minutes=6,scored_test_minutes=6,excluded_unscored_test_minutes=0,
        normal_minutes=normal,attack_minutes=attack,unknown_minutes=6-normal-attack,unknown_source_attack_present=0)
    for policy in ('P_U','P_B','P_A'):
        report['shared_context']['test_denominators_by_policy'][policy]=deepcopy(population)
        for row in report['runs']:
            row['policies'][policy]=dict(**population,confusion_counts=deepcopy(counts),metrics=deepcopy(metrics),
                undefined_reasons={key:REASONS[key] for key,value in metrics.items() if value is None})


@pytest.mark.parametrize('metric',list(REASONS))
def test_metric_cannot_be_null_with_nonzero_project_denominator(report,metric):
    value=report['runs'][0]['policies']['P_U']
    value['metrics'][metric]=None;value['undefined_reasons'][metric]=REASONS[metric]
    with pytest.raises(c.CandidateCapacityComparisonError):c.validate_capacity_report(report)


@pytest.mark.parametrize('metric,counts,metrics',DOMAINS,ids=[item[0] for item in DOMAINS])
def test_metric_cannot_be_defined_with_zero_project_denominator(report,metric,counts,metrics):
    set_population_and_metrics(report,counts,metrics)
    c.validate_capacity_report(report)  # The legitimate null and literal zeros pass.
    value=report['runs'][0]['policies']['P_U']
    value['metrics'][metric]=0.;value['undefined_reasons'].pop(metric)
    with pytest.raises(c.CandidateCapacityComparisonError):c.validate_capacity_report(report)


@pytest.mark.parametrize('metric,counts,metrics',DOMAINS,ids=[item[0] for item in DOMAINS])
def test_metric_null_reason_is_exact_and_present_only_for_null(report,metric,counts,metrics):
    set_population_and_metrics(report,counts,metrics)
    original=deepcopy(report);c.validate_capacity_report(report)
    assert report==original
    report['runs'][0]['policies']['P_U']['undefined_reasons'][metric]='wrong reason'
    with pytest.raises(c.CandidateCapacityComparisonError):c.validate_capacity_report(report)


@pytest.mark.parametrize('metric',list(REASONS))
def test_defined_metric_cannot_carry_an_undefined_reason(report,metric):
    report['runs'][0]['policies']['P_U']['undefined_reasons'][metric]=REASONS[metric]
    with pytest.raises(c.CandidateCapacityComparisonError):c.validate_capacity_report(report)


def test_existing_f1_domain_allows_zero_with_false_positive_but_no_attacks(report):
    # F1 denominator is 2TP+FP+FN=1, although recall/FNR have no attack domain.
    set_population_and_metrics(report,dict(tp=0,fp=1,tn=3,fn=0),
        dict(precision=0.,recall=None,f1=0.,fpr=.25,fnr=None))
    original=deepcopy(report);c.validate_capacity_report(report)
    assert report==original


def test_all_unknown_population_has_all_five_metrics_null(report):
    set_population_and_metrics(report,dict(tp=0,fp=0,tn=0,fn=0),
        dict(precision=None,recall=None,f1=None,fpr=None,fnr=None))
    original=deepcopy(report);c.validate_capacity_report(report)
    assert report==original
