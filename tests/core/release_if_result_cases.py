"""Independent hand-valued inputs/results; no preparation or estimator execution."""
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json

from traffic_anomaly.candidate_inputs import G13U_FEATURE_NAMES
from traffic_anomaly._release_minutes import ReleaseSegment
from traffic_anomaly.release_minute_contract import ReleaseMinutePackageIdentity
from traffic_anomaly.release_inputs import (
    ReleasePreparationConfig, ReleaseInputIdentity, ReleasePreprocessState,
    ReleasePreparedHistory, ReleasePreparedMinutes, ReleaseInputLabels,
    ReleasePolicyQualification,
)
from traffic_anomaly.release_model_inputs import (
    ReleaseModelInputPair, ReleaseModelLabelSidecar, ReleaseModelPopulation,
)

TRAIN = tuple(range(30, 48))
COMMON = (*range(30, 48), *range(78, 88), *range(118, 128), *range(158, 176))


def _digest(doc):
    payload = (json.dumps(doc, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':')) + '\n').encode()
    return hashlib.sha256(payload).hexdigest()


def _mask(indices, n=176):
    return tuple(i in indices for i in range(n))


def hand_pair(*, kinds=None, train=tuple(range(31, 48)), cal=(124, 125, 126, 127), fit=TRAIN,
          invalid_train=False, invalid_first=True):
    # Four hand-chosen segments: 48/40/40/48. First 30 rows of each
    # cannot have a complete 31-minute current-plus-history normal window.
    start = datetime(2026, 1, 1)
    bounds = (0, 48, 88, 128, 176)
    roles = ('train', 'validation', 'calibration', 'test')
    segments = tuple(ReleaseSegment(f's{j}', role, start + timedelta(minutes=a),
                                    start + timedelta(minutes=b))
                     for j, (role, a, b) in enumerate(zip(roles, bounds, bounds[1:])))
    ordinals = (0,) * 48 + (1,) * 40 + (2,) * 40 + (3,) * 48
    stamps = tuple(start + timedelta(minutes=i) for i in range(176))
    valid = tuple(not (invalid_train and i < 48 or invalid_first and i == 0)
                  for i in range(176))
    current = tuple(tuple(float(i) + j / 100 for j in range(13))
                    if valid[i] else (None,) * 13 for i in range(176))
    histories = []
    for window in (15, 30):
        good, reasons = [], []
        for i, ordinal in enumerate(ordinals):
            local = i - bounds[ordinal]
            if invalid_train and ordinal == 0 or invalid_first and i == 0:
                ok, reason = False, 'invalid_input'
            elif invalid_first and ordinal == 0:
                ok = local >= window + 1
                reason = None if ok else 'invalid_input'
            else:
                ok = local >= window
                reason = None if ok else ('warmup' if ordinal == 0 else 'boundary')
            good.append(ok)
            reasons.append(reason)
        residual = tuple(tuple(-float(i) - j / 10 for j in range(13))
                         if good[i] else (None,) * 13 for i in range(176))
        histories.append(ReleasePreparedHistory(window, residual, tuple(good), tuple(reasons)))
    common_indices = COMMON
    if invalid_train:
        common_indices = (*range(78, 88), *range(118, 128), *range(158, 176))
    elif invalid_first:
        common_indices = (*range(31, 48), *range(78, 88), *range(118, 128), *range(158, 176))
    common = _mask(common_indices)
    minutes = ReleasePreparedMinutes(stamps, ordinals, (True,) * 176, current, valid,
        tuple(None if ok else 'nonfinite_transform' for ok in valid), tuple(histories), common)
    if kinds is None:
        # Attack at 93 excludes calibration windows 118..123; windows starting
        # at 94 leave exactly the four saved calibration minutes 124..127.
        kinds = (('normal',) * 3,) * 93 + (('attack',) * 3,) + (('normal',) * 3,) * 82
    quals = []
    for column, policy in enumerate(('P_U', 'P_B', 'P_A')):
        masks = [_mask(train), _mask(cal)]
        for role in ('validation', 'test'):
            for kind in ('normal', 'attack', 'unknown'):
                masks.append(tuple(i in common_indices and roles[ordinals[i]] == role
                                   and kinds[i][column] == kind for i in range(176)))
        quals.append(ReleasePolicyQualification(policy, *masks))
    labels = ReleaseInputLabels(('P_U', 'P_B', 'P_A'), kinds, _mask(fit), fit, tuple(quals))
    config = ReleasePreparationConfig(1, 'c17-release-log1p-mad-input-rules-v1',
        G13U_FEATURE_NAMES, (15, 30), 30, 1e-6, 'P_U', 'AUDIT_ONLY')
    state = ReleasePreprocessState((0.,) * 13, (1.,) * 13, len(fit), 30, 'P_U',
        _digest(dict(schema_version=1, minute_count=176, mask=_mask(fit))), 'e' * 64)
    joined = tuple(tuple(c + r if ok else (None,) * 26
                         for c, r, ok in zip(current, h.residual, h.valid)) for h in histories)
    return ReleaseModelInputPair('c17-release-model-input-pair-v1',
        ReleaseMinutePackageIdentity('c17-release-minute-package-v1', 'a' * 64, 'b' * 64, 123),
        ReleaseInputIdentity('c17-release-prepared-input-package-v1', 'c' * 64, 'd' * 64, 456),
        config, _digest(asdict(config)), state, segments,
        tuple(f's{j}' for j in ordinals), tuple(roles[j] for j in ordinals),
        tuple(tuple(float(i + j) for j in range(13)) for i in range(176)),
        minutes, joined[0], joined[1], ReleaseModelLabelSidecar(labels, (False,) * 176),
        ReleaseModelPopulation('P_U', _mask(fit), fit, _mask(train), train, _mask(cal), cal),
        'PACKAGE_INTERNAL_CONSISTENCY_ONLY', 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY',
        'c17-release-91-v1', 'NOT_AUTHENTICATED', 'SOURCE_WALL_CLOCK_COMPLETION_PROXY')


def hand_result(pair=None, view='current13'):
    from traffic_anomaly.release_iforest import ReleaseIFResult, ReleaseIFConfiguration
    pair = hand_pair() if pair is None else pair
    scores = [None] * 176
    for i in (*range(31, 48), *range(78, 88), *range(118, 128), *range(158, 176)):
        scores[i] = 0.
    scores[31] = -0.
    scores[124:128] = [0., 1., 2., 3.]
    scores[158] = 4.
    threshold = 2.9699999999999998
    return ReleaseIFResult('c17-release-iforest-engineering-v1', view,
        pair.raw_identity, pair.prepared_identity, pair.configuration_sha256,
        tuple(scores), tuple(None if v is None else v > threshold for v in scores),
        tuple(v is not None for v in scores), threshold, tuple(range(31, 48)),
        (124, 125, 126, 127), tuple(range(30, 48)),
        ReleaseIFConfiguration(13 if view == 'current13' else 26, 16, 17, 1., False, 'auto', 42, 1))


def canonical(document):
    return (json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def reference_members(pair=None, view='current13'):
    """Independent JSON schema construction; does not call any product codec."""
    pair = hand_pair() if pair is None else pair
    result = hand_result(pair, view)
    context = dict(profile_id='c17-release-iforest-result-package-v1',
        result_profile_id='c17-release-iforest-engineering-v1', view=view,
        source_schema_id='c17-release-91-v1', source_authentication='NOT_AUTHENTICATED',
        time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY', policy_status='AUDIT_ONLY',
        audit_fit_policy='P_U', raw_identity=asdict(pair.raw_identity),
        prepared_identity=asdict(pair.prepared_identity),
        configuration_sha256=pair.configuration_sha256, model_configuration=asdict(result.configuration),
        segments=[dict(ordinal=j, id=f's{j}', role=role, start=start, end=end)
            for j, (role, start, end) in enumerate((
                ('train', '2026-01-01T00:00:00', '2026-01-01T00:48:00'),
                ('validation', '2026-01-01T00:48:00', '2026-01-01T01:28:00'),
                ('calibration', '2026-01-01T01:28:00', '2026-01-01T02:08:00'),
                ('test', '2026-01-01T02:08:00', '2026-01-01T02:56:00')))],
        minute_count=176, score_direction='NEGATIVE_SCORE_SAMPLES',
        calibration=dict(quantile=0.99, method='linear', comparison='STRICT_GREATER'))
    sha = hashlib.sha256(canonical(context)).hexdigest()
    document = dict(schema_version=1, profile_id='c17-release-iforest-result-package-v1',
        context_sha256=sha, **{key: getattr(result, key) for key in ('scores', 'predictions',
            'scored_mask', 'threshold', 'train_indices', 'calibration_indices', 'preprocessing_fit_indices')})
    payload = canonical(document)
    manifest = canonical(dict(schema_version=1, profile_id='c17-release-iforest-result-package-v1',
        context_sha256=sha, context=context, members={'result.json': dict(byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest())}))
    complete = canonical(dict(schema_version=1, profile_id='c17-release-iforest-result-package-v1',
        status='COMPLETE', manifest=dict(byte_count=len(manifest), sha256=hashlib.sha256(manifest).hexdigest())))
    return {'result.json': payload, 'manifest.json': manifest, 'COMPLETE.json': complete}
