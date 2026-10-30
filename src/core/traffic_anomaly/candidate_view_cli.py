"""Read-only CLI views of checked synthetic candidate artifacts.

Loaders verify stored relations without executing models; queries then consume
the checked snapshots without I/O or recalculating histories or evaluation.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from .candidate_cli import _Parser, _SafeError
from .candidate_artifacts import CandidateArtifactError, load_verified_candidate_artifacts
from .candidate_run_artifacts import CandidateRunArtifactError, load_verified_candidate_if_run
from .candidate_ae_run_artifacts import CandidateAERunArtifactError, load_verified_candidate_ae_run
from .candidate_details import CandidateDetailError, candidate_minute_detail
from .candidate_series import CandidateSeriesError, candidate_series_page

MAX_OUTPUT_BYTES = 1024 * 1024


def _error(code):
    print(json.dumps({'error': code}), file=sys.stderr)
    return 2


def main(argv=None):
    parser = _Parser(description='Read-only minute and series views of synthetic candidate runs',
                     allow_abbrev=False)
    parser.add_argument('--records', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--source-fixture', type=Path)
    family = parser.add_mutually_exclusive_group(required=True)
    family.add_argument('--if-run', type=Path)
    family.add_argument('--ae-run', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    series = commands.add_parser('series', allow_abbrev=False)
    series.add_argument('--start')
    series.add_argument('--end')
    series.add_argument('--page', type=int, default=1)
    series.add_argument('--page-size', type=int, default=100)
    detail = commands.add_parser('detail', allow_abbrev=False)
    detail.add_argument('--timestamp', required=True)
    try:
        args = parser.parse_args(argv)
        loader = load_verified_candidate_if_run if args.if_run is not None else load_verified_candidate_ae_run
        directory = args.if_run if args.if_run is not None else args.ae_run
        run = loader(directory, args.records, args.inputs, source_fixture=args.source_fixture)
        if args.command == 'series':
            result = candidate_series_page(run, start=args.start, end=args.end,
                                           page=args.page, page_size=args.page_size)
        else:
            inputs = load_verified_candidate_artifacts(args.records, args.inputs,
                                                        source_fixture=args.source_fixture)
            result = candidate_minute_detail(run, inputs, args.timestamp)
    except _SafeError:
        return _error('INVALID_ARGUMENTS')
    except (CandidateArtifactError, CandidateRunArtifactError, CandidateAERunArtifactError,
            CandidateDetailError, CandidateSeriesError) as exc:
        return _error(exc.code)
    try:
        payload = (json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        return _error('INVALID_RESULT')
    if len(payload) > MAX_OUTPUT_BYTES:
        return _error('RESOURCE_LIMIT')
    # Binary output preserves the counted UTF-8 bytes and LF on Windows too.
    sys.stdout.buffer.write(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
