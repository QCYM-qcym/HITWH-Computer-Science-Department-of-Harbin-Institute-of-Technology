"""Saved evaluation consumers use manual snapshots; no labels or model execution."""
import importlib
import json
from pathlib import Path

import pytest

from traffic_anomaly.candidate_run_snapshot import VerifiedCandidateRun


def api():
    name = 'traffic_anomaly.candidate_evaluation_view'
    assert importlib.util.find_spec(name) is not None, 'stored evaluation consumer is missing'
    return importlib.import_module(name)


def policy():
    return dict(calendar_test_minutes=8, scored_test_minutes=7, excluded_unscored_test_minutes=1,
        normal_minutes=3, attack_minutes=3, unknown_minutes=1, unknown_source_attack_present=1,
        confusion_counts=dict(tp=2, fp=1, tn=2, fn=1),
        metrics=dict(precision=.625, recall=.625, f1=.625, fpr=.375, fnr=.375),
        undefined_reasons={})


@pytest.fixture
def run():
    from traffic_anomaly.candidate_iforest import MODEL_PROFILE_ID
    from traffic_anomaly.candidate_run_artifacts import VERIFIER_PROFILE_ID
    common = dict(schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        model_profile_id=MODEL_PROFILE_ID, run_id='saved-evaluation', selected_policy='P_B')
    report = dict(common, verifier_profile_id=VERIFIER_PROFILE_ID, status='VERIFIED',
        scope='STORED_ARTIFACT_CONSISTENCY_ONLY', checks=dict(evaluation='VERIFIED', source_replay='NOT_PROVIDED'),
        artifacts={'evaluation.json': dict(sha256='a'*64, byte_count=300)},
        policies={p: policy() for p in ('P_U', 'P_B', 'P_A')})
    scores = dict(common, scope='ENGINEERING_TOY_ONLY', time_basis='synthetic_source_clock',
        score_direction='HIGHER_IS_MORE_ANOMALOUS')
    # Values deliberately differ from exact ratios: consumers preserve stored
    # finite metrics and only check the zero-denominator/null contract.
    report['policies']['P_A']['metrics']['precision'] = 0
    return VerifiedCandidateRun(report, scores)


def test_preserves_three_policies_and_saved_origin_without_recalculation(run, monkeypatch):
    from traffic_anomaly import candidate_evaluation, candidate_series
    def forbidden(*args, **kwargs):
        raise AssertionError('consumer performed I/O, axis reconstruction or evaluation')
    monkeypatch.setattr(Path, 'open', forbidden)
    monkeypatch.setattr(candidate_evaluation, 'evaluate_candidate_predictions', forbidden)
    monkeypatch.setattr(candidate_series, 'candidate_series_page', forbidden)
    result = api().candidate_evaluation_view(run)
    assert result == dict(schema_version=1, evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        scope='FULL_STORED_TEST_EVALUATION', unit='minute', run_id='saved-evaluation',
        model_profile_id=run.report['model_profile_id'], score_origin_policy='P_B',
        run_source_replay='NOT_PROVIDED', policies=run.report_dict()['policies'],
        evaluation_reference=dict(scope='FULL_STORED_RUN', run_id='saved-evaluation',
            artifact=dict(sha256='a'*64, byte_count=300)))
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('kind,counts,metrics', [
    ('zero_normal', dict(tp=1, fp=0, tn=0, fn=1), dict(precision=1, recall=.5, f1=.6, fpr=None, fnr=.5)),
    ('zero_attack', dict(tp=0, fp=1, tn=1, fn=0), dict(precision=0, recall=None, f1=0, fpr=.5, fnr=None)),
    ('all_unknown', dict(tp=0, fp=0, tn=0, fn=0), dict(precision=None, recall=None, f1=None, fpr=None, fnr=None)),
    ('no_scoring', dict(tp=0, fp=0, tn=0, fn=0), dict(precision=None, recall=None, f1=None, fpr=None, fnr=None)),
    ('no_positive', dict(tp=0, fp=0, tn=2, fn=0), dict(precision=None, recall=None, f1=None, fpr=0, fnr=None)),
    ('missed_attack', dict(tp=0, fp=0, tn=0, fn=2), dict(precision=None, recall=0, f1=0, fpr=None, fnr=1)),
])
def test_zero_denominators_preserve_null_reasons_and_defined_zero(run, kind, counts, metrics):
    r = run.report_dict()
    for value in r['policies'].values():
        value.update(normal_minutes=counts['fp']+counts['tn'], attack_minutes=counts['tp']+counts['fn'],
            unknown_minutes=0 if kind == 'no_scoring' else 2, unknown_source_attack_present=0,
            confusion_counts=counts, metrics=metrics,
            undefined_reasons={k: 'stored undefined reason' for k, v in metrics.items() if v is None})
        value['scored_test_minutes'] = value['normal_minutes']+value['attack_minutes']+value['unknown_minutes']
        value['excluded_unscored_test_minutes'] = 8-value['scored_test_minutes']
    result = api().candidate_evaluation_view(VerifiedCandidateRun(r, run.scores_dict()))
    assert result['policies'] == r['policies']


@pytest.mark.parametrize('path,value', [
    (('schema_version',), True), (('evidence_kind',), 'REAL_DATA'), (('policy_status',), 'APPROVED'),
    (('verifier_profile_id',), 'other'), (('status',), 'UNVERIFIED'), (('scope',), 'OTHER'),
    (('checks', 'evaluation'), 'NOT_CHECKED'), (('checks', 'source_replay'), 'ASSUMED'),
    (('run_id',), 'different'), (('selected_policy',), 'P_A'), (('model_profile_id',), 'unknown'),
    (('artifacts', 'evaluation.json', 'sha256'), 'A'*64),
    (('artifacts', 'evaluation.json', 'sha256'), 'a'*63),
    (('artifacts', 'evaluation.json', 'byte_count'), True),
    (('artifacts', 'evaluation.json', 'byte_count'), 0),
    (('artifacts', 'evaluation.json', 'byte_count'), 16*1024*1024+1),
    (('policies', 'P_U', 'scored_test_minutes'), True),
    (('policies', 'P_U', 'normal_minutes'), -1),
    (('policies', 'P_U', 'calendar_test_minutes'), 10001),
    (('policies', 'P_U', 'attack_minutes'), 3.0),
    (('policies', 'P_U', 'unknown_source_attack_present'), 2),
    (('policies', 'P_U', 'excluded_unscored_test_minutes'), 0),
    (('policies', 'P_U', 'normal_minutes'), 4),
    (('policies', 'P_U', 'confusion_counts', 'tp'), 1),
    (('policies', 'P_U', 'confusion_counts', 'tn'), 1),
    (('policies', 'P_U', 'metrics', 'precision'), float('nan')),
    (('policies', 'P_U', 'metrics', 'recall'), float('inf')),
    (('policies', 'P_U', 'metrics', 'f1'), True),
    (('policies', 'P_U', 'metrics', 'fpr'), -0.1),
    (('policies', 'P_U', 'metrics', 'fnr'), 1.1),
    (('policies', 'P_U', 'metrics', 'precision'), None),
    (('policies', 'P_U', 'undefined_reasons'), {'precision': 'unexpected'}),
])
def test_rejects_incompatible_report_with_fixed_safe_error(run, path, value):
    r = run.report_dict()
    target = r
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    module = api()
    with pytest.raises(module.CandidateEvaluationViewError, match='^INCOMPATIBLE_SNAPSHOT$') as caught:
        module.candidate_evaluation_view(VerifiedCandidateRun(r, run.scores_dict()))
    assert caught.value.code == 'INCOMPATIBLE_SNAPSHOT'


@pytest.mark.parametrize('mutation', ['policy_missing', 'policy_extra', 'metric_missing', 'metric_extra',
    'reason_empty', 'reason_too_long', 'reason_nonstring', 'defined_on_zero', 'population_mismatch',
    'missing_checks', 'extra_identity', 'bad_scores_version', 'bad_scores_scope', 'bad_scores_policy'])
def test_missing_extra_fields_and_null_contract_are_rejected(run, mutation):
    r, s = run.report_dict(), run.scores_dict()
    p = r['policies']['P_U']
    if mutation == 'policy_missing': del r['policies']['P_A']
    elif mutation == 'policy_extra': r['policies']['P_X'] = policy()
    elif mutation == 'metric_missing': del p['metrics']['fnr']
    elif mutation == 'metric_extra': p['metrics']['accuracy'] = .9
    elif mutation.startswith('reason_') or mutation == 'defined_on_zero':
        p.update(attack_minutes=0, normal_minutes=0, unknown_minutes=7, unknown_source_attack_present=1,
            confusion_counts=dict(tp=0, fp=0, tn=0, fn=0),
            metrics={k: None for k in p['metrics']}, undefined_reasons={k: 'reason' for k in p['metrics']})
        if mutation == 'defined_on_zero': p['metrics']['recall'] = 0; del p['undefined_reasons']['recall']
        else: p['undefined_reasons']['recall'] = {'reason_empty': '', 'reason_too_long': 'x'*257, 'reason_nonstring': 1}[mutation]
    elif mutation == 'population_mismatch': p['calendar_test_minutes'] += 1; p['excluded_unscored_test_minutes'] += 1
    elif mutation == 'missing_checks': del r['checks']
    elif mutation == 'extra_identity': r['artifacts']['evaluation.json']['path'] = 'private-path'
    elif mutation == 'bad_scores_version': s['schema_version'] = True
    elif mutation == 'bad_scores_scope': s['scope'] = 'REAL_DATA'
    elif mutation == 'bad_scores_policy': s['selected_policy'] = 'P_X'
    module = api()
    with pytest.raises(module.CandidateEvaluationViewError, match='^INCOMPATIBLE_SNAPSHOT$'):
        module.candidate_evaluation_view(VerifiedCandidateRun(r, s))


def test_ae_matching_profiles_source_proof_and_inclusive_identity_bound(run):
    from traffic_anomaly.candidate_autoencoder import MODEL_PROFILE_ID
    from traffic_anomaly.candidate_ae_run_artifacts import VERIFIER_PROFILE_ID
    r, s = run.report_dict(), run.scores_dict()
    r['model_profile_id'] = s['model_profile_id'] = MODEL_PROFILE_ID
    r['verifier_profile_id'] = VERIFIER_PROFILE_ID
    r['checks']['source_replay'] = 'VERIFIED'
    r['artifacts']['evaluation.json']['byte_count'] = 16*1024*1024
    assert api().candidate_evaluation_view(VerifiedCandidateRun(r, s))['run_source_replay'] == 'VERIFIED'


def test_returns_independent_mutable_copies(run):
    before = run.report_dict()
    first = api().candidate_evaluation_view(run)
    first['policies']['P_U']['metrics']['precision'] = 1
    first['policies']['P_B']['confusion_counts']['tp'] = 0
    first['evaluation_reference']['artifact']['sha256'] = 'changed'
    again = api().candidate_evaluation_view(run)
    assert again['policies'] == before['policies']
    assert again['evaluation_reference']['artifact']['sha256'] == 'a'*64
    assert run.report_dict() == before


@pytest.mark.parametrize('value', [None, {}, 0, 'private-path'])
def test_requires_verified_snapshot_value_type(value):
    module = api()
    with pytest.raises(module.CandidateEvaluationViewError, match='^INCOMPATIBLE_SNAPSHOT$'):
        module.candidate_evaluation_view(value)
