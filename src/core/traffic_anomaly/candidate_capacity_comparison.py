"""Separate four-slot stored AE capacity context, without model execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .candidate_artifacts import CandidateArtifactError,_ancestors,_ordinary,_same
from .candidate_ae_run_artifacts import (load_verified_candidate_ae_run,CandidateAERunArtifactError,_COMMON)
from .candidate_comparison import (_read_manifest,_execution_controls,CandidateComparisonError,_SHARED)
from .candidate_ae_profiles import resolve_candidate_ae_configuration,strict_configuration_equal
from .candidate_capacity_contract import (CandidateCapacityComparisonError,COMPARISON_PROFILE_ID,SLOT_ORDER,
    SLOT_SPECS,COUNT_KEYS,POPULATION_KEYS,PROTOCOL_KEYS,LIMITATIONS,control_design_for_slots,
    validate_capacity_report,CHECKS)


def _need(condition,code='INVALID_CAPACITY_COMPARISON'):
    if not condition:raise CandidateCapacityComparisonError(code)


def _configuration(manifest,report):
    raw=manifest['configuration']
    config=resolve_candidate_ae_configuration(raw['method'],raw['history_window'],model_profile_id=manifest['model_profile_id'])
    _need(strict_configuration_equal(raw,config),'INCOMPATIBLE_RUN')
    for slot,(profile,method,window,verifier) in zip(SLOT_ORDER,SLOT_SPECS):
        if (config['model_profile_id'],config['method'],config['history_window'])==(profile,method,window):
            _need(type(report['model_profile_id']) is str and report['model_profile_id']==profile
                and type(report['verifier_profile_id']) is str and report['verifier_profile_id']==verifier
                and strict_configuration_equal(report['method'],method)
                and strict_configuration_equal(report['history_window'],window),'INCONSISTENT_VERIFICATION_SCOPE')
            return slot,config
    raise CandidateCapacityComparisonError('INCOMPATIBLE_RUN')


def _qualification(manifest,scores,report):
    n=report['minute_count']
    _need(type(n) is int and 1<=n<=10000)
    keys=('timestamps','segment_ids','partitions','current_input_valid','common_valid','score_valid','history_invalid_reason')
    value={key:scores[key] for key in keys}
    for key in keys[:-1]:_need(type(value[key]) is list and len(value[key])==n)
    for key in ('current_input_valid','common_valid','score_valid'):
        _need(all(type(item) is bool for item in value[key]))
    for key in ('fit_indices','calibration_indices'):
        items=manifest[key]
        _need(type(items) is list and all(type(i) is int and 0<=i<n for i in items)
            and items==sorted(set(items)))
        value[key]=items
    _need(not set(value['fit_indices']) & set(value['calibration_indices']))
    expected=dict(minute_count=n,score_valid_count=sum(value['score_valid']),
        fit_count=len(value['fit_indices']),calibration_count=len(value['calibration_indices']))
    _need(strict_configuration_equal({key:report[key] for key in COUNT_KEYS},expected),'INCOMPARABLE_QUALIFICATION')
    return value


def _compare(runs,records,inputs,source):
    _need(source is not None,'SOURCE_REQUIRED')
    _need(type(runs) in (list,tuple) and 2<=len(runs)<=4
        and all(isinstance(path,(str,Path)) for path in runs))
    directories=[]
    for requested in runs:
        path=Path(requested)
        _ancestors(path);_ordinary(path,directory=True)
        directories.append(path.resolve(strict=True))
    _need(len(set(directories))==len(directories),'DUPLICATE_RUN_DIRECTORY')
    rows,ids,slots=[],set(),set()
    reference=None
    for directory in directories:
        manifest,identity=_read_manifest(directory)
        loaded=load_verified_candidate_ae_run(directory,records,inputs,source_fixture=source)
        report,scores=loaded.report_dict(),loaded.scores_dict()
        _need(_same(identity,report['artifacts']['manifest.json']),'CHANGED_DURING_COMPARISON')
        _need(report['status']=='VERIFIED' and report['scope']=='STORED_ARTIFACT_CONSISTENCY_ONLY'
            and report['evidence_kind']=='SYNTHETIC_ONLY' and report['policy_status']=='AUDIT_ONLY'
            and strict_configuration_equal(report['checks'],CHECKS),'INCONSISTENT_VERIFICATION_SCOPE')
        slot,configuration=_configuration(manifest,report)
        _need(_same({key:manifest[key] for key in _COMMON},{key:scores[key] for key in _COMMON}),'INCOMPATIBLE_RUN')
        _need(_same(manifest['run_id'],report['run_id'])
            and _same(manifest['selected_policy'],report['selected_policy'])
            and _same(manifest['library_versions'],report['declared_library_versions'])
            and _same(manifest['runtime'],report['declared_runtime']),'INCOMPATIBLE_RUN')
        run_id=manifest['run_id']
        _need(run_id not in ids,'DUPLICATE_RUN_ID');_need(slot not in slots,'DUPLICATE_RUN_SLOT')
        ids.add(run_id);slots.add(slot)
        context={key:manifest[key] for key in _SHARED}
        protocol={key:configuration[key] for key in PROTOCOL_KEYS}
        counts={key:report[key] for key in COUNT_KEYS}
        population={policy:{key:report['policies'][policy][key] for key in POPULATION_KEYS}
                    for policy in ('P_U','P_B','P_A')}
        qualification=_qualification(manifest,scores,report)
        if reference is None:reference=context,protocol,counts,population,qualification
        else:
            _need(_same(context,reference[0]),'INCOMPARABLE_UPSTREAM')
            _need(_same(protocol,reference[1]) and _same(counts,reference[2])
                and _same(population,reference[3]) and _same(qualification,reference[4]),'INCOMPARABLE_QUALIFICATION')
        rows.append(dict(slot=slot,run_id=run_id,model_profile_id=report['model_profile_id'],
            verifier_profile_id=report['verifier_profile_id'],configuration=configuration,
            configuration_sha256=manifest['configuration_sha256'],library_versions=report['declared_library_versions'],
            runtime=report['declared_runtime'],architecture=configuration['architecture'],parameter_count=configuration['parameter_count'],
            parameter_count_reason=None,threshold=report['threshold'],calibration=report['calibration'],policies=report['policies'],
            actual_five_artifacts=report['artifacts'],verification_checks=report['checks'],verification_scope=report['scope']))
    _need(SLOT_ORDER[1] in slots and any(slot in slots for slot in SLOT_ORDER[2:]),'REQUIRED_CAPACITY_CONTROLS_MISSING')
    rows.sort(key=lambda row:SLOT_ORDER.index(row['slot']))
    included=[slot for slot in SLOT_ORDER if slot in slots]
    context,protocol,counts,population,qualification=reference
    encoded=json.dumps(qualification,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    shared=dict(selected_policy=context['selected_policy'],source_replay='VERIFIED',feature_names=context['feature_names'],
        qualification_windows=context['qualification_windows'],five_provenance=context['provenance'],
        preprocessing_identity=context['provenance']['preprocess'],preprocessing_state=context['preprocessing_state'],
        qualification_protocol=protocol,qualification_axis_identity=dict(sha256=hashlib.sha256(encoded).hexdigest(),byte_count=len(encoded)),
        **counts,test_denominators_by_policy=population)
    result=dict(schema_version=1,comparison_profile_id=COMPARISON_PROFILE_ID,status='DATA_QUALIFICATION_ALIGNED',
        evidence_kind='SYNTHETIC_ONLY',policy_status='AUDIT_ONLY',scope='SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY',
        included_slots=included,missing_slots=[slot for slot in SLOT_ORDER if slot not in slots],
        shared_context=shared,runs=rows,control_design=control_design_for_slots(included),
        limitations=dict(LIMITATIONS,execution_controls=_execution_controls(rows)))
    validate_capacity_report(result)
    return result


def compare_candidate_ae_capacity_runs(runs,record_directory,input_directory,*,source_fixture):
    """Admit each explicit AE run once; source is required, training is not checked.

    The extra bounded manifest read is joined to the loader's actual identity.
    Constructing a VerifiedCandidateRun is not an authentication capability.
    """
    try:
        return _compare(runs,record_directory,input_directory,source_fixture)
    except CandidateCapacityComparisonError:raise
    except (CandidateArtifactError,CandidateAERunArtifactError,CandidateComparisonError) as error:
        raise CandidateCapacityComparisonError(error.code) from None
    except OSError:
        raise CandidateCapacityComparisonError('INPUT_UNAVAILABLE') from None
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError,RecursionError,RuntimeError):
        raise CandidateCapacityComparisonError('INVALID_CAPACITY_COMPARISON') from None
