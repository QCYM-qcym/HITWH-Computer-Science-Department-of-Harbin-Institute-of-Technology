"""Pure full-test evaluation view of loader-checked synthetic saved runs."""
import math
import re

from .candidate_artifacts import _deep_thaw
from .candidate_run_snapshot import VerifiedCandidateRun
from .candidate_run_artifacts import MAX_JSON_BYTES, VERIFIER_PROFILE_ID as IF_VERIFIER
from .candidate_ae_run_artifacts import VERIFIER_PROFILE_ID as AE_VERIFIER
from .candidate_iforest import MODEL_PROFILE_ID as IF_PROFILE
from .candidate_autoencoder import MODEL_PROFILE_ID as AE_PROFILE
from .candidate_inputs import MAX_MINUTES
from .candidate_records import POLICIES

_PROFILES = {IF_PROFILE: IF_VERIFIER, AE_PROFILE: AE_VERIFIER}
_COUNTS = {'calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes',
    'normal_minutes', 'attack_minutes', 'unknown_minutes', 'unknown_source_attack_present'}
_CONFUSION = {'tp', 'fp', 'tn', 'fn'}
_METRICS = {'precision', 'recall', 'f1', 'fpr', 'fnr'}


class CandidateEvaluationViewError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition):
    if not condition:
        raise CandidateEvaluationViewError('INCOMPATIBLE_SNAPSHOT')


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
        and type(s['run_id']) is str and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', s['run_id']))
        and r['run_id'] == s['run_id'] and r['selected_policy'] == s['selected_policy']
        and s['selected_policy'] in POLICIES and r['checks']['evaluation'] == 'VERIFIED'
        and r['checks']['source_replay'] in ('VERIFIED', 'NOT_PROVIDED'))
    identity = r['artifacts']['evaluation.json']
    _require(set(identity) == {'sha256', 'byte_count'} and type(identity['sha256']) is str
        and bool(re.fullmatch('[0-9a-f]{64}', identity['sha256']))
        and type(identity['byte_count']) is int and 1 <= identity['byte_count'] <= MAX_JSON_BYTES)
    _require(set(r['policies']) == set(POLICIES))
    population = None
    for value in r['policies'].values():
        _require(set(value) == _COUNTS | {'confusion_counts', 'metrics', 'undefined_reasons'})
        counts, metrics, reasons = value['confusion_counts'], value['metrics'], value['undefined_reasons']
        _require(set(counts) == _CONFUSION and set(metrics) == _METRICS)
        _require(all(type(n) is int and 0 <= n <= MAX_MINUTES
            for n in [*(value[k] for k in _COUNTS), *counts.values()]))
        calendar, scored, excluded = (value[k] for k in
            ('calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes'))
        _require(calendar == scored + excluded
            and scored == value['normal_minutes'] + value['attack_minutes'] + value['unknown_minutes']
            and counts['fp'] + counts['tn'] == value['normal_minutes']
            and counts['tp'] + counts['fn'] == value['attack_minutes']
            and value['unknown_source_attack_present'] <= value['unknown_minutes'])
        current = (calendar, scored, excluded)
        _require(population is None or population == current)
        population = current
        _require(all(n is None or type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1
            for n in metrics.values()))
        # Validate undefinedness using the stored confusion counts. Never divide
        # or reconstruct metrics, labels, predictions, or minute axes here.
        denominators = dict(precision=counts['tp'] + counts['fp'], recall=counts['tp'] + counts['fn'],
            f1=2*counts['tp'] + counts['fp'] + counts['fn'], fpr=counts['fp'] + counts['tn'],
            fnr=counts['tp'] + counts['fn'])
        nulls = {key for key, n in metrics.items() if n is None}
        _require(nulls == {key for key, n in denominators.items() if n == 0}
            and set(reasons) == nulls
            and all(type(reason) is str and 1 <= len(reason) <= 256 for reason in reasons.values()))
    return r, s, identity


def candidate_evaluation_view(run_snapshot):
    """Copy the original full stored test evaluation without I/O or recomputation.

    Use a loader-produced immutable snapshot. These consumer shape checks do
    not authenticate a directly constructed snapshot or establish model origin.
    """
    try:
        r, s, identity = _checked(run_snapshot)
        return dict(schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
            scope='FULL_STORED_TEST_EVALUATION', unit='minute', run_id=s['run_id'],
            model_profile_id=s['model_profile_id'], score_origin_policy=s['selected_policy'],
            run_source_replay=r['checks']['source_replay'], policies=_deep_thaw(r['policies']),
            evaluation_reference=dict(scope='FULL_STORED_RUN', run_id=s['run_id'], artifact=_deep_thaw(identity)))
    except CandidateEvaluationViewError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError, RecursionError):
        raise CandidateEvaluationViewError('INCOMPATIBLE_SNAPSHOT') from None
