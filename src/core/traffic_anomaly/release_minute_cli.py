"""Bounded explicit raw-minute aggregation and fixed package persistence."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import sys


_SPEC_LIMIT=65536
_OUTPUT_LIMIT=65536
_BUDGET_LIMITS={'max_total_source_bytes':2147483648,'max_rows':2500000,
    'max_database_bytes':2147483648,'max_elapsed_seconds':1800,'max_minutes':10000}
_HELP=(
    'usage: python -m traffic_anomaly.release_minute_cli --spec ABS_JSON --scratch NEW_ABS_DIR --output NEW_ABS_DIR\n'
    'Aggregate explicit sources once and save a raw-minute package.\n'
    '-h, --help  show this fixed usage (use alone)\n'
).encode('utf-8')
_RAW_CODES=frozenset(('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE',
    'OUTPUT_EXISTS','PACKAGE_CHANGED','OUTPUT_ERROR'))
# Exact vocabulary from the pinned error-table specification, independently held.
_CORE_CODES=frozenset(('invalid_budget','invalid_sources','invalid_source','invalid_source_path','duplicate_source',
    'source_size_mismatch','source_hash_mismatch','source_changed','source_io_error','source_close_error',
    'input_byte_cap','max_rows','database_byte_cap','elapsed_time_cap','scratch_cleanup_failed',
    'scratch_ownership_changed','scratch_io_error','invalid_scratch_directory','invalid_disk_budget',
    'integer_string_limit_environment','csv_field_limit_environment','logical_record_char_cap','invalid_utf8',
    'invalid_csv','missing_header','header_mismatch','ragged_row','field_nul','max_field_chars','max_label_values',
    'max_category_values','max_protocol_values','integer_expansion_limit','duration_cap','completion_overflow',
    'invalid_segments','invalid_max_minutes','minute_cap','sqlite_environment','sqlite_error','sqlite_query_plan',
    'sqlite_close_error','database_size_mismatch','record_conservation_failure','quantile_consistency_failure',
    'numeric_materialization_overflow','reader_state','invalid_deadline','incomplete_read'))


class _CLIError(ValueError):
    def __init__(self,code: str):
        self.code=code
        super().__init__(code)


class _Parser(argparse.ArgumentParser):
    def error(self,message):raise _CLIError('INVALID_ARGUMENTS')
    def exit(self,status=0,message=None):raise _CLIError('INVALID_ARGUMENTS')


def _parse_cli(argv: Sequence[str] | None) -> argparse.Namespace | None:
    if argv is None:argv=sys.argv[1:]
    if isinstance(argv,(str,bytes)) or not isinstance(argv,Sequence):raise _CLIError('INVALID_ARGUMENTS')
    values=list(argv)
    if any(type(value) is not str for value in values):raise _CLIError('INVALID_ARGUMENTS')
    if values in (['-h'],['--help']):return None
    seen=set()
    for value in values:
        if value in ('-h','--help') or value.startswith('@'):
            raise _CLIError('INVALID_ARGUMENTS')
        if value.startswith('--'):
            option,separator,argument=value.partition('=')
            if option in seen or separator and argument.startswith('@'):
                raise _CLIError('INVALID_ARGUMENTS')
            seen.add(option)
    parser=_Parser(prog='python -m traffic_anomaly.release_minute_cli',allow_abbrev=False,add_help=False)
    for name in ('spec','scratch','output'):parser.add_argument('--'+name,required=True)
    return parser.parse_args(values)


@dataclass(frozen=True)
class _Request:
    sources: tuple
    segments: tuple
    budget: object
    spec_path: Path
    scratch: Path
    output: Path
    observations: tuple


def _lexical(value,code):
    if type(value) is not str or not value or '\0' in value or value.startswith(('\\\\','//')):
        raise _CLIError(code)
    path=Path(value)
    if not path.is_absolute() or '..' in path.parts:raise _CLIError(code)
    if os.name=='nt' and (len(path.drive)!=2 or path.drive[1]!=':'
            or any(':' in part or os.path.isreserved(part) for part in path.parts[1:])):
        raise _CLIError(code)
    return path


def _signature(info,kind,code):
    if (stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400
            or not (stat.S_ISDIR(info.st_mode) if kind=='directory' else stat.S_ISREG(info.st_mode))):
        raise _CLIError(code)
    identity=(info.st_dev,info.st_ino,info.st_mode,getattr(info,'st_file_attributes',0))
    return identity if kind=='directory' else identity+(info.st_size,info.st_mtime_ns,info.st_nlink)


def _record(path,kind,signature,observations,code):
    key=(path,kind)
    if key in observations and observations[key]!=signature:raise _CLIError(code)
    observations[key]=signature


def _observe(path,kind,observations,code):
    try:signature=_signature(path.lstat(),kind,code)
    except (OSError,ValueError,UnicodeError) as error:
        if isinstance(error,_CLIError):raise
        raise _CLIError(code) from None
    _record(path,kind,signature,observations,code)
    return signature


def _file(path,observations,code):
    for parent in reversed(path.parents):_observe(parent,'directory',observations,code)
    return _observe(path,'file',observations,code)


def _read_spec(path,observations):
    before=_file(path,observations,'INVALID_SPEC_PATH')
    if before[4]>_SPEC_LIMIT:raise _CLIError('RESOURCE_LIMIT')
    try:
        with path.open('rb') as stream:
            if _signature(os.fstat(stream.fileno()),'file','SPEC_CHANGED')!=before:
                raise _CLIError('SPEC_CHANGED')
            payload=stream.read(_SPEC_LIMIT+1)
            if _signature(os.fstat(stream.fileno()),'file','SPEC_CHANGED')!=before:
                raise _CLIError('SPEC_CHANGED')
            if type(payload) is not bytes or len(payload)!=before[4]:raise _CLIError('SPEC_CHANGED')
            if len(payload)>_SPEC_LIMIT:raise _CLIError('RESOURCE_LIMIT')
    except _CLIError:raise
    except (OSError,ValueError,AttributeError):raise _CLIError('INPUT_UNAVAILABLE') from None
    if _file(path,observations,'SPEC_CHANGED')!=before:raise _CLIError('SPEC_CHANGED')
    return payload


def _keys(value,names):
    if type(value) is not dict or set(value)!=set(names):raise _CLIError('INVALID_SPEC')


def _uint(value,maximum):
    if type(value) is not int or not 1<=value<=maximum:raise _CLIError('INVALID_SPEC')


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise _CLIError('INVALID_SPEC')
        result[key]=value
    return result


def _integer_token(value):
    if re.fullmatch('[0-9]{1,10}',value) is None:raise _CLIError('INVALID_SPEC')
    return int(value)


def _reject_number(value):raise _CLIError('INVALID_SPEC')


def _time(value):
    if type(value) is not str or re.fullmatch('[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00',value) is None:
        raise _CLIError('INVALID_SPEC')
    try:return datetime.fromisoformat(value)
    except ValueError:raise _CLIError('INVALID_SPEC') from None


def _spec(payload):
    try:
        value=json.loads(payload.decode('utf-8'),object_pairs_hook=_pairs,
            parse_int=_integer_token,parse_float=_reject_number,parse_constant=_reject_number)
    except _CLIError:raise
    except (ValueError,UnicodeError,RecursionError):raise _CLIError('INVALID_SPEC') from None
    _keys(value,('version','sources','segments','budget'))
    if type(value['version']) is not int or value['version']!=1:raise _CLIError('INVALID_SPEC')
    sources=value['sources'];segments=value['segments'];budget=value['budget']
    if type(sources) is not list or not 1<=len(sources)<=5:raise _CLIError('INVALID_SPEC')
    if type(segments) is not list or not 1<=len(segments)<=7:raise _CLIError('INVALID_SPEC')
    _keys(budget,_BUDGET_LIMITS)
    for key,maximum in _BUDGET_LIMITS.items():_uint(budget[key],maximum)
    if budget['max_database_bytes']<65536 or budget['max_database_bytes']%4096:
        raise _CLIError('INVALID_SPEC')
    for source in sources:
        _keys(source,('path','bytes','sha256'))
        if type(source['path']) is not str or not source['path']:raise _CLIError('INVALID_SPEC')
        _uint(source['bytes'],2147483648)
        if type(source['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',source['sha256']) is None:
            raise _CLIError('INVALID_SPEC')
    parsed_segments=[]
    for segment in segments:
        _keys(segment,('id','role','start','end'))
        name=segment['id']
        if (type(name) is not str or not 1<=len(name)<=128
                or any(ord(c)<32 or ord(c)==127 or 0xd800<=ord(c)<=0xdfff for c in name)
                or type(segment['role']) is not str or segment['role'] not in ('train','validation','calibration','test')):
            raise _CLIError('INVALID_SPEC')
        parsed_segments.append((name,segment['role'],_time(segment['start']),_time(segment['end'])))
    if sum(s['bytes'] for s in sources)>budget['max_total_source_bytes']:raise _CLIError('RESOURCE_LIMIT')
    return sources,parsed_segments,budget


def _target_probe(path,observations,code):
    """Observe the existing parent chain; retain a missing suffix for alias layout."""
    chain=[];last=None
    for parent in reversed(path.parents):
        try:info=parent.lstat()
        except FileNotFoundError:
            if last is None:raise _CLIError(code) from None
            suffix=tuple(os.path.normcase(p) for p in path.relative_to(last).parts)
            return chain[-1],suffix,False,False,None,tuple(chain)
        except (OSError,ValueError):raise _CLIError(code) from None
        signature=_signature(info,'directory',code)
        _record(parent,'directory',signature,observations,code)
        chain.append(signature);last=parent
    if not chain or not path.name:raise _CLIError(code)
    try:info=path.lstat()
    except FileNotFoundError:exists=False;identity=None
    except (OSError,ValueError):raise _CLIError(code) from None
    else:
        kind='directory' if stat.S_ISDIR(info.st_mode) else 'file'
        identity=_signature(info,kind,code)[:4];exists=True
    return chain[-1],(os.path.normcase(path.name),),True,exists,identity,tuple(chain)


def _layout(scratch,output,probes,files,observations):
    if scratch.is_relative_to(output) or output.is_relative_to(scratch):raise _CLIError('INVALID_PATH_LAYOUT')
    a,b=probes
    if a[0]==b[0] and (a[1][:len(b[1])]==b[1] or b[1][:len(a[1])]==a[1]):
        raise _CLIError('INVALID_PATH_LAYOUT')
    if a[4] is not None and a[4] in b[5] or b[4] is not None and b[4] in a[5]:
        raise _CLIError('INVALID_PATH_LAYOUT')
    for target,probe in zip((scratch,output),probes):
        for path in files:
            if path.is_relative_to(target):raise _CLIError('INVALID_PATH_LAYOUT')
            if probe[4] is not None and probe[4][:2]==observations[(path,'file')][:2]:
                raise _CLIError('INVALID_PATH_LAYOUT')


def _targets(scratch,output,files,observations):
    probes=(_target_probe(scratch,observations,'INVALID_SCRATCH_DIRECTORY'),
        _target_probe(output,observations,'INVALID_PACKAGE_PATH'))
    _layout(scratch,output,probes,files,observations)
    for probe,code in zip(probes,('INVALID_SCRATCH_DIRECTORY','INVALID_PACKAGE_PATH')):
        if not probe[2]:raise _CLIError(code)
    if probes[0][3]:raise _CLIError('INVALID_SCRATCH_DIRECTORY')
    if probes[1][3]:raise _CLIError('OUTPUT_EXISTS')


def _preflight(spec_arg: str,scratch_arg: str,output_arg: str) -> _Request:
    observations={}
    spec_path=_lexical(spec_arg,'INVALID_SPEC_PATH')
    source_values,segment_values,budget_values=_spec(_read_spec(spec_path,observations))
    scratch=_lexical(scratch_arg,'INVALID_SCRATCH_DIRECTORY')
    output=_lexical(output_arg,'INVALID_PACKAGE_PATH')
    paths=[];identities={observations[(spec_path,'file')][:2]}
    for source in source_values:
        path=_lexical(source['path'],'INVALID_SOURCE_PATH')
        signature=_file(path,observations,'INVALID_SOURCE_PATH')
        if signature[:2] in identities:raise _CLIError('DUPLICATE_SOURCE')
        identities.add(signature[:2])
        if signature[4]!=source['bytes']:raise _CLIError('SOURCE_SIZE_MISMATCH')
        paths.append(path)
    _targets(scratch,output,(spec_path,*paths),observations)
    # Admission imports types/geometry only; it never opens CSV or starts work.
    from ._release_file_reader import ReleaseFileSource
    from ._release_minutes import ReleaseSegment,_axis
    from ._release_disk import ReleaseDiskBudget
    sources=tuple(ReleaseFileSource(path,s['bytes'],s['sha256']) for path,s in zip(paths,source_values))
    segments=tuple(ReleaseSegment(*values) for values in segment_values)
    try:_axis(segments,budget_values['max_minutes'])
    except ValueError as error:
        code='RESOURCE_LIMIT' if type(error) is ValueError and error.args==('minute_cap',) else 'INVALID_SPEC'
        raise _CLIError(code) from None
    budget=ReleaseDiskBudget(**{key:budget_values[key] for key in _BUDGET_LIMITS if key!='max_minutes'})
    return _Request(sources,segments,budget,spec_path,scratch,output,
        tuple((path,kind,signature) for (path,kind),signature in observations.items()))


def _recheck_request(request: _Request) -> None:
    observations={}
    for path,kind,expected in request.observations:
        if path==request.spec_path:code='SPEC_CHANGED'
        elif kind=='file':code='INPUT_UNAVAILABLE'
        else:code='INVALID_PATH_LAYOUT'
        if _observe(path,kind,observations,code)!=expected:raise _CLIError(code)
    _targets(request.scratch,request.output,(request.spec_path,*(s.path for s in request.sources)),observations)


def _summary(result,identity) -> dict:
    from .release_minute_contract import ReleaseMinutePackageIdentity
    try:
        if type(identity) is not ReleaseMinutePackageIdentity:raise ValueError()
        identity.__post_init__()
    except Exception:raise _CLIError('INVALID_RESULT') from None
    minutes=result.minutes;resources=result.resources;receipts=resources.reader_receipts
    if (type(minutes.source_authentication) is not str or minutes.source_authentication!='NOT_AUTHENTICATED'
            or type(minutes.time_basis) is not str or minutes.time_basis!='SOURCE_WALL_CLOCK_COMPLETION_PROXY'):
        raise _CLIError('INVALID_RESULT')
    return dict(version=1,command='aggregate',status='SAVED',
        identity={key:getattr(identity,key) for key in ('profile_id','context_sha256','manifest_sha256','manifest_byte_count')},
        source_authentication=minutes.source_authentication,time_basis=minutes.time_basis,
        source_identities=[dict(ordinal=s.source_ordinal,byte_count=s.source_bytes,sha256=s.source_sha256) for s in receipts.sources],
        counts=dict(source_count=len(receipts.sources),minute_count=len(minutes.timestamps),
            source_valid_minutes=sum(minutes.source_valid),
            **{key:getattr(minutes,key) for key in ('raw_records','eligible_records','excluded_records','outside_records','unplaced_invalid_rows')}),
        resources={**{key:getattr(receipts,key) for key in ('source_content_open_count','source_bytes_consumed','logical_rows')},
            **{key:getattr(resources,key) for key in ('database_bytes_at_close','observed_database_high_water_bytes','cleanup_status')}},
    )


def _json_bytes(value):
    try:payload=(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
    except Exception:raise _CLIError('INVALID_RESULT') from None
    if len(payload)>_OUTPUT_LIMIT:raise _CLIError('RESOURCE_LIMIT')
    return payload


def _write_stream(stream,payload):
    try:
        written=stream.buffer.write(payload)
        if type(written) is not int or written!=len(payload):raise _CLIError('OUTPUT_ERROR')
        stream.buffer.flush()
    except KeyboardInterrupt:raise
    except Exception:raise _CLIError('OUTPUT_ERROR') from None


def _write_stdout(payload: bytes) -> None:
    _write_stream(sys.stdout,payload)


def _error(code,cleanup_failed=False):
    message={'error':code}
    if cleanup_failed is True:message['cleanup_failed']=True
    try:_write_stream(sys.stderr,_json_bytes(message))
    except (Exception,KeyboardInterrupt):pass
    return 2


def _safe_code(error):
    if isinstance(error,_CLIError):return error.code
    if isinstance(error,KeyboardInterrupt):return 'INTERRUPTED'
    from .release_minute_contract import ReleaseMinutePackageError
    if isinstance(error,ReleaseMinutePackageError):
        code=getattr(error,'code',None)
        return code if type(code) is str and code in _RAW_CODES else 'INTERNAL_ERROR'
    if type(error) is ValueError and len(error.args)==1:
        code=error.args[0]
        if type(code) is str and code in _CORE_CODES:return code.upper()
    return 'INTERNAL_ERROR'


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args=_parse_cli(argv)
        if args is None:payload=_HELP
        else:
            request=_preflight(args.spec,args.scratch,args.output)
            _recheck_request(request)
            from ._release_disk import _aggregate_release_files
            from .release_minute_package import save_release_minute_package
            result=_aggregate_release_files(request.sources,request.segments,
                scratch_directory=request.scratch,budget=request.budget)
            if type(result.resources.cleanup_status) is not str or result.resources.cleanup_status!='CLEANED':
                raise _CLIError('SCRATCH_CLEANUP_FAILED')
            try:request.scratch.lstat()
            except FileNotFoundError:pass
            else:raise _CLIError('SCRATCH_CLEANUP_FAILED')
            _recheck_request(request)
            identity=save_release_minute_package(result.minutes,request.segments,request.output)
            payload=_json_bytes(_summary(result,identity))
    except (Exception,KeyboardInterrupt,SystemExit) as error:
        # Invalid/help parsing has no reason to import product modules.
        code=error.code if isinstance(error,_CLIError) else _safe_code(error)
        return _error(code,getattr(error,'cleanup_failed',False) is True)
    try:_write_stdout(payload)
    except KeyboardInterrupt:return _error('INTERRUPTED')
    except Exception:return _error('OUTPUT_ERROR')
    return 0


def _cli_entrypoint():
    """Seal failed module-owned descriptors before interpreter final flushing.

    main() keeps host stream ownership; successful module output is untouched.
    Unusable descriptors/resources are best effort, never extra diagnostics.
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
            except (AttributeError,OSError,ValueError):pass
    return status


if __name__=='__main__':
    raise SystemExit(_cli_entrypoint())
