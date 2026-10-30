"""Read-only AE JSON structure and stored arithmetic; never rebuilds a model."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from .candidate_artifacts import (CandidateArtifactError, load_verified_candidate_artifacts,
    _directory, _ordinary, _ancestors, _same, _deep_thaw)
from .candidate_autoencoder import MODEL_PROFILE_ID, CandidateAEError, _configuration, _calibrate
from .candidate_ae_weights import CandidateAEWeightsError, validate_candidate_ae_weights
from .candidate_cli import _unique_object, _reject_constant
from .candidate_evaluation import evaluate_candidate_predictions
from .candidate_run_snapshot import VerifiedCandidateRun

VERIFIER_PROFILE_ID='c17-i1-g13u-ae-run-verifier-v1'
MAX_WEIGHTS_BYTES=1024*1024
MAX_JSON_BYTES=16*1024*1024
MAX_TOTAL_BYTES=32*1024*1024
_FILES={'manifest.json','model-state.json','weights.json','scores.json','evaluation.json'}
_ARTIFACTS=_FILES-{'manifest.json'}
_COMMON={'schema_version','run_id','model_profile_id','evidence_kind','time_basis','policy_status',
    'scope','selected_policy','score_direction','value_space','feature_names','qualification_windows',
    'configuration','configuration_sha256','library_versions','provenance','preprocessing_state','runtime'}
_STATE=_COMMON|{'weights','fit_indices','calibration_indices','training_losses'}
_MANIFEST=_COMMON|{'status','artifacts','fit_indices','calibration_indices','training_losses'}
_SCORES=_COMMON|{'timestamps','segment_ids','partitions','current_input_valid','common_valid',
    'score_valid','scores','alarms','history_invalid_reason','threshold','calibration',
    'current_reconstruction_mse','history_deviation_reconstruction_mse','history_deviation_reconstruction_mse_status'}
_EVALUATION=_COMMON|{'scores','threshold','calibration','evaluation'}
_RUN_ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
_VERSION=re.compile(r'[A-Za-z0-9][A-Za-z0-9._+!-]{0,63}\Z')


class CandidateAERunArtifactError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


def _require(condition,code='INVALID_RUN_ARTIFACTS'):
    if not condition:raise CandidateAERunArtifactError(code)


def _identity(payload):
    return dict(sha256=hashlib.sha256(payload).hexdigest(),byte_count=len(payload))


def _float(text):
    number=float(text);_require(math.isfinite(number));return number


def _json(payload):
    value=json.loads(payload.decode('utf-8'),object_pairs_hook=_unique_object,
                     parse_constant=_reject_constant,parse_float=_float)
    _require(type(value) is dict)
    return value


def _read_package(directory):
    _directory(directory,_FILES)
    directory=directory.resolve(strict=True)
    stats={}
    for name in _FILES:
        path=directory/name;_ancestors(path);info=_ordinary(path)
        limit=MAX_WEIGHTS_BYTES if name=='weights.json' else MAX_JSON_BYTES
        _require(info.st_size<=limit,'RESOURCE_LIMIT');_require(info.st_size>0)
        stats[name]=info
    _require(sum(info.st_size for info in stats.values())<=MAX_TOTAL_BYTES,'RESOURCE_LIMIT')
    remaining=MAX_TOTAL_BYTES;data={}
    identity=lambda info:(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
    for name in ('manifest.json','model-state.json','scores.json','evaluation.json','weights.json'):
        path=directory/name
        limit=min(MAX_WEIGHTS_BYTES if name=='weights.json' else MAX_JSON_BYTES,remaining)
        with path.open('rb') as stream:payload=stream.read(limit+1)
        _require(len(payload)<=limit,'RESOURCE_LIMIT')
        after=_ordinary(path)
        _require(identity(stats[name])==identity(after) and len(payload)==after.st_size,'INTEGRITY_MISMATCH')
        remaining-=len(payload);data[name]=(payload,_json(payload))
    return data


def _versions(value):
    _require(type(value) is dict and set(value)=={'python','numpy','torch'}
             and all(type(v) is str and bool(_VERSION.fullmatch(v)) for v in value.values()))
    return value


def _runtime(value):
    _require(type(value) is dict and set(value)=={'device','torch_num_threads','torch_num_interop_threads'}
             and value['device']=='cpu'
             and all(type(value[k]) is int and value[k]>0 for k in ('torch_num_threads','torch_num_interop_threads')))
    return value


def _common(snapshot,run_id,configuration,versions,runtime):
    _require(snapshot.training_normal.any() and snapshot.calibration_normal.any())
    canonical=json.dumps(configuration,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return dict(schema_version=1,run_id=run_id,model_profile_id=MODEL_PROFILE_ID,
        evidence_kind='SYNTHETIC_ONLY',time_basis='synthetic_source_clock',policy_status='AUDIT_ONLY',
        scope='ENGINEERING_TOY_ONLY',selected_policy=snapshot.report['selected_policy'],
        score_direction='HIGHER_IS_MORE_ANOMALOUS',value_space='prepared',
        feature_names=list(snapshot.feature_names),qualification_windows=[15,30],configuration=configuration,
        configuration_sha256=hashlib.sha256(canonical).hexdigest(),library_versions=versions,runtime=runtime,
        provenance=_deep_thaw(snapshot.provenance),preprocessing_state=_deep_thaw(snapshot.preprocessing_state))


def _axis(values,common,*,applicable=True):
    _require(type(values) is list and len(values)==len(common))
    result=np.full(len(common),np.nan)
    for i,value in enumerate(values):
        if common[i] and applicable:
            _require(type(value) in (int,float) and math.isfinite(value) and value>=0)
            result[i]=value
        else:_require(value is None)
    return result


def _verify(run,records,inputs,source):
    data=_read_package(run)
    manifest,state,scores_doc,evaluation_doc,weights=(data[name][1] for name in
        ('manifest.json','model-state.json','scores.json','evaluation.json','weights.json'))
    _require(set(manifest)==_MANIFEST and manifest['status']=='COMPLETE'
             and set(state)==_STATE and set(scores_doc)==_SCORES and set(evaluation_doc)==_EVALUATION)
    run_id=manifest['run_id'];_require(type(run_id) is str and bool(_RUN_ID.fullmatch(run_id)))
    digests={name:_identity(payload) for name,(payload,_) in data.items()}
    _require(_same(manifest['artifacts'],{name:digests[name] for name in _ARTIFACTS})
             and _same(state['weights'],digests['weights.json'])
             and _same(evaluation_doc['scores'],digests['scores.json']),'INTEGRITY_MISMATCH')
    configuration=_configuration(manifest['configuration']['method'],manifest['configuration']['history_window'])
    method,window=configuration['method'],configuration['history_window']
    versions,runtime=_versions(manifest['library_versions']),_runtime(manifest['runtime'])
    snapshot=load_verified_candidate_artifacts(records,inputs,source_fixture=source)
    expected_common=_common(snapshot,run_id,configuration,versions,runtime)
    for document in (manifest,state,scores_doc,evaluation_doc):
        _require(_same({k:document[k] for k in _COMMON},expected_common),'INCOMPATIBLE_RUN')
    # This validates only JSON arrays and their binding, without importing torch.
    validate_candidate_ae_weights(weights,expected_common)
    losses=manifest['training_losses']
    _require(type(losses) is list and len(losses)==5
             and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in losses))
    qualification=dict(fit_indices=np.flatnonzero(snapshot.training_normal).tolist(),
        calibration_indices=np.flatnonzero(snapshot.calibration_normal).tolist(),training_losses=losses)
    _require(_same(state,dict(expected_common,weights=digests['weights.json'],**qualification))
             and _same({k:manifest[k] for k in qualification},qualification),'REPLAY_MISMATCH')
    common=snapshot.common_valid
    scores=_axis(scores_doc['scores'],common)
    current=_axis(scores_doc['current_reconstruction_mse'],common)
    historical=_axis(scores_doc['history_deviation_reconstruction_mse'],common,applicable=method=='history_ae')
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        expected_scores=current if method=='current_ae' else .5*current+.5*historical
        _require(np.isfinite(expected_scores[common]).all()
                 and np.array_equal(scores[common],expected_scores[common]),'REPLAY_MISMATCH')
        threshold,alarms,calibration=_calibrate(scores,common,snapshot.calibration_normal)
    expected_score=dict(expected_common,timestamps=[str(t) for t in snapshot.timestamps],
        segment_ids=snapshot.segment_ids.tolist(),partitions=snapshot.partitions.tolist(),
        current_input_valid=snapshot.row_valid.tolist(),common_valid=common.tolist(),score_valid=common.tolist(),
        scores=scores_doc['scores'],alarms=[bool(v) if keep else None for v,keep in zip(alarms,common)],
        current_reconstruction_mse=scores_doc['current_reconstruction_mse'],
        history_deviation_reconstruction_mse=scores_doc['history_deviation_reconstruction_mse'],
        history_deviation_reconstruction_mse_status='NOT_APPLICABLE' if method=='current_ae' else 'APPLICABLE',
        history_invalid_reason={str(h):list(v.invalid_reason) for h,v in snapshot.histories.items()},
        threshold=threshold,calibration=calibration)
    _require(_same(scores_doc,expected_score),'REPLAY_MISMATCH')
    evaluation=evaluate_candidate_predictions(labels=snapshot.labels,partitions=snapshot.partitions,
        score_valid=common,alarms=alarms,source_attack_label_present=snapshot.source_attack_label_present,
        score_origin_policy=snapshot.report['selected_policy'])
    _require(_same(evaluation_doc,dict(expected_common,scores=digests['scores.json'],threshold=threshold,
                                      calibration=calibration,evaluation=evaluation)),'REPLAY_MISMATCH')
    report=dict(schema_version=1,status='VERIFIED',verifier_profile_id=VERIFIER_PROFILE_ID,
        evidence_kind='SYNTHETIC_ONLY',policy_status='AUDIT_ONLY',scope='STORED_ARTIFACT_CONSISTENCY_ONLY',
        run_id=run_id,model_profile_id=MODEL_PROFILE_ID,selected_policy=snapshot.report['selected_policy'],
        method=method,history_window=window,minute_count=len(common),score_valid_count=int(common.sum()),
        fit_count=int(snapshot.training_normal.sum()),calibration_count=int(snapshot.calibration_normal.sum()),
        threshold=threshold,calibration=calibration,policies=evaluation['policies'],artifacts=digests,
        declared_library_versions=dict(versions),declared_runtime=dict(runtime),
        run_payload_bytes=sum(v['byte_count'] for v in digests.values()),
        checks=dict(byte_integrity='VERIFIED',upstream_lineage='VERIFIED',
            source_replay=snapshot.report['checks']['source_replay'],weights_json_structure='VERIFIED',
            stored_channel_score_relation='VERIFIED',stored_score_calibration='VERIFIED',
            strict_alarms='VERIFIED',evaluation='VERIFIED',model_deserialization='NOT_PERFORMED',
            network_reconstruction='NOT_PERFORMED',model_score_replay='NOT_CHECKED',training_execution='NOT_CHECKED',
            training_loss_replay='NOT_CHECKED',model_origin='NOT_AUTHENTICATED',
            library_versions='DECLARATION_CONSISTENT_ONLY'))
    return VerifiedCandidateRun(report,scores_doc)


def load_verified_candidate_ae_run(run_directory,record_directory,input_directory,*,source_fixture=None):
    """Load checked stored minute values, without rebuilding or executing a model."""
    try:
        return _verify(Path(run_directory),Path(record_directory),Path(input_directory),
                       None if source_fixture is None else Path(source_fixture))
    except CandidateAERunArtifactError:raise
    except CandidateArtifactError as exc:raise CandidateAERunArtifactError(exc.code) from exc
    except (CandidateAEError,CandidateAEWeightsError) as exc:raise CandidateAERunArtifactError('INCOMPATIBLE_RUN') from exc
    except OSError as exc:raise CandidateAERunArtifactError('INPUT_UNAVAILABLE') from exc
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,RecursionError) as exc:
        raise CandidateAERunArtifactError('INVALID_RUN_ARTIFACTS') from exc


def verify_candidate_ae_run(run_directory,record_directory,input_directory,*,source_fixture=None):
    """Return the original bounded consistency report, not model certification."""
    return load_verified_candidate_ae_run(run_directory,record_directory,input_directory,
                                         source_fixture=source_fixture).report_dict()
