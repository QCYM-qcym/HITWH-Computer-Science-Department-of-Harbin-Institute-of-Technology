"""Pure pages of checked candidate scores; the full stored evaluation is retained."""
from datetime import datetime, timedelta
import math
import re

from .candidate_details import _query, CandidateDetailError
from .candidate_run_snapshot import VerifiedCandidateRun
from .candidate_artifacts import _same
from .candidate_run_artifacts import VERIFIER_PROFILE_ID as IF_VERIFIER
from .candidate_ae_run_artifacts import VERIFIER_PROFILE_ID as AE_VERIFIER
from .candidate_iforest import MODEL_PROFILE_ID as IF_PROFILE
from .candidate_autoencoder import MODEL_PROFILE_ID as AE_PROFILE
from .candidate_inputs import MAX_MINUTES, PARTITIONS

_PROFILES = {IF_PROFILE: IF_VERIFIER, AE_PROFILE: AE_VERIFIER}
_REASONS = {None, 'warmup', 'gap', 'boundary', 'invalid_input', 'nonfinite_history'}
_AXES = ('timestamps', 'segment_ids', 'partitions', 'current_input_valid',
         'common_valid', 'score_valid', 'scores', 'alarms')


class CandidateSeriesError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition):
    if not condition:
        raise CandidateSeriesError('INCOMPATIBLE_SNAPSHOT')


def _canonical(value, code):
    try:
        return _query(value)
    except CandidateDetailError:
        raise CandidateSeriesError(code) from None


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _checked(run):
    _require(isinstance(run, VerifiedCandidateRun))
    r, s = run.report, run.scores_document
    for document in (r, s):
        _require(type(document['schema_version']) is int and document['schema_version'] == 1
            and document['evidence_kind'] == 'SYNTHETIC_ONLY' and document['policy_status'] == 'AUDIT_ONLY')
    profile = s['model_profile_id']
    _require(profile in _PROFILES and r['model_profile_id'] == profile
        and r['verifier_profile_id'] == _PROFILES[profile]
        and r['status'] == 'VERIFIED' and r['scope'] == 'STORED_ARTIFACT_CONSISTENCY_ONLY'
        and s['scope'] == 'ENGINEERING_TOY_ONLY' and s['time_basis'] == 'synthetic_source_clock'
        and s['score_direction'] == 'HIGHER_IS_MORE_ANOMALOUS'
        and r['run_id'] == s['run_id'] and type(s['run_id']) is str
        and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', s['run_id']))
        and r['selected_policy'] == s['selected_policy'] and s['selected_policy'] in ('P_U', 'P_B', 'P_A')
        and r['checks']['source_replay'] in ('VERIFIED', 'NOT_PROVIDED'))
    n = len(s['timestamps'])
    _require(1 <= n <= MAX_MINUTES and type(r['minute_count']) is int and r['minute_count'] == n)
    _require(all(type(s[field]) is tuple and len(s[field]) == n for field in _AXES))
    _require(set(s['history_invalid_reason']) == {'15', '30'})
    for reasons in s['history_invalid_reason'].values():
        _require(type(reasons) is tuple and len(reasons) == n
                 and all(reason in _REASONS for reason in reasons))
    _require(_finite(s['threshold']) and _same(r['threshold'], s['threshold']))
    moments, breaks, valid_count = [], [], 0
    previous_partition = -1
    for i, stamp in enumerate(s['timestamps']):
        _require(_canonical(stamp, 'INCOMPATIBLE_SNAPSHOT') == stamp)
        moment = datetime.fromisoformat(stamp)
        _require(not moments or moment > moments[-1])
        segment, partition = s['segment_ids'][i], s['partitions'][i]
        _require(type(segment) is str and 1 <= len(segment) <= 128 and partition in PARTITIONS)
        rank = PARTITIONS.index(partition)
        _require(rank >= previous_partition)
        previous_partition = rank
        current, common, valid = (s[field][i] for field in ('current_input_valid', 'common_valid', 'score_valid'))
        _require(type(current) is bool and type(common) is bool and type(valid) is bool
            and common == valid and (not valid or current))
        reasons_ready = all(s['history_invalid_reason'][h][i] is None for h in ('15', '30'))
        _require(valid == reasons_ready)
        score, alarm = s['scores'][i], s['alarms'][i]
        _require((_finite(score) and type(alarm) is bool) if valid else (score is None and alarm is None))
        valid_count += valid
        breaks.append(i == 0 or moment - moments[-1] > timedelta(minutes=1)
            or segment != s['segment_ids'][i-1] or partition != s['partitions'][i-1])
        moments.append(moment)
    _require(type(r['score_valid_count']) is int and r['score_valid_count'] == valid_count)
    identity = r['artifacts']['evaluation.json']
    _require(set(identity) == {'sha256', 'byte_count'} and type(identity['sha256']) is str
        and bool(re.fullmatch('[0-9a-f]{64}', identity['sha256']))
        and type(identity['byte_count']) is int and identity['byte_count'] > 0)
    return r, s, breaks, identity


def candidate_series_page(run_snapshot, *, start=None, end=None, page=1, page_size=100):
    """Return an independent page from the original axis after half-open filtering.

    Use a verified loader result. These shape checks do not authenticate models
    or real-data permission. No page selection changes saved metric denominators.
    """
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 1000:
        raise CandidateSeriesError('INVALID_QUERY')
    first = None if start is None else _canonical(start, 'INVALID_QUERY')
    last = None if end is None else _canonical(end, 'INVALID_QUERY')
    if first is not None and last is not None and first >= last:
        raise CandidateSeriesError('INVALID_QUERY')
    try:
        r, s, breaks, identity = _checked(run_snapshot)
        selected = [i for i, stamp in enumerate(s['timestamps'])
                    if (first is None or stamp >= first) and (last is None or stamp < last)]
        offset = (page - 1) * page_size
        indexes = [] if offset >= len(selected) else selected[offset:offset + page_size]
        items = [dict(source_index=i, timestamp=s['timestamps'][i], segment_id=s['segment_ids'][i],
            partition=s['partitions'][i], current_input_valid=s['current_input_valid'][i],
            valid=s['score_valid'][i], score=s['scores'][i], alarm=s['alarms'][i], threshold=s['threshold'],
            history_invalid_reason={h: s['history_invalid_reason'][h][i] for h in ('15', '30')},
            break_before=breaks[i]) for i in indexes]
        return dict(schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
            time_basis='synthetic_source_clock', run_id=s['run_id'], selected_policy=s['selected_policy'],
            source_replay=r['checks']['source_replay'], range=dict(start=first, end=last),
            page=page, page_size=page_size, total=len(selected), returned=len(items), items=items,
            evaluation_reference=dict(scope='FULL_STORED_RUN', run_id=s['run_id'],
                                      artifact=dict(sha256=identity['sha256'], byte_count=identity['byte_count'])))
    except CandidateSeriesError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError):
        raise CandidateSeriesError('INCOMPATIBLE_SNAPSHOT') from None
