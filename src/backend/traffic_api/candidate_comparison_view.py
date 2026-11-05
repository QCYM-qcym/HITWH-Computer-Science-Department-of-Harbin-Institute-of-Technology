"""Bind a trusted startup comparison to the exact already-admitted snapshots.

This is a pure consumer join, not model/source authentication. Call the original
comparison verifier at trusted startup; a hand-written dictionary is no proof.
"""
import math
import re

from traffic_anomaly.candidate_artifacts import _deep_freeze, _deep_thaw, _same
from traffic_anomaly.candidate_comparison import COMPARISON_PROFILE_ID, SLOT_ORDER, _execution_controls
from traffic_anomaly.candidate_evaluation_view import candidate_evaluation_view
from traffic_anomaly.candidate_iforest import MODEL_PROFILE_ID as IF_PROFILE, _configuration as if_config
from traffic_anomaly.candidate_autoencoder import _configuration as ae_config

_COUNTS = ('minute_count', 'score_valid_count', 'fit_count', 'calibration_count')
_POPULATION = ('calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes',
    'normal_minutes', 'attack_minutes', 'unknown_minutes', 'unknown_source_attack_present')
_PROTOCOL = ('fit_scope', 'calibration_scope', 'quantile', 'quantile_method',
    'alarm_comparison', 'preprocessing_fit_provenance')


def freeze_candidate_comparison(report: dict, registrations: list | tuple):
    """Check exact shape/semantics/identity and freeze without any I/O or evaluation."""
    from .candidate_app import CandidateRegistration, CandidateRegistrationError

    def require(condition):
        if not condition:
            raise CandidateRegistrationError('INVALID_COMPARISON')

    try:
        require(type(report) is dict and type(registrations) in (list, tuple)
                and 2 <= len(registrations) <= 4)
        rows, seen, slots, shared = [], set(), set(), None
        for registration in registrations:
            require(isinstance(registration, CandidateRegistration))
            run = registration.run
            candidate_evaluation_view(run)  # Validate consumer shape; does not recompute metrics.
            r, s = run.report_dict(), run.scores_dict()
            is_if = r['model_profile_id'] == IF_PROFILE
            config = s['configuration']
            fixed = if_config(r['fit_count']) if is_if else ae_config(r['method'], r['history_window'])
            require(_same(config, fixed))
            slot = SLOT_ORDER[0] if is_if else SLOT_ORDER[1] if r['method'] == 'current_ae' else f"history_ae26_h{r['history_window']}"
            require(slot in SLOT_ORDER and slot not in slots and r['run_id'] not in seen)
            seen.add(r['run_id']); slots.add(slot)
            artifacts = r['artifacts']
            require(set(artifacts) == {'manifest.json', 'scores.json', 'evaluation.json', 'model-state.json',
                'weights.bin' if is_if else 'weights.json'})
            for identity in artifacts.values():
                require(set(identity) == {'sha256', 'byte_count'} and type(identity['sha256']) is str
                    and bool(re.fullmatch('[0-9a-f]{64}', identity['sha256']))
                    and type(identity['byte_count']) is int and 1 <= identity['byte_count'] <= 32*1024*1024)
            checks = r['checks']
            require(all(checks[key] == 'VERIFIED' for key in
                ('byte_integrity', 'upstream_lineage', 'stored_score_calibration', 'strict_alarms', 'evaluation'))
                and checks['model_deserialization'] == 'NOT_PERFORMED' and checks['model_score_replay'] == 'NOT_CHECKED'
                and checks['source_replay'] == registration.inputs.report['checks']['source_replay'])
            if not is_if:
                require(checks['network_reconstruction'] == 'NOT_PERFORMED'
                    and checks['training_execution'] == checks['training_loss_replay'] == 'NOT_CHECKED'
                    and checks['model_origin'] == 'NOT_AUTHENTICATED')
            require(all(type(r[k]) is int and 0 <= r[k] <= r['minute_count'] for k in _COUNTS)
                and 1 <= r['fit_count'] <= r['score_valid_count']
                and 1 <= r['calibration_count'] <= r['score_valid_count'])
            threshold, calibration = r['threshold'], r['calibration']
            require(type(threshold) in (int, float) and math.isfinite(threshold)
                and _same(threshold, s['threshold'])
                and type(calibration) is dict and set(calibration) == {'sample_count', 'quantile', 'method',
                    'comparison', 'order_position_zero_based', 'strictly_above_count', 'equal_count'}
                and type(calibration['sample_count']) is int
                and calibration['sample_count'] == r['calibration_count']
                and _same(calibration['quantile'], .99) and calibration['method'] == 'linear'
                and calibration['comparison'] == 'STRICT_GREATER'
                and type(calibration['order_position_zero_based']) in (int, float)
                and math.isfinite(calibration['order_position_zero_based'])
                and 0 <= calibration['order_position_zero_based'] <= calibration['sample_count']-1
                and all(type(calibration[k]) is int and 0 <= calibration[k] <= calibration['sample_count']
                    for k in ('strictly_above_count', 'equal_count'))
                and calibration['strictly_above_count'] + calibration['equal_count'] <= calibration['sample_count'])
            current = dict(selected_policy=r['selected_policy'], source_replay=checks['source_replay'],
                feature_names=s['feature_names'], qualification_windows=s['qualification_windows'],
                five_provenance=s['provenance'], preprocessing_identity=s['provenance']['preprocess'],
                preprocessing_state=s['preprocessing_state'], qualification_protocol={k:config[k] for k in _PROTOCOL},
                **{k:r[k] for k in _COUNTS},
                test_denominators_by_policy={p:{k:v[k] for k in _POPULATION} for p,v in r['policies'].items()})
            require(shared is None or _same(current, shared))
            shared = current
            rows.append(dict(slot=slot, run_id=r['run_id'], model_profile_id=r['model_profile_id'],
                verifier_profile_id=r['verifier_profile_id'], configuration=config,
                library_versions=r['declared_library_versions'], runtime=r.get('declared_runtime'),
                architecture=config.get('architecture'), parameter_count=config.get('parameter_count'),
                parameter_count_reason='NOT_DEFINED_FOR_OPAQUE_IF' if is_if else None,
                threshold=r['threshold'], calibration=r['calibration'], policies=r['policies'],
                actual_five_artifacts=artifacts, verification_checks=checks, verification_scope=r['scope']))
        rows.sort(key=lambda row: SLOT_ORDER.index(row['slot']))
        expected = dict(schema_version=1, comparison_profile_id=COMPARISON_PROFILE_ID,
            status='DATA_QUALIFICATION_ALIGNED', evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
            scope='SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY',
            included_slots=[slot for slot in SLOT_ORDER if slot in slots],
            missing_slots=[slot for slot in SLOT_ORDER if slot not in slots], shared_context=shared, runs=rows,
            limitations=dict(capacity_control='NOT_COMPARABLE', history_causal_attribution='NOT_COMPARABLE',
                cross_model_score_scale='NOT_COMPARABLE', ranking='NOT_PERFORMED', statistical_significance='NOT_PERFORMED',
                model_execution='NOT_CHECKED', model_origin='NOT_AUTHENTICATED', execution_controls=_execution_controls(rows)))
        require(_same(report, expected))
        return _deep_freeze(_deep_thaw(report))
    except CandidateRegistrationError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, RecursionError):
        raise CandidateRegistrationError('INVALID_COMPARISON') from None
