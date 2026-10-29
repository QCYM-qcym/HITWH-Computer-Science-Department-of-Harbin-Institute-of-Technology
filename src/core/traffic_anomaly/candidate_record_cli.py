"""Bounded synthetic records to G13U minute fixtures; no numerical fitting."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys

from .candidate_cli import (
    EVIDENCE_KIND, MAX_FIXTURE_BYTES, TIME_BASIS, _Parser, _SafeError,
    _digest, _json_value, _number, _reject_constant, _unique_object, _write_json,
)
from .candidate_inputs import MAX_MINUTES
from .candidate_records import RECORD_PROFILE_ID, adapt_synthetic_records


POLICIES = ("P_U", "P_B", "P_A")
_TOP_FIELDS = {"schema_version", "evidence_kind", "time_basis", "minutes", "records", "epsilon"}


def _minute_fixture_bytes(value):
    """Match the exclusive writer, including its platform newline translation."""
    with io.BytesIO() as payload:
        with io.TextIOWrapper(payload, encoding="utf-8") as stream:
            json.dump(value, stream, allow_nan=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            return payload.getvalue()


def _read_fixture(path, policy):
    try:
        if path.suffix.lower() != ".json":
            raise _SafeError("INVALID_FIXTURE")
        if not path.is_file():
            raise _SafeError("INPUT_UNAVAILABLE")
        if path.stat().st_size > MAX_FIXTURE_BYTES:
            raise _SafeError("INVALID_FIXTURE")
        with path.open("rb") as stream:
            payload = stream.read(MAX_FIXTURE_BYTES + 1)
    except OSError as exc:
        raise _SafeError("INPUT_UNAVAILABLE") from exc
    if len(payload) > MAX_FIXTURE_BYTES:
        raise _SafeError("INVALID_FIXTURE")
    try:
        fixture = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        if (not isinstance(fixture, dict) or set(fixture) != _TOP_FIELDS
                or type(fixture["schema_version"]) is not int or fixture["schema_version"] != 1
                or fixture["evidence_kind"] != EVIDENCE_KIND
                or fixture["time_basis"] != TIME_BASIS
                or not _number(fixture["epsilon"], positive=True)
                or not isinstance(fixture["minutes"], list)
                or not 1 <= len(fixture["minutes"]) <= MAX_MINUTES
                or not isinstance(fixture["records"], list)
                or len(fixture["records"]) > MAX_MINUTES):
            raise ValueError("invalid_record_fixture_contract")
        adapted = adapt_synthetic_records(fixture["minutes"], fixture["records"],
                                          evidence_kind=fixture["evidence_kind"])
        minute_fixture = adapted.to_fixture(policy, epsilon=fixture["epsilon"])
        if len(_minute_fixture_bytes(minute_fixture)) > MAX_FIXTURE_BYTES:
            raise ValueError("exported_minute_fixture_too_large")
        label_audit = _json_value({
            "schema_version": 1, "profile_id": RECORD_PROFILE_ID,
            "evidence_kind": EVIDENCE_KIND, "time_basis": TIME_BASIS,
            "selected_policy": policy, "policy_status": "AUDIT_ONLY",
            "labels": adapted.labels,
            "normal_candidates": adapted.normal_candidates,
            "audit": adapted.audit,
        })
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise _SafeError("INVALID_FIXTURE") from exc
    return payload, fixture, minute_fixture, label_audit


def _run(fixture_path, policy, output):
    payload, fixture, minute_fixture, label_audit = _read_fixture(fixture_path, policy)
    configuration = {
        "profile_id": RECORD_PROFILE_ID,
        "evidence_kind": EVIDENCE_KIND, "time_basis": TIME_BASIS,
        "selected_policy": policy, "policy_status": "AUDIT_ONLY",
        "epsilon": fixture["epsilon"],
        "completion_time": "start_plus_duration_us_proxy",
        "max_minutes": MAX_MINUTES, "max_records": MAX_MINUTES,
        "max_fixture_bytes": MAX_FIXTURE_BYTES,
    }
    configuration_bytes = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise _SafeError("OUTPUT_EXISTS") from exc
    except OSError as exc:
        raise _SafeError("OUTPUT_ERROR") from exc
    try:
        _write_json(output / "minute-fixture.json", minute_fixture)
        _write_json(output / "label-audit.json", label_audit)
        artifacts = {name: _digest((output / name).read_bytes())
                     for name in ("minute-fixture.json", "label-audit.json")}
        # Completion is written only after both independently inspectable artifacts.
        _write_json(output / "manifest.json", {
            "schema_version": 1, "profile_id": RECORD_PROFILE_ID,
            "evidence_kind": EVIDENCE_KIND, "time_basis": TIME_BASIS,
            "status": "COMPLETE", "selected_policy": policy, "policy_status": "AUDIT_ONLY",
            "fixture": _digest(payload), "configuration": configuration,
            "configuration_sha256": hashlib.sha256(configuration_bytes).hexdigest(),
            "artifacts": artifacts,
        })
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        raise _SafeError("OUTPUT_ERROR") from exc


def main(argv=None):
    parser = _Parser(description="Synthetic-only G13U record adaptation with an explicit audit policy")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--policy", choices=POLICIES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        _run(args.fixture, args.policy, args.output)
    except _SafeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"evidence_kind": EVIDENCE_KIND, "status": "COMPLETE",
                      "selected_policy": args.policy, "policy_status": "AUDIT_ONLY"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
