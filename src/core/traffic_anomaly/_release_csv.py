"""Pure bounded release-format parsing; input identity is not authentication.

All inputs are explicit in-memory bytes. No file discovery, source approval,
model execution or production adapter is provided here.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException
import hashlib
import io
import math
import re
import unicodedata


EXPECTED_HEADER = ('id', 'Flow ID', 'Src IP', 'Src Port', 'Dst IP', 'Dst Port', 'Protocol', 'Timestamp',
 'Flow Duration', 'Total Fwd Packet', 'Total Bwd packets', 'Total Length of Fwd Packet',
 'Total Length of Bwd Packet', 'Fwd Packet Length Max', 'Fwd Packet Length Min',
 'Fwd Packet Length Mean', 'Fwd Packet Length Std', 'Bwd Packet Length Max',
 'Bwd Packet Length Min', 'Bwd Packet Length Mean', 'Bwd Packet Length Std', 'Flow Bytes/s',
 'Flow Packets/s', 'Flow IAT Mean', 'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min', 'Fwd IAT Total',
 'Fwd IAT Mean', 'Fwd IAT Std', 'Fwd IAT Max', 'Fwd IAT Min', 'Bwd IAT Total', 'Bwd IAT Mean',
 'Bwd IAT Std', 'Bwd IAT Max', 'Bwd IAT Min', 'Fwd PSH Flags', 'Bwd PSH Flags', 'Fwd URG Flags',
 'Bwd URG Flags', 'Fwd RST Flags', 'Bwd RST Flags', 'Fwd Header Length', 'Bwd Header Length',
 'Fwd Packets/s', 'Bwd Packets/s', 'Packet Length Min', 'Packet Length Max', 'Packet Length Mean',
 'Packet Length Std', 'Packet Length Variance', 'FIN Flag Count', 'SYN Flag Count',
 'RST Flag Count', 'PSH Flag Count', 'ACK Flag Count', 'URG Flag Count', 'CWR Flag Count',
 'ECE Flag Count', 'Down/Up Ratio', 'Average Packet Size', 'Fwd Segment Size Avg',
 'Bwd Segment Size Avg', 'Fwd Bytes/Bulk Avg', 'Fwd Packet/Bulk Avg', 'Fwd Bulk Rate Avg',
 'Bwd Bytes/Bulk Avg', 'Bwd Packet/Bulk Avg', 'Bwd Bulk Rate Avg', 'Subflow Fwd Packets',
 'Subflow Fwd Bytes', 'Subflow Bwd Packets', 'Subflow Bwd Bytes', 'FWD Init Win Bytes',
 'Bwd Init Win Bytes', 'Fwd Act Data Pkts', 'Fwd Seg Size Min', 'Active Mean', 'Active Std',
 'Active Max', 'Active Min', 'Idle Mean', 'Idle Std', 'Idle Max', 'Idle Min', 'ICMP Code',
 'ICMP Type', 'Total TCP Flow Time', 'Label', 'Attempted Category')

_NORMAL_LABELS = ('BENIGN',)

_ATTACK_LABELS = ('FTP-Patator', 'SSH-Patator', 'DoS Slowloris', 'DoS Slowhttptest', 'DoS Hulk', 'DoS GoldenEye',
 'Heartbleed', 'Web Attack - Brute Force', 'Web Attack - XSS', 'Web Attack - SQL Injection',
 'Infiltration', 'Infiltration - Portscan', 'Portscan', 'Botnet', 'DDoS')

_ATTEMPTED_LABELS = ('FTP-Patator - Attempted', 'SSH-Patator - Attempted', 'DoS Slowloris - Attempted',
 'DoS Slowhttptest - Attempted', 'DoS Hulk - Attempted', 'DoS GoldenEye - Attempted',
 'Heartbleed - Attempted', 'Web Attack - Brute Force - Attempted', 'Web Attack - XSS - Attempted',
 'Web Attack - SQL Injection - Attempted', 'Infiltration - Attempted', 'Botnet - Attempted',
 'DDoS - Attempted')

_EMPTY_CATEGORIES = ('-1',)

_ATTEMPTED_CATEGORIES = ('0', '1', '2', '3', '4', '5', '6')

_NUMERIC_COLUMNS = frozenset(('id', 'Src Port', 'Dst Port', 'Protocol', 'Flow Duration', 'Total Fwd Packet', 'Total Bwd packets',
 'Total Length of Fwd Packet', 'Total Length of Bwd Packet', 'Fwd Packet Length Max',
 'Fwd Packet Length Min', 'Fwd Packet Length Mean', 'Fwd Packet Length Std',
 'Bwd Packet Length Max', 'Bwd Packet Length Min', 'Bwd Packet Length Mean',
 'Bwd Packet Length Std', 'Flow Bytes/s', 'Flow Packets/s', 'Flow IAT Mean', 'Flow IAT Std',
 'Flow IAT Max', 'Flow IAT Min', 'Fwd IAT Total', 'Fwd IAT Mean', 'Fwd IAT Std', 'Fwd IAT Max',
 'Fwd IAT Min', 'Bwd IAT Total', 'Bwd IAT Mean', 'Bwd IAT Std', 'Bwd IAT Max', 'Bwd IAT Min',
 'Fwd PSH Flags', 'Bwd PSH Flags', 'Fwd URG Flags', 'Bwd URG Flags', 'Fwd RST Flags',
 'Bwd RST Flags', 'Fwd Header Length', 'Bwd Header Length', 'Fwd Packets/s', 'Bwd Packets/s',
 'Packet Length Min', 'Packet Length Max', 'Packet Length Mean', 'Packet Length Std',
 'Packet Length Variance', 'FIN Flag Count', 'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count',
 'ACK Flag Count', 'URG Flag Count', 'CWR Flag Count', 'ECE Flag Count', 'Down/Up Ratio',
 'Average Packet Size', 'Fwd Segment Size Avg', 'Bwd Segment Size Avg', 'Fwd Bytes/Bulk Avg',
 'Fwd Packet/Bulk Avg', 'Fwd Bulk Rate Avg', 'Bwd Bytes/Bulk Avg', 'Bwd Packet/Bulk Avg',
 'Bwd Bulk Rate Avg', 'Subflow Fwd Packets', 'Subflow Fwd Bytes', 'Subflow Bwd Packets',
 'Subflow Bwd Bytes', 'FWD Init Win Bytes', 'Bwd Init Win Bytes', 'Fwd Act Data Pkts',
 'Fwd Seg Size Min', 'Active Mean', 'Active Std', 'Active Max', 'Active Min', 'Idle Mean',
 'Idle Std', 'Idle Max', 'Idle Min', 'ICMP Code', 'ICMP Type', 'Total TCP Flow Time',
 'Attempted Category'))


@dataclass(frozen=True)
class ReleaseFixtureBudget:
    """Explicit caller budget; defaults are hard ceilings, never source policy."""

    max_sources: int = 5
    max_total_input_bytes: int = 8 * 1024 * 1024
    max_rows: int = 10000
    max_field_chars: int = 4096
    max_label_values: int = 100
    max_category_values: int = 32
    max_protocol_values: int = 256
    max_expanded_integer_digits: int = 4096


@dataclass(frozen=True)
class ParsedReleaseRow:
    """Source ordinal is 0-based; logical data-record ordinal is 1-based.

    Embedded CSV newlines do not advance the record ordinal. The entire row
    participates in lexical identity. Raw strings are private and excluded
    from repr; numeric reasons never include label or unused-field anomalies.
    """

    source_ordinal: int
    record_ordinal: int
    lexical_fingerprint: bytes
    raw_fields: tuple[str, ...] = field(repr=False)
    start: datetime | None
    duration_us: int | None
    completion: datetime | None
    fwd_packets: int | None
    bwd_packets: int | None
    fwd_length: int | None
    bwd_length: int | None
    protocol_channel: str
    reasons: tuple[str, ...]
    raw_label: str = field(repr=False)
    raw_category: str = field(repr=False)
    label_kinds: tuple[str, str, str]
    attempted: bool
    definite_attack: bool
    label_anomaly: str | None
    unused_field_issues: tuple[str, ...]


@dataclass(frozen=True)
class ParsedReleaseBatch:
    schema_id: str
    source_bytes: tuple[int, ...]
    source_sha256: tuple[str, ...]
    rows: tuple[ParsedReleaseRow, ...]
    source_authentication: str = 'NOT_AUTHENTICATED'
    time_basis: str = 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'


_HARD_BUDGET = ReleaseFixtureBudget()
_INTEGER_LEXEME = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE]([+-]?\d+))?$')


def _validate_budget(budget: ReleaseFixtureBudget) -> None:
    if type(budget) is not ReleaseFixtureBudget:
        raise ValueError('invalid_budget')
    for spec in fields(ReleaseFixtureBudget):
        value = getattr(budget, spec.name)
        if type(value) is not int or not 0 < value <= getattr(_HARD_BUDGET, spec.name):
            raise ValueError('invalid_budget')


def _integer(raw: str, digits: int) -> int | None:
    """Decimal mathematical integer, guarding expansion before int conversion.

    Decimal cannot represent arbitrarily long exponents. Handle that lexical
    corner without expanding an exponent or changing zero's integer meaning.
    Decimal itself accepts underscores and Unicode decimal digits.
    """
    text = raw.strip().replace('_', '')
    match = _INTEGER_LEXEME.fullmatch(text)
    if match and match.group(1) is not None:
        exponent = match.group(1)
        significant_exponent = ''.join(str(unicodedata.decimal(c))
                                       for c in exponent.lstrip('+-')).lstrip('0')
        coefficient = re.split('[eE]', text)[0]
        mantissa = Decimal(coefficient)
        if mantissa.is_zero():
            return 0
        if mantissa < 0:
            return None
        if len(significant_exponent) > 18:
            if exponent.startswith('-'):
                return None
            raise ValueError('integer_expansion_limit')
        power = int(significant_exponent or '0')
        if exponent.startswith('-'):
            power = -power
        # A multi-digit coefficient can exceed Decimal's adjusted-exponent
        # representation even when the lexical exponent has only 18 digits.
        if mantissa.as_tuple().exponent + power >= 0 and mantissa.adjusted() + power >= digits:
            raise ValueError('integer_expansion_limit')
    try:
        value = Decimal(raw)
        if not value.is_finite() or value < 0:
            return None
        if value.is_zero():
            return 0
        if value != value.to_integral_value():
            return None
        if value.adjusted() >= digits:
            raise ValueError('integer_expansion_limit')
        return int(value)
    except DecimalException:
        return None


def _labels(label: str, category: str) -> tuple[tuple[str, str, str], bool, bool, str | None]:
    attempted = label in _ATTEMPTED_LABELS or category not in _EMPTY_CATEGORIES
    definite = label in _ATTACK_LABELS
    known = label in _NORMAL_LABELS + _ATTACK_LABELS + _ATTEMPTED_LABELS
    category_known = category in _EMPTY_CATEGORIES + _ATTEMPTED_CATEGORIES
    contradiction = (label in _NORMAL_LABELS + _ATTACK_LABELS and attempted
                     or label in _ATTEMPTED_LABELS and category in _EMPTY_CATEGORIES)
    if not known or not category_known or contradiction:
        anomaly = ('unknown_label' if not known else 'unknown_attempted_category'
                   if not category_known else 'label_category_conflict')
        return ('unknown', 'unknown', 'unknown'), attempted, definite, anomaly
    if attempted:
        return ('unknown', 'normal', 'attack'), attempted, definite, None
    kind = 'attack' if definite else 'normal'
    return (kind, kind, kind), attempted, definite, None


def _parse_row(values: tuple[str, ...], source: int, record: int, digits: int) -> ParsedReleaseRow:
    digest = hashlib.sha256()
    for value in values:
        raw = value.encode('utf-8')
        digest.update(len(raw).to_bytes(4, 'little'))
        digest.update(raw)
    row = dict(zip(EXPECTED_HEADER, values))
    numbers = {}
    reasons = []
    columns = (('duration', 'Flow Duration'), ('protocol', 'Protocol'),
               ('fwd_packets', 'Total Fwd Packet'), ('bwd_packets', 'Total Bwd packets'),
               ('fwd_length', 'Total Length of Fwd Packet'), ('bwd_length', 'Total Length of Bwd Packet'))
    for key, column in columns:
        number = _integer(row[column], digits)
        if key == 'protocol' and number is not None and number > 255:
            number = None
        if number is None:
            reasons.append('invalid_' + key)
        numbers[key] = number
    duration = numbers['duration']
    if duration is not None and duration > 86400 * 1000000:
        raise ValueError('duration_cap')
    try:
        start = datetime.strptime(row['Timestamp'], '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        start = None
        reasons.append('invalid_timestamp')
    completion = None
    if start is not None and duration is not None:
        try:
            completion = start + timedelta(microseconds=duration)
        except OverflowError:
            raise ValueError('completion_overflow') from None
    protocol = numbers['protocol']
    channel = {0: 'unresolved', 6: 'tcp', 17: 'udp', 1: 'known_other',
               2: 'known_other', 132: 'known_other'}.get(protocol, 'excluded_protocol')
    if protocol is not None and channel == 'excluded_protocol':
        reasons.append('invalid_unsupported_protocol')
    label, category = row['Label'], row['Attempted Category']
    kinds, attempted, definite, anomaly = _labels(label, category)
    used = {column for _, column in columns} | {'Timestamp', 'Label', 'Attempted Category'}
    unused_issues = ()
    for name, raw in row.items():
        if name in used:
            continue
        text = raw.strip()
        issue = not text or text.lower() in {'nan', '+nan', '-nan', 'inf', '+inf', '-inf',
                                           'infinity', '+infinity', '-infinity'}
        if name in _NUMERIC_COLUMNS:
            try:
                issue |= not math.isfinite(float(raw))
            except (ValueError, OverflowError):
                issue = True
        if issue:
            unused_issues = ('unused_field_issue',)
            break
    return ParsedReleaseRow(
        source, record, digest.digest(), values, start, duration, completion,
        numbers['fwd_packets'], numbers['bwd_packets'], numbers['fwd_length'], numbers['bwd_length'],
        channel, tuple(reasons), label, category, kinds, attempted, definite, anomaly, unused_issues)


def _parse_release_csv(sources: tuple[bytes, ...], *, budget: ReleaseFixtureBudget) -> ParsedReleaseBatch:
    """Parse a complete bounded batch, or fail with a fixed content-free code.

    Field length applies to data fields; the exact constant header is already
    bounded. All vocabulary budgets use exact lexical values across all sources.
    Source sizes and SHA-256 values bind consistency only, never provenance.
    """
    _validate_budget(budget)
    if type(sources) is not tuple or any(type(source) is not bytes for source in sources):
        raise ValueError('invalid_sources')
    if not sources:
        raise ValueError('empty_batch')
    if len(sources) > budget.max_sources:
        raise ValueError('max_sources')
    sizes = tuple(map(len, sources))
    if sum(sizes) > budget.max_total_input_bytes:
        raise ValueError('input_byte_cap')
    rows = []
    vocabularies = [set(), set(), set()]
    vocab_specs = (('Label', budget.max_label_values, 'max_label_values'),
                   ('Attempted Category', budget.max_category_values, 'max_category_values'),
                   ('Protocol', budget.max_protocol_values, 'max_protocol_values'))
    for source_ordinal, source in enumerate(sources):
        try:
            decoded = source.decode('utf-8-sig', errors='strict')
        except UnicodeError:
            raise ValueError('invalid_utf8') from None
        reader = csv.reader(io.StringIO(decoded, newline=''), strict=True)
        try:
            header = next(reader, None)
            if header is None:
                raise ValueError('missing_header')
            if tuple(header) != EXPECTED_HEADER:
                raise ValueError('header_mismatch')
            for record_ordinal, values in enumerate(reader, 1):
                if len(rows) >= budget.max_rows:
                    raise ValueError('max_rows')
                if len(values) != len(EXPECTED_HEADER):
                    raise ValueError('ragged_row')
                if any('\x00' in value for value in values):
                    raise ValueError('field_nul')
                if any(len(value) > budget.max_field_chars for value in values):
                    raise ValueError('max_field_chars')
                for vocabulary, (column, limit, code) in zip(vocabularies, vocab_specs):
                    vocabulary.add(values[EXPECTED_HEADER.index(column)])
                    if len(vocabulary) > limit:
                        raise ValueError(code)
                rows.append(_parse_row(tuple(values), source_ordinal, record_ordinal,
                                       budget.max_expanded_integer_digits))
        except csv.Error:
            raise ValueError('invalid_csv') from None
    return ParsedReleaseBatch('c17-release-91-v1', sizes,
                              tuple(hashlib.sha256(source).hexdigest() for source in sources), tuple(rows))
