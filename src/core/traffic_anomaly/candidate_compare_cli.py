"""Read-only comparison context for verified synthetic IF/AE saved runs."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from .candidate_cli import _Parser, _SafeError
from .candidate_comparison import CandidateComparisonError, CandidateComparisonRun, compare_candidate_runs


def main(argv=None):
    parser = _Parser(description="Read-only shared-data qualification comparison of synthetic saved runs",
                     allow_abbrev=False)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--source-fixture", type=Path)
    parser.add_argument("--if-run", dest="if_runs", type=Path, action="append", default=[])
    parser.add_argument("--ae-run", dest="ae_runs", type=Path, action="append", default=[])
    try:
        args = parser.parse_args(argv)
        if (len(args.if_runs) > 1 or len(args.ae_runs) > 3
                or not 2 <= len(args.if_runs) + len(args.ae_runs) <= 4):
            raise _SafeError("INVALID_ARGUMENTS")
        runs = [CandidateComparisonRun("iforest", path) for path in args.if_runs]
        runs.extend(CandidateComparisonRun("autoencoder", path) for path in args.ae_runs)
        report = compare_candidate_runs(runs, args.records, args.inputs, source_fixture=args.source_fixture)
    except _SafeError:
        print(json.dumps({"error": "INVALID_ARGUMENTS"}), file=sys.stderr)
        return 2
    except CandidateComparisonError as exc:
        print(json.dumps({"error": exc.code}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
