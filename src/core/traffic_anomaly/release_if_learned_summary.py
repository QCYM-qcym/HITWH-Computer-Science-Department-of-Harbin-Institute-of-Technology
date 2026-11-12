"""Project the admitted learned-package declarations for read-only consumers."""
from .release_if_learned_contract import (
    ReleaseIFLearnedError, ReleaseIFLearnedPackage, ReleaseIFLearnedReference,
    _canonical, encode_release_if_learned_package,
)

_SUMMARY_BYTE_LIMIT = 16384


def _reference(identity: ReleaseIFLearnedReference) -> dict:
    return {
        'profile_id': identity.profile_id,
        'context_sha256': identity.context_sha256,
        'manifest_sha256': identity.manifest_sha256,
        'manifest_byte_count': identity.manifest_byte_count,
    }


def summarize_release_if_learned(package: ReleaseIFLearnedPackage) -> dict:
    """Validate the saved state and return fresh summary fields without replay."""
    try:
        encode_release_if_learned_package(package)
        context = package.context
        config = context.model_configuration
        report = package.load_report
        trees = package.state.trees
        summary = {
            'version': 1,
            'profile_id': 'c17-release-iforest-learned-summary-v1',
            'scope': report.scope,
            'learned_identity': _reference(package.identity),
            'view': context.view,
            'input_references': {
                'raw': _reference(context.raw_identity),
                'prepared': _reference(context.prepared_identity),
            },
            'result_reference': _reference(context.result_identity),
            'declarations': {
                'configuration_sha256': context.configuration_sha256,
                'population_sha256': context.population_sha256,
                'input_rules_id': context.input_rules_id,
                'feature_columns': list(context.feature_columns),
                'model_configuration': {
                    'input_width': config.input_width,
                    'n_estimators': config.n_estimators,
                    'max_samples': config.max_samples,
                    'max_features': config.max_features,
                    'bootstrap': config.bootstrap,
                    'contamination': config.contamination,
                    'random_state': config.random_state,
                    'n_jobs': config.n_jobs,
                },
                'fit_runtime_id': context.fit_runtime_id,
            },
            'counts': {
                'total': context.minute_count,
                'training': context.train_count,
                'calibration': context.calibration_count,
                'preprocessing_fit': context.preprocessing_fit_count,
                'trees': len(trees),
                'nodes': sum(len(tree.nodes) for tree in trees),
            },
            'checks': {
                'byte_integrity': report.byte_integrity,
                'structure': report.structure,
                'numerical_replay': report.numerical_replay,
                'input_pair_binding': 'NOT_PERFORMED',
                'result_binding': 'NOT_PERFORMED',
                'source_authentication': report.source_authentication,
                'model_origin': report.model_origin,
            },
        }
        _canonical(summary, _SUMMARY_BYTE_LIMIT)
        return summary
    except MemoryError:
        raise ReleaseIFLearnedError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is ReleaseIFLearnedError:
            raise
        raise ReleaseIFLearnedError('LEARNED_ERROR') from None
