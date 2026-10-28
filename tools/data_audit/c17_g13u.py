"""Offline G13U supply qualification for hash-bound released CSV records.

Only exact source protocol 0 gains a separate unresolved channel. The prior
payload rules and fingerprint index are reused read-only. Real auditing keeps
bounded minute counters, never source rows or duration samples, and emits no
production feature matrix, preprocessing state, model, or scores.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import timedelta
from decimal import Decimal, DecimalException
import json
from pathlib import Path
import sqlite3
import sys

try:
    from tools.data_audit import c17_payload as payload
except ModuleNotFoundError:
    import c17_payload as payload

rules = payload.rules
KNOWN = frozenset((1, 2, 6, 17, 132))
CHANNELS = ('tcp', 'udp', 'known_other', 'unresolved')
POLICIES = ('P_U', 'P_B', 'P_A')
FEATURE_ORDER = (
    'completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
    'duration_p95_s', 'no_backward_packet_source_record_count',
)


def _nonnegative_integer(value):
    if isinstance(value, bool):
        raise ValueError('integer')
    try:
        text = str(value)
        if len(text) > 4096:
            raise ValueError('integer_size')
        parsed = Decimal(text)
        if (not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value()
                or parsed.adjusted() >= 4096):
            raise ValueError('integer')
        return int(parsed)
    except (DecimalException, TypeError, OverflowError) as exc:
        raise ValueError('integer') from exc


def _channel(raw):
    try:
        if isinstance(raw, bool):
            return 'excluded_protocol'
        parsed = Decimal(str(raw))
        if not parsed.is_finite() or not 0 <= parsed <= 255 or parsed != parsed.to_integral_value():
            return 'excluded_protocol'
        value = int(parsed)
    except (ValueError, DecimalException, TypeError):
        return 'excluded_protocol'
    if value == 6:
        return 'tcp'
    if value == 17:
        return 'udp'
    if value == 0:
        return 'unresolved'
    return 'known_other' if value in KNOWN else 'excluded_protocol'


def _quantile(ordered, q):
    if all(type(v) is int for v in ordered):
        # Integer completion counts need an exact interpolation weight. Binary
        # 0.9 * 9 can put the result just below an integer and change strict >.
        position = Decimal(len(ordered) - 1) * Decimal(str(q))
        low = int(position)
        return float(Decimal(ordered[low]) + Decimal(ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low))
    position = (len(ordered) - 1) * q
    low = int(position)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)


def aggregate_candidate_records(records, max_records=10000):
    """Pure capped sample definition check; labels/identities never enter G13U.

    Any invalid record makes the whole sample vector unavailable. The raw and
    eligible counts remain visible; silently aggregating a partial minute would
    hide the same contamination that disqualifies a real minute.
    """
    if type(max_records) is not int or not 1 <= max_records <= 10000:
        raise ValueError('sample_cap')
    raw = eligible = no_backward = 0
    channels = Counter({k: 0 for k in CHANNELS})
    sums = Counter()
    durations = []
    for record in records:
        raw += 1
        if raw > max_records:
            raise ValueError('sample_cap')
        try:
            values = {k: _nonnegative_integer(record[k]) for k in
                      ('protocol', 'fwd_packets', 'bwd_packets', 'fwd_length', 'bwd_length', 'duration_us')}
            channel = _channel(values['protocol'])
            if channel == 'excluded_protocol' or values['duration_us'] > 86400000000:
                raise ValueError('invalid_record')
        except (ValueError, KeyError, TypeError):
            continue
        eligible += 1
        channels[channel] += 1
        for k in ('fwd_packets', 'bwd_packets', 'fwd_length', 'bwd_length'):
            sums[k] += values[k]
        no_backward += values['bwd_packets'] == 0
        durations.append(values['duration_us'] / 1000000)
    features = None
    if raw and eligible == raw:
        durations.sort()
        vector = [eligible, sums['fwd_packets'], sums['bwd_packets'], sums['fwd_length'], sums['bwd_length'],
                  channels['tcp'], channels['udp'], channels['known_other'], channels['unresolved'],
                  durations[-1], _quantile(durations, 0.5), _quantile(durations, 0.95), no_backward]
        features = dict(zip(FEATURE_ORDER, vector))
    return {'features': features, 'raw_records': raw, 'eligible_records': eligible,
            'excluded_records': raw - eligible, 'channels': dict(channels),
            'channel_conservation': sum(channels.values()) == eligible}


def _validate(config):
    payload._validate(config)
    known = config.get('supported_protocols')
    if (not isinstance(known, list) or any(type(v) is not int for v in known)
            or len(known) != 5 or set(known) != KNOWN):
        raise ValueError('known_protocol_set_required')
    if type(config.get('unresolved_source_protocol')) is not int or config['unresolved_source_protocol'] != 0:
        raise ValueError('unresolved_source_protocol_required')
    if config.get('population') != 'HASH_BOUND_RELEASED_CSV_RECORDS':
        raise ValueError('population_required')
    if config.get('feature_order') != list(FEATURE_ORDER):
        raise ValueError('candidate_feature_order')
    if config.get('candidate_widths', {'current': 13, 'current_and_history_deviation': 26}) != {
            'current': 13, 'current_and_history_deviation': 26}:
        raise ValueError('candidate_widths')
    registration = config.get('candidate_registration', {})
    if registration.get('history_minutes', [15, 30]) != [15, 30] or registration.get('normal_high_count_quantile', 0.9) != 0.9:
        raise ValueError('preserved_history_or_quantile')
    receipts = config.get('expected_inputs')
    if not isinstance(receipts, list) or not receipts or any(not isinstance(v, dict) for v in receipts):
        raise ValueError('receipt_identity_required')
    return payload._registered_segments(config)


def _stat(path):
    value = path.stat()
    return value.st_size, value.st_mtime_ns, value.st_ino


def _check_source(path, source, cap):
    before = _stat(path)
    size, digest = rules._digest_file(path, cap)
    if (before != _stat(path) or size != source['bytes'] or digest != source['sha256']):
        raise ValueError('source_identity_mismatch_or_changed')
    return before


def _budget(directory, index, config, incoming=0):
    """Count shared old/new audit and task trees once, including scratch/logs.

    An external index in the established runtime layout shares the .runtime
    parent with the new run. Standalone synthetic layouts use their common
    parent. No database or scratch file is created by this auditor.
    """
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('new_audit_directory_required')
    directory = directory.resolve(strict=True)
    if directory == index.parent:
        raise ValueError('new_audit_directory_required')
    if index.parent.name == 'audit' and directory.name == 'audit':
        old_run, new_run = index.parent.parent, directory.parent
    else:
        old_run, new_run = index.parent, directory
    audit_roots = {index.parent, directory}
    for run in (old_run, new_run):
        for name in ('logs', 'scratch', 'tmp'):
            child = run / name
            if child.is_dir():
                audit_roots.add(child)
    if old_run.parent == new_run.parent and old_run.parent.name == '.runtime':
        scratch = old_run.parent.parent / '.superpowers'
        if scratch.is_dir():
            audit_roots.add(scratch)
    files = set()
    for root in audit_roots:
        files.update(p.resolve() for p in root.rglob('*') if p.is_file())
    used = sum(p.stat().st_size for p in files)
    if used + incoming > min(payload.AUDIT_CAP, config['limits']['audit_max_bytes']):
        raise ValueError('combined_audit_scratch_byte_cap')
    if old_run.parent == new_run.parent:
        task_roots = {old_run.parent}
    else:
        task_roots = {old_run, new_run}
    task_files = set()
    for root in task_roots:
        task_files.update(p.resolve() for p in root.rglob('*') if p.is_file())
    task_files.update(files)
    if sum(p.stat().st_size for p in task_files) + incoming > payload.TASK_CAP:
        raise ValueError('task_byte_cap')
    return used


def _raw_channels():
    return Counter({k: 0 for k in (*CHANNELS, 'excluded_protocol')})


def _new_bucket(segment=None):
    return {'segment': segment, 'raw': 0, 'n': 0, 'tainted': False,
            'policies': {p: Counter() for p in POLICIES}, 'attempted': 0,
            'definite_attack': False, 'reasons': Counter(), 'other_field_issues': 0,
            'raw_channels': _raw_channels(), 'eligible_channels': Counter({k: 0 for k in CHANNELS})}


def _unresolved_accumulator():
    return {'record_count': 0, 'eligible_record_count': 0, 'unplaced_records': 0,
            'original_labels': Counter(), 'original_attempted_categories': Counter(),
            'label_category_counts': Counter(), 'excluded_reasons': Counter()}


def _add_unresolved(target, label, category, eligible, why, placed, config):
    target['record_count'] += 1
    target['eligible_record_count'] += eligible
    target['unplaced_records'] += not placed
    payload._count(target['original_labels'], label, config['limits']['max_label_values'], 'max_label_values')
    payload._count(target['original_attempted_categories'], category, config['limits']['max_category_values'], 'max_category_values')
    target['label_category_counts'][(rules._safe_label(label), rules._safe_label(category))] += 1
    target['excluded_reasons'].update(why)


def _pairs(counter):
    return [{'label': k[0], 'attempted_category': k[1], 'rows': n} for k, n in sorted(counter.items())]


def _distribution(values):
    ordered = sorted(values)
    return {'buckets': len(ordered), 'linear_quantiles': {
        name: _quantile(ordered, q) if ordered else None
        for name, q in (('min', 0), ('p25', 0.25), ('p50', 0.5), ('p75', 0.75),
                        ('p90', 0.9), ('p95', 0.95), ('max', 1))}}


def _diagnostic(target, ledger):
    """Descriptive encoded-clock patterns; no causal or model conclusions."""
    ordered = sorted(ledger)
    occupied = [m for m in ordered if ledger[m]['raw_channels']['unresolved']]
    eligible_occupied = [m for m in ordered if ledger[m]['eligible_channels']['unresolved']]
    gaps = Counter(str(int((b - a) / rules.MINUTE)) for a, b in zip(occupied, occupied[1:]))
    raw_counts = Counter(str(ledger[m]['raw_channels']['unresolved']) for m in ordered)
    eligible_counts = Counter(str(ledger[m]['eligible_channels']['unresolved']) for m in ordered)
    fractions = [ledger[m]['raw_channels']['unresolved'] / ledger[m]['raw'] for m in ordered if ledger[m]['raw']]
    eligible_fractions = [ledger[m]['eligible_channels']['unresolved'] / ledger[m]['n'] for m in ordered if ledger[m]['n']]
    runs = payload._clock_intervals(occupied)
    hour_counts, day_counts = Counter(), Counter()
    for m in occupied:
        n = ledger[m]['raw_channels']['unresolved']
        hour_counts[str(m.hour)] += n
        day_counts[m.date().isoformat()] += n
    lags = []
    for lag in (1, 2, 5, 10, 15, 30, 60):
        delta = rules.MINUTE * lag
        pairs = [(m, m + delta) for m in ordered if m + delta in ledger]
        both = sum(bool(ledger[a]['raw_channels']['unresolved'] and ledger[b]['raw_channels']['unresolved']) for a, b in pairs)
        lags.append({'lag_minutes': lag, 'available_encoded_clock_pairs': len(pairs), 'both_occupied_pairs': both})
    result = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in target.items() if k != 'label_category_counts'}
    result.update(label_category_counts=_pairs(target['label_category_counts']),
                  minute_domain='REGISTERED_MINUTES_UNION_OBSERVED_SOURCE_COMPLETION_MINUTES',
                  calendar_minutes=len(ordered), occupied_minutes=len(occupied),
                  eligible_occupied_minutes=len(eligible_occupied),
                  count_histogram=dict(sorted(raw_counts.items(), key=lambda v: int(v[0]))),
                  eligible_count_histogram=dict(sorted(eligible_counts.items(), key=lambda v: int(v[0]))),
                  occupied_bucket_gap_minutes=dict(sorted(gaps.items(), key=lambda v: int(v[0]))),
                  occupied_intervals=runs,
                  longest_occupied_run_minutes=max((run['minutes'] for run in runs), default=0),
                  original_source_clock_hour_counts=dict(sorted(hour_counts.items(), key=lambda v: int(v[0]))),
                  original_source_clock_day_counts=dict(sorted(day_counts.items())),
                  unresolved_record_fraction={
                      'definition': 'RAW_UNRESOLVED_RECORD_COUNT_DIVIDED_BY_RAW_COMPLETED_SOURCE_RECORD_COUNT',
                      'zero_denominator_minutes': sum(ledger[m]['raw'] == 0 for m in ordered),
                      **_distribution(fractions)},
                  eligible_unresolved_record_fraction={
                      'definition': 'ELIGIBLE_UNRESOLVED_RECORD_COUNT_DIVIDED_BY_ELIGIBLE_COMPLETED_SOURCE_RECORD_COUNT',
                      'zero_denominator_minutes': sum(ledger[m]['n'] == 0 for m in ordered),
                      **_distribution(eligible_fractions)},
                  descriptive_lags=lags,
                  inference='DESCRIPTIVE_ONLY_NO_CAPTURE_PHYSICAL_PROTOCOL_CAUSAL_OR_MODEL_CERTIFICATION')
    return result


def _channel_summary(ledger):
    raw, eligible = _raw_channels(), Counter({k: 0 for k in CHANNELS})
    for b in ledger.values():
        raw.update(b['raw_channels']); eligible.update(b['eligible_channels'])
    n_raw, n_eligible = sum(raw.values()), sum(eligible.values())
    return {'raw_completed_records': n_raw, 'eligible_completed_records': n_eligible,
            'excluded_records': n_raw - n_eligible, 'raw_protocol_channels': dict(raw),
            'eligible_protocol_channels': dict(eligible),
            'raw_channel_conservation': n_raw == sum(b['raw'] for b in ledger.values()),
            'eligible_channel_conservation': n_eligible == sum(b['n'] for b in ledger.values()),
            'record_conservation': n_raw == n_eligible + (n_raw - n_eligible)}


def _kind(bucket, policy):
    counts = bucket['policies'][policy]
    return ('unknown' if bucket['tainted'] or not bucket['n'] or counts['unknown'] else
            'attack' if counts['attack'] else 'normal')


def _policy_report(policy, segments, buckets):
    # Keep the registered G12 qualification and linear train-Q90 rules intact.
    report = payload._conditional_policy(policy, segments, buckets)
    overlap = Counter({k: 0 for k in ('test_common_current_normal_with_unresolved',
                                     'test_high_normal_with_unresolved', 'test_ordinary_normal_with_unresolved')})
    training_counts = []
    for s in segments:
        if s['role'] != 'train':
            continue
        minutes = sorted(m for m in buckets if buckets[m]['segment'] == s['id'])
        for i, m in enumerate(minutes):
            if i >= 30 and all(_kind(buckets[t], policy) == 'normal' for t in minutes[i-30:i+1]):
                training_counts.append(buckets[m]['n'])
    threshold = _quantile(sorted(training_counts), 0.9) if training_counts else None
    high_minutes = []
    for segment, summary in zip(segments, report['segments']):
        minutes = sorted(m for m in buckets if buckets[m]['segment'] == segment['id'])
        valid = {m for m in minutes if not buckets[m]['tainted'] and buckets[m]['n']}
        kinds = {m: _kind(buckets[m], policy) for m in minutes}
        for h in (15, 30):
            selected = [m for i, m in enumerate(minutes) if i >= h and all(t in valid for t in minutes[i-h:i+1])]
            summary['history'][str(h)]['current_label_counts'] = {k: sum(kinds[m] == k for m in selected) for k in ('normal', 'attack', 'unknown')}
        summary['normal_supply_rule'] = ('CURRENT_AND_HISTORY_ALL_NORMAL' if segment['role'] != 'test'
                                         else 'CURRENT_TRUTH_ON_COMMON_INPUT_VALID_HISTORY')
        summary['eligible_normal_supply'] = (summary['common_normal'] if segment['role'] != 'test'
                                             else summary['common_label_counts']['normal'])
        if segment['role'] == 'test':
            common = [m for i, m in enumerate(minutes) if i >= 30 and all(t in valid for t in minutes[i-30:i+1])]
            for m in common:
                if kinds[m] == 'normal' and threshold is not None and buckets[m]['n'] > threshold:
                    high_minutes.append(m)
                if kinds[m] == 'normal' and buckets[m]['eligible_channels']['unresolved']:
                    overlap['test_common_current_normal_with_unresolved'] += 1
                    if threshold is not None:
                        key = ('test_high_normal_with_unresolved' if buckets[m]['n'] > threshold
                               else 'test_ordinary_normal_with_unresolved')
                        overlap[key] += 1
    high = report['high_completion']
    high.update(threshold=threshold, test_high_normal=len(high_minutes) if threshold is not None else None,
                test_ordinary_normal=high['test_normal'] - len(high_minutes) if threshold is not None else None,
                high_intervals=payload._clock_intervals(high_minutes) if threshold is not None else None,
                interpolation_implementation='EXACT_DECIMAL_WEIGHTS_ON_INTEGER_COUNTS',
                unresolved_overlap=dict(overlap))
    high['unavailable_reason'] = ('NO_TRAIN_COMMON_NORMAL_MINUTES' if threshold is None else
                                  'NO_TEST_COMMON_INPUT_VALID_NORMAL_MINUTES' if not high['test_normal'] else
                                  'NO_TEST_MINUTES_STRICTLY_ABOVE_TRAIN_THRESHOLD' if not high_minutes else None)
    for day in report['days']:
        day['test_high_normal'] = sum(m.date().isoformat() == day['day'] for m in high_minutes) if threshold is not None else None
    if threshold is None:
        report['high_completion']['unresolved_overlap']['test_high_normal_with_unresolved'] = None
        report['high_completion']['unresolved_overlap']['test_ordinary_normal_with_unresolved'] = None
    return report


def audit_g13u(paths, config, audit_dir, index_path, progress=None):
    """Stream local source rows against an immutable prior profile index.

    Returns aggregate qualifications only; this function writes no files. The
    CLI can exclusively create one new aggregate JSON under the new audit dir.
    """
    segments = _validate(config)
    paths = [rules._local_file(p) for p in paths]
    if not paths or len(paths) > 100 or len(set(paths)) != len(paths):
        raise ValueError('input_paths')
    limits = config['limits']
    if sum(p.stat().st_size for p in paths) > limits['max_total_input_bytes']:
        raise ValueError('input_byte_cap')
    directory = Path(audit_dir)
    index = rules._local_file(index_path)
    if index in paths or index.stat().st_size > limits['index_max_bytes']:
        raise ValueError('index_identity_or_byte_cap')
    _budget(directory, index, config)
    index_before = _stat(index)
    index_digest = rules._digest_file(index, limits['index_max_bytes'])[1]
    if index_before != _stat(index):
        raise ValueError('index_changed')
    db = sqlite3.connect(index.as_uri() + '?mode=ro', uri=True)
    previous_field_limit = csv.field_size_limit()
    csv.field_size_limit(limits['max_field_chars'])
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA cache_size=-8192')
        db.execute('PRAGMA mmap_size=0')
        db.execute('PRAGMA temp_store=MEMORY')
        meta = dict(db.execute('SELECT name,value FROM metadata'))
        if meta.get('core_config_sha256') != payload._core_hash(config):
            raise ValueError('core_config_identity_mismatch')
        profile = json.loads(meta['profile'])
        if profile.get('status') != 'COMPLETE_RELEASE_RECORD_PROFILE' or len(profile['files']) != len(paths):
            raise ValueError('source_identity_profile_mismatch')
        receipts = config['expected_inputs']
        if (len(receipts) != len(paths) or any(r.get('bytes') != s['bytes'] or r.get('sha256') != s['sha256']
                                             for r, s in zip(receipts, profile['files']))):
            raise ValueError('receipt_identity_mismatch')
        source_stats = [_check_source(p, source, limits['max_total_input_bytes']) for p, source in zip(paths, profile['files'])]
        ledger = {}
        by_id = {s['id']: s for s in segments}
        for s in segments:
            s['source_labels'], s['source_categories'] = Counter(), Counter()
            m = s['begin']
            while m < s['finish']:
                ledger[m] = _new_bucket(s['id'])
                m += rules.MINUTE
        global_unresolved = _unresolved_accumulator()
        segment_unresolved = {s['id']: _unresolved_accumulator() for s in segments}
        raw_channels, eligible_channels = _raw_channels(), Counter({k: 0 for k in CHANNELS})
        protocols, pairs, reasons, anomalies = Counter(), Counter(), Counter(), Counter()
        labels, categories = Counter(), Counter()
        count = unplaced = eligible_total = 0
        days = set()
        file_results = []
        for number, (path, source, before) in enumerate(zip(paths, profile['files'], source_stats), 1):
            file_reasons, file_protocols, file_pairs = Counter(), Counter(), Counter()
            file_labels, file_categories = Counter(), Counter()
            file_raw, file_eligible = _raw_channels(), Counter({k: 0 for k in CHANNELS})
            file_unresolved = _unresolved_accumulator()
            raw_count = eligible = in_candidate = 0
            issue_fields = [name for name, counts in source['fields'].items() if any(counts.values())]
            numeric = set(config['numeric_columns'])
            for values in payload._rows(path, config):
                count += 1; raw_count += 1
                if count > limits['max_rows']:
                    raise ValueError('max_rows')
                row = dict(zip(config['expected_header'], values))
                bad, duration = payload._g12(row, config)
                why = {'invalid_' + key for key in bad}
                protocol = row[config['columns']['protocol']]
                channel = _channel(protocol)
                raw_channels[channel] += 1; file_raw[channel] += 1
                for target in (protocols, file_protocols):
                    payload._count(target, protocol, limits.get('max_protocol_values', 256), 'max_protocol_values')
                if channel == 'excluded_protocol' and 'protocol' not in bad:
                    why.add('invalid_unsupported_protocol')
                start = payload._parse_time(row[config['columns']['start']], config)
                if start is None:
                    why.add('invalid_timestamp')
                duplicate = db.execute('SELECT n FROM fingerprints WHERE digest=?', (payload._fingerprint(values),)).fetchone()
                if duplicate is None:
                    raise ValueError('source_identity_index_mismatch')
                if duplicate[0] > 1:
                    why.add('duplicate_record')
                b = None
                if start is None or duration is None:
                    unplaced += 1
                else:
                    try:
                        end = start + timedelta(microseconds=duration)
                    except OverflowError as exc:
                        raise ValueError('end_clock_overflow') from exc
                    m = rules._minute(end)
                    days.update((start.date(), end.date()))
                    if len(days) > limits['max_days']:
                        raise ValueError('max_days')
                    if m not in ledger:
                        if len(ledger) >= limits['max_minutes']:
                            raise ValueError('max_minutes')
                        ledger[m] = _new_bucket()
                    b = ledger[m]
                    b['raw'] += 1; b['raw_channels'][channel] += 1
                    if b['segment'] is None:
                        why.add('outside_candidate_ranges')
                    else:
                        in_candidate += 1
                        start_segment = next((s['id'] for s in segments if s['begin'] <= start < s['finish']), None)
                        if start_segment != b['segment']:
                            why.add('cross_partition')
                label, category = row[config['columns']['label']], row[config['columns']['attempted']]
                for target in (labels, file_labels):
                    payload._count(target, label, limits['max_label_values'], 'max_label_values')
                for target in (categories, file_categories):
                    payload._count(target, category, limits['max_category_values'], 'max_category_values')
                kinds, attempted, definite, anomaly = payload._label_kinds(label, category, config['labels'])
                pair = (rules._safe_label(label), rules._safe_label(category))
                pairs[pair] += 1; file_pairs[pair] += 1
                if anomaly:
                    anomalies[anomaly] += 1
                qualified = b is not None and not why
                if b is not None:
                    if b['segment'] is not None:
                        segment = by_id[b['segment']]
                        payload._count(segment['source_labels'], label, limits['max_label_values'], 'max_label_values')
                        payload._count(segment['source_categories'], category, limits['max_category_values'], 'max_category_values')
                    b['definite_attack'] |= definite
                    if why:
                        b['tainted'] = True; b['reasons'].update(why)
                    else:
                        eligible += 1; eligible_total += 1; b['n'] += 1
                        b['attempted'] += attempted
                        eligible_channels[channel] += 1; file_eligible[channel] += 1
                        b['eligible_channels'][channel] += 1
                        b['other_field_issues'] += payload._other_field_issue(row, issue_fields, numeric)
                        for policy, kind in zip(POLICIES, kinds):
                            b['policies'][policy][kind] += 1
                if channel == 'unresolved':
                    for target in (global_unresolved, file_unresolved):
                        _add_unresolved(target, label, category, qualified, why, b is not None, config)
                    if b is not None and b['segment'] is not None:
                        _add_unresolved(segment_unresolved[b['segment']], label, category, qualified, why, True, config)
                reasons.update(why); file_reasons.update(why)
                if count % 10000 == 0:
                    _budget(directory, index, config)
                    if progress:
                        progress({'phase': 'G13U_SUPPLY', 'rows': count, 'files_started': number})
            if before != _stat(path) or before != _check_source(path, source, limits['max_total_input_bytes']):
                raise ValueError('source_identity_changed_during_audit')
            if raw_count != source['rows']:
                raise ValueError('source_identity_file_row_count_mismatch')
            file_results.append({'file_id': f'input_{number}', 'rows': raw_count, 'in_candidate_ranges': in_candidate,
                                 'eligible_completed_records': eligible, 'excluded_records': raw_count - eligible,
                                 'raw_protocol_channels': dict(file_raw), 'eligible_protocol_channels': dict(file_eligible),
                                 'flow_reasons': dict(file_reasons), 'protocol_counts': dict(file_protocols),
                                 'source_labels': dict(file_labels), 'source_attempted_categories': dict(file_categories),
                                 'label_category_counts': _pairs(file_pairs),
                                 'unresolved': {k: dict(v) if isinstance(v, Counter) else v
                                                for k, v in file_unresolved.items() if k != 'label_category_counts'}})
        if count != profile['input_rows']:
            raise ValueError('source_identity_row_count_mismatch')
        buckets = {m: b for m, b in ledger.items() if b['segment'] is not None}
        if unplaced:
            for b in buckets.values():
                b['tainted'] = True
        policies = {p: _policy_report(p, segments, buckets) for p in POLICIES}
        per_segment, unresolved_segments = [], []
        for s in segments:
            selected = {m: b for m, b in buckets.items() if b['segment'] == s['id']}
            per_segment.append({'id': s['id'], 'role': s['role'], **_channel_summary(selected)})
            unresolved_segments.append({'id': s['id'], 'role': s['role'], **_diagnostic(segment_unresolved[s['id']], selected)})
        _budget(directory, index, config)
        if (index_before != _stat(index)
                or rules._digest_file(index, limits['index_max_bytes'])[1] != index_digest
                or index_before != _stat(index)):
            raise ValueError('index_changed_during_audit')
        return {
            'schema': 'C17_G13U_SUPPLY_AUDIT_V1', 'identity': config['identity'],
            'status': 'COMPLETE_AUDIT_ONLY', 'audit_id': 'C17-I1-G13U',
            'population': 'HASH_BOUND_RELEASED_CSV_RECORDS', 'input_rows': count,
            'files': file_results, 'source_sha_binding': 'VERIFIED_BEFORE_AND_AFTER_AGAINST_READ_ONLY_PROFILE_INDEX',
            'extraction_receipt_binding': 'VERIFIED',
            'index': {'mode': 'READ_ONLY', 'sha256_before': index_digest, 'sha256_after': index_digest,
                      'bytes': index_before[0], 'core_config_sha256': payload._core_hash(config), 'contains_raw_rows': False},
            'all_source': {'raw_records': count, 'eligible_completed_records': eligible_total,
                           'excluded_records': count - eligible_total, 'raw_protocol_channels': dict(raw_channels),
                           'eligible_protocol_channels': dict(eligible_channels),
                           'raw_channel_conservation': sum(raw_channels.values()) == count,
                           'eligible_channel_conservation': sum(eligible_channels.values()) == eligible_total},
            'record_channels': {'segments': per_segment},
            'unresolved': {'all_source': _diagnostic(global_unresolved, ledger), 'segments': unresolved_segments},
            'flow_reasons': dict(reasons), 'protocol_counts': dict(protocols),
            'source_labels': dict(labels), 'source_attempted_categories': dict(categories),
            'supported_protocols': sorted(KNOWN), 'unresolved_source_protocol': 0,
            'protocol_semantics': 'SOURCE_CODES_ONLY_ZERO_IS_UNRESOLVED_NOT_KNOWN_OTHER_OR_PHYSICAL_CERTIFICATION',
            'label_category_counts': _pairs(pairs), 'label_anomalies': dict(anomalies),
            'all_column_filter_impact': payload._filter_impact(buckets, buckets.keys()),
            'unplaced_invalid_rows': unplaced, 'policies': policies,
            'strict': {'coverage': 'UNKNOWN_NOT_CERTIFIED', 'actual_input_valid_minutes': None,
                       'certified_input_valid_minutes': 0, 'actual_label_supply': None, 'high_completion': None},
            'conditional_assumptions': [
                'COMPLETE_HASH_BOUND_RELEASED_RECORDS_WITHIN_REGISTERED_SEGMENTS_ONLY',
                'SOURCE_CLOCK_UTC_US_AUTHOR_COMPATIBILITY_HYPOTHESIS_ONLY',
                'ENCODED_START_PLUS_DURATION_IS_NOMINAL_COMPLETION_PROXY_NOT_VERIFIED_EXPORT_TIME',
                'PHYSICAL_QUANTIZATION_AND_CAPTURE_COMPLETENESS_NOT_CLAIMED',
                'EMPTY_OR_TAINTED_MINUTES_INVALID_EACH_SEGMENT_RESETS_HISTORY',
                'TEST_HISTORY_INPUT_QUALIFICATION_NEVER_LABEL_CLEANED',
                'UNUSED_FIELD_ISSUES_DO_NOT_DROP_OTHERWISE_VALID_RECORDS'],
            'candidate': {'feature_order': list(FEATURE_ORDER), 'current_width': 13, 'current_and_history_deviation_width': 26,
                          'history_definition': 'CURRENT_THEN_DEVIATION_FROM_PREVIOUS_CONTIGUOUS_H_MINUTES_MEDIAN_MAD',
                          'history_minutes': [15, 30], 'numeric_history_vectors': 'NOT_RUN'},
            'common_valid_scope': 'G13U_SOURCE_COMPUTABILITY_CURRENT_H15_H30_QUALIFICATION_ONLY',
            'model_common_valid_minutes': None, 'feature_vectors': 'NOT_PRODUCED', 'preprocessing': 'NOT_RUN',
            'real_training': 'NOT_RUN', 'scoring': 'NOT_RUN', 'score_calibration': 'NOT_RUN',
            'score_calibration_quantile': 0.99, 'score_alarm_rule': 'STRICTLY_GREATER',
            'physical_quantization_sensitivity': 'NOT_RUN_PHYSICAL_BOUND_UNVERIFIED',
            'dataset_adoption': 'NOT_APPROVED', 'final_label_policy': 'NOT_APPROVED', 'production_migration': 'NOT_APPROVED',
        }
    except (sqlite3.DatabaseError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError('incomplete_or_invalid_profile_index') from exc
    except csv.Error as exc:
        raise ValueError('csv_parse_or_field_limit') from exc
    finally:
        csv.field_size_limit(previous_field_limit)
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index-path', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        directory = args.audit_dir.resolve(strict=True)
        output = args.output.resolve()
        if (output.parent != directory or args.output.is_symlink() or output.exists()
                or output in [p.resolve() for p in args.input]
                or output in (args.config.resolve(), args.index_path.resolve())):
            raise ValueError('output_new_inside_audit_required')
        config_path = rules._local_file(args.config)
        if config_path.stat().st_size > 1048576:
            raise ValueError('config_size')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        result = audit_g13u(args.input, config, directory, args.index_path,
                           progress=lambda value: print(json.dumps(value), flush=True))
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        _budget(directory, rules._local_file(args.index_path), config, len(encoded.encode('utf-8')))
        with output.open('x', encoding='utf-8') as handle:
            handle.write(encoded)
        print(json.dumps({'status': result['status'], 'rows': result['input_rows']}))
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError,
            RuntimeError, csv.Error, sqlite3.Error, DecimalException):
        print('G13U_AUDIT_FAILED_SAFE_INPUT_CONFIG_OR_RESOURCE_ERROR', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
