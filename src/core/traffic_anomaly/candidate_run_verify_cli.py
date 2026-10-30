"""Read-only stored-score consistency checks without model deserialization."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from .candidate_cli import _Parser, _SafeError
from .candidate_run_artifacts import CandidateRunArtifactError, verify_candidate_if_run


def main(argv=None):
    parser = _Parser(description="Read-only synthetic IF artifact and stored-score consistency verification")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--source-fixture", type=Path)
    try:
        args = parser.parse_args(argv)
        report = verify_candidate_if_run(args.run, args.records, args.inputs, source_fixture=args.source_fixture)
    except _SafeError:
        print(json.dumps({"error": "INVALID_ARGUMENTS"}), file=sys.stderr)
        return 2
    except CandidateRunArtifactError as exc:
        print(json.dumps({"error": exc.code}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
