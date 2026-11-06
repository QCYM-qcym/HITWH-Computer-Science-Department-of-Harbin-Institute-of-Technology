"""Bounded readonly CLI for the separate predefined AE capacity group."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from .candidate_cli import _Parser,_SafeError
from .candidate_capacity_comparison import compare_candidate_ae_capacity_runs,CandidateCapacityComparisonError

MAX_OUTPUT_BYTES=1048576


def main(argv=None):
    parser=_Parser(description='Readonly fixed artificial AE parameter-count comparison',allow_abbrev=False)
    parser.add_argument('--records',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--source-fixture',type=Path,required=True)
    parser.add_argument('--ae-run',type=Path,action='append',default=[])
    try:
        args=parser.parse_args(argv)
        if not 2<=len(args.ae_run)<=4:raise _SafeError('INVALID_ARGUMENTS')
        report=compare_candidate_ae_capacity_runs(args.ae_run,args.records,args.inputs,source_fixture=args.source_fixture)
        payload=json.dumps(report,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')+b'\n'
        if len(payload)>MAX_OUTPUT_BYTES:raise CandidateCapacityComparisonError('RESOURCE_LIMIT')
    except _SafeError:
        code='INVALID_ARGUMENTS'
    except CandidateCapacityComparisonError as error:
        code=error.code
    except OSError:
        code='INPUT_UNAVAILABLE'
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError,RuntimeError):
        code='INVALID_CAPACITY_REPORT'
    else:
        try:
            sys.stdout.buffer.write(payload)
            sys.stdout.buffer.flush()
        except OSError:
            return 2
        return 0
    print(json.dumps({'error':code},separators=(',',':')),file=sys.stderr)
    return 2


if __name__=='__main__':raise SystemExit(main())
