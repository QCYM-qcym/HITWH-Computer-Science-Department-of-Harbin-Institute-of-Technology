"""Bounded, offline release-record audit; no acquisition, extraction or models.

CSV source values are read-only. A capped SQLite fingerprint index replaces
the preparation auditor's per-flow Python object graph. All reports aggregate
source values; the index stores only hashes/counts/anonymous file numbers.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

try:
    from tools.data_audit import c17_improved as rules
except ModuleNotFoundError:
    import c17_improved as rules


INDEX_CAP = 512 * 1024 * 1024
AUDIT_CAP = 1024 * 1024 * 1024
TASK_CAP = 6 * 1024 * 1024 * 1024
NONFINITE = {'nan', '+nan', '-nan', 'inf', '+inf', '-inf', 'infinity', '+infinity', '-infinity'}


def _validate(config):
    if not isinstance(config, dict) or config.get('identity') not in ('SYNTHETIC_ONLY', 'REAL_LOCAL_AUTHORIZED'):
        raise ValueError('config_identity')
    for key in ('columns', 'time', 'limits'):
        if not isinstance(config.get(key), dict):
            raise ValueError('config_objects')
    header = config.get('expected_header')
    numeric = config.get('numeric_columns')
    if not isinstance(header, list) or not header or any(not isinstance(v, str) or not v for v in header) or len(header) != len(set(header)):
        raise ValueError('expected_header')
    if not isinstance(numeric, list) or not set(numeric) <= set(header):
        raise ValueError('numeric_columns')
    columns = config['columns']
    if not all(isinstance(columns.get(k), str) and columns[k] in header for k in ('start', 'duration', 'label', 'attempted', *rules.FEATURE_FIELDS)):
        raise ValueError('g12_columns')
    if not set(columns[k] for k in ('duration', *rules.FEATURE_FIELDS)) <= set(numeric):
        raise ValueError('g12_numeric_columns')
    formats = config['time'].get('formats')
    if not isinstance(formats, list) or not 1 <= len(formats) <= 8 or any(not isinstance(v, str) or not v for v in formats):
        raise ValueError('time_formats')
    if any('%I' in f and '%p' not in f or '%H' in f and '%p' in f for f in formats):
        raise ValueError('AM_PM')
    if config['time'].get('duration_unit') not in ('us', 'ms', 's'):
        raise ValueError('duration_unit')
    limits = config['limits']
    for key in ('max_total_input_bytes', 'max_rows', 'max_days', 'max_fields', 'max_field_chars',
                'max_label_values', 'max_category_values', 'max_minutes', 'index_max_bytes', 'audit_max_bytes'):
        rules._integer(limits.get(key), key)
    rules._positive(limits.get('max_duration_seconds'), 'max_duration_seconds')
    if (limits['max_rows'] > 5000000 or limits['max_days'] > 7 or limits['index_max_bytes'] > INDEX_CAP
            or limits['audit_max_bytes'] > AUDIT_CAP or limits['max_duration_seconds'] > 86400
            or limits['index_max_bytes'] < 8192 or limits['max_fields'] > 512
            or limits['max_field_chars'] > 65536 or limits['max_minutes'] > 10080):
        raise ValueError('hard_resource_cap')
    if len(header) > limits['max_fields']:
        raise ValueError('max_fields')
    return config


def _space(directory, cap):
    roots = [directory]
    logs = directory.parent / 'logs'
    if logs.is_dir():
        roots.append(logs)
    total = sum(p.stat().st_size for root in roots for p in root.rglob('*') if p.is_file())
    if total > cap:
        raise ValueError('audit_logs_byte_cap')
    return total


def _open_index(directory, config, name):
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.sqlite3', name):
        raise ValueError('index_name')
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('audit_directory_required')
    used = _space(directory, config['limits']['audit_max_bytes'])
    task_used = sum(p.stat().st_size for p in directory.parent.rglob('*') if p.is_file())
    reserve = config['limits'].get('output_reserve_bytes', 262144)
    rules._integer(reserve, 'output_reserve_bytes')
    budget = min(config['limits']['index_max_bytes'], config['limits']['audit_max_bytes'] - used - reserve,
                 TASK_CAP - task_used - reserve)
    if budget < 12288:
        raise ValueError('index_byte_cap_or_remaining_audit_budget')
    path = directory / name
    if path.exists():
        raise ValueError('index_exists')
    # Reserve exclusively before SQLite opens, preventing accidental reuse.
    with path.open('xb'):
        pass
    db = sqlite3.connect(path)
    db.execute('PRAGMA page_size=4096')
    db.execute('PRAGMA max_page_count=' + str(budget // 4096))
    db.execute('PRAGMA cache_size=-8192')
    db.execute('PRAGMA mmap_size=0')
    db.execute('PRAGMA journal_mode=OFF')
    db.execute('PRAGMA synchronous=OFF')
    db.execute('PRAGMA temp_store=FILE')
    try:
        db.execute('CREATE TABLE fingerprints (digest BLOB PRIMARY KEY, n INTEGER NOT NULL, first_file INTEGER NOT NULL, cross_file INTEGER NOT NULL) WITHOUT ROWID')
        db.execute('CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID')
    except sqlite3.DatabaseError as exc:
        db.close()
        raise ValueError('index_byte_cap_or_sqlite_failure') from exc
    return db, path


def _rows(path, config):
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError('missing_header') from exc
        if header != config['expected_header']:
            raise ValueError('header_mismatch')
        for values in reader:
            if len(values) != len(header):
                raise ValueError('ragged_row')
            if any(len(v) > config['limits']['max_field_chars'] or '\x00' in v for v in values):
                raise ValueError('field_limit_or_nul')
            yield values


def _fingerprint(values):
    # Length framing preserves field boundaries without retaining source values.
    digest = hashlib.sha256()
    for value in values:
        raw = value.encode('utf-8')
        digest.update(len(raw).to_bytes(4, 'little')); digest.update(raw)
    return digest.digest()


def _parse_time(raw, config):
    for fmt in config['time']['formats']:
        try:
            value = datetime.fromisoformat(raw) if fmt == 'ISO8601' else datetime.strptime(raw, fmt)
            if value.tzinfo is not None:
                # Preserve source wall-clock aggregates; offset is not silently converted.
                if value.utcoffset() != timedelta(0):
                    raise ValueError('nonzero_source_offset')
                value = value.replace(tzinfo=None)
            return value
        except ValueError:
            continue
    return None


def _g12(row, config):
    bad = []
    duration_us = None
    for key in ('duration', *rules.FEATURE_FIELDS):
        try:
            value = Decimal(row[config['columns'][key]])
            if not value.is_finite() or value < 0 or value != value.to_integral_value() or key == 'protocol' and value > 255:
                raise ValueError(key)
            if key == 'duration':
                factor = {'us': Decimal(1), 'ms': Decimal(1000), 's': Decimal(1000000)}[config['time']['duration_unit']]
                value *= factor
                if value > Decimal(str(config['limits']['max_duration_seconds'])) * 1000000:
                    raise OverflowError('duration_cap')
                if value != value.to_integral_value():
                    raise ValueError(key)
                duration_us = int(value)
        except OverflowError as exc:
            raise ValueError('duration_cap') from exc
        except (ValueError, DecimalException):
            bad.append(key)
    return bad, duration_us


def _count(counter, raw, cap, reason):
    value = rules._safe_label(raw)
    if value not in counter and len(counter) >= cap:
        raise ValueError(reason)
    counter[value] += 1


def _core_hash(config):
    return hashlib.sha256(json.dumps({k: config[k] for k in ('expected_header', 'numeric_columns', 'columns', 'time')}, sort_keys=True).encode()).hexdigest()


def profile_csv(paths, config, audit_dir, index_name='profile-index.sqlite3', progress=None):
    """First bounded pass: complete field profile and exact-row hash index.

    Returns aggregate metadata; the private scratch database is retained in the
    explicit audit directory for a second pass. Never infer sensor coverage,
    UTC binding, a label mapping, or real-time feature availability.
    """
    _validate(config)
    paths = [rules._local_file(path) for path in paths]
    if not paths or len(set(paths)) != len(paths) or len(paths) > 100:
        raise ValueError('input_paths')
    limit = config['limits']
    if sum(p.stat().st_size for p in paths) > limit['max_total_input_bytes']:
        raise ValueError('input_byte_cap')
    directory = Path(audit_dir)
    db, index_path = _open_index(directory, config, index_name)
    files, labels, categories, days, minutes = [], Counter(), Counter(), set(), set()
    count = 0
    numeric = set(config['numeric_columns'])
    previous_field_limit = csv.field_size_limit()
    csv.field_size_limit(limit['max_field_chars'])
    try:
        for number, path in enumerate(paths, 1):
            before = path.stat()
            fields = {name: {'missing': 0, 'nonfinite': 0, 'unparseable_numeric': 0} for name in config['expected_header']}
            invalid = Counter(); rows = source_bad = dropna = g12_valid = g12_valid_other_issue = 0
            clocks = {'parsed': 0, 'invalid': 0, 'min': None, 'max': None, 'hour_counts': Counter(), 'fraction_digits': Counter(), 'order_inversions': 0}
            previous = None
            file_labels, file_categories = Counter(), Counter()
            for values in _rows(path, config):
                count += 1; rows += 1
                if count > limit['max_rows']:
                    raise ValueError('max_rows')
                row = dict(zip(config['expected_header'], values))
                bad_source = missing_or_nan = False
                for name, raw in row.items():
                    stripped = raw.strip()
                    if not stripped:
                        fields[name]['missing'] += 1; bad_source = missing_or_nan = True
                    elif stripped.lower() in NONFINITE:
                        fields[name]['nonfinite'] += 1; bad_source = True
                        missing_or_nan |= 'nan' in stripped.lower()
                    elif name in numeric:
                        try:
                            finite = math.isfinite(float(stripped))
                        except (ValueError, OverflowError):
                            fields[name]['unparseable_numeric'] += 1; bad_source = True
                        else:
                            if not finite:
                                fields[name]['nonfinite'] += 1; bad_source = True
                source_bad += bad_source; dropna += missing_or_nan
                bad, duration = _g12(row, config); invalid.update(bad)
                raw_clock = row[config['columns']['start']]
                value = _parse_time(raw_clock, config)
                if value is not None and not bad:
                    g12_valid += 1
                    g12_valid_other_issue += bad_source
                if value is None:
                    clocks['invalid'] += 1
                else:
                    clocks['parsed'] += 1
                    text = value.isoformat(timespec='microseconds')
                    clocks['min'] = text if clocks['min'] is None else min(clocks['min'], text)
                    clocks['max'] = text if clocks['max'] is None else max(clocks['max'], text)
                    clocks['hour_counts'][str(value.hour)] += 1
                    fraction = re.search(r'\.(\d+)', raw_clock)
                    clocks['fraction_digits'][str(len(fraction[1]) if fraction else 0)] += 1
                    clocks['order_inversions'] += previous is not None and value < previous
                    previous = value
                    days.add(value.date())
                    minutes.add(rules._minute(value))
                    if duration is not None:
                        try:
                            end = value + timedelta(microseconds=duration)
                        except OverflowError as exc:
                            raise ValueError('end_clock_overflow') from exc
                        days.add(end.date()); minutes.add(rules._minute(end))
                    if len(days) > limit['max_days']:
                        raise ValueError('max_days')
                    if len(minutes) > limit['max_minutes']:
                        raise ValueError('max_minutes')
                label, category = row[config['columns']['label']], row[config['columns']['attempted']]
                for target in (labels, file_labels):
                    _count(target, label, limit['max_label_values'], 'max_label_values')
                for target in (categories, file_categories):
                    _count(target, category, limit['max_category_values'], 'max_category_values')
                db.execute('INSERT INTO fingerprints VALUES (?,1,?,0) ON CONFLICT(digest) DO UPDATE SET n=n+1,cross_file=(cross_file OR first_file!=excluded.first_file)', (_fingerprint(values), number))
                if count % 10000 == 0:
                    db.commit(); _space(directory, limit['audit_max_bytes'])
                    if progress:
                        progress({'phase': 'PROFILE', 'rows': count, 'files_started': number})
            db.commit()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('input_changed')
            _, sha256 = rules._digest_file(path, limit['max_total_input_bytes'])
            after_hash = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after_hash.st_size, after_hash.st_mtime_ns, after_hash.st_ino):
                raise ValueError('input_changed_during_final_hash')
            files.append({'file_id': f'input_{number}', 'bytes': after.st_size, 'sha256': sha256, 'rows': rows,
                          'fields': fields, 'source_field_issue_rows': source_bad, 'dropna_like_rows': dropna,
                          'all_column_complete_case_rows': rows - source_bad,
                          'g12_valid_rows': g12_valid, 'g12_valid_with_other_field_issue_rows': g12_valid_other_issue,
                          'g12_invalid': dict(invalid), 'time': clocks,
                          'labels': dict(file_labels), 'attempted_categories': dict(file_categories)})
        unique, groups, duplicate_rows, cross = db.execute('SELECT COUNT(*),COALESCE(SUM(n>1),0),COALESCE(SUM(CASE WHEN n>1 THEN n ELSE 0 END),0),COALESCE(SUM(cross_file),0) FROM fingerprints').fetchone()
        _space(directory, limit['audit_max_bytes'])
        result = {'schema': 'C17_PAYLOAD_PROFILE_V1', 'identity': config['identity'], 'status': 'COMPLETE_RELEASE_RECORD_PROFILE',
                'input_rows': count, 'files': files, 'labels': dict(labels), 'attempted_categories': dict(categories),
                'duplicates': {'unique_rows': unique, 'groups': groups, 'rows_in_groups': duplicate_rows, 'cross_file_groups': cross},
                'index': {'basename': index_name, 'bytes': index_path.stat().st_size, 'max_bytes': limit['index_max_bytes'], 'contains_raw_rows': False},
                'time_semantics': 'SOURCE_CLOCK_ONLY_TIMEZONE_AND_RELEASE_BINDING_NOT_CERTIFIED',
                'minute_audit': 'NOT_RUN', 'model_common_valid_minutes': None, 'real_training': 'NOT_RUN',
                'scoring': 'NOT_RUN', 'score_calibration': 'NOT_RUN', 'dataset_adoption': 'NOT_APPROVED'}
        db.execute('INSERT INTO metadata VALUES (?,?)', ('profile', json.dumps(result, ensure_ascii=True)))
        db.execute('INSERT INTO metadata VALUES (?,?)', ('core_config_sha256', _core_hash(config)))
        db.commit()
        result['index']['bytes'] = index_path.stat().st_size
        return result
    except sqlite3.DatabaseError as exc:
        raise ValueError('index_byte_cap_or_sqlite_failure') from exc
    except csv.Error as exc:
        raise ValueError('csv_parse_or_field_limit') from exc
    finally:
        csv.field_size_limit(previous_field_limit)
        db.close()


def _registered_segments(config):
    registration = config.get('candidate_registration', {})
    if (registration.get('status') != 'AUDIT_CANDIDATE_ONLY_NOT_APPROVED_PROTOCOL'
            or registration.get('label_values_seen_before_registration') is not False
            or registration.get('model_results_seen') is not False):
        raise ValueError('pre_label_candidate_registration_required')
    segments, names = [], set()
    for item in registration.get('segments', []):
        name = item.get('id', '')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', name) or name in names:
            raise ValueError('segment_id')
        names.add(name)
        begin, finish = rules._clock(item['start']), rules._clock(item['end'])
        if begin >= finish or item['role'] not in ('train', 'validation', 'calibration', 'test'):
            raise ValueError('segment_range_or_role')
        segments.append({'id': name, 'role': item['role'], 'begin': begin, 'finish': finish})
    segments.sort(key=lambda v: v['begin'])
    order = {'train': 0, 'validation': 1, 'calibration': 2, 'test': 3}
    if not segments or any(a['finish'] > b['begin'] or order[a['role']] > order[b['role']] for a, b in zip(segments, segments[1:])):
        raise ValueError('segment_overlap_or_role_order')
    if sum(int((s['finish'] - s['begin']) / rules.MINUTE) for s in segments) > config['limits']['max_minutes']:
        raise ValueError('max_minutes')
    labels = config.get('labels', {})
    all_words = []
    for key in ('normal', 'attack', 'attempted', 'attempted_empty', 'attempted_categories'):
        if not isinstance(labels.get(key), list) or any(not isinstance(v, str) for v in labels[key]):
            raise ValueError('label_vocabulary')
        if key in ('normal', 'attack', 'attempted'):
            all_words += labels[key]
    if len(all_words) != len(set(all_words)) or set(labels['attempted_empty']) & set(labels['attempted_categories']):
        raise ValueError('overlapping_label_vocabulary')
    if labels.get('policy', {}).get('status') != 'AUDIT_ONLY':
        raise ValueError('AUDIT_ONLY_required')
    supported = config.get('supported_protocols')
    if (not isinstance(supported, list) or not supported or any(type(v) is not int or not 0 <= v <= 255 for v in supported)
            or len(set(supported)) != len(supported)):
        raise ValueError('supported_protocols_required')
    return segments


def _label_kinds(label, category, labels):
    attempted = label in labels['attempted'] or category not in labels['attempted_empty']
    definite_attack = label in labels['attack']
    known = label in labels['normal'] + labels['attack'] + labels['attempted']
    category_known = category in labels['attempted_empty'] + labels['attempted_categories']
    contradiction = (label in labels['normal'] + labels['attack'] and attempted
                     or label in labels['attempted'] and category in labels['attempted_empty'])
    if not known or not category_known or contradiction:
        kinds = ('unknown', 'unknown', 'unknown')
        reason = 'unknown_label' if not known else 'unknown_attempted_category' if not category_known else 'label_category_conflict'
    elif attempted:
        kinds = ('unknown', 'normal', 'attack'); reason = None
    else:
        kind = 'attack' if definite_attack else 'normal'
        kinds = (kind, kind, kind); reason = None
    return kinds, attempted, definite_attack, reason


def _clock_intervals(minutes):
    # Source clocks are not independently authenticated UTC clocks.
    return [{**run, 'start': run['start'].removesuffix('Z'), 'end': run['end'].removesuffix('Z')}
            for run in rules._intervals(minutes)]


def _filter_impact(buckets, minutes):
    changed = [m for m in minutes if buckets[m]['other_field_issues']]
    return {'eligible_records_removed': sum(buckets[m]['other_field_issues'] for m in changed),
            'completed_count_changed_buckets': len(changed),
            'buckets_becoming_empty': sum(buckets[m]['other_field_issues'] == buckets[m]['n'] for m in changed),
            'affected_intervals': _clock_intervals(changed),
            'meaning': 'HYPOTHETICAL_FILTER_ONLY_NOT_EXECUTED_COMPLETENESS_WOULD_NEED_REASSESSMENT'}


def _other_field_issue(row, field_names, numeric):
    for name in field_names:
        raw = row[name].strip()
        if not raw or raw.lower() in NONFINITE:
            return True
        if name in numeric:
            try:
                if not math.isfinite(float(raw)):
                    return True
            except (ValueError, OverflowError):
                return True
    return False


def _conditional_policy(policy, segments, buckets):
    reports, train, test_normal = [], [], []
    all_kinds, all_valid, all_common, all_normal = {}, set(), set(), set()
    all_history = {15: set(), 30: set()}
    for segment in segments:
        minutes = [m for m, b in buckets.items() if b['segment'] == segment['id']]
        kinds = {}
        for m in minutes:
            b = buckets[m]; counts = b['policies'][policy]
            kinds[m] = ('unknown' if b['tainted'] or not b['n'] or counts['unknown'] else
                        'attack' if counts['attack'] else 'normal')
        valid = {m for m in minutes if not buckets[m]['tainted'] and buckets[m]['n'] > 0}
        history, normal_history = {}, {}
        for h in (15, 30):
            selected = {m for i, m in enumerate(minutes) if i >= h and all(t in valid for t in minutes[i-h:i+1])}
            normals = {m for i, m in enumerate(minutes) if m in selected and all(kinds[t] == 'normal' for t in minutes[i-h:i+1])}
            history[str(h)] = {'input_valid': len(selected), 'normal_eligible': len(normals)}
            normal_history[h] = normals
            all_history[h].update(selected)
        common = {m for i, m in enumerate(minutes) if i >= 30 and all(t in valid for t in minutes[i-30:i+1])}
        common_normal = normal_history[15] & normal_history[30]
        all_kinds.update(kinds); all_valid.update(valid); all_common.update(common); all_normal.update(common_normal)
        if segment['role'] == 'train':
            train.extend(buckets[m]['n'] for m in common_normal)
        if segment['role'] == 'test':
            test_normal.extend(m for m in common if kinds[m] == 'normal')
        label_counts = Counter(kinds.values())
        reasons = Counter()
        for m in minutes:
            reasons.update(buckets[m]['reasons'])
        common_labels = {k: sum(kinds[m] == k for m in common) for k in ('normal', 'attack', 'unknown')}
        present = lambda m: bool(buckets[m]['definite_attack'] or buckets[m]['policies'][policy]['attack'])
        attempted_exclusion = lambda m: (policy == 'P_U' and kinds[m] == 'unknown' and not buckets[m]['tainted']
            and buckets[m]['definite_attack'] and buckets[m]['policies']['P_U']['unknown'] > 0
            and buckets[m]['policies']['P_B']['unknown'] == 0)
        reports.append({'id': segment['id'], 'role': segment['role'], 'calendar_minutes': len(minutes),
                        'input_valid': len(valid), 'invalid_minutes': len(minutes) - len(valid),
                        'normal': label_counts['normal'], 'attack': label_counts['attack'], 'unknown': label_counts['unknown'],
                        'mixed': sum(bool(buckets[m]['policies'][policy]['normal'] and buckets[m]['policies'][policy]['attack']) for m in minutes),
                        'attempted': sum(buckets[m]['attempted'] > 0 for m in minutes),
                        'attack_present': sum(buckets[m]['definite_attack'] or buckets[m]['policies'][policy]['attack'] > 0 for m in minutes),
                        'attack_present_unknown': sum(kinds[m] == 'unknown' and present(m) for m in minutes),
                        'attack_excluded_by_attempted': sum(attempted_exclusion(m) for m in minutes),
                        'empty': sum(buckets[m]['raw'] == 0 for m in minutes),
                        'label_incomplete': sum(buckets[m]['policies'][policy]['unknown'] > 0 or buckets[m]['raw'] == 0 for m in minutes),
                        'eligible_completed_records': sum(buckets[m]['n'] for m in minutes),
                        'raw_completed_records': sum(buckets[m]['raw'] for m in minutes),
                        'source_labels': dict(segment['source_labels']), 'source_attempted_categories': dict(segment['source_categories']),
                        'all_column_filter_impact': _filter_impact(buckets, minutes),
                        'flow_reasons': dict(reasons), 'history': history,
                        'common_input_valid': len(common), 'common_normal': len(common_normal),
                        'common_label_counts': common_labels,
                        'common_attack_present': sum(present(m) for m in common),
                        'common_attack_excluded_unknown': sum(kinds[m] == 'unknown' and present(m) for m in common),
                        'common_attack_excluded_by_attempted': sum(attempted_exclusion(m) for m in common),
                        'valid_intervals': _clock_intervals(valid)})
    threshold = None
    if train:
        ordered = sorted(train); position = (len(ordered) - 1) * 0.9; lower = int(position)
        threshold = ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)
    high = [m for m in test_normal if threshold is not None and buckets[m]['n'] > threshold]
    days = []
    for day in sorted({m.date().isoformat() for m in buckets}):
        minutes = {m for m in buckets if m.date().isoformat() == day}
        common = all_common & minutes
        present = lambda m: bool(buckets[m]['definite_attack'] or buckets[m]['policies'][policy]['attack'])
        exclude = lambda m: (policy == 'P_U' and all_kinds[m] == 'unknown' and not buckets[m]['tainted']
            and buckets[m]['definite_attack'] and buckets[m]['policies']['P_U']['unknown'] > 0
            and buckets[m]['policies']['P_B']['unknown'] == 0)
        days.append({'day': day, 'calendar_minutes': len(minutes), 'input_valid': len(all_valid & minutes),
            **{k: sum(all_kinds[m] == k for m in minutes) for k in ('normal', 'attack', 'unknown')},
            'attack_present': sum(present(m) for m in minutes),
            'attack_present_unknown': sum(all_kinds[m] == 'unknown' and present(m) for m in minutes),
            'attack_excluded_by_attempted': sum(exclude(m) for m in minutes),
            'common_input_valid': len(common), 'common_normal': len(all_normal & minutes),
            'common_label_counts': {k: sum(all_kinds[m] == k for m in common) for k in ('normal', 'attack', 'unknown')},
            'common_attack_present': sum(present(m) for m in common),
            'common_attack_excluded_unknown': sum(all_kinds[m] == 'unknown' and present(m) for m in common),
            'history_input_valid': {str(h): len(v & minutes) for h, v in all_history.items()},
            'all_column_filter_impact': _filter_impact(buckets, minutes),
            'test_common_current_normal': sum(m in minutes for m in test_normal),
            'test_high_normal': sum(m in minutes for m in high) if threshold is not None else None})
    reason = ('NO_TRAIN_COMMON_NORMAL_MINUTES' if threshold is None else
              'NO_TEST_COMMON_INPUT_VALID_NORMAL_MINUTES' if not test_normal else
              'NO_TEST_MINUTES_STRICTLY_ABOVE_TRAIN_THRESHOLD' if not high else None)
    return {'policy_status': 'AUDIT_ONLY_NOT_ACCEPTED_LABEL_POLICY', 'segments': reports, 'days': days,
            'high_completion': {'training_eligible': len(train), 'quantile': 0.9, 'interpolation': 'linear',
                'threshold': threshold, 'comparison': 'STRICTLY_GREATER', 'test_normal': len(test_normal),
                'test_high_normal': len(high) if threshold is not None else None,
                'test_ordinary_normal': len(test_normal) - len(high) if threshold is not None else None,
                'high_intervals': _clock_intervals(high) if threshold is not None else None, 'unavailable_reason': reason}}


def audit_minutes(paths, config, audit_dir, index_name='profile-index.sqlite3', progress=None):
    """Second read-only pass with SHA-bound source and nominal encoded-grid ends.

    Strict coverage remains unknown. Conditional counts assume complete released
    records within the preregistered ranges, never complete physical capture.
    Empty buckets stay unknown and source physical quantization is unverified.
    """
    _validate(config); segments = _registered_segments(config)
    paths = [rules._local_file(p) for p in paths]
    if not paths or len(paths) > 100 or len(set(paths)) != len(paths):
        raise ValueError('input_paths')
    directory = Path(audit_dir)
    index = rules._local_file(directory / index_name)
    db = sqlite3.connect(index.as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA cache_size=-8192'); db.execute('PRAGMA mmap_size=0')
    try:
        meta = dict(db.execute('SELECT name,value FROM metadata'))
        if meta.get('core_config_sha256') != _core_hash(config):
            raise ValueError('core_config_identity_mismatch')
        profile = json.loads(meta['profile'])
        if profile.get('status') != 'COMPLETE_RELEASE_RECORD_PROFILE' or len(profile['files']) != len(paths):
            raise ValueError('source_identity_mismatch')
        receipts = config.get('expected_inputs')
        if receipts is not None and (not isinstance(receipts, list) or len(receipts) != len(paths)):
            raise ValueError('receipt_identity_count_mismatch')
        if receipts is not None and any(r.get('bytes') != s['bytes'] or r.get('sha256') != s['sha256'] for r, s in zip(receipts, profile['files'])):
            raise ValueError('receipt_identity_mismatch')
        for path, source in zip(paths, profile['files']):
            if path.stat().st_size != source['bytes'] or rules._digest_file(path, config['limits']['max_total_input_bytes'])[1] != source['sha256']:
                raise ValueError('source_identity_mismatch')
        buckets = {}
        for s in segments:
            s['source_labels'], s['source_categories'] = Counter(), Counter()
            m = s['begin']
            while m < s['finish']:
                buckets[m] = {'segment': s['id'], 'n': 0, 'raw': 0, 'tainted': False,
                    'policies': {p: Counter() for p in ('P_U', 'P_B', 'P_A')}, 'attempted': 0,
                    'definite_attack': False, 'reasons': Counter(), 'other_field_issues': 0}
                m += rules.MINUTE
        def segment_at(t):
            return next((s['id'] for s in segments if s['begin'] <= t < s['finish']), None)
        reasons, label_anomalies = Counter(), Counter()
        protocol_counts, pairs = Counter(), Counter()
        count = unplaced = 0
        file_results = []
        for file_number, (path, source) in enumerate(zip(paths, profile['files']), 1):
            file_reasons = Counter(); raw_count = in_candidate = eligible = 0
            before = path.stat()
            issue_fields = [name for name, counts in source['fields'].items() if any(counts.values())]
            file_protocols, file_pairs = Counter(), Counter()
            for values in _rows(path, config):
                count += 1; raw_count += 1
                if count > config['limits']['max_rows']:
                    raise ValueError('max_rows')
                row = dict(zip(config['expected_header'], values))
                bad, duration = _g12(row, config)
                why = {'invalid_' + key for key in bad}
                protocol = row[config['columns']['protocol']]
                _count(protocol_counts, protocol, config['limits'].get('max_protocol_values', 256), 'max_protocol_values')
                _count(file_protocols, protocol, config['limits'].get('max_protocol_values', 256), 'max_protocol_values')
                if 'protocol' not in bad and int(Decimal(protocol)) not in config['supported_protocols']:
                    why.add('invalid_unsupported_protocol')
                start = _parse_time(row[config['columns']['start']], config)
                if start is None:
                    why.add('invalid_timestamp')
                duplicate = db.execute('SELECT n FROM fingerprints WHERE digest=?', (_fingerprint(values),)).fetchone()
                if duplicate is None:
                    raise ValueError('source_identity_index_mismatch')
                if duplicate[0] > 1:
                    why.add('duplicate_record')
                b = None
                if start is None or duration is None:
                    unplaced += 1
                else:
                    end = start + timedelta(microseconds=duration)
                    m = rules._minute(end)
                    b = buckets.get(m)
                    if b is None:
                        why.add('outside_candidate_ranges')
                    else:
                        in_candidate += 1; b['raw'] += 1
                        if segment_at(start) != b['segment']:
                            why.add('cross_partition')
                kinds, attempted, definite, anomaly = _label_kinds(row[config['columns']['label']], row[config['columns']['attempted']], config['labels'])
                pair = (rules._safe_label(row[config['columns']['label']]), rules._safe_label(row[config['columns']['attempted']]))
                pairs[pair] += 1; file_pairs[pair] += 1
                if anomaly:
                    label_anomalies[anomaly] += 1
                if b is not None:
                    segment = next(s for s in segments if s['id'] == b['segment'])
                    segment['source_labels'][pair[0]] += 1; segment['source_categories'][pair[1]] += 1
                    b['definite_attack'] |= definite
                    if why:
                        b['tainted'] = True; b['reasons'].update(why)
                    else:
                        eligible += 1; b['n'] += 1; b['attempted'] += attempted
                        b['other_field_issues'] += _other_field_issue(row, issue_fields, set(config['numeric_columns']))
                        for policy, kind in zip(('P_U', 'P_B', 'P_A'), kinds):
                            b['policies'][policy][kind] += 1
                reasons.update(why); file_reasons.update(why)
                if count % 10000 == 0 and progress:
                    progress({'phase': 'MINUTES', 'rows': count, 'files_started': file_number})
            after = path.stat()
            if ((before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino)
                    or rules._digest_file(path, config['limits']['max_total_input_bytes'])[1] != source['sha256']):
                raise ValueError('source_identity_changed_during_second_pass')
            file_results.append({'file_id': f'input_{file_number}', 'rows': raw_count, 'in_candidate_ranges': in_candidate,
                                 'eligible_completed_records': eligible, 'flow_reasons': dict(file_reasons),
                                 'protocol_counts': dict(file_protocols),
                                 'label_category_counts': [{'label': k[0], 'attempted_category': k[1], 'rows': n} for k, n in sorted(file_pairs.items())]})
        if count != profile['input_rows']:
            raise ValueError('source_identity_row_count_mismatch')
        if unplaced:
            for b in buckets.values():
                b['tainted'] = True
        conditional = {p: _conditional_policy(p, segments, buckets) for p in ('P_U', 'P_B', 'P_A')}
        _space(directory, config['limits']['audit_max_bytes'])
        return {'schema': 'C17_PAYLOAD_MINUTE_AUDIT_V1', 'identity': config['identity'], 'status': 'COMPLETE_AUDIT_ONLY',
                'profile': profile, 'input_rows': count, 'files': file_results, 'flow_reasons': dict(reasons),
                'protocol_counts': dict(protocol_counts),
                'protocol_semantics': 'EXPLICIT_AUTHOR_ENUM_CANDIDATE_SUPPORTED_SET_NOT_RELEASE_GENERATION_CERTIFICATION',
                'supported_protocols': sorted(config['supported_protocols']),
                'label_category_counts': [{'label': k[0], 'attempted_category': k[1], 'rows': n} for k, n in sorted(pairs.items())],
                'source_sha_binding': 'VERIFIED_AGAINST_COMPLETE_FIRST_PASS_INDEX',
                'extraction_receipt_binding': 'VERIFIED' if receipts is not None else 'NOT_PROVIDED',
                'all_column_filter_impact': _filter_impact(buckets, buckets.keys()),
                'label_anomalies': dict(label_anomalies), 'unplaced_invalid_rows': unplaced,
                'strict': {'coverage': 'UNKNOWN_NOT_CERTIFIED', 'actual_input_valid_minutes': None,
                           'certified_input_valid_minutes': 0, 'actual_label_supply': None, 'high_completion': None},
                'conditional': conditional,
                'conditional_assumptions': ['COMPLETE_RELEASED_RECORDS_WITHIN_PREREGISTERED_SEGMENTS',
                    'SOURCE_CLOCK_UTC_US_AUTHOR_COMPATIBILITY_HYPOTHESIS_ONLY', 'ENCODED_VALUES_USED_EXACTLY_FOR_NOMINAL_END_PROXY',
                    'PHYSICAL_QUANTIZATION_AND_CAPTURE_COMPLETENESS_UNKNOWN', 'EACH_REGISTERED_SEGMENT_RESETS_HISTORY',
                    'EMPTY_MINUTES_ARE_UNKNOWN', 'UNUSED_FIELD_ISSUES_DO_NOT_DROP_G12_VALID_RECORDS'],
                'common_valid_scope': 'G12_SOURCE_FIELDS_AND_CURRENT_H15_H30_QUALIFICATION_ONLY',
                'model_common_valid_minutes': None, 'feature_vectors': 'NOT_PRODUCED',
                'physical_quantization_sensitivity': 'NOT_RUN_PHYSICAL_BOUND_UNVERIFIED',
                'real_training': 'NOT_RUN', 'scoring': 'NOT_RUN', 'score_calibration': 'NOT_RUN',
                'dataset_adoption': 'NOT_APPROVED', 'production_migration': 'NOT_APPROVED'}
    except (sqlite3.DatabaseError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError('incomplete_or_invalid_profile_index') from exc
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index-name', default='profile-index.sqlite3')
    parser.add_argument('--profile-only', action='store_true')
    parser.add_argument('--minutes-only', action='store_true', help='Reuse complete SHA-bound first-pass index')
    args = parser.parse_args(argv)
    try:
        directory = args.audit_dir.resolve(strict=True)
        output = args.output.resolve()
        if output.parent != directory or output.exists() or output in [p.resolve() for p in args.input] or output == args.config.resolve():
            raise ValueError('output_new_inside_audit_required')
        config_path = rules._local_file(args.config)
        if config_path.stat().st_size > 1048576:
            raise ValueError('config_size')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if args.profile_only and args.minutes_only:
            raise ValueError('choose_one_pass_mode')
        callback = lambda value: print(json.dumps(value), flush=True)
        if not args.minutes_only:
            result = profile_csv(args.input, config, directory, args.index_name, progress=callback)
        if not args.profile_only:
            result = audit_minutes(args.input, config, directory, args.index_name, progress=callback)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if _space(directory, config['limits']['audit_max_bytes']) + len(encoded.encode('utf-8')) > config['limits']['audit_max_bytes']:
            raise ValueError('audit_logs_byte_cap')
        with output.open('x', encoding='utf-8') as handle:
            handle.write(encoded)
        print(json.dumps({'status': result['status'], 'rows': result['input_rows']}))
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError, RuntimeError, csv.Error, sqlite3.Error, DecimalException):
        print('PAYLOAD_AUDIT_FAILED_SAFE_INPUT_CONFIG_OR_RESOURCE_ERROR', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
