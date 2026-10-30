"""Align stored synthetic runs by verified byte lineage, never by score rank."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .candidate_artifacts import CandidateArtifactError, _ancestors, _ordinary, _same
from .candidate_run_artifacts import (
    CandidateRunArtifactError, verify_candidate_if_run, _json,
    VERIFIER_PROFILE_ID as IF_VERIFIER, _RUN_ID,
)
from .candidate_ae_run_artifacts import (
    CandidateAERunArtifactError, verify_candidate_ae_run,
    VERIFIER_PROFILE_ID as AE_VERIFIER,
)
from .candidate_iforest import MODEL_PROFILE_ID as IF_MODEL, _configuration as if_configuration
from .candidate_autoencoder import MODEL_PROFILE_ID as AE_MODEL, _configuration as ae_configuration

COMPARISON_PROFILE_ID = 'c17-i1-g13u-comparison-context-v1'
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
SLOT_ORDER = ('iforest_current13', 'current_ae13', 'history_ae26_h15', 'history_ae26_h30')
_COUNTS = ('minute_count', 'score_valid_count', 'fit_count', 'calibration_count')
_POPULATION = ('calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes',
              'normal_minutes', 'attack_minutes', 'unknown_minutes', 'unknown_source_attack_present')
_PROTOCOL = ('fit_scope', 'calibration_scope', 'quantile', 'quantile_method',
             'alarm_comparison', 'preprocessing_fit_provenance')
_SHARED = ('evidence_kind', 'policy_status', 'time_basis', 'scope', 'selected_policy',
           'score_direction', 'value_space', 'feature_names', 'qualification_windows',
           'provenance', 'preprocessing_state')


class CandidateComparisonError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CandidateComparisonRun:
    family: str
    directory: str | Path


def _require(condition, code='INVALID_COMPARISON'):
    if not condition:
        raise CandidateComparisonError(code)


def _read_manifest(directory):
    """One additional bounded read, later joined to the verifier's actual digest."""
    path = directory / 'manifest.json'
    _ancestors(path)
    before = _ordinary(path)
    _require(0 < before.st_size <= MAX_MANIFEST_BYTES, 'RESOURCE_LIMIT')
    with path.open('rb') as stream:
        payload = stream.read(MAX_MANIFEST_BYTES + 1)
    _require(len(payload) <= MAX_MANIFEST_BYTES, 'RESOURCE_LIMIT')
    after = _ordinary(path)
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    _require(identity(before) == identity(after) and len(payload) == after.st_size,
             'CHANGED_DURING_COMPARISON')
    return _json(payload), dict(sha256=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))


def _slot(family, manifest, report):
    configuration = manifest['configuration']
    if family == 'iforest':
        _require(_same(configuration, if_configuration(report['fit_count'])))
        return SLOT_ORDER[0]
    method, window = configuration['method'], configuration['history_window']
    # The pure fixed configuration function imports no model library.
    _require(_same(configuration, ae_configuration(method, window)))
    return SLOT_ORDER[1] if method == 'current_ae' else f'history_ae26_h{window}'


def _validate_report(family, manifest, report, source):
    expected_profile = IF_VERIFIER if family == 'iforest' else AE_VERIFIER
    expected_model = IF_MODEL if family == 'iforest' else AE_MODEL
    _require(report['status'] == 'VERIFIED' and report['verifier_profile_id'] == expected_profile
             and report['scope'] == 'STORED_ARTIFACT_CONSISTENCY_ONLY'
             and report['evidence_kind'] == 'SYNTHETIC_ONLY' and report['policy_status'] == 'AUDIT_ONLY',
             'INCONSISTENT_VERIFICATION_SCOPE')
    checks = report['checks']
    _require(checks['source_replay'] == ('NOT_PROVIDED' if source is None else 'VERIFIED')
             and checks['model_score_replay'] == 'NOT_CHECKED'
             and checks['model_deserialization'] == 'NOT_PERFORMED'
             and all(checks[key] == 'VERIFIED' for key in
                     ('byte_integrity', 'upstream_lineage', 'stored_score_calibration', 'strict_alarms', 'evaluation')),
             'INCONSISTENT_VERIFICATION_SCOPE')
    if family == 'autoencoder':
        _require(checks['network_reconstruction'] == 'NOT_PERFORMED'
                 and checks['training_execution'] == checks['training_loss_replay'] == 'NOT_CHECKED'
                 and checks['model_origin'] == 'NOT_AUTHENTICATED', 'INCONSISTENT_VERIFICATION_SCOPE')
    _require(manifest['model_profile_id'] == report['model_profile_id'] == expected_model
             and _same(manifest['run_id'], report['run_id'])
             and _same(manifest['selected_policy'], report['selected_policy'])
             and _same(manifest['library_versions'], report['declared_library_versions']))
    _require(type(manifest['run_id']) is str and bool(_RUN_ID.fullmatch(manifest['run_id'])))
    if family == 'autoencoder':
        _require(_same(manifest['runtime'], report['declared_runtime']))


def _execution_controls(rows):
    # Compare only shared declaration keys. IF-only sklearn/joblib and AE-only
    # torch are not a common execution environment or a comparable runtime unit.
    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            lv, rv = left['library_versions'], right['library_versions']
            if any(not _same(lv[key], rv[key]) for key in lv.keys() & rv.keys()):
                return 'DECLARED_EXECUTION_CONTROLS_DIFFER'
            if left['runtime'] is not None and right['runtime'] is not None:
                if not _same(left['runtime'], right['runtime']):
                    return 'DECLARED_EXECUTION_CONTROLS_DIFFER'
    return 'SHARED_DECLARATIONS_CONSISTENT_ONLY'


def _compare(runs, records, inputs, source):
    _require(type(runs) in (list, tuple) and 2 <= len(runs) <= 4)
    _require(all(type(run) is CandidateComparisonRun and type(run.family) is str
                 and run.family in ('iforest', 'autoencoder')
                 and isinstance(run.directory, (str, Path)) for run in runs))
    # Resolve only after lexical checks, including ancestors hidden by '..'.
    directories = []
    for run in runs:
        directory = Path(run.directory)
        _ancestors(directory)
        _ordinary(directory, directory=True)
        directories.append(directory.resolve(strict=True))
    _require(len(set(directories)) == len(directories), 'DUPLICATE_RUN_DIRECTORY')
    rows, ids, slots = [], set(), set()
    reference_context = reference_protocol = reference_counts = reference_population = None
    for spec, directory in zip(runs, directories):
        manifest, identity = _read_manifest(directory)
        verify = verify_candidate_if_run if spec.family == 'iforest' else verify_candidate_ae_run
        report = verify(directory, records, inputs, source_fixture=source)
        # No unverified manifest context is used above this binding point.
        _require(_same(identity, report['artifacts']['manifest.json']), 'CHANGED_DURING_COMPARISON')
        _validate_report(spec.family, manifest, report, source)
        slot = _slot(spec.family, manifest, report)
        _require(slot in SLOT_ORDER)
        run_id = manifest['run_id']
        _require(run_id not in ids, 'DUPLICATE_RUN_ID')
        _require(slot not in slots, 'DUPLICATE_RUN_SLOT')
        ids.add(run_id)
        slots.add(slot)
        context = {key: manifest[key] for key in _SHARED}
        protocol = {key: manifest['configuration'][key] for key in _PROTOCOL}
        counts = {key: report[key] for key in _COUNTS}
        population = {policy: {key: report['policies'][policy][key] for key in _POPULATION}
                      for policy in ('P_U', 'P_B', 'P_A')}
        if reference_context is None:
            reference_context, reference_protocol = context, protocol
            reference_counts, reference_population = counts, population
        else:
            _require(_same(context, reference_context), 'INCOMPARABLE_UPSTREAM')
            _require(_same(protocol, reference_protocol) and _same(counts, reference_counts)
                     and _same(population, reference_population), 'INCOMPARABLE_QUALIFICATION')
        config = manifest['configuration']
        rows.append(dict(slot=slot, run_id=run_id, model_profile_id=report['model_profile_id'],
            verifier_profile_id=report['verifier_profile_id'], configuration=config,
            library_versions=report['declared_library_versions'], runtime=report.get('declared_runtime'),
            architecture=config.get('architecture'), parameter_count=config.get('parameter_count'),
            parameter_count_reason='NOT_DEFINED_FOR_OPAQUE_IF' if spec.family == 'iforest' else None,
            threshold=report['threshold'], calibration=report['calibration'], policies=report['policies'],
            actual_five_artifacts=report['artifacts'], verification_checks=report['checks'],
            verification_scope=report['scope']))
    rows.sort(key=lambda row: SLOT_ORDER.index(row['slot']))
    shared = dict(selected_policy=reference_context['selected_policy'],
        source_replay='NOT_PROVIDED' if source is None else 'VERIFIED',
        feature_names=reference_context['feature_names'], qualification_windows=reference_context['qualification_windows'],
        five_provenance=reference_context['provenance'],
        preprocessing_identity=reference_context['provenance']['preprocess'],
        preprocessing_state=reference_context['preprocessing_state'], qualification_protocol=reference_protocol,
        **reference_counts, test_denominators_by_policy=reference_population)
    return dict(schema_version=1, comparison_profile_id=COMPARISON_PROFILE_ID,
        status='DATA_QUALIFICATION_ALIGNED', evidence_kind='SYNTHETIC_ONLY', policy_status='AUDIT_ONLY',
        scope='SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY',
        included_slots=[slot for slot in SLOT_ORDER if slot in slots],
        missing_slots=[slot for slot in SLOT_ORDER if slot not in slots], shared_context=shared, runs=rows,
        limitations=dict(capacity_control='NOT_COMPARABLE', history_causal_attribution='NOT_COMPARABLE',
            cross_model_score_scale='NOT_COMPARABLE', ranking='NOT_PERFORMED', statistical_significance='NOT_PERFORMED',
            model_execution='NOT_CHECKED', model_origin='NOT_AUTHENTICATED',
            execution_controls=_execution_controls(rows)))


def compare_candidate_runs(runs, record_directory, input_directory, *, source_fixture=None):
    """Return shared stored-data context, not a model execution or effect claim."""
    try:
        return _compare(runs, record_directory, input_directory, source_fixture)
    except CandidateComparisonError:
        raise
    except (CandidateArtifactError, CandidateRunArtifactError, CandidateAERunArtifactError) as exc:
        raise CandidateComparisonError(exc.code) from exc
    except OSError as exc:
        raise CandidateComparisonError('INPUT_UNAVAILABLE') from exc
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        raise CandidateComparisonError('INVALID_COMPARISON') from exc
