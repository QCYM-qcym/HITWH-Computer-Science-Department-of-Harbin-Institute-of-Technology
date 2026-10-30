"""Pure candidate minute inspection; no I/O, model execution or recalculation."""
from datetime import datetime
import math
import re

import numpy as np

from .candidate_artifacts import (VerifiedCandidateArtifacts, VERIFIER_PROFILE_ID as INPUT_VERIFIER,
    _deep_thaw, _same)
from .candidate_run_snapshot import VerifiedCandidateRun
from .candidate_run_artifacts import VERIFIER_PROFILE_ID as IF_VERIFIER
from .candidate_ae_run_artifacts import VERIFIER_PROFILE_ID as AE_VERIFIER
from .candidate_iforest import MODEL_PROFILE_ID as IF_PROFILE
from .candidate_autoencoder import MODEL_PROFILE_ID as AE_PROFILE
from .candidate_inputs import G13U_FEATURE_NAMES, MAX_MINUTES

_QUERY = re.compile(r'\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::00(?:\.000000)?)?\Z', re.ASCII)
_PROVENANCE = {'record_manifest', 'input_manifest', 'source_fixture', 'minute_fixture', 'preprocess'}
_POLICIES = {'P_U', 'P_B', 'P_A'}
_INPUT_SCOPE = 'synthetic_internal_consistency_not_source_authentication_or_research_validation'


class CandidateDetailError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition):
    if not condition:
        raise CandidateDetailError('INCOMPATIBLE_SNAPSHOTS')


def _query(timestamp):
    if type(timestamp) is not str or not _QUERY.fullmatch(timestamp):
        raise CandidateDetailError('INVALID_QUERY')
    try:
        return datetime.fromisoformat(timestamp).isoformat(timespec='microseconds')
    except ValueError:
        raise CandidateDetailError('INVALID_QUERY') from None


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _boolean(values, n):
    _require(values.shape == (n,) and values.dtype == np.dtype(bool))
    return values


def _pair(run, inputs):
    _require(isinstance(run, VerifiedCandidateRun) and isinstance(inputs, VerifiedCandidateArtifacts))
    r, s, p = run.report, run.scores_document, inputs.report
    _require(r['status'] == p['status'] == 'VERIFIED'
        and r['evidence_kind'] == s['evidence_kind'] == p['evidence_kind'] == 'SYNTHETIC_ONLY'
        and r['policy_status'] == s['policy_status'] == p['policy_status'] == 'AUDIT_ONLY'
        and s['time_basis'] == p['time_basis'] == 'synthetic_source_clock'
        and r['scope'] == 'STORED_ARTIFACT_CONSISTENCY_ONLY'
        and s['scope'] == 'ENGINEERING_TOY_ONLY' and p['scope'] == _INPUT_SCOPE
        and p['verifier_profile_id'] == INPUT_VERIFIER
        and type(r['schema_version']) is int and r['schema_version'] == 1
        and type(s['schema_version']) is int and s['schema_version'] == 1
        and type(p['schema_version']) is int and p['schema_version'] == 1)
    profile = s['model_profile_id']
    _require(profile in (IF_PROFILE, AE_PROFILE) and r['model_profile_id'] == profile
        and r['verifier_profile_id'] == (IF_VERIFIER if profile == IF_PROFILE else AE_VERIFIER))
    _require(r['run_id'] == s['run_id'] and type(s['run_id']) is str
        and r['selected_policy'] == s['selected_policy'] == p['selected_policy']
        and s['selected_policy'] in _POLICIES
        and s['score_direction'] == 'HIGHER_IS_MORE_ANOMALOUS')
    _require(set(s['provenance']) == set(inputs.provenance) == _PROVENANCE)
    for key in _PROVENANCE:
        identity = s['provenance'][key]
        _require(set(identity) == {'sha256', 'byte_count'}
            and type(identity['sha256']) is str and bool(re.fullmatch('[0-9a-f]{64}', identity['sha256']))
            and type(identity['byte_count']) is int and identity['byte_count'] > 0
            and _same(_deep_thaw(identity), _deep_thaw(inputs.provenance[key])))
    _require(inputs.feature_names == G13U_FEATURE_NAMES
        and _same(_deep_thaw(s['feature_names']), list(inputs.feature_names))
        and inputs.value_space == s['value_space'] == 'prepared'
        and _same(_deep_thaw(s['preprocessing_state']), _deep_thaw(inputs.preprocessing_state))
        and _same(_deep_thaw(s['qualification_windows']), [15, 30])
        and _same(_deep_thaw(p['windows']), [15, 30])
        and _same(_deep_thaw(p['dimensions']), {'current': 13, 'joined': 26}))
    stamps = inputs.timestamps
    n = len(stamps)
    _require(1 <= n <= MAX_MINUTES and stamps.shape == (n,) and stamps.dtype == np.dtype('datetime64[us]')
        and not np.isnat(stamps).any() and (stamps.view('i8') % 60000000 == 0).all()
        and (np.diff(stamps) > np.timedelta64(0, 'us')).all())
    _require(type(r['minute_count']) is int and r['minute_count'] == n
        and type(p['minute_count']) is int and p['minute_count'] == n)
    rows, common, raw_valid = (_boolean(values, n) for values in
        (inputs.row_valid, inputs.common_valid, inputs.raw_valid))
    axes = dict(timestamps=[str(t) for t in stamps], segment_ids=inputs.segment_ids.tolist(),
        partitions=inputs.partitions.tolist(), current_input_valid=rows.tolist(),
        common_valid=common.tolist(), score_valid=common.tolist())
    _require(inputs.segment_ids.shape == inputs.partitions.shape == (n,))
    for field, expected in axes.items():
        _require(_same(_deep_thaw(s[field]), expected))
    _require(set(inputs.histories) == {15, 30} and set(s['history_invalid_reason']) == {'15', '30'})
    for h in (15, 30):
        history = inputs.histories[h]
        _boolean(history.valid, n)
        _require(history.residual.shape == (n, 13) and len(history.invalid_reason) == n
            and _same(_deep_thaw(s['history_invalid_reason'][str(h)]), list(history.invalid_reason))
            and all((reason is None) == bool(valid) for reason, valid in zip(history.invalid_reason, history.valid)))
    _require(np.array_equal(common, inputs.histories[15].valid & inputs.histories[30].valid))
    _require(inputs.raw_values.shape == inputs.current_values.shape == (n, 13)
        and len(s['scores']) == len(s['alarms']) == n and _finite(s['threshold'])
        and _same(r['threshold'], s['threshold']))
    for valid, score, alarm in zip(common, s['scores'], s['alarms']):
        _require((_finite(score) and type(alarm) is bool) if valid else (score is None and alarm is None))
    _require(set(inputs.labels) == _POLICIES)
    for labels in inputs.labels.values():
        _require(len(labels) == n and all(value in ('normal', 'attack', 'unknown') for value in labels))
    _boolean(inputs.source_attack_label_present, n)
    for report in (r, p):
        _require(report['checks']['source_replay'] in ('VERIFIED', 'NOT_PROVIDED'))
    if profile == AE_PROFILE:
        method = s['configuration']['method']
        _require(method in ('current_ae', 'history_ae') and r['method'] == method
            and r['history_window'] == s['configuration']['history_window'])
        status = 'APPLICABLE' if method == 'history_ae' else 'NOT_APPLICABLE'
        _require(s['history_deviation_reconstruction_mse_status'] == status)
        for name, applies in [('current_reconstruction_mse', True),
                ('history_deviation_reconstruction_mse', method == 'history_ae')]:
            _require(len(s[name]) == n)
            for valid, value in zip(common, s[name]):
                _require((_finite(value) and value >= 0) if valid and applies else value is None)
    return s, axes['timestamps'], raw_valid, rows, common


def _vector(values, valid):
    _require(values.shape == (13,))
    if valid:
        _require(np.isfinite(values).all())
        return values.tolist()
    _require(np.isnan(values).all())
    return [None] * 13


def candidate_minute_detail(run_snapshot, input_snapshot, timestamp):
    """Join checked candidate snapshots by one naive source-clock minute.

    This verifies compatibility of loaded values, not their origin or permission
    to use real data. The returned JSON-ready containers are independent copies.
    """
    stamp = _query(timestamp)
    try:
        run, inputs = run_snapshot, input_snapshot
        s, stamps, raw_valid, rows, common = _pair(run, inputs)
        if stamp not in stamps:
            raise CandidateDetailError('MINUTE_NOT_FOUND')
        i = stamps.index(stamp)
        proof = dict(run=run.report['checks']['source_replay'], inputs=inputs.report['checks']['source_replay'])
        proof['combined'] = 'VERIFIED' if all(value == 'VERIFIED' for value in proof.values()) else 'NOT_PROVIDED'
        current, historical = dict(status='NOT_APPLICABLE', value=None), dict(status='NOT_APPLICABLE', value=None)
        if s['model_profile_id'] == AE_PROFILE:
            current = dict(status='APPLICABLE', value=s['current_reconstruction_mse'][i])
            historical = dict(status=s['history_deviation_reconstruction_mse_status'],
                              value=s['history_deviation_reconstruction_mse'][i])
        return dict(schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
            time_basis='synthetic_source_clock', run_id=s['run_id'], selected_policy=s['selected_policy'],
            feature_names=list(inputs.feature_names), source_replay=proof,
            point=dict(timestamp=stamp, segment_id=s['segment_ids'][i], partition=s['partitions'][i],
                valid=bool(common[i]), score=s['scores'][i], alarm=s['alarms'][i], threshold=s['threshold']),
            inputs=dict(raw=dict(valid=bool(raw_valid[i]), values=_vector(inputs.raw_values[i], raw_valid[i])),
                prepared=dict(valid=bool(rows[i]), values=_vector(inputs.current_values[i], rows[i]))),
            histories={str(h): dict(valid=bool(history.valid[i]), invalid_reason=history.invalid_reason[i],
                residual=_vector(history.residual[i], history.valid[i])) for h, history in inputs.histories.items()},
            labels=dict(policies={p: inputs.labels[p][i] for p in ('P_U', 'P_B', 'P_A')},
                        source_attack_label_present=bool(inputs.source_attack_label_present[i])),
            reconstruction=dict(current=current, history_deviation=historical,
                                per_feature=dict(status='NOT_STORED', values=None)))
    except CandidateDetailError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError):
        raise CandidateDetailError('INCOMPATIBLE_SNAPSHOTS') from None
