"""Pure fixed artificial release-format CSV, aggregation spec and recipe.

Only the spec contains the future CSV path. No file access, aggregation,
preprocessing, estimator or source-authentication claim belongs to this builder.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path

from ._release_csv import EXPECTED_HEADER

EXAMPLE_PROFILE_ID = 'release-artificial-example-v1'
EXAMPLE_MEMBER_NAMES = ('artificial.csv', 'aggregate-spec.json', 'recipe.json')
EXAMPLE_MEMBER_BYTE_LIMITS = (
    ('artificial.csv', 1048576), ('aggregate-spec.json', 65536), ('recipe.json', 16384))
EXAMPLE_TOTAL_BYTE_LIMIT = 1130496

_SEGMENTS = (
    ('artificial-train', 'train', '2026-01-01T00:00:00', '2026-01-01T00:48:00', 48),
    ('artificial-validation', 'validation', '2026-01-01T01:00:00', '2026-01-01T01:40:00', 40),
    ('artificial-calibration', 'calibration', '2026-01-01T02:00:00', '2026-01-01T02:40:00', 40),
    ('artificial-test', 'test', '2026-01-01T03:00:00', '2026-01-01T03:48:00', 48),
)
_CODES = frozenset(('INVALID_EXAMPLE_ARGUMENTS', 'RESOURCE_LIMIT', 'EXAMPLE_ERROR'))


@dataclass(frozen=True, slots=True)
class ReleaseExample:
    profile_id: str
    members: tuple[tuple[str, bytes], ...]


class ReleaseExampleError(ValueError):
    """Safe finite construction codes, without paths or original exceptions."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in _CODES else 'EXAMPLE_ERROR'
        super().__init__(self.code)


def _need(condition, code):
    if not condition:
        raise ReleaseExampleError(code) from None


def _source_path(path, limit):
    code = 'INVALID_EXAMPLE_ARGUMENTS'
    _need(type(path) is type(Path()), code)
    value = str(path)
    _need(path.is_absolute() and path.name == 'artificial.csv' and '..' not in path.parts
        and '\0' not in value and not value.startswith(('\\\\', '//'))
        and not any(0xD800 <= ord(char) <= 0xDFFF for char in value), code)
    if os.name == 'nt':
        _need(len(path.drive) == 2 and path.drive[1] == ':'
            and all(':' not in part and not os.path.isreserved(part) for part in path.parts[1:]), code)
    # The unescaped path alone cannot fit if it already exceeds the spec cap.
    # Bound it before JSON constructs a potentially large escaped string chunk.
    _need(len(value) <= limit, 'RESOURCE_LIMIT')
    _need(len(value.encode('utf-8')) <= limit, 'RESOURCE_LIMIT')
    return value


def _csv_bytes():
    # The entire CSV has a fixed 176x91 finite recipe, no caller-provided cells.
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=',', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    writer.writerow(EXPECTED_HEADER)
    index = 0
    for _, role, start, _, count in _SEGMENTS:
        beginning = datetime.fromisoformat(start)
        for local in range(count):
            packets = 1 + local % 3
            if role == 'test' and local in (36, 40):
                packets *= 8
            backwards = 0 if local % 5 == 0 else 1
            protocol = 0 if role == 'test' and local in (36, 40) else (6, 17, 0)[local % 3]
            label, category = ('BENIGN', '-1')
            if role == 'test':
                label, category = {36: ('DoS Hulk', '-1'), 40: ('SSH-Patator - Attempted', '0'),
                                   44: ('ARTIFICIAL_UNKNOWN', '-1')}.get(local, (label, category))
            values = dict.fromkeys(EXPECTED_HEADER, '0')
            values.update({
                'id': str(index), 'Flow ID': f'artificial-{index:04d}',
                'Src IP': 'ARTIFICIAL_SRC', 'Dst IP': 'ARTIFICIAL_DST',
                'Timestamp': (beginning + timedelta(minutes=local, seconds=10)).strftime('%Y-%m-%d %H:%M:%S.%f'),
                'Flow Duration': '1000000', 'Total Fwd Packet': str(packets),
                'Total Bwd packets': str(backwards), 'Total Length of Fwd Packet': str(10 * packets),
                'Total Length of Bwd Packet': str(10 * backwards), 'Protocol': str(protocol),
                'Label': label, 'Attempted Category': category,
            })
            writer.writerow(tuple(values[name] for name in EXPECTED_HEADER))
            index += 1
    return stream.getvalue().encode('ascii')


def _canonical(document, limit):
    result = bytearray()
    for chunk in json.JSONEncoder(sort_keys=True, ensure_ascii=False, allow_nan=False,
                                  separators=(',', ':')).iterencode(document):
        encoded = chunk.encode('utf-8')
        _need(len(result) + len(encoded) + 1 <= limit, 'RESOURCE_LIMIT')
        result.extend(encoded)
    return bytes(result) + b'\n'


def build_release_example(*, source_csv_path: Path) -> ReleaseExample:
    """Return three finite immutable members for a future source path, without I/O."""
    try:
        limits = dict(EXAMPLE_MEMBER_BYTE_LIMITS)
        path = _source_path(source_csv_path, min(limits['aggregate-spec.json'], EXAMPLE_TOTAL_BYTE_LIMIT))
        members = []
        total = 0
        def append(name, payload):
            nonlocal total
            _need(len(payload) <= limits[name] and total + len(payload) <= EXAMPLE_TOTAL_BYTE_LIMIT,
                  'RESOURCE_LIMIT')
            total += len(payload)
            members.append((name, payload))
        csv_bytes = _csv_bytes()
        append('artificial.csv', csv_bytes)
        digest = hashlib.sha256(csv_bytes).hexdigest()
        segments = [dict(id=name, role=role, start=start, end=end)
                    for name, role, start, end, _ in _SEGMENTS]
        spec = dict(version=1, sources=[dict(path=path, bytes=len(csv_bytes), sha256=digest)],
            segments=segments, budget=dict(max_total_source_bytes=1048576, max_rows=512,
                max_database_bytes=8388608, max_elapsed_seconds=30, max_minutes=240))
        append('aggregate-spec.json', _canonical(spec, min(limits['aggregate-spec.json'],
                                                          EXAMPLE_TOTAL_BYTE_LIMIT - total)))
        recipe = dict(version=1, profile_id=EXAMPLE_PROFILE_ID,
            evidence_kind='ARTIFICIAL_ENGINEERING_EXAMPLE', format_schema_id='c17-release-91-v1',
            source_authentication='NOT_AUTHENTICATED', time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',
            policy_status='AUDIT_ONLY', generation='FIXED_RECIPE_NO_RANDOMNESS',
            notice='Artificial format-compatible example; not an official CICIDS2017 dataset.',
            source=dict(member='artificial.csv', byte_count=len(csv_bytes), sha256=digest, row_count=176),
            segments=segments)
        append('recipe.json', _canonical(recipe, min(limits['recipe.json'], EXAMPLE_TOTAL_BYTE_LIMIT - total)))
        return ReleaseExample(EXAMPLE_PROFILE_ID, tuple(members))
    except ReleaseExampleError:
        raise
    except Exception:
        raise ReleaseExampleError('EXAMPLE_ERROR') from None
