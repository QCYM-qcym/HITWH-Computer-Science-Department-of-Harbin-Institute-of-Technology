"""Bounded immutable delivery of the existing checked capacity comparison.

The snapshot is a value, not an authentication credential. Constructing it
checks only field types and bounds; package admission remains in comparison.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from .candidate_capacity_contract import (
    CandidateCapacityComparisonError, validate_capacity_report, _ID,
)
from .candidate_capacity_comparison import compare_candidate_ae_capacity_runs

MAX_OUTPUT_BYTES = 1048576


@dataclass(frozen=True, slots=True)
class CandidateCapacitySnapshot:
    """Own bytes and ordered IDs only; never retain a caller's mutable report."""

    payload: bytes
    run_ids: tuple[str, ...]

    def __post_init__(self):
        if type(self.payload) is not bytes or not self.payload:
            raise CandidateCapacityComparisonError('INVALID_CAPACITY_REPORT')
        if len(self.payload) > MAX_OUTPUT_BYTES:
            raise CandidateCapacityComparisonError('RESOURCE_LIMIT')
        if (type(self.run_ids) is not tuple or not 2 <= len(self.run_ids) <= 4
                or any(type(value) is not str or _ID.fullmatch(value) is None for value in self.run_ids)
                or len(set(self.run_ids)) != len(self.run_ids)):
            raise CandidateCapacityComparisonError('INVALID_CAPACITY_REPORT')


def encode_capacity_report(report) -> bytes:
    """Validate once here, then prepare all UTF8 bytes before any output IO."""
    try:
        validate_capacity_report(report)
        payload = json.dumps(report, ensure_ascii=False, allow_nan=False,
                             sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n'
    except CandidateCapacityComparisonError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise CandidateCapacityComparisonError('INVALID_CAPACITY_REPORT') from None
    if len(payload) > MAX_OUTPUT_BYTES:
        raise CandidateCapacityComparisonError('RESOURCE_LIMIT')
    return payload


def load_verified_candidate_capacity_comparison(
    runs, record_directory, input_directory, *, source_fixture,
) -> CandidateCapacitySnapshot:
    """Admit through the existing comparison exactly once, then detach bytes.

    Upstream source reloads and the comparison's extra bound manifest read are
    unchanged; this is not a claim that each underlying file is read once.
    """
    report = compare_candidate_ae_capacity_runs(
        runs, record_directory, input_directory, source_fixture=source_fixture,
    )
    payload = encode_capacity_report(report)
    return CandidateCapacitySnapshot(payload, tuple(row['run_id'] for row in report['runs']))
