"""Read-only stored-score consistency; weights are bytes, never executable models."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from .candidate_artifacts import (
    CandidateArtifactError, load_verified_candidate_artifacts,
    _ancestors, _ordinary, _directory, _same, _deep_thaw,
)
from .candidate_cli import _unique_object, _reject_constant
from .candidate_evaluation import evaluate_candidate_predictions
from .candidate_iforest import MODEL_PROFILE_ID, CandidateIFError, _configuration, calibrate_candidate_scores

MAX_MODEL_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
VERIFIER_PROFILE_ID = 'c17-i1-g13u-iforest-run-verifier-v1'
_RUN_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
_VERSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+!-]{0,63}\Z')
_FILES = {'manifest.json', 'model-state.json', 'weights.bin', 'scores.json', 'evaluation.json'}
_ARTIFACTS = _FILES - {'manifest.json'}
_COMMON = {'schema_version', 'run_id', 'model_profile_id', 'evidence_kind', 'time_basis',
           'policy_status', 'scope', 'selected_policy', 'score_direction', 'value_space',
           'feature_names', 'qualification_windows', 'configuration', 'configuration_sha256',
           'library_versions', 'provenance', 'preprocessing_state'}
_STATE = _COMMON | {'model_type', 'weights', 'fit_indices', 'calibration_indices'}
_SCORES = _COMMON | {'timestamps', 'segment_ids', 'partitions', 'current_input_valid', 'common_valid',
                     'score_valid', 'scores', 'alarms', 'history_invalid_reason', 'threshold', 'calibration'}
_EVALUATION = _COMMON | {'scores', 'threshold', 'calibration', 'evaluation'}


class CandidateRunArtifactError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code='INVALID_RUN_ARTIFACTS'):
    if not condition:
        raise CandidateRunArtifactError(code)


def _identity(payload):
    return dict(sha256=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))


def _float(value):
    result = float(value)
    _require(math.isfinite(result))
    return result


def _json(payload):
    value = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_object,
                       parse_constant=_reject_constant, parse_float=_float)
    _require(isinstance(value, dict))
    return value


def _read_package(directory):
    _directory(directory, _FILES)
    # Only resolve after the lexical ancestor/link checks above.
    directory = directory.resolve(strict=True)
    # Check all declared physical sizes before parsing any run JSON.
    info = {}
    for name in _FILES:
        path = directory / name
        _ancestors(path)
        current = _ordinary(path)
        limit = MAX_MODEL_BYTES if name == 'weights.bin' else MAX_JSON_BYTES
        _require(current.st_size <= limit, 'RESOURCE_LIMIT')
        _require(current.st_size > 0)
        info[name] = current
    _require(sum(value.st_size for value in info.values()) <= MAX_TOTAL_BYTES, 'RESOURCE_LIMIT')
    remaining, data = MAX_TOTAL_BYTES, {}
    for name in ('manifest.json', 'model-state.json', 'scores.json', 'evaluation.json', 'weights.bin'):
        path = directory / name
        limit = min(MAX_MODEL_BYTES if name == 'weights.bin' else MAX_JSON_BYTES, remaining)
        with path.open('rb') as stream:
            payload = stream.read(limit + 1)
        _require(len(payload) <= limit, 'RESOURCE_LIMIT')
        after = _ordinary(path)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        _require(identity(info[name]) == identity(after) and len(payload) == after.st_size,
                 'INTEGRITY_MISMATCH')
        remaining -= len(payload)
        data[name] = (payload, None if name == 'weights.bin' else _json(payload))
    return data


def _versions(value):
    _require(isinstance(value, dict) and set(value) == {'python', 'numpy', 'scikit_learn', 'joblib'}
             and all(isinstance(version, str) and bool(_VERSION.fullmatch(version)) for version in value.values()))
    return value


def _common(snapshot, run_id, versions):
    n_train = int(snapshot.training_normal.sum())
    _require(n_train > 0 and snapshot.calibration_normal.any())
    configuration = _configuration(n_train)
    canonical = json.dumps(configuration, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return dict(schema_version=1, run_id=run_id, model_profile_id=MODEL_PROFILE_ID,
        evidence_kind='SYNTHETIC_ONLY', time_basis='synthetic_source_clock', policy_status='AUDIT_ONLY',
        scope='ENGINEERING_TOY_ONLY', selected_policy=snapshot.report['selected_policy'],
        score_direction='HIGHER_IS_MORE_ANOMALOUS', value_space='prepared',
        feature_names=list(snapshot.feature_names), qualification_windows=[15, 30],
        configuration=configuration, configuration_sha256=hashlib.sha256(canonical).hexdigest(),
        library_versions=versions, provenance=_deep_thaw(snapshot.provenance),
        preprocessing_state=_deep_thaw(snapshot.preprocessing_state))


def _verify(run, records, inputs, source):
    data = _read_package(run)
    manifest, state, score_doc, evaluation_doc = (data[name][1] for name in
        ('manifest.json', 'model-state.json', 'scores.json', 'evaluation.json'))
    _require(set(manifest) == _COMMON | {'status', 'artifacts'} and manifest['status'] == 'COMPLETE')
    _require(set(state) == _STATE and set(score_doc) == _SCORES and set(evaluation_doc) == _EVALUATION)
    run_id = manifest['run_id']
    _require(isinstance(run_id, str) and bool(_RUN_ID.fullmatch(run_id)))
    _require(isinstance(manifest['artifacts'], dict) and set(manifest['artifacts']) == _ARTIFACTS)
    digests = {name: _identity(payload) for name, (payload, _) in data.items()}
    _require(_same(manifest['artifacts'], {name: digests[name] for name in _ARTIFACTS})
             and _same(state['weights'], digests['weights.bin'])
             and _same(evaluation_doc['scores'], digests['scores.json']), 'INTEGRITY_MISMATCH')
    versions = _versions(manifest['library_versions'])
    snapshot = load_verified_candidate_artifacts(records, inputs, source_fixture=source)
    expected_common = _common(snapshot, run_id, versions)
    for document in (manifest, state, score_doc, evaluation_doc):
        _require(_same({key: document[key] for key in _COMMON}, expected_common), 'INCOMPATIBLE_RUN')
    expected_state = dict(expected_common, model_type='sklearn.ensemble.IsolationForest',
        weights=digests['weights.bin'], fit_indices=np.flatnonzero(snapshot.training_normal).tolist(),
        calibration_indices=np.flatnonzero(snapshot.calibration_normal).tolist())
    _require(_same(state, expected_state), 'REPLAY_MISMATCH')
    n = len(snapshot.timestamps)
    common = snapshot.common_valid
    stored_scores = score_doc['scores']
    _require(isinstance(stored_scores, list) and len(stored_scores) == n)
    scores = np.full(n, np.nan)
    for i, value in enumerate(stored_scores):
        if common[i]:
            _require(type(value) in (int, float) and math.isfinite(value))
            scores[i] = value
        else:
            _require(value is None)
    # Finite untrusted inputs may still overflow interpolation. The helper's
    # finite-result guard rejects them; arithmetic warnings must not leak paths.
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        threshold, alarms, calibration = calibrate_candidate_scores(scores, common, snapshot.calibration_normal)
    expected_score = dict(expected_common, timestamps=[str(stamp) for stamp in snapshot.timestamps],
        segment_ids=snapshot.segment_ids.tolist(), partitions=snapshot.partitions.tolist(),
        current_input_valid=snapshot.row_valid.tolist(), common_valid=common.tolist(), score_valid=common.tolist(),
        scores=stored_scores, alarms=[bool(alarm) if valid else None for alarm, valid in zip(alarms, common)],
        history_invalid_reason={str(window): list(history.invalid_reason) for window, history in snapshot.histories.items()},
        threshold=threshold, calibration=calibration)
    _require(_same(score_doc, expected_score), 'REPLAY_MISMATCH')
    evaluation = evaluate_candidate_predictions(labels=snapshot.labels, partitions=snapshot.partitions,
        score_valid=common, alarms=alarms, source_attack_label_present=snapshot.source_attack_label_present,
        score_origin_policy=snapshot.report['selected_policy'])
    expected_evaluation = dict(expected_common, scores=digests['scores.json'], threshold=threshold,
                               calibration=calibration, evaluation=evaluation)
    _require(_same(evaluation_doc, expected_evaluation), 'REPLAY_MISMATCH')
    return dict(schema_version=1, verifier_profile_id=VERIFIER_PROFILE_ID,
        status='VERIFIED', run_id=run_id, evidence_kind='SYNTHETIC_ONLY',
        policy_status='AUDIT_ONLY', scope='STORED_ARTIFACT_CONSISTENCY_ONLY', model_profile_id=MODEL_PROFILE_ID,
        selected_policy=snapshot.report['selected_policy'], minute_count=n, score_valid_count=int(common.sum()),
        fit_count=int(snapshot.training_normal.sum()), calibration_count=int(snapshot.calibration_normal.sum()),
        threshold=threshold, calibration=calibration, policies=evaluation['policies'], artifacts=digests,
        declared_library_versions=dict(versions),
        checks=dict(byte_integrity='VERIFIED', upstream_lineage='VERIFIED',
                    source_replay=snapshot.report['checks']['source_replay'],
                    stored_score_calibration='VERIFIED', strict_alarms='VERIFIED', evaluation='VERIFIED',
                    model_deserialization='NOT_PERFORMED', model_score_replay='NOT_CHECKED',
                    library_versions='DECLARATION_CONSISTENT_ONLY', model_type='DECLARED_ONLY'),
        run_payload_bytes=sum(entry['byte_count'] for entry in digests.values()))


def verify_candidate_if_run(run_directory, record_directory, input_directory, *, source_fixture=None):
    """Validate five fixed files and stored predictions without loading weights.

    Success certifies internal consistency, not model origin or executable state.
    Missing optional source remains explicitly NOT_PROVIDED.
    """
    try:
        return _verify(Path(run_directory), Path(record_directory), Path(input_directory),
                       Path(source_fixture) if source_fixture is not None else None)
    except CandidateRunArtifactError:
        raise
    except CandidateArtifactError as exc:
        raise CandidateRunArtifactError(exc.code) from exc
    except CandidateIFError as exc:
        raise CandidateRunArtifactError('REPLAY_MISMATCH') from exc
    except OSError as exc:
        raise CandidateRunArtifactError('INPUT_UNAVAILABLE') from exc
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise CandidateRunArtifactError('INVALID_RUN_ARTIFACTS') from exc
