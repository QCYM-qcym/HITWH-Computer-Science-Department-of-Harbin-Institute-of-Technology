"""Bounded offline C17 improved supply audit. No download, extraction or fitting.

The source schema is intentionally unknown: every field and time interpretation
must be supplied explicitly. This is an audit candidate, not a production input
adapter or approved label/split policy. See tests for SYNTHETIC_ONLY examples.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import struct
import sys
import unicodedata
import zipfile


MINUTE = timedelta(minutes=1)
FEATURE_FIELDS = ('protocol', 'fwd_packets', 'bwd_packets', 'fwd_length', 'bwd_length')


def _positive(value, name):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(name)
    return value


def _integer(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(name)
    return value


def _local_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('regular_singly_linked_file_required')
    return path.resolve(strict=True)


def _clock(raw):
    """Configuration interval clocks are UTC ISO, independent of source format."""
    try:
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if value.tzinfo is not None:
            if value.utcoffset() != timedelta(0):
                raise ValueError('non_UTC_interval')
            value = value.replace(tzinfo=None)
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError('invalid_interval_clock') from exc
    if value.second or value.microsecond:
        raise ValueError('interval_not_minute_aligned')
    return value


def _iso(value):
    return value.strftime('%Y-%m-%d %H:%M:%S.%f') + 'Z'


def _minute(value):
    return value.replace(second=0, microsecond=0)


def _safe_label(value):
    # Count original label words; arbitrary sensitive content is identified by hash.
    if (len(value) <= 128 and all(c.isprintable() for c in value)
            and not re.search(r'[@:/\\]|\b(?:\d{1,3}\.){3}\d{1,3}\b', value)):
        return value
    return 'REDACTED_SHA256_' + hashlib.sha256(value.encode('utf-8')).hexdigest()


def _validate(config):
    if not isinstance(config, dict) or any(not isinstance(config.get(k), dict) for k in ('columns', 'time', 'limits', 'labels')):
        raise ValueError('config_objects_required')
    if any(not isinstance(config.get(k), list) or any(not isinstance(v, dict) for v in config[k]) for k in ('segments', 'capture')):
        raise ValueError('segment_capture_lists_required')
    if config.get('schema') != 'C17_IMPROVED_AUDIT_V1':
        raise ValueError('schema')
    if config.get('identity') not in ('SYNTHETIC_ONLY', 'REAL_LOCAL_AUTHORIZED'):
        raise ValueError('identity')
    columns = config.get('columns', {})
    if not all(isinstance(columns.get(k), str) and columns[k] for k in ('start', 'duration', 'label', 'attempted')):
        raise ValueError('columns')
    if set(columns) - {'start', 'duration', 'label', 'attempted', *FEATURE_FIELDS}:
        raise ValueError('unsupported_columns')
    if len(set(columns.values())) != len(columns):
        raise ValueError('duplicate_column_mapping')
    identity_columns = config.get('identity_columns', [])
    if not isinstance(identity_columns, list) or any(not isinstance(k, str) or not k for k in identity_columns):
        raise ValueError('identity_columns')
    time = config.get('time', {})
    fmt = time.get('format', '')
    if not isinstance(fmt, str) or not all(k in fmt for k in ('%Y', '%m', '%d', '%M', '%S')):
        raise ValueError('time_format')
    if '%I' in fmt and '%p' not in fmt or '%H' in fmt and '%p' in fmt:
        raise ValueError('AM_PM')
    if ('%I' in fmt) == ('%H' in fmt):
        raise ValueError('hour_format')
    if time.get('timezone') != 'UTC' or not isinstance(time.get('utc_evidence'), str) or not time['utc_evidence'].strip():
        raise ValueError('utc_evidence')
    if time.get('duration_unit') not in ('us', 'ms', 's') or not time.get('duration_unit_evidence'):
        raise ValueError('duration_unit')
    for key in ('timestamp_precision_us', 'duration_precision_us'):
        _integer(time.get(key), key)
    if time.get('precision_model') != 'TRUNCATION' or not isinstance(time.get('precision_evidence'), str) or not time['precision_evidence'].strip():
        raise ValueError('precision_model_and_evidence_required')
    if '%f' not in fmt and time['timestamp_precision_us'] < 1000000:
        raise ValueError('timestamp_precision_better_than_text')
    if time['timestamp_precision_us'] > 60000000:
        raise ValueError('timestamp_precision_too_coarse')
    limits = config.get('limits', {})
    for key in ('max_total_input_bytes', 'max_rows', 'max_minutes', 'max_field_chars'):
        _integer(limits.get(key), key)
    _positive(limits.get('max_duration_seconds'), 'max_duration_seconds')
    labels = config.get('labels', {})
    groups = []
    for key in ('normal', 'attack', 'attempted', 'attempted_empty', 'attempted_categories'):
        values = labels.get(key)
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError('label_vocabulary')
        if key in ('normal', 'attack', 'attempted'):
            groups += values
    if not labels['normal'] or len(set(groups)) != len(groups):
        raise ValueError('overlapping_label_vocabulary')
    if set(labels['attempted_empty']) & set(labels['attempted_categories']):
        raise ValueError('overlapping_attempted_categories')
    policy = labels.get('policy', {})
    if not isinstance(policy, dict) or policy.get('status') != 'AUDIT_ONLY' or policy.get('attempted') not in ('normal', 'attack', 'unknown'):
        raise ValueError('AUDIT_ONLY_label_policy')
    segments = []
    ids = set()
    for item in config.get('segments', []):
        name = item.get('id', '')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', name) or name in ids:
            raise ValueError('segment_id')
        ids.add(name)
        if item.get('role') not in ('train', 'calibration', 'validation', 'test'):
            raise ValueError('segment_role')
        begin, end = _clock(item['start']), _clock(item['end'])
        if begin >= end:
            raise ValueError('segment_range')
        segments.append({**item, 'begin': begin, 'finish': end})
    segments.sort(key=lambda item: item['begin'])
    if not segments or any(a['finish'] > b['begin'] for a, b in zip(segments, segments[1:])):
        raise ValueError('segment_overlap_or_missing')
    role_order = {'train': 0, 'validation': 1, 'calibration': 2, 'test': 3}
    if any(role_order[a['role']] > role_order[b['role']] for a, b in zip(segments, segments[1:])):
        raise ValueError('segment_role_order')
    if sum(int((s['finish'] - s['begin']) / MINUTE) for s in segments) > limits['max_minutes']:
        raise ValueError('max_minutes')
    captures = []
    if 'capture' not in config:
        raise ValueError('explicit_capture_mask_required')
    for capture_index, item in enumerate(config['capture']):
        begin, end = _clock(item['start']), _clock(item['end'])
        if begin >= end or item.get('status') not in ('complete', 'gap', 'unknown'):
            raise ValueError('capture_range')
        if item['status'] != 'unknown' and not item.get('evidence'):
            raise ValueError('capture_evidence')
        # Each explicit complete interval is an independent capture epoch.
        captures.append((begin, end, item['status'], capture_index))
    captures.sort()
    if any(a[1] > b[0] for a, b in zip(captures, captures[1:])):
        raise ValueError('capture_overlap')
    empty_normal = []
    if not isinstance(config.get('empty_normal', []), list):
        raise ValueError('empty_normal_intervals_required')
    for item in config.get('empty_normal', []):
        if not isinstance(item, dict):
            raise ValueError('empty_normal_intervals_required')
        begin, end = _clock(item['start']), _clock(item['end'])
        if begin >= end:
            raise ValueError('empty_normal_range')
        if not isinstance(item.get('normal_evidence'), str) or not item['normal_evidence'].strip():
            raise ValueError('empty_normal_evidence')
        empty_normal.append((begin, end))
    empty_normal.sort()
    if any(a[1] > b[0] for a, b in zip(empty_normal, empty_normal[1:])):
        raise ValueError('empty_normal_overlap')
    return segments, captures, empty_normal


def _intervals(minutes, epochs=None):
    runs = []
    for value in sorted(minutes):
        if runs and value == runs[-1][1] and (epochs is None or epochs[value] == epochs[runs[-1][0]]):
            runs[-1][1] += MINUTE
        else:
            runs.append([value, value + MINUTE])
    return [{'start': _iso(a), 'end': _iso(b), 'minutes': int((b - a) / MINUTE)} for a, b in runs]


def _flow_summary(records):
    reasons = Counter(reason for row in records for reason in row['reasons'])
    valid = sum(not row['reasons'] for row in records)
    return {'raw': len(records), 'valid': valid, 'invalid': len(records) - valid, 'reasons': dict(sorted(reasons.items()))}


def _minute_summary(minutes, buckets):
    counts = Counter({k: 0 for k in ('normal', 'attack', 'unknown', 'mixed', 'attempted', 'attack_present',
                                     'label_incomplete', 'confirmed_empty', 'empty_normal', 'empty_unknown',
                                     'invalid', 'gap', 'capture_unknown')})
    for m in minutes:
        b = buckets[m]
        counts[b['kind']] += 1
        for flag in ('mixed', 'attempted', 'attack_present', 'label_incomplete'):
            counts[flag] += b[flag]
        counts['confirmed_empty'] += b['valid'] and not b['rows']
        counts['empty_normal'] += b['valid'] and not b['rows'] and b['kind'] == 'normal'
        counts['empty_unknown'] += b['valid'] and not b['rows'] and b['kind'] == 'unknown'
        counts['invalid'] += b['tainted']
        counts['gap'] += b['capture'] == 'gap'
        counts['capture_unknown'] += b['capture'] == 'unknown'
    return dict(counts)


def _digest_file(path, cap):
    digest = hashlib.sha256()
    count = 0
    with path.open('rb') as handle:
        while chunk := handle.read(min(1048576, cap - count + 1)):
            count += len(chunk)
            if count > cap:
                raise ValueError('max_total_input_bytes_changed')
            digest.update(chunk)
    return count, digest.hexdigest()


def audit_csv(paths, config):
    """Read approved local complete CSVs and return aggregates, never raw rows.

    Unknown or malformed timing quarantines all candidate minutes because the
    affected bucket cannot be bounded. Known invalid events quarantine their
    possible completion bucket(s). Duplicate/identity conflicts invalidate all
    copies. Outside-range events are excluded explicitly. Segment history resets
    at each segment; it never depends on labels. No feature vectors are emitted.
    """
    segments, captures, empty_normal = _validate(config)
    if not paths:
        raise ValueError('input_required')
    paths = [_local_file(path) for path in paths]
    if len(set(paths)) != len(paths):
        raise ValueError('duplicate_input_path')
    limits, time, columns, labels = (config[k] for k in ('limits', 'time', 'columns', 'labels'))
    if sum(p.stat().st_size for p in paths) > limits['max_total_input_bytes']:
        raise ValueError('max_total_input_bytes')
    buckets = {}
    for segment in segments:
        value = segment['begin']
        while value < segment['finish']:
            found = next(((s, epoch) for a, b, s, epoch in captures if a <= value and value + MINUTE <= b), ('unknown', None))
            state, epoch = found
            buckets[value] = {'capture': state, 'epoch': epoch if state == 'complete' else None,
                              'empty_normal': any(a <= value and value + MINUTE <= b for a, b in empty_normal),
                              'rows': [], 'tainted': False}
            value += MINUTE

    def segment_at(value):
        return next((s['id'] for s in segments if s['begin'] <= value < s['finish']), None)

    def capture_epoch_at(value):
        return next((epoch for a, b, s, epoch in captures if s == 'complete' and a <= value < b), None)

    epochs = {m: b['epoch'] for m, b in buckets.items()}

    records, files = [], []
    exact, identities = defaultdict(list), defaultdict(list)
    events = Counter()
    original, attempted_counts, label_anomalies = Counter(), Counter(), Counter()
    global_taint = False
    previous_end = None
    factor = {'us': Decimal(1), 'ms': Decimal(1000), 's': Decimal(1000000)}[time['duration_unit']]
    actual_total_bytes = 0
    for file_index, path in enumerate(paths, 1):
        before = path.stat()
        size, digest = _digest_file(path, limits['max_total_input_bytes'] - actual_total_bytes)
        actual_total_bytes += size
        file_records = []
        previous_file_end = None
        with path.open('r', encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream, strict=True)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError('missing_header') from exc
            if len(header) != len(set(header)) or any(not k or len(k) > limits['max_field_chars'] for k in header):
                raise ValueError('duplicate_or_invalid_header')
            if not set(columns.values()).union(config.get('identity_columns', [])) <= set(header):
                raise ValueError('mapped_columns_missing')
            for values in reader:
                if len(records) >= limits['max_rows']:
                    raise ValueError('max_rows')
                if len(values) != len(header):
                    raise ValueError('inconsistent_column_count')
                if any(len(v) > limits['max_field_chars'] for v in values):
                    raise ValueError('max_field_chars')
                row = dict(zip(header, values))
                record = {'file': file_index, 'reasons': set(), 'possible': set(), 'start': None, 'end': None}
                records.append(record)
                file_records.append(record)
                label, attempted = row[columns['label']], row[columns['attempted']]
                original[_safe_label(label)] += 1
                attempted_counts[_safe_label(attempted)] += 1
                has_attempt = label in labels['attempted'] or attempted not in labels['attempted_empty']
                record['attempted'] = has_attempt
                record['unknown_label'] = label not in labels['normal'] + labels['attack'] + labels['attempted']
                record['attack_present'] = label in labels['attack']
                record['kind'] = (labels['policy']['attempted'] if has_attempt else
                                  'normal' if label in labels['normal'] else
                                  'attack' if label in labels['attack'] else 'unknown')
                if record['unknown_label']:
                    record['kind'] = 'unknown'
                category_known = attempted in labels['attempted_empty'] + labels['attempted_categories']
                contradiction = (label in labels['normal'] + labels['attack'] and has_attempt or
                                 label in labels['attempted'] and attempted in labels['attempted_empty'])
                if not category_known:
                    label_anomalies['unknown_attempted_category'] += 1
                    record['kind'] = 'unknown'
                elif contradiction:
                    label_anomalies['attempted_category_conflict'] += 1
                    record['kind'] = 'unknown'
                if record['unknown_label']:
                    label_anomalies['unknown_original_label'] += 1
                # Hash every source field internally; no source identities leave the process.
                signature = hashlib.sha256(json.dumps(sorted(row.items()), ensure_ascii=False).encode()).digest()
                exact[signature].append(record)
                if config.get('identity_columns'):
                    identity = tuple(row[k] for k in config['identity_columns'])
                    if any(not value for value in identity):
                        record['reasons'].add('missing_flow_identity')
                    else:
                        identities[identity].append(record)
                try:
                    start = datetime.strptime(row[columns['start']], time['format'])
                    if start.tzinfo is not None:
                        if start.utcoffset() != timedelta(0):
                            raise ValueError('non_UTC_source')
                        start = start.replace(tzinfo=None)
                    record['start'] = start
                except (ValueError, OverflowError):
                    record['reasons'].add('invalid_timestamp')
                    global_taint = True
                duration = None
                try:
                    duration = Decimal(row[columns['duration']]) * factor
                    if not duration.is_finite() or duration < 0 or duration != duration.to_integral_value():
                        raise ValueError('duration')
                except (DecimalException, ValueError, OverflowError):
                    record['reasons'].add('invalid_duration')
                    global_taint = True
                    duration = None
                if duration is not None and record['start'] is not None:
                    try:
                        if duration > Decimal('315537897599999999'):
                            raise OverflowError('duration_out_of_datetime_range')
                        end = record['start'] + timedelta(microseconds=int(duration))
                        latest = end + timedelta(microseconds=time['timestamp_precision_us'] + time['duration_precision_us'] - 2)
                        record['end'] = end
                        record['possible'] = {m for m in buckets if _minute(end) <= m <= _minute(latest)}
                        if duration > Decimal(str(limits['max_duration_seconds'])) * 1000000:
                            record['reasons'].add('long_flow')
                        if _minute(end) != _minute(latest):
                            record['reasons'].add('precision_bucket_ambiguity')
                        if _minute(record['start']) != _minute(end):
                            events['cross_minute'] += 1
                        if record['start'].date() != end.date():
                            events['cross_day'] += 1
                        if segment_at(end) is None:
                            record['reasons'].add('outside_candidate_ranges')
                        elif segment_at(record['start']) != segment_at(end):
                            record['reasons'].add('cross_partition')
                        elif segment_at(record['start'] + timedelta(microseconds=time['timestamp_precision_us'] - 1)) != segment_at(end):
                            record['reasons'].add('precision_partition_ambiguity')
                        epoch = capture_epoch_at(record['start'])
                        if (epoch is None or any(capture_epoch_at(t) != epoch for t in
                                                (record['start'] + timedelta(microseconds=time['timestamp_precision_us'] - 1), end, latest))):
                            record['reasons'].add('cross_capture_boundary')
                        if previous_end is not None and end < previous_end:
                            events['order_inversions'] += 1
                        if previous_file_end is not None and end < previous_file_end:
                            events['within_file_order_inversions'] += 1
                        previous_end = previous_file_end = end
                    except (OverflowError, ValueError):
                        # Long unit-mismatched flows cannot be placed safely.
                        record['reasons'].add('long_flow')
                        global_taint = True
                for field in FEATURE_FIELDS:
                    if field not in columns:
                        continue
                    try:
                        value = Decimal(row[columns[field]])
                        if not value.is_finite() or value < 0 or value != value.to_integral_value() or field == 'protocol' and value > 255:
                            raise ValueError(field)
                    except (DecimalException, ValueError):
                        record['reasons'].add('invalid_' + field)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('input_changed_during_audit')
        files.append({'file_id': 'input_' + str(file_index), 'sha256': digest,
                      'bytes': size, '_records': file_records,
                      'observed_completion_buckets': len({ _minute(r['end']) for r in file_records if r['end'] is not None }),
                      'per_file_complete_minutes': None,
                      'per_file_supply_reason': 'GLOBAL_CAPTURE_MASK_NOT_ATTRIBUTABLE_TO_INDIVIDUAL_FILES'})
    for group in exact.values():
        if len(group) > 1:
            for row in group:
                row['reasons'].add('duplicate_record')
            events['duplicate_groups'] += 1
            events['duplicate_cross_file_groups'] += len({r['file'] for r in group}) > 1
    for group in identities.values():
        if len(group) > 1:
            for row in group:
                row['reasons'].add('conflicting_flow_identity')
            events['cross_file_identity_groups'] += len({r['file'] for r in group}) > 1
    for row in records:
        if row['reasons']:
            for m in row['possible']:
                buckets[m]['tainted'] = True
        else:
            buckets[_minute(row['end'])]['rows'].append(row)
    for bucket in buckets.values():
        bucket['tainted'] |= global_taint
        bucket['valid'] = bucket['capture'] == 'complete' and not bucket['tainted']
        kinds = {row['kind'] for row in bucket['rows']}
        bucket['mixed'] = 'normal' in kinds and ('attack' in kinds or any(r['attack_present'] for r in bucket['rows']))
        bucket['attack_present'] = 'attack' in kinds or any(r['attack_present'] for r in bucket['rows'])
        bucket['label_incomplete'] = 'unknown' in kinds or not bucket['rows'] and not bucket['empty_normal']
        bucket['attempted'] = any(row['attempted'] for row in bucket['rows'])
        bucket['kind'] = ('unknown' if not bucket['valid'] or bucket['label_incomplete'] else
                          'attack' if bucket['attack_present'] else 'normal')
    reports = []
    all_history = {15: set(), 30: set()}
    all_common, all_common_normal = set(), set()
    train_counts, test_normal, test_high_candidates = [], [], []
    for segment in segments:
        minutes = [m for m in buckets if segment['begin'] <= m < segment['finish']]
        valid = [m for m in minutes if buckets[m]['valid']]
        counts = _minute_summary(minutes, buckets)
        history, eligible = {}, {}
        for h in (15, 30):
            selected = [m for i, m in enumerate(minutes) if i >= h
                        and all(buckets[t]['valid'] and buckets[t]['epoch'] == buckets[m]['epoch'] for t in minutes[i-h:i+1])]
            normal = [m for i, m in enumerate(minutes) if m in selected and all(buckets[t]['kind'] == 'normal' for t in minutes[i-h:i+1])]
            history[str(h)] = {'valid': len(selected), 'normal_eligible': len(normal)}
            eligible[h] = (set(selected), set(normal))
            all_history[h].update(selected)
        common = eligible[15][0] & eligible[30][0]
        common_normal = eligible[15][1] & eligible[30][1]
        all_common.update(common)
        all_common_normal.update(common_normal)
        if segment['role'] == 'train':
            train_counts += [len(buckets[m]['rows']) for m in common_normal]
        if segment['role'] == 'test':
            test_normal += sorted(m for m in common if buckets[m]['kind'] == 'normal')
            test_high_candidates += sorted(m for m in common if buckets[m]['kind'] == 'normal')
        source_rows = [r for r in records if r['end'] is not None and segment['begin'] <= r['end'] < segment['finish']]
        reports.append({'id': segment['id'], 'role': segment['role'], 'calendar_minutes': len(minutes),
                        'complete_minutes': sum(buckets[m]['capture'] == 'complete' for m in minutes),
                        'input_valid_minutes': len(valid), 'minutes': dict(counts), 'history': history,
                        'common_valid': len(common), 'common_normal': len(common_normal),
                        'current_normal_eligible': counts['normal'], 'flows': _flow_summary(source_rows),
                        'valid_intervals': _intervals(valid, epochs)})
    threshold = None
    if train_counts:
        values = sorted(train_counts)
        position = (len(values) - 1) * 0.9
        lower = int(position)
        threshold = values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)
    high = [m for m in test_high_candidates if threshold is not None and len(buckets[m]['rows']) > threshold]
    high_reason = ('NO_TRAIN_COMMON_NORMAL_MINUTES' if threshold is None else
                   'NO_TEST_COMMON_VALID_NORMAL_MINUTES' if not test_normal else
                   'NO_TEST_MINUTES_STRICTLY_ABOVE_TRAIN_THRESHOLD' if not high else None)
    days = defaultdict(list)
    for row in records:
        days[row['end'].date().isoformat() if row['end'] is not None else 'UNASSIGNED'].append(row)
    for m in buckets:
        days[m.date().isoformat()]
    day_reports = []
    for day, rows in sorted(days.items()):
        day_minutes = {m for m in buckets if m.date().isoformat() == day}
        valid = [m for m in day_minutes if buckets[m]['valid']]
        day_reports.append({'day': day, **_flow_summary(rows), 'minutes': _minute_summary(day_minutes, buckets),
                            'calendar_minutes': len(day_minutes), 'input_valid_minutes': len(valid),
                            'valid_intervals': _intervals(valid, epochs),
                            'history_valid': {str(h): len(v & day_minutes) for h, v in all_history.items()},
                            'common_valid': len(all_common & day_minutes),
                            'common_normal': len(all_common_normal & day_minutes)})
    return {
        'schema': 'C17_IMPROVED_AUDIT_REPORT_V1', 'identity': config['identity'],
        'scope': 'LOCAL_SUPPLY_AUDIT_ONLY', 'config_sha256': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        'label_policy': {k: labels['policy'][k] for k in ('status', 'attempted')},
        'labels': {'original': dict(original), 'attempted_category': dict(attempted_counts)},
        'label_anomalies': dict(label_anomalies),
        'flows': _flow_summary(records), 'flow_events': dict(events),
        'files': [{k: v for k, v in item.items() if k != '_records'} | _flow_summary(item['_records']) for item in files],
        'days': day_reports,
        'segments': reports,
        'high_completion': {'quantile': 0.9, 'interpolation': 'linear', 'comparison': 'STRICTLY_GREATER',
                            'training_eligible': len(train_counts), 'threshold': threshold,
                            'test_normal': len(test_normal), 'test_high_normal': len(high) if threshold is not None else None,
                            'test_ordinary_normal': len(test_normal) - len(high) if threshold is not None else None,
                            'high_intervals': _intervals(high, epochs) if threshold is not None else None,
                            'unavailable_reason': high_reason},
        'time_semantics': {'timezone': 'UTC_CONFIG_ASSERTED_NOT_INDEPENDENTLY_VERIFIED',
                           'bucket': 'START_PLUS_DURATION_END_PROXY_HALF_OPEN',
                           'source_export_time': 'UNKNOWN', 'realtime_availability': 'UNKNOWN',
                           'unplaced_invalid_rows_taint_all_minutes': global_taint,
                           'raw_time_text': 'LOCAL_INPUT_ONLY_NOT_EXPORTED',
                           'precision': 'CONFIGURED_TRUNCATION_INTERVAL_PLUS_QUANTA_MINUS_ONE_MICROSECOND'},
        'capture_epoch_policy': 'EACH_COMPLETE_CAPTURE_INTERVAL_IS_AN_INDEPENDENT_EPOCH',
        'empty_minute_label_policy': 'UNKNOWN_UNLESS_EXPLICIT_EMPTY_NORMAL_INTERVAL_WITH_INDEPENDENT_EVIDENCE',
        'feature_vector_status': 'NOT_VERIFIED_NO_12_OR_24_DIMENSION_VECTOR_PRODUCED',
        'common_valid_scope': 'CONFIGURED_FIELDS_ONLY_CURRENT_AND_H15_H30_COMPLETENESS_INTERSECTION',
        'model_common_valid_minutes': {'IF': None, 'current_AE': None, 'history_AE_H15': None, 'history_AE_H30': None},
        'protocol_semantics': 'NOT_VERIFIED_NUMERIC_RANGE_ONLY',
        'mapped_numeric_fields': [k for k in FEATURE_FIELDS if k in columns],
        'missing_numeric_fields': [k for k in FEATURE_FIELDS if k not in columns],
        'deduplication_limit': 'EXACT_FULL_ROW_HASH_AND_OPTIONAL_EXPLICIT_IDENTITY_ONLY',
        'real_training': 'NOT_RUN', 'scoring': 'NOT_RUN', 'score_calibration': 'NOT_RUN',
        'dataset_adoption': 'NOT_APPROVED', 'production_contract_migration': 'NOT_APPROVED',
    }


def _preflight_directory(path, offset, length, declared_count, max_members):
    """Count real directory records with fixed-size reads before ZipFile allocates.

    The maximum record has 46 fixed bytes and three unsigned-16-bit metadata
    lengths. Reject excessive directory bytes, malformed lengths and false EOCD
    counts before any bulk directory parser or ZipInfo construction.
    """
    if length > max_members * (46 + 3 * 65535):
        raise ValueError('max_directory_bytes')
    finish = offset + length
    observed = 0
    with path.open('rb') as handle:
        handle.seek(offset)
        while handle.tell() < finish:
            if observed >= max_members:
                raise ValueError('max_members')
            if finish - handle.tell() < 46:
                raise ValueError('invalid_directory_record_length')
            fixed = handle.read(46)
            if len(fixed) != 46 or fixed[:4] != b'PK\x01\x02':
                raise ValueError('invalid_directory_record')
            fields = struct.unpack('<4s6H3L5H2L', fixed)
            if fields[2] > 20:
                raise ValueError('unsupported_zip_version')
            if fields[8] == 4294967295 or fields[9] == 4294967295 or fields[16] == 4294967295 or fields[13]:
                raise ValueError('multidisk_or_zip64_unsupported')
            metadata_bytes = fields[10] + fields[11] + fields[12]
            if handle.tell() + metadata_bytes > finish:
                raise ValueError('invalid_directory_metadata_length')
            handle.seek(metadata_bytes, 1)
            observed += 1
    if observed != declared_count:
        raise ValueError('zip_member_count_mismatch')


def check_archive(path, limits):
    """Inspect EOCD/central directory metadata only; never open/extract members.

    Fail closed on multi-disk/ZIP64, unsupported compression or unsafe paths.
    This is a pre-extraction gate, not a CRC/content or source authenticity check.
    """
    if not isinstance(limits, dict):
        raise ValueError('archive_limits_object_required')
    allowed_limits = ('max_archive_bytes', 'max_members', 'max_member_bytes',
                      'max_total_uncompressed_bytes', 'max_compression_ratio')
    for key in allowed_limits[:-1]:
        _integer(limits.get(key), key)
    _positive(limits.get('max_compression_ratio'), 'max_compression_ratio')
    path = _local_file(path)
    size = path.stat().st_size
    if size > limits['max_archive_bytes']:
        raise ValueError('max_archive_bytes')
    with path.open('rb') as handle:
        handle.seek(max(0, size - 65557))
        tail = handle.read(65557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError('invalid_zip_eocd')
    _, disk, directory_disk, disk_count, count, directory_bytes, directory_offset, comment = struct.unpack_from('<4s4H2LH', tail, offset)
    if disk or directory_disk or disk_count != count or count == 65535 or directory_bytes == 4294967295 or directory_offset == 4294967295:
        raise ValueError('multidisk_or_zip64_unsupported')
    if len(tail) - offset != 22 + comment or directory_offset + directory_bytes != size - len(tail) + offset:
        raise ValueError('zip_directory_layout')
    if count > limits['max_members']:
        raise ValueError('max_members')
    _preflight_directory(path, directory_offset, directory_bytes, count, limits['max_members'])
    total = compressed = 0
    seen = {}
    with zipfile.ZipFile(path, 'r') as archive:
        members = archive.infolist()
        if len(members) != count:
            raise ValueError('zip_member_count_mismatch')
        for item in members:
            name = unicodedata.normalize('NFC', item.orig_filename)
            parts = name.rstrip('/').split('/')
            if (not name or '\\' in name or ':' in name or '//' in name or name.startswith('/')
                    or any(part in ('', '.', '..') or part.rstrip(' .') != part for part in parts)
                    or any(ord(c) < 32 for c in name)):
                raise ValueError('member_path')
            if any(re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p) for p in parts):
                raise ValueError('member_path_reserved')
            normalized = '/'.join(parts).casefold()
            if normalized in seen:
                raise ValueError('member_path_collision')
            is_directory = item.is_dir()
            if any(normalized.startswith(known + '/') and not directory or
                   known.startswith(normalized + '/') and not is_directory for known, directory in seen.items()):
                raise ValueError('member_file_directory_collision')
            seen[normalized] = is_directory
            kind = stat.S_IFMT(item.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or item.external_attr & 0x400:
                raise ValueError('member_type')
            if item.flag_bits & (1 | 64):
                raise ValueError('encrypted_member')
            if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError('unsupported_compression')
            if item.file_size > limits['max_member_bytes']:
                raise ValueError('max_member_bytes')
            if item.file_size and not item.compress_size:
                raise ValueError('invalid_compressed_size')
            if item.file_size / max(item.compress_size, 1) > limits['max_compression_ratio']:
                raise ValueError('max_compression_ratio')
            total += item.file_size
            compressed += item.compress_size
            if total > limits['max_total_uncompressed_bytes']:
                raise ValueError('max_total_uncompressed_bytes')
    return {'scope': 'ZIP_CENTRAL_DIRECTORY_ONLY', 'archive_bytes': size, 'members': count,
            'identity': 'UNCLASSIFIED_LOCAL_ARCHIVE',
            'total_uncompressed_bytes': total, 'total_compressed_member_bytes': compressed,
            'extracted': False, 'member_contents_read': False, 'crc_verified': False,
            'limits': {k: limits[k] for k in allowed_limits}, 'source_authenticity': 'NOT_VERIFIED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', help='Explicit approved local CSV; repeat for multiple files')
    parser.add_argument('--archive-check', type=Path, help='Approved local ZIP, central-directory metadata only')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New aggregate JSON; never overwrite')
    args = parser.parse_args(argv)
    try:
        if bool(args.input) == bool(args.archive_check):
            raise ValueError('choose_csv_or_archive')
        config_path = _local_file(args.config)
        if config_path.stat().st_size > 1048576:
            raise ValueError('config_size')
        output = args.output.resolve()
        inputs = [_local_file(p) for p in (args.input or [args.archive_check])]
        if output.exists() or output in inputs or output == config_path:
            raise ValueError('output_exists_or_aliases_input')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if not isinstance(config, dict):
            raise ValueError('config_objects_required')
        report = (audit_csv(inputs, config) if args.input else
                  check_archive(inputs[0], config['archive_limits']))
        if args.archive_check:
            if config.get('identity') not in ('SYNTHETIC_ONLY', 'REAL_LOCAL_AUTHORIZED'):
                raise ValueError('identity')
            report['identity'] = config['identity']
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'status': 'AUDIT_PREPARATION_ONLY', 'scope': report['scope']}))
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, csv.Error,
            zipfile.BadZipFile, OverflowError, NotImplementedError, RuntimeError, struct.error, DecimalException) as exc:
        # Never print source rows, local paths or arbitrary exception messages.
        if isinstance(exc, json.JSONDecodeError):
            code = 'INVALID_JSON'
        elif isinstance(exc, KeyError):
            code = 'CONFIG_KEY_MISSING'
        elif isinstance(exc, OSError):
            code = 'IO_ERROR'
        elif isinstance(exc, csv.Error):
            code = 'CSV_PARSE_ERROR'
        elif isinstance(exc, zipfile.BadZipFile):
            code = 'INVALID_ZIP'
        elif isinstance(exc, (TypeError, AttributeError)):
            code = 'CONFIG_SCHEMA_ERROR'
        elif isinstance(exc, (OverflowError, DecimalException)):
            code = 'NUMERIC_LIMIT_OR_VALUE_ERROR'
        elif isinstance(exc, NotImplementedError):
            code = 'UNSUPPORTED_ARCHIVE_OR_CONFIG'
        elif isinstance(exc, (RuntimeError, struct.error)):
            code = 'INVALID_ARCHIVE_OR_CONFIG'
        else:
            code = str(exc) if type(exc) is ValueError and re.fullmatch(r'[A-Za-z0-9_]+', str(exc)) else 'INVALID_INPUT_CONFIG_ARCHIVE_OR_OUTPUT'
        print('AUDIT_FAILED_' + code + '; no full audit claim', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
