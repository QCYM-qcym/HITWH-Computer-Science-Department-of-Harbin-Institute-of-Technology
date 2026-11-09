"""Pure saved-field summary; no package I/O, replay or parameter estimation."""
from __future__ import annotations

from .release_inputs import ReleasePreparedInputs

_QUALIFICATION_NAMES=('train_full_history_normal','calibration_full_history_normal',
    'validation_current_normal','validation_current_attack','validation_current_unknown',
    'test_current_normal','test_current_attack','test_current_unknown')
_CHECK_NAMES=('status','scope','byte_integrity','structure','upstream_replay',
    'transform_history_replay','fit_parameters')


def _identity(value):
    return {name:getattr(value,name) for name in ('profile_id','context_sha256','manifest_sha256','manifest_byte_count')}


def summarize_release_inputs(saved: ReleasePreparedInputs) -> dict:
    """Project only the documented saved fields; count masks without replay."""
    context=saved.context;config=context.configuration;minutes=saved.minutes
    state=saved.preprocessing
    return dict(
        identity=_identity(saved.identity),upstream_identity=_identity(context.upstream),
        source_authentication=context.source_authentication,time_basis=context.time_basis,
        configuration=dict(schema_version=config.schema_version,numeric_rules_id=config.numeric_rules_id,
            windows=list(config.windows),fit_window=config.fit_window,epsilon=config.epsilon,
            audit_fit_policy=config.audit_fit_policy,policy_status=config.policy_status,
            feature_count=len(config.feature_names)),
        configuration_sha256=context.configuration_sha256,
        minute_counts=dict(total=context.minute_count,raw_valid=sum(minutes.raw_valid),
            prepared_valid=sum(minutes.prepared_valid),common_valid=sum(minutes.common_valid),
            history_h15_valid=sum(minutes.histories[0].valid),history_h30_valid=sum(minutes.histories[1].valid)),
        fit=dict(count=state.n_samples_seen,mask_sha256=state.fit_mask_sha256,rows_sha256=state.fit_rows_sha256),
        qualification_counts={q.policy:{name:sum(getattr(q,name)) for name in _QUALIFICATION_NAMES}
                              for q in saved.labels.qualification_masks},
        package_checks={name:getattr(saved.load_report,name) for name in _CHECK_NAMES},
    )
