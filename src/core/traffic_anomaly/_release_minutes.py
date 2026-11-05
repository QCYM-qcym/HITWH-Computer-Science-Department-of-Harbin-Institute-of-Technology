"""Exact bounded release-minute aggregation on an unauthenticated source clock.

All counts and samples stay integer until a usable bucket is materialized.
Linear quantiles use rational microseconds; the final float may round (including
integer counts above 2**53). A nonfinite conversion aborts the complete result.
No file, source-authentication, synthetic-certification or model bridge exists.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
import math
import re

from ._release_csv import EXPECTED_HEADER, ParsedReleaseBatch, ParsedReleaseRow
from .candidate_inputs import G13U_FEATURE_NAMES

POLICIES = ('P_U', 'P_B', 'P_A')
LABEL_KINDS = ('normal', 'attack', 'unknown')
PROTOCOL_CHANNELS = ('tcp', 'udp', 'known_other', 'unresolved', 'excluded_protocol')
ELIGIBLE_CHANNELS = PROTOCOL_CHANNELS[:4]
LABEL_ANOMALIES = ('unknown_label', 'unknown_attempted_category', 'label_category_conflict')
REASON_CODES = ('invalid_duration', 'invalid_protocol', 'invalid_fwd_packets',
    'invalid_bwd_packets', 'invalid_fwd_length', 'invalid_bwd_length',
    'invalid_unsupported_protocol', 'invalid_timestamp', 'duplicate_record',
    'cross_partition', 'outside_registered_minutes', 'unplaced_invalid_row',
    'empty_unconfirmed')
_PARSED_REASONS = frozenset(REASON_CODES[:8])
_ROLES = ('train', 'validation', 'calibration', 'test')
_MINUTE = timedelta(minutes=1)
_SHA = re.compile('[0-9a-f]{64}\\Z')
_COUNTS = ('fwd_packets', 'bwd_packets', 'fwd_length', 'bwd_length')
_MAX_INTEGER = 10**4096 - 1


@dataclass(frozen=True)
class ReleaseSegment:
    id: str
    role: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class ReleaseBucketCounts:
    """Assigned rows only; global unplaced taint has its own reason count.

    Fixed channel, anomaly and policy/kind orders also apply to global counters.
    Reasons overlap; empty_unconfirmed counts a bucket, not an excluded row.
    """

    raw_records: int
    eligible_records: int
    excluded_records: int
    reason_counts: tuple[tuple[str, int], ...]
    raw_protocol_counts: tuple[tuple[str, int], ...]
    eligible_protocol_counts: tuple[tuple[str, int], ...]
    label_kind_counts: tuple[tuple[int, int, int], ...]
    label_anomaly_counts: tuple[tuple[str, int], ...]
    definite_attack_present: bool
    attempted_present: bool
    unused_field_issue_records: int


@dataclass(frozen=True)
class ReleaseMinuteResult:
    """Immutable complete registered axis, without source row payloads.

    label_kinds[i] follows POLICIES; label_kind_counts[p] follows LABEL_KINDS.
    Source SHA/size binds supplied inputs for consistency only. User-constructed
    parsed dataclasses are not proof of parser execution or provenance.
    """

    schema_id: str
    source_bytes: tuple[int, ...]
    source_sha256: tuple[str, ...]
    source_authentication: str
    time_basis: str
    feature_names: tuple[str, ...]
    timestamps: tuple[datetime, ...]
    segment_ids: tuple[str, ...]
    roles: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]
    source_valid: tuple[bool, ...]
    label_kinds: tuple[tuple[str, str, str], ...]
    bucket_counts: tuple[ReleaseBucketCounts, ...]
    raw_records: int
    eligible_records: int
    excluded_records: int
    outside_records: int
    unplaced_invalid_rows: int
    duplicate_groups: int
    reason_counts: tuple[tuple[str, int], ...]
    raw_protocol_counts: tuple[tuple[str, int], ...]
    eligible_protocol_counts: tuple[tuple[str, int], ...]
    label_kind_counts: tuple[tuple[int, int, int], ...]
    label_anomaly_counts: tuple[tuple[str, int], ...]


def _stamp(value: object, *, minute: bool = False) -> bool:
    return (type(value) is datetime and value.tzinfo is None
            and (not minute or value.second == value.microsecond == 0))


def _integer(value: object) -> bool:
    return type(value) is int and 0 <= value <= _MAX_INTEGER


def _validate_parsed(parsed: ParsedReleaseBatch) -> None:
    """Check bounded immutable shapes and internal consistency, never origin."""
    def fail():
        raise ValueError('invalid_parsed_batch')

    if (type(parsed) is not ParsedReleaseBatch
            or type(parsed.schema_id) is not str or parsed.schema_id != 'c17-release-91-v1'
            or type(parsed.source_authentication) is not str or parsed.source_authentication != 'NOT_AUTHENTICATED'
            or type(parsed.time_basis) is not str or parsed.time_basis != 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'
            or type(parsed.source_bytes) is not tuple or not 1 <= len(parsed.source_bytes) <= 5
            or any(type(n) is not int or n <= 0 for n in parsed.source_bytes)
            or sum(parsed.source_bytes) > 8 * 1024 * 1024
            or type(parsed.source_sha256) is not tuple
            or len(parsed.source_sha256) != len(parsed.source_bytes)
            or any(type(s) is not str or not _SHA.fullmatch(s) for s in parsed.source_sha256)
            or type(parsed.rows) is not tuple or len(parsed.rows) > 10000):
        fail()
    locators = set()
    for r in parsed.rows:
        if (type(r) is not ParsedReleaseRow
                or type(r.source_ordinal) is not int or not 0 <= r.source_ordinal < len(parsed.source_bytes)
                or type(r.record_ordinal) is not int or not 1 <= r.record_ordinal <= 10000
                or (r.source_ordinal, r.record_ordinal) in locators
                or type(r.lexical_fingerprint) is not bytes or len(r.lexical_fingerprint) != 32
                or type(r.raw_fields) is not tuple or len(r.raw_fields) != 91
                or any(type(s) is not str or len(s) > 4096 or '\x00' in s for s in r.raw_fields)
                or r.start is not None and not _stamp(r.start)
                or r.completion is not None and not _stamp(r.completion)
                or r.duration_us is not None and (not _integer(r.duration_us) or r.duration_us > 86400000000)
                or any(getattr(r, k) is not None and not _integer(getattr(r, k)) for k in _COUNTS)
                or type(r.protocol_channel) is not str or r.protocol_channel not in PROTOCOL_CHANNELS
                or type(r.reasons) is not tuple
                or any(type(s) is not str or s not in _PARSED_REASONS for s in r.reasons)
                or len(set(r.reasons)) != len(r.reasons)
                or type(r.label_kinds) is not tuple or len(r.label_kinds) != 3
                or any(type(s) is not str or s not in LABEL_KINDS for s in r.label_kinds)
                or type(r.attempted) is not bool or type(r.definite_attack) is not bool
                or r.label_anomaly is not None and (type(r.label_anomaly) is not str or r.label_anomaly not in LABEL_ANOMALIES)
                or type(r.unused_field_issues) is not tuple
                or any(type(s) is not str for s in r.unused_field_issues)
                or r.unused_field_issues not in ((), ('unused_field_issue',))
                or type(r.raw_label) is not str or r.raw_label != r.raw_fields[EXPECTED_HEADER.index('Label')]
                or type(r.raw_category) is not str or r.raw_category != r.raw_fields[EXPECTED_HEADER.index('Attempted Category')]):
            fail()
        locators.add((r.source_ordinal, r.record_ordinal))
        expected = {'invalid_' + k for k in _COUNTS if getattr(r, k) is None}
        if r.start is None:
            expected.add('invalid_timestamp')
        if r.duration_us is None:
            expected.add('invalid_duration')
        proto = set(r.reasons) & {'invalid_protocol', 'invalid_unsupported_protocol'}
        if (r.protocol_channel == 'excluded_protocol' and len(proto) != 1
                or r.protocol_channel != 'excluded_protocol' and proto):
            fail()
        if set(r.reasons) != expected | proto:
            fail()
        completion = None
        if r.start is not None and r.duration_us is not None:
            try:
                completion = r.start + timedelta(microseconds=r.duration_us)
            except OverflowError:
                fail()
        if r.completion != completion:
            fail()


def _axis(segments: tuple[ReleaseSegment, ...], max_minutes: int):
    if type(max_minutes) is not int or not 1 <= max_minutes <= 10000:
        raise ValueError('invalid_max_minutes')
    if type(segments) is not tuple or not 1 <= len(segments) <= 7:
        raise ValueError('invalid_segments')
    ids = set()
    stamps, segment_ids, roles, owners = [], [], [], {}
    prior_end, prior_role = None, -1
    total = 0
    for j, s in enumerate(segments):
        if (type(s) is not ReleaseSegment or type(s.id) is not str or not 1 <= len(s.id) <= 128
                or s.id in ids or type(s.role) is not str or s.role not in _ROLES
                or not _stamp(s.start, minute=True) or not _stamp(s.end, minute=True)
                or s.start >= s.end or prior_end is not None and s.start < prior_end
                or _ROLES.index(s.role) < prior_role):
            raise ValueError('invalid_segments')
        n = (s.end - s.start) // _MINUTE
        total += n
        if total > max_minutes:
            raise ValueError('minute_cap')
        ids.add(s.id)
        prior_end, prior_role = s.end, _ROLES.index(s.role)
        for k in range(n):
            t = s.start + k * _MINUTE
            owners[t] = (len(stamps), j)
            stamps.append(t)
            segment_ids.append(s.id)
            roles.append(s.role)
    return tuple(stamps), tuple(segment_ids), tuple(roles), owners


def _fixed(counter: Counter, keys: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    return tuple((k, counter[k]) for k in keys)


def _label_counts(rows) -> tuple[tuple[int, int, int], ...]:
    return tuple(tuple(sum(r.label_kinds[p] == k for r in rows) for k in LABEL_KINDS)
                 for p in range(3))


def _features(rows: list[ParsedReleaseRow]) -> tuple[float, ...]:
    durations = sorted(r.duration_us for r in rows)
    channels = Counter(r.protocol_channel for r in rows)
    def quantile(numerator: int, denominator: int) -> Fraction:
        rank, remainder = divmod((len(durations) - 1) * numerator, denominator)
        value = Fraction(durations[rank])
        if remainder:
            value += Fraction((durations[rank+1] - durations[rank]) * remainder, denominator)
        return value / 1000000
    numbers = [len(rows), *(sum(getattr(r, k) for r in rows) for k in _COUNTS),
               *(channels[k] for k in ELIGIBLE_CHANNELS), Fraction(durations[-1], 1000000),
               quantile(1, 2), quantile(19, 20), sum(r.bwd_packets == 0 for r in rows)]
    try:
        result = tuple(float(n) for n in numbers)
    except OverflowError:
        raise ValueError('numeric_materialization_overflow') from None
    if not all(math.isfinite(n) for n in result):
        raise ValueError('numeric_materialization_overflow')
    return result


def _aggregate_release_minutes(parsed: ParsedReleaseBatch, segments: tuple[ReleaseSegment, ...],
                               *, max_minutes: int) -> ReleaseMinuteResult:
    """Aggregate the entire bounded batch, retaining every registered minute.

    Duplicates exclude every full lexical copy across the complete population,
    including outside/unplaced rows. Eligibility counts rows, while any assigned
    exclusion or globally unplaceable row invalidates a whole minute. Source
    label descriptions include excluded rows and never expose raw label words.
    """
    timestamps, segment_ids, roles, owners = _axis(segments, max_minutes)
    _validate_parsed(parsed)
    frequencies = Counter(r.lexical_fingerprint for r in parsed.rows)
    buckets = [[] for _ in timestamps]
    bucket_reasons = [Counter() for _ in timestamps]
    eligible_buckets = [[] for _ in timestamps]
    reasons, raw_channels, good_channels = Counter(), Counter(), Counter()
    outside = unplaced = eligible = 0
    for r in parsed.rows:
        bad = set(r.reasons)
        if frequencies[r.lexical_fingerprint] > 1:
            bad.add('duplicate_record')
        raw_channels[r.protocol_channel] += 1
        owner = None
        if r.completion is None:
            unplaced += 1
            bad.add('unplaced_invalid_row')
        else:
            owner = owners.get(r.completion.replace(second=0, microsecond=0))
            if owner is None:
                outside += 1
                bad.add('outside_registered_minutes')
            else:
                origin = owners.get(r.start.replace(second=0, microsecond=0))
                if origin is None or origin[1] != owner[1]:
                    bad.add('cross_partition')
        reasons.update(bad)
        if owner is not None:
            i = owner[0]
            buckets[i].append(r)
            bucket_reasons[i].update(bad)
            if not bad:
                eligible_buckets[i].append(r)
                eligible += 1
                good_channels[r.protocol_channel] += 1
    values, valid, kinds, reports = [], [], [], []
    for bucket, good, why in zip(buckets, eligible_buckets, bucket_reasons):
        if unplaced:
            why['unplaced_invalid_row'] = unplaced
        if not bucket:
            why['empty_unconfirmed'] = 1
        usable = not why
        valid.append(usable)
        values.append(_features(good) if usable else (None,) * 13)
        policy_kinds = []
        for p in range(3):
            observed = {r.label_kinds[p] for r in good}
            policy_kinds.append('unknown' if not usable or 'unknown' in observed
                                else 'attack' if 'attack' in observed else 'normal')
        kinds.append(tuple(policy_kinds))
        reports.append(ReleaseBucketCounts(len(bucket), len(good), len(bucket)-len(good),
            _fixed(why, REASON_CODES),
            _fixed(Counter(r.protocol_channel for r in bucket), PROTOCOL_CHANNELS),
            _fixed(Counter(r.protocol_channel for r in good), ELIGIBLE_CHANNELS),
            _label_counts(bucket), _fixed(Counter(r.label_anomaly for r in bucket), LABEL_ANOMALIES),
            any(r.definite_attack for r in bucket), any(r.attempted for r in bucket),
            sum(bool(r.unused_field_issues) for r in bucket)))
    raw = len(parsed.rows)
    # Conservation deliberately counts rows independently of usable buckets.
    if sum(raw_channels.values()) != raw or sum(good_channels.values()) != eligible:
        raise ValueError('record_conservation_failure')
    return ReleaseMinuteResult(parsed.schema_id, parsed.source_bytes, parsed.source_sha256,
        parsed.source_authentication, parsed.time_basis, G13U_FEATURE_NAMES,
        timestamps, segment_ids, roles, tuple(values), tuple(valid), tuple(kinds), tuple(reports),
        raw, eligible, raw-eligible, outside, unplaced,
        sum(n > 1 for n in frequencies.values()), _fixed(reasons, REASON_CODES),
        _fixed(raw_channels, PROTOCOL_CHANNELS), _fixed(good_channels, ELIGIBLE_CHANNELS),
        _label_counts(parsed.rows), _fixed(Counter(r.label_anomaly for r in parsed.rows), LABEL_ANOMALIES))
