"""Bounded prepare, inspect and saved-parameter replay of release inputs."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import math
import os
from pathlib import Path
import sys

from .release_input_package import load_release_input_package,save_release_input_package
from .release_inputs import (ReleaseInputPreparationError,ReleasePreparationConfig,
    prepare_release_inputs,verify_release_input_derivation)
from .release_minute_contract import ReleaseMinutePackageError
from .release_minute_package import load_release_minute_package

_PROG='python -m traffic_anomaly.release_input_cli'
_HELP=(
    'usage: python -m traffic_anomaly.release_input_cli [-h] {prepare,inspect,verify} ...\n'
    '\ncommands:\n'
    '  prepare --raw-package ABS_DIR --output NEW_ABS_DIR --epsilon POSITIVE_FLOAT --audit-fit-policy {P_U,P_B,P_A}\n'
    '  inspect --prepared-package ABS_DIR\n'
    '  verify --raw-package ABS_DIR --prepared-package ABS_DIR\n'
    '\nPrepare fits preprocessing parameters; inspect checks saved consistency; verify replays saved parameters.\n'
    '  -h, --help   show this fixed usage\n'
).encode('utf-8')
_OUTPUT_LIMIT=65536
_RELEASE_CODES=frozenset(('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE','OUTPUT_EXISTS',
    'PACKAGE_CHANGED','OUTPUT_ERROR','INVALID_PREPARATION_CONFIG','UPSTREAM_IDENTITY_MISMATCH',
    'NO_TRAINING_NORMAL_MINUTES','NONFINITE_FIT_STATE','DERIVATION_MISMATCH'))
_QUALIFICATION_NAMES=('train_full_history_normal','calibration_full_history_normal',
    'validation_current_normal','validation_current_attack','validation_current_unknown',
    'test_current_normal','test_current_attack','test_current_unknown')
_CHECK_NAMES=('status','scope','byte_integrity','structure','upstream_replay',
    'transform_history_replay','fit_parameters')


class _ArgumentsError(ValueError):pass


class _HelpRequested(Exception):pass


class _CLIError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)


class _Parser(argparse.ArgumentParser):
    def __init__(self,*args,**kwargs):
        kwargs.update(allow_abbrev=False,add_help=False)
        super().__init__(*args,**kwargs)
        self.add_argument('-h','--help',action='help')

    def error(self,message):raise _ArgumentsError()

    def exit(self,status=0,message=None):
        if status==0:raise _HelpRequested()
        raise _ArgumentsError()

    def print_help(self,file=None):raise _HelpRequested()


def _positive_epsilon(value):
    try:result=float(value)
    except (ValueError,OverflowError):raise _ArgumentsError() from None
    if not math.isfinite(result) or result<=0:raise _ArgumentsError()
    return result


def _arguments(argv):
    if argv is None:argv=sys.argv[1:]
    if isinstance(argv,(str,bytes)) or not isinstance(argv,Sequence):raise _ArgumentsError()
    values=list(argv)
    if any(type(value) is not str for value in values):raise _ArgumentsError()
    seen=set()
    for value in values:
        if value.startswith('@') or (value.startswith('--') and '=' in value and value.split('=',1)[1].startswith('@')):raise _ArgumentsError()
        if value=='-h':option='--help'
        elif value.startswith('--'):option=value.split('=',1)[0]
        else:continue
        if option in seen:raise _ArgumentsError()
        seen.add(option)
    parser=_Parser(prog=_PROG)
    commands=parser.add_subparsers(dest='command',required=True)
    inspect=commands.add_parser('inspect')
    inspect.add_argument('--prepared-package',required=True)
    prepare=commands.add_parser('prepare')
    prepare.add_argument('--raw-package',required=True)
    prepare.add_argument('--output',required=True)
    prepare.add_argument('--epsilon',required=True,type=_positive_epsilon)
    prepare.add_argument('--audit-fit-policy',required=True,choices=('P_U','P_B','P_A'))
    verify=commands.add_parser('verify')
    verify.add_argument('--raw-package',required=True)
    verify.add_argument('--prepared-package',required=True)
    return parser.parse_args(values)


def _identity(value):
    return {name:getattr(value,name) for name in ('profile_id','context_sha256','manifest_sha256','manifest_byte_count')}


def _summary(saved) -> dict:
    """Project only the documented saved fields; count masks without replay."""
    context=saved.context;config=context.configuration;minutes=saved.minutes
    state=saved.preprocessing
    return dict(
        identity=_identity(saved.identity),upstream_identity=_identity(context.upstream),
        source_authentication=context.source_authentication,time_basis=context.time_basis,
        configuration=dict(schema_version=config.schema_version,numeric_rules_id=config.numeric_rules_id,
            windows=list(config.windows),fit_window=config.fit_window,epsilon=config.epsilon,
            audit_fit_policy=config.audit_fit_policy,policy_status=config.policy_status,
            feature_count=len(config.feature_names)),
        configuration_sha256=context.configuration_sha256,
        minute_counts=dict(total=context.minute_count,raw_valid=sum(minutes.raw_valid),
            prepared_valid=sum(minutes.prepared_valid),common_valid=sum(minutes.common_valid),
            history_h15_valid=sum(minutes.histories[0].valid),history_h30_valid=sum(minutes.histories[1].valid)),
        fit=dict(count=state.n_samples_seen,mask_sha256=state.fit_mask_sha256,rows_sha256=state.fit_rows_sha256),
        qualification_counts={q.policy:{name:sum(getattr(q,name)) for name in _QUALIFICATION_NAMES}
                              for q in saved.labels.qualification_masks},
        package_checks={name:getattr(saved.load_report,name) for name in _CHECK_NAMES},
    )


def _replay(report):
    """Project the actual verifier return; retain its NOT_REESTIMATED boundary."""
    result={name:getattr(report,name) for name in ('profile_id','status','scope','minute_count','fit_count')}
    result.update(upstream_identity=_identity(report.upstream_identity),input_identity=_identity(report.input_identity),
        checks={name:getattr(report.checks,name) for name in ('byte_identity','upstream_fields','fit_selection',
            'saved_transform','history','labels_and_masks','fit_parameters','source_authentication')},
        numerical_tolerance={name:getattr(report.numerical_tolerance,name) for name in ('rtol','atol','reference')})
    return result


def _json_bytes(value: dict) -> bytes:
    try:
        payload=(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
    except Exception:raise _CLIError('INVALID_RESULT') from None
    if len(payload)>_OUTPUT_LIMIT:raise _CLIError('RESOURCE_LIMIT')
    return payload


def _write(stream,payload):
    try:
        binary=stream.buffer
        written=binary.write(payload)
        if type(written) is not int or written!=len(payload):raise _CLIError('OUTPUT_ERROR')
        binary.flush()
    except KeyboardInterrupt:raise
    except Exception:raise _CLIError('OUTPUT_ERROR') from None


def _error(code):
    try:_write(sys.stderr,_json_bytes({'error':code}))
    except (Exception,KeyboardInterrupt):pass
    return 2


def main(argv: Sequence[str]|None=None) -> int:
    try:
        args=_arguments(argv)
        if args.command=='prepare':
            upstream=load_release_minute_package(Path(args.raw_package))
            config=ReleasePreparationConfig(schema_version=1,numeric_rules_id='c17-release-log1p-mad-input-rules-v1',
                feature_names=upstream.minutes.feature_names,windows=(15,30),fit_window=30,
                epsilon=args.epsilon,audit_fit_policy=args.audit_fit_policy,policy_status='AUDIT_ONLY')
            saved=prepare_release_inputs(upstream,config)
            payload=_json_bytes(dict(version=1,command='prepare',status='SAVED',summary=_summary(saved),replay=None))
            identity=save_release_input_package(saved,Path(args.output))
            if type(identity) is not type(saved.identity) or identity!=saved.identity:raise _CLIError('INVALID_RESULT')
        else:
            saved=load_release_input_package(Path(args.prepared_package))
            if args.command=='verify':
                upstream=load_release_minute_package(Path(args.raw_package))
                report=verify_release_input_derivation(upstream,saved)
                payload=_json_bytes(dict(version=1,command='verify',status='MATCHED',summary=_summary(saved),replay=_replay(report)))
            else:
                payload=_json_bytes(dict(version=1,command='inspect',status='INTERNAL_CONSISTENCY_CHECKED',summary=_summary(saved),replay=None))
    except _HelpRequested:payload=_HELP
    except _ArgumentsError:return _error('INVALID_ARGUMENTS')
    except _CLIError as error:return _error(error.code)
    except (ReleaseInputPreparationError,ReleaseMinutePackageError) as error:
        code=getattr(error,'code',None)
        return _error(code if type(code) is str and code in _RELEASE_CODES else 'INTERNAL_ERROR')
    except KeyboardInterrupt:return _error('INTERRUPTED')
    except Exception:return _error('INTERNAL_ERROR')
    try:_write(sys.stdout,payload)
    except KeyboardInterrupt:return _error('INTERRUPTED')
    except _CLIError:return _error('OUTPUT_ERROR')
    return 0


def _cli_entrypoint():
    """Own failed process streams, leaving the callable main() host untouched.

    A failed BufferedWriter.flush can retain bytes. Redirect descriptors before
    Python's final flush so it cannot replace exit2 with exit120 or add details.
    The already-flushed safe stderr message is preserved. This runs only from
    the module entry, never from main(); successful output is unchanged.
    """
    status=main()
    if status!=0:
        for stream in (sys.stdout,sys.stderr):
            try:
                target=stream.fileno()
                null_fd=os.open(os.devnull,os.O_WRONLY)
                try:os.dup2(null_fd,target)
                finally:
                    if null_fd!=target:os.close(null_fd)
            except (AttributeError,OSError,ValueError):
                # Missing/unusable descriptors cannot be repaired here. Never
                # print another error, close a host object, or skip finally.
                pass
    return status


if __name__=='__main__':
    raise SystemExit(_cli_entrypoint())
