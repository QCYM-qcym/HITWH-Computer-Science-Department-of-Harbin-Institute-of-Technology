"""Offline, aggregate-only inspection of approved C18-S CSV prefixes.

No network, model fitting, imputation, timezone inference, or minute aggregation.
Benign/BENIGN are spelling references only, not certified normal-minute truth.
Other labels remain unmapped, not automatically made normal/attack.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

PER_OBJECT_CAP = 4 * 1024 * 1024
REQUIRED_FIELDS = (
    'Flow Duration', 'Protocol', 'Tot Fwd Pkts', 'Tot Bwd Pkts',
    'TotLen Fwd Pkts', 'TotLen Bwd Pkts',
)


def audit_prefix(data: bytes) -> dict:
    """Inspect complete CSV records in a byte prefix; return no raw records."""
    if len(data) > PER_OBJECT_CAP:
        raise ValueError('Input exceeds approved 4 MiB per-object limit')
    boundary = data.rfind(b'\n') + 1
    if not boundary:
        raise ValueError('Prefix contains no complete header line')
    text = data[:boundary].decode('utf-8-sig', errors='strict')
    csv.field_size_limit(65536)
    rows = csv.reader(io.StringIO(text, newline=''), strict=True)
    raw_header = next(rows)
    header = [name.strip() for name in raw_header]
    if not header or len(header) > 256 or any(not n or len(n) > 128 for n in header):
        raise ValueError('Invalid or oversized header')
    if len(set(header)) != len(header):
        raise ValueError('duplicate column names after whitespace normalization')
    for field in ('Timestamp', 'Label'):
        if field not in header:
            raise ValueError(f'Missing required field {field}')
    numeric_fields = [n for n in header if n not in ('Timestamp', 'Label')]
    nonfinite, missing, unparseable, required_invalid = Counter(), Counter(), Counter(), Counter()
    label_counts, protocols = Counter(), Counter()
    timestamp_values, timestamps = Counter(), []
    numeric_rows_with_issue = required_rows_with_issue = 0
    timestamp_errors = empty_labels = zero_duration = 0
    duration_min = duration_max = None
    count = 0
    present_required = [n for n in REQUIRED_FIELDS if n in header]
    for row in rows:
        if len(row) != len(header):
            raise ValueError(f'Complete record {count + 1} has inconsistent column count')
        if any(len(value) > 2048 for value in row):
            raise ValueError('Oversized field')
        count += 1
        values = dict(zip(header, row))
        numeric_values = {}
        bad_numeric = False
        for field in numeric_fields:
            raw = values[field].strip()
            if not raw:
                missing[field] += 1
                bad_numeric = True
                continue
            try:
                value = float(raw)
            except ValueError:
                unparseable[field] += 1
                bad_numeric = True
                continue
            if not math.isfinite(value):
                nonfinite[field] += 1
                bad_numeric = True
                continue
            numeric_values[field] = value
        numeric_rows_with_issue += bad_numeric
        required_bad = False
        for field in present_required:
            value = numeric_values.get(field)
            invalid = value is None or value < 0
            if value is not None:
                if field == 'Protocol':
                    invalid |= not value.is_integer() or value > 255
                elif field != 'Flow Duration':
                    invalid |= not value.is_integer()
            if invalid:
                required_invalid[field] += 1
                required_bad = True
        required_rows_with_issue += required_bad
        duration = numeric_values.get('Flow Duration')
        if duration is not None:
            duration_min = duration if duration_min is None else min(duration_min, duration)
            duration_max = duration if duration_max is None else max(duration_max, duration)
            zero_duration += duration == 0
        protocol = numeric_values.get('Protocol')
        if protocol is not None and protocol.is_integer() and 0 <= protocol <= 255:
            protocols[str(int(protocol))] += 1
        label = values['Label'].strip()
        if not label:
            empty_labels += 1
        else:
            label_counts[label] += 1
        raw_time = values['Timestamp'].strip()
        try:
            # This is nominal source clock parsing, not a timezone or 12/24-hour decision.
            value = datetime.strptime(raw_time, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            timestamp_errors += 1
        else:
            timestamp_values[raw_time] += 1
            timestamps.append(value)
    hours = {value.hour for value in timestamps}
    return {
        'scope': 'BYTE_PREFIX_ONLY_NOT_COMPLETE_FILE',
        'prefix_bytes': len(data),
        'prefix_sha256': hashlib.sha256(data).hexdigest(),
        'complete_line_bytes': boundary,
        'discarded_tail_bytes': len(data) - boundary,
        'header': raw_header,
        'column_count': len(header),
        'complete_data_rows': count,
        'numeric': {
            'missing_cells': dict(missing), 'unparseable_cells': dict(unparseable),
            'nonfinite_cells': dict(nonfinite), 'rows_with_issue': numeric_rows_with_issue,
        },
        'required_source_fields': {
            'present': present_required,
            'missing': [n for n in REQUIRED_FIELDS if n not in header],
            'invalid_counts': dict(required_invalid), 'rows_with_issue': required_rows_with_issue,
        },
        'duration': {
            'observed_raw_min': duration_min, 'observed_raw_max': duration_max,
            'zero_rows': zero_duration, 'unit': 'NOT_VERIFIED_FOR_DISTRIBUTION',
        },
        'protocol_value_counts': dict(protocols),
        'protocol_zero_semantics': 'UNVERIFIED_SOURCE_ENCODING',
        'labels': {
            'observed_counts': dict(label_counts), 'missing_rows': empty_labels,
            'benign_flow_rows': sum(label_counts.get(k, 0) for k in ('Benign', 'BENIGN')),
            'unmapped_non_benign_rows': sum(v for k, v in label_counts.items() if k not in ('Benign', 'BENIGN')),
            'non_benign_policy': 'UNMAPPED_REQUIRES_VERSION_SPECIFIC_VOCABULARY',
            'minute_truth_verified': False,
        },
        'timestamp': {
            'parser': 'day/month/year nominal clock HMS; no AM/PM resolution',
            'parsed_rows': len(timestamps), 'parse_error_rows': timestamp_errors,
            'nominal_min': min(timestamps).isoformat() if timestamps else None,
            'nominal_max': max(timestamps).isoformat() if timestamps else None,
            'hour_values': sorted(hours),
            'hour_ambiguity': 'ALL_VALUES_01_TO_12_WITHOUT_AM_PM' if hours and all(1 <= h <= 12 for h in hours) else 'GENERATOR_BINDING_REQUIRED',
            'timezone': None, 'dst': None, 'export_time': None, 'availability_time': None,
            'precision': 'TEXT_SECONDS_NO_FRACTION',
            'unique_timestamp_texts': len(timestamp_values),
            'duplicate_timestamp_rows': sum(v - 1 for v in timestamp_values.values()),
            'raw_order_inversions': sum(b < a for a, b in zip(timestamps, timestamps[1:])),
            'observed_nominal_start_clock_minutes': len({v.replace(second=0) for v in timestamps}),
        },
        'can_estimate_four_split_supply': False,
        'four_split_supply': None,
        'capture_continuity': 'NOT_ESTIMABLE_FROM_BYTE_PREFIX',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Approved local prefix directory')
    parser.add_argument('--output', type=Path, required=True, help='New aggregate report; refuses overwrite')
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    ledger_path = root / 'acquisition.json'
    if ledger_path.is_symlink() or ledger_path.stat().st_size > 65536:
        raise ValueError('Invalid acquisition ledger')
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    if ledger['status'] != 'ACQUIRED_4_PREFIXES_ONLY' or len(ledger['objects']) != 4:
        raise ValueError('Expected four completed, approved prefixes')
    results = []
    for item in ledger['objects']:
        path = root / item['saved_basename']
        if path.is_symlink() or path.resolve().parent != root or path.stat().st_nlink != 1:
            raise ValueError('Only regular, singly linked prefixes inside root are accepted')
        if path.stat().st_size > PER_OBJECT_CAP:
            raise ValueError('Prefix exceeds 4 MiB')
        result = audit_prefix(path.read_bytes())
        if result['prefix_sha256'] != item['prefix_sha256'] or result['prefix_bytes'] != item['actual_body_bytes']:
            raise ValueError('Prefix no longer matches acquisition identity')
        results.append({'filename': item['filename'], **result})
    report = {
        'scope': 'C18-S_FOUR_APPROVED_PREFIXES_ONLY',
        'total_prefix_bytes': sum(r['prefix_bytes'] for r in results),
        'same_header_all_four': all(r['header'] == results[0]['header'] for r in results),
        'objects': results,
        'four_split_supply': None, 'real_training': 'NOT_RUN', 'dataset_adoption': 'NOT_APPROVED',
    }
    if report['total_prefix_bytes'] > 4 * PER_OBJECT_CAP:
        raise ValueError('Total exceeds 16 MiB')
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'objects': len(results), 'total_prefix_bytes': report['total_prefix_bytes'], 'same_header_all_four': report['same_header_all_four']}))


if __name__ == '__main__':
    main()
