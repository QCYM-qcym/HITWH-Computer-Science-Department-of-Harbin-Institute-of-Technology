"""Sealed artificial evaluation cases; prepare happens only in test setup.

All label/role changes precede raw sealing and actual artificial preparation.
Saved scores are hand-valued, never produced by an estimator. These identities
prove internal bytes only; no source CSV or source authentication is claimed.
"""
from types import SimpleNamespace


def sealed_evaluation_case(*, scenario='mixed', view='current13'):
    from tests.core.release_input_cases import make_upstream, make_config
    from traffic_anomaly.release_inputs import (
        prepare_release_inputs, encode_release_input_package, decode_release_input_package,
    )
    from traffic_anomaly.release_model_inputs import pair_release_model_inputs
    from traffic_anomaly.release_iforest import ReleaseIFResult, ReleaseIFConfiguration
    from traffic_anomaly.release_if_result_contract import (
        make_release_if_result_package, encode_release_if_result_package, decode_release_if_result_package,
    )
    if scenario not in ('mixed', 'no_test', 'no_normal', 'no_attack', 'no_positive', 'all_unknown'):
        raise ValueError('unknown_artificial_evaluation_scenario')
    if view not in ('current13', 'h30_26'):
        raise ValueError('unknown_artificial_evaluation_view')
    roles = ('train', 'validation', 'calibration', 'calibration' if scenario == 'no_test' else 'test')
    labels = {}
    if scenario in ('mixed', 'no_positive'):
        # test local0/1/2 are unscored attack/attempted/unknown; local30..37
        # cover scored normal/attack/unknown/attempted with True/False each.
        for local in (0, 32, 33): labels[128 + local] = ('attack',) * 3
        for local in (1, 36, 37): labels[128 + local] = ('unknown', 'normal', 'attack')
        for local in (2, 34, 35): labels[128 + local] = ('unknown',) * 3
    elif scenario in ('no_normal', 'no_attack', 'all_unknown'):
        kind = {'no_normal': 'attack', 'no_attack': 'normal', 'all_unknown': 'unknown'}[scenario]
        labels = {index: (kind,) * 3 for index in range(128, 176)}
    raw = make_upstream(roles=roles, label_overrides=labels)
    # Exactly one real artificial preprocessing call per helper invocation.
    # It is setup, not an operation performed by the evaluator or readonly CLI.
    prepared = prepare_release_inputs(raw, make_config())
    prepared = decode_release_input_package(dict(encode_release_input_package(prepared)))
    pair = pair_release_model_inputs(raw, prepared)
    positive = {30, 78}  # non-test saved alarms must not enter test metrics.
    if scenario not in ('no_test', 'no_positive'):
        positive |= {158, 160, 162, 164}
    scores = tuple((1. if index in positive else 0.) if valid else None
                   for index, valid in enumerate(pair.prepared_minutes.common_valid))
    predictions = tuple(None if score is None else score > 0. for score in scores)
    population = pair.population
    result = ReleaseIFResult('c17-release-iforest-engineering-v1', view, pair.raw_identity,
        pair.prepared_identity, pair.configuration_sha256, scores, predictions,
        pair.prepared_minutes.common_valid, 0., population.train_indices, population.calibration_indices,
        population.preprocessing_fit_indices, ReleaseIFConfiguration(13 if view == 'current13' else 26,
            16, min(32, len(population.train_indices)), 1., False, 'auto', 42, 1))
    package = make_release_if_result_package(pair, result)
    package = decode_release_if_result_package(dict(encode_release_if_result_package(package)))
    return SimpleNamespace(raw=raw, prepared=prepared, pair=pair, result=package.result, package=package)
