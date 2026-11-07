"""Independent, bounded A10 mathematics; no products, numerical libraries or I/O.

Consumes six explicit artificial source recipes. It never consumes their
``expected`` tables. Dict envelopes are freshly allocated ordinary projections;
all axes, masks and numerical rows are tuples, with no product value objects.
"""
from datetime import datetime, timedelta
import hashlib
import json
import math

POLICIES = ('P_U', 'P_B', 'P_A')
FEATURES = ('completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
    'duration_p95_s', 'no_backward_packet_source_record_count')
MASKS = ('train_full_history_normal', 'calibration_full_history_normal',
    'validation_current_normal', 'validation_current_attack', 'validation_current_unknown',
    'test_current_normal', 'test_current_attack', 'test_current_unknown')


def _labels(row):
    label, category = row['Label'], row['Attempted Category']
    if label == 'BENIGN' and category == '-1': return ('normal',) * 3
    if label == 'Portscan' and category == '-1': return ('attack',) * 3
    if label == 'FTP-Patator - Attempted' and category == '0': return ('unknown', 'normal', 'attack')
    if label == 'UNLISTED_ARTIFICIAL_LABEL' and category == '-1': return ('unknown',) * 3
    raise ValueError('UNSUPPORTED_REFERENCE_LABEL')


def _raw(case):
    stamps, ordinals, ids, roles = [], [], [], []
    for ordinal, segment in enumerate(case['segments']):
        current, end = datetime.fromisoformat(segment['start']), datetime.fromisoformat(segment['end'])
        while current < end:
            stamps.append(current); ordinals.append(ordinal)
            ids.append(segment['id']); roles.append(segment['role'])
            if len(stamps) > 240: raise ValueError('REFERENCE_RECIPE_LIMIT')
            current += timedelta(minutes=1)
    lookup = {stamp: index for index, stamp in enumerate(stamps)}
    buckets = [[] for _ in stamps]
    rows = [row for source in case['sources'] for row in source]
    if not 1 <= len(rows) <= 512: raise ValueError('REFERENCE_RECIPE_LIMIT')
    unplaced = outside = 0
    for row in rows:
        if row['Protocol'] != '6' or not row['id'].isascii() or not row['id'].isdecimal():
            raise ValueError('UNSUPPORTED_REFERENCE_ROW')
        try: start = datetime.strptime(row['Timestamp'], '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            if case['name'] != 'D' or row['Timestamp'] != 'not-a-time': raise
            unplaced += 1
            continue
        completion = start + timedelta(microseconds=int(row['Flow Duration']))
        index = lookup.get(completion.replace(second=0, microsecond=0))
        if index is None:
            outside += 1
            continue
        if start.replace(second=0, microsecond=0) != stamps[index]:
            raise ValueError('UNSUPPORTED_REFERENCE_CROSSING')
        buckets[index].append(row)
    values, valid, kinds = [], [], []
    for bucket in buckets:
        if len(bucket) > 1: raise ValueError('UNSUPPORTED_REFERENCE_MULTIPLE_ROWS')
        usable = len(bucket) == 1 and unplaced == 0
        valid.append(usable)
        if not usable:
            values.append((None,) * 13); kinds.append(('unknown',) * 3)
            continue
        row = bucket[0]
        fwd, bwd = float(int(row['Total Fwd Packet'])), float(int(row['Total Bwd packets']))
        fwd_length = float(int(row['Total Length of Fwd Packet']))
        bwd_length = float(int(row['Total Length of Bwd Packet']))
        duration = int(row['Flow Duration']) / 1000000.0
        values.append((1.0, fwd, bwd, fwd_length, bwd_length, 1.0, 0.0, 0.0, 0.0,
                       duration, duration, duration, float(bwd == 0)))
        kinds.append(_labels(row))
    eligible = sum(len(bucket) for bucket in buckets)
    return dict(schema_id='c17-release-91-v1', feature_names=FEATURES,
        timestamps=tuple(stamp.isoformat() for stamp in stamps), segment_ordinals=tuple(ordinals),
        segment_ids=tuple(ids), roles=tuple(roles), values=tuple(values), source_valid=tuple(valid),
        label_kinds=tuple(kinds), counts=dict(raw_records=len(rows), eligible_records=eligible,
            excluded_records=len(rows)-eligible, outside_records=outside, unplaced_invalid_rows=unplaced, duplicate_groups=0),
        bucket_raw_records=tuple(len(bucket) for bucket in buckets),
        bucket_eligible_records=tuple(len(bucket) for bucket in buckets),
        bucket_excluded_records=(0,) * len(stamps), unused_field_issue_records=(0,) * len(stamps))


def _full_normal(valid, normal, stamps, ordinals, window):
    run = 0
    result = []
    for index in range(len(valid)):
        if index == 0 or ordinals[index] != ordinals[index-1] or stamps[index]-stamps[index-1] != timedelta(minutes=1):
            run = 0
        run = run + 1 if valid[index] and normal[index] else 0
        result.append(run >= window + 1)
    return tuple(result)


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle-1] + ordered[middle]) / 2.0


def _history(current, valid, stamps, ordinals, window, epsilon):
    residual, usable, reasons = [], [], []
    start, pending = 0, 'warmup'
    for index, row in enumerate(current):
        if index and ordinals[index] != ordinals[index-1]: start, pending = index, 'boundary'
        elif index and stamps[index]-stamps[index-1] != timedelta(minutes=1): start, pending = index, 'gap'
        if not valid[index]:
            reason = 'invalid_input'; start, pending = index+1, reason
        elif index-start < window:
            reason = pending
        else:
            output = []
            for column in range(13):
                past = tuple(current[j][column] for j in range(index-window, index))
                median = _median(past)
                mad = _median(tuple(abs(value-median) for value in past))
                numerator, denominator = row[column]-median, mad+epsilon
                try: value = numerator/denominator
                except (OverflowError, ZeroDivisionError): value = float('inf')
                if not all(math.isfinite(value) for value in (median, mad, numerator, denominator, value)):
                    break
                output.append(value)
            if len(output) == 13:
                residual.append(tuple(output)); usable.append(True); reasons.append(None)
                continue
            reason = 'nonfinite_history'; start, pending = index+1, reason
        residual.append((None,) * 13); usable.append(False); reasons.append(reason)
    return dict(window=window, residual=tuple(residual), valid=tuple(usable), invalid_reason=tuple(reasons))


def _digest(value):
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8') + b'\n').hexdigest()


def reference_case(case: dict, policy: str) -> dict:
    """Return a new ordinary-value A10 projection, independent of case.expected."""
    if type(case) is not dict or case['name'] not in ('A','A-L','A-V','B','C','D') or policy not in POLICIES:
        raise ValueError('UNSUPPORTED_REFERENCE_CASE')
    configurations = [item for item in case['configurations'] if item['audit_fit_policy'] == policy]
    if len(configurations) != 1: raise ValueError('REFERENCE_POLICY_REQUIRED')
    config = dict(configurations[0])
    config['feature_names'] = tuple(config['feature_names']); config['windows'] = tuple(config['windows'])
    if config['feature_names'] != FEATURES or config['windows'] != (15,30) or config['fit_window'] != 30:
        raise ValueError('UNSUPPORTED_REFERENCE_CONFIG')
    epsilon = config['epsilon']
    if type(epsilon) is not float or not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError('REFERENCE_EPSILON_REQUIRED')
    raw = _raw(case)
    stamps = tuple(datetime.fromisoformat(value) for value in raw['timestamps'])
    ordinals, raw_valid, raw_labels = raw['segment_ordinals'], raw['source_valid'], raw['label_kinds']
    selected = tuple(row[POLICIES.index(policy)] == 'normal' for row in raw_labels)
    qualified = _full_normal(raw_valid, selected, stamps, ordinals, 30)
    fit_mask = tuple(role == 'train' and value for role,value in zip(raw['roles'],qualified))
    indices = tuple(index for index,value in enumerate(fit_mask) if value)
    labels = dict(policies=POLICIES, label_kinds=raw_labels, fit_mask=fit_mask, fit_indices=indices,
                  qualification_masks=None)
    result = dict(schema_version=1, audit_fit_policy=policy, error=None, configuration=config,
                  raw=raw, preprocessing=None, minutes=None, labels=labels)
    if not indices:
        result['error'] = 'NO_TRAINING_NORMAL_MINUTES'
        return result
    means, scales = [], []
    for column in range(13):
        logged = tuple(math.log1p(raw['values'][index][column]) for index in indices)
        if all(value == logged[0] for value in logged):
            mean, scale = logged[0], 1.0
        else:
            mean = math.fsum(logged) / len(logged)
            scale = math.sqrt(math.fsum((value-mean)**2 for value in logged) / len(logged))
            if scale == 0.0: scale = 1.0
        if not math.isfinite(mean) or not math.isfinite(scale) or scale <= 0:
            raise ValueError('REFERENCE_NONFINITE_FIT_STATE')
        means.append(mean); scales.append(scale)
    result['preprocessing'] = dict(mean=tuple(means), scale=tuple(scales), n_samples_seen=len(indices),
        fit_window=30, audit_fit_policy=policy,
        fit_mask_sha256=_digest(dict(schema_version=1,minute_count=len(stamps),mask=fit_mask)),
        fit_rows_sha256=_digest(dict(schema_version=1,rows=tuple(
            dict(index=index,timestamp=raw['timestamps'][index],values=raw['values'][index]) for index in indices))))
    current, valid, reasons = [], [], []
    for ok,row in zip(raw_valid,raw['values']):
        if not ok:
            current.append((None,)*13); valid.append(False); reasons.append('source_invalid')
            continue
        transformed = tuple((math.log1p(value)-mean)/scale for value,mean,scale in zip(row,means,scales))
        good = all(math.isfinite(value) for value in transformed)
        current.append(transformed if good else (None,)*13); valid.append(good)
        reasons.append(None if good else 'nonfinite_transform')
    current, valid = tuple(current), tuple(valid)
    histories = tuple(_history(current, valid, stamps, ordinals, window, epsilon) for window in (15,30))
    common = tuple(valid[index] and histories[0]['valid'][index] and histories[1]['valid'][index] for index in range(len(stamps)))
    result['minutes'] = dict(timestamps=raw['timestamps'],segment_ordinals=ordinals,raw_valid=raw_valid,
        current_values=current,prepared_valid=valid,prepared_reason=tuple(reasons),histories=histories,common_valid=common)
    qualifications = []
    for p_index,p in enumerate(POLICIES):
        normal = tuple(row[p_index] == 'normal' for row in raw_labels)
        full = _full_normal(valid, normal, stamps, ordinals, 30)
        arrays = []
        for mask in MASKS:
            role = mask.split('_',1)[0]
            kind = mask.rsplit('_',1)[1]
            arrays.append(tuple(common[index] and raw['roles'][index] == role and
                (full[index] if role in ('train','calibration') else raw_labels[index][p_index] == kind)
                for index in range(len(stamps))))
        qualifications.append(dict(policy=p,**dict(zip(MASKS,arrays))))
    labels['qualification_masks'] = tuple(qualifications)
    return result


def ready_failure_indices(minutes, window):
    """Diagnostic helper: distinguish ready failures from their pending warmup."""
    history = next(item for item in minutes['histories'] if item['window'] == window)
    start, failures = 0, []
    for index in range(len(minutes['timestamps'])):
        if index and minutes['segment_ordinals'][index] != minutes['segment_ordinals'][index-1]: start = index
        if not minutes['prepared_valid'][index]: start = index+1
        elif index-start >= window and history['invalid_reason'][index] == 'nonfinite_history':
            failures.append(index); start = index+1
    return tuple(failures)
