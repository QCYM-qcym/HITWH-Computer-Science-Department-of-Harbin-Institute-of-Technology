"""Two prescribed artificial AE profiles; configuration is not provenance.

No model runtime, paths, fixture reads, arbitrary topology or tuning API.
Every call returns a fresh complete configuration with exact scalar types.
"""
from __future__ import annotations

import math
from collections.abc import Mapping


MODEL_PROFILE_ID = 'c17-i1-g13u-ae-synthetic-v1'
CAPACITY492_MODEL_PROFILE_ID = 'c17-i1-g13u-ae-current-capacity492-synthetic-v1'
CAPACITY492_SOURCE_SHA256 = '6f42399eabb07dc218eac19f4d648e57eb360a0c7167968ca1770733ea8649b2'
CAPACITY492_SOURCE_BYTE_COUNT = 213497
# Predeclared byte identities of the fixed artificial fixture only. Git's LF
# blob and the previously admitted CRLF checkout remain distinct sources in
# provenance; admission never normalizes bytes or derives an accepted hash.
CAPACITY492_SOURCE_IDENTITIES = (
    (CAPACITY492_SOURCE_SHA256, CAPACITY492_SOURCE_BYTE_COUNT),
    ('0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff', 205567),
)


def capacity492_source_identity_matches(identity) -> bool:
    """Match an exact size/SHA pair, without IO or caller-supplied allowlists."""
    return isinstance(identity, Mapping) and any(
        strict_configuration_equal(dict(identity), dict(sha256=sha, byte_count=size))
        for sha, size in CAPACITY492_SOURCE_IDENTITIES)


def capacity492_source_binding_matches(report, provenance) -> bool:
    """Check metadata from the actual loader, never authenticate declarations.

    Execution/admission must call the loader with the real source argument
    first; this helper neither reads paths nor accepts an authorization flag.
    """
    if not isinstance(report,Mapping) or not isinstance(provenance,Mapping):
        return False
    checks=report.get('checks')
    if (not isinstance(checks,Mapping) or type(checks.get('source_replay')) is not str
            or checks['source_replay'] != 'VERIFIED'):
        return False
    identity, bound = report.get('source_fixture'), provenance.get('source_fixture')
    return (isinstance(identity, Mapping) and isinstance(bound, Mapping)
        and strict_configuration_equal(dict(identity), dict(bound))
        and capacity492_source_identity_matches(identity))


def strict_configuration_equal(actual, expected) -> bool:
    """Compare the prescribed JSON tree, including bool/int/float/list types."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (all(type(key) is str for key in actual)
                and actual.keys() == expected.keys()
                and all(strict_configuration_equal(actual[key],value) for key,value in expected.items()))
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            strict_configuration_equal(left,right) for left,right in zip(actual,expected))
    if type(expected) is float:
        return math.isfinite(actual) and actual.hex() == expected.hex()
    return type(expected) in (str,int,float,bool,type(None)) and actual == expected


def resolve_candidate_ae_configuration(method, history_window=None, *, model_profile_id=MODEL_PROFILE_ID):
    """Resolve only the old current/H15/H30 and the predefined current492."""
    if (type(model_profile_id) is not str
            or model_profile_id not in (MODEL_PROFILE_ID,CAPACITY492_MODEL_PROFILE_ID)
            or type(method) is not str or method not in ('current_ae','history_ae')
            or (history_window is not None if method == 'current_ae'
                else type(history_window) is not int or history_window not in (15,30))
            or model_profile_id == CAPACITY492_MODEL_PROFILE_ID and method != 'current_ae'):
        raise ValueError('INVALID_AE_PROFILE')
    width = 13 if method == 'current_ae' else 26
    hidden = 14 if model_profile_id == CAPACITY492_MODEL_PROFILE_ID else 8
    parameters = 492 if hidden == 14 else 288 if width == 13 else 509
    return dict(model_profile_id=model_profile_id, parameter_status='ENGINEERING_TOY_ONLY',
        method=method, input_width=width, history_window=history_window,
        architecture=[width,hidden,3,hidden,width], parameter_count=parameters,
        activation='RELU_HIDDEN_LINEAR_OUTPUT', device='cpu', training_dtype='float32',
        score_dtype='float64', score_rule='FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT',
        epochs=5, batch_strategy='FULL_BATCH', shuffle=False, optimizer='Adam',
        optimizer_cpu_guard='INSTANCE_LOCAL_HEALTH_CHECK_V1',
        optimizer_healthcheck_api='_accelerator_graph_capture_health_check',
        learning_rate=.001, adam_betas=[.9,.999], adam_epsilon=1e-8,
        weight_decay=0., amsgrad=False, random_state=42,
        fit_scope='TRAIN_NORMAL_COMMON', calibration_scope='CALIBRATION_NORMAL_COMMON',
        quantile=.99, quantile_method='linear', alarm_comparison='STRICT_GREATER',
        preprocessing_fit_provenance='NOT_REESTIMATED')
