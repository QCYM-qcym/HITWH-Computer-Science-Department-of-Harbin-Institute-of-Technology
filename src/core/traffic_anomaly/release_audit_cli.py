"""Bounded offline release audit summaries, never candidate/model artifacts.

Byte identities are consistency checks, not authentication or data-use approval.
Only successful frozen disk results are projected; failed output is not resumed.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import stat
import sys

from ._release_disk import ReleaseDiskBudget, _aggregate_release_files
from ._release_file_reader import ReleaseFileSource
from ._release_minutes import ReleaseSegment, REASON_CODES, _axis

_CAP = 65536
_LIMITS = dict(max_total_source_bytes=8*1024*1024, max_rows=10000,
               max_database_bytes=32*1024*1024, max_elapsed_seconds=30, max_minutes=10000)
_KINDS = ('normal', 'attack', 'unknown')
_POLICIES = ('P_U', 'P_B', 'P_A')
# Exact, finite mapping: neither prefixes nor exception text are echoed.
_KNOWN = {
    code: code.upper() for code in (
        'invalid_budget', 'invalid_sources', 'invalid_source', 'invalid_source_path', 'duplicate_source',
        'source_size_mismatch', 'source_hash_mismatch', 'source_changed', 'source_io_error',
        'source_close_error', 'input_byte_cap', 'max_rows', 'database_byte_cap',
        'elapsed_time_cap', 'scratch_cleanup_failed', 'scratch_ownership_changed',
        'scratch_io_error', 'invalid_scratch_directory', 'invalid_disk_budget',
        'integer_string_limit_environment', 'csv_field_limit_environment',
        'logical_record_char_cap', 'invalid_utf8', 'invalid_csv', 'missing_header',
        'header_mismatch', 'ragged_row', 'field_nul', 'max_field_chars',
        'max_label_values', 'max_category_values', 'max_protocol_values',
        'integer_expansion_limit', 'duration_cap', 'completion_overflow',
        'invalid_segments', 'invalid_max_minutes', 'minute_cap',
        'sqlite_environment', 'sqlite_error', 'sqlite_query_plan', 'sqlite_close_error',
        'database_size_mismatch', 'record_conservation_failure', 'quantile_consistency_failure',
        'numeric_materialization_overflow', 'reader_state', 'invalid_deadline', 'incomplete_read')}


class _AuditError(ValueError):
    pass


def _fail(code):
    raise _AuditError(code)


def _ordinary(info, directory):
    return (not stat.S_ISLNK(info.st_mode)
        and not getattr(info, 'st_file_attributes', 0) & 0x400
        and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)))


def _signature(info, *, directory=False):
    base = (info.st_dev, info.st_ino, info.st_mode, getattr(info, 'st_file_attributes', 0))
    return base if directory else base+(info.st_size, info.st_mtime_ns)


def _ancestors(path, code):
    for parent in reversed(path.parents):
        if not _ordinary(parent.lstat(), True):
            _fail(code)


def _file(path, code):
    _ancestors(path, code)
    info = path.lstat()
    if not _ordinary(info, False):
        _fail(code)
    return _signature(info)


def _lexical(value, *, absolute=False):
    if type(value) is not str or not value or '\x00' in value:
        _fail('INVALID_PATH')
    drive, tail = ntpath.splitdrive(value)
    if (value.startswith(('\\', '//')) or ':' in tail or
            drive and not tail.startswith(('\\', '/'))):
        _fail('INVALID_PATH')
    path = Path(value)
    if '..' in re.split(r'[\\/]', value) or path.root and not path.is_absolute():
        _fail('INVALID_PATH')
    if absolute and not path.is_absolute():
        _fail('INVALID_PATH')
    return path


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('INVALID_SPEC')
        result[key] = value
    return result


def _reject(value):
    _fail('INVALID_SPEC')


def _decode(payload):
    return json.loads(payload.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_reject)


def _read_spec(path):
    before = _file(path, 'INVALID_SPEC_PATH')
    if before[-2] > _CAP:
        _fail('INVALID_SPEC')
    with path.open('rb') as stream:
        if _signature(os.fstat(stream.fileno())) != before:
            _fail('SPEC_CHANGED')
        payload = stream.read(_CAP+1)
        if _signature(os.fstat(stream.fileno())) != before:
            _fail('SPEC_CHANGED')
    if _file(path, 'INVALID_SPEC_PATH') != before:
        _fail('SPEC_CHANGED')
    if len(payload) > _CAP:
        _fail('INVALID_SPEC')
    try:
        data = _decode(payload)
    except (UnicodeError, ValueError, RecursionError):
        _fail('INVALID_SPEC')
    return data, before


def _fields(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        _fail('INVALID_SPEC')


def _stamp(value):
    if type(value) is not str or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::00)?', value):
        _fail('INVALID_SPEC')
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        _fail('INVALID_SPEC')


def _output_preflight(path):
    _ancestors(path, 'INVALID_OUTPUT')
    try:
        path.lstat()
    except FileNotFoundError:
        return
    _fail('OUTPUT_EXISTS')


def _preflight(spec_arg, output_arg):
    spec_path = _lexical(spec_arg).absolute()
    data, spec_identity = _read_spec(spec_path)
    _fields(data, ('version', 'sources', 'segments', 'budget'))
    if type(data['version']) is not int or data['version'] != 1:
        _fail('INVALID_SPEC')
    limits = data['budget']
    _fields(limits, _LIMITS)
    if any(type(limits[k]) is not int or not 0 < limits[k] <= maximum for k, maximum in _LIMITS.items()):
        _fail('INVALID_SPEC')
    if limits['max_database_bytes'] < 65536 or limits['max_database_bytes'] % 4096:
        _fail('INVALID_SPEC')
    if type(data['sources']) is not list or not 1 <= len(data['sources']) <= 5:
        _fail('INVALID_SPEC')
    sources, identities, aliases = [], [], {spec_identity[:2]}
    for item in data['sources']:
        _fields(item, ('path', 'bytes', 'sha256'))
        path = _lexical(item['path'])
        if not path.is_absolute():
            path = spec_path.parent/path
        if (type(item['bytes']) is not int or item['bytes'] < 0 or type(item['sha256']) is not str
                or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            _fail('INVALID_SPEC')
        identity = _file(path, 'INVALID_SOURCE_PATH')
        if identity[:2] in aliases:
            _fail('DUPLICATE_SOURCE')
        aliases.add(identity[:2])
        if identity[-2] != item['bytes']:
            _fail('SOURCE_SIZE_MISMATCH')
        sources.append(ReleaseFileSource(path, item['bytes'], item['sha256']))
        identities.append(identity)
    if sum(s.expected_bytes for s in sources) > limits['max_total_source_bytes']:
        _fail('INPUT_BYTE_CAP')
    if type(data['segments']) is not list or not 1 <= len(data['segments']) <= 7:
        _fail('INVALID_SPEC')
    segments = []
    for item in data['segments']:
        _fields(item, ('id', 'role', 'start', 'end'))
        segments.append(ReleaseSegment(item['id'], item['role'], _stamp(item['start']), _stamp(item['end'])))
    registered = tuple(segments)
    _axis(registered, limits['max_minutes'])
    output = _lexical(output_arg, absolute=True)
    _output_preflight(output)
    # Component-aware comparison uses the platform's Path case semantics.
    for path in (spec_path, *(s.path for s in sources)):
        if path == output or path.is_relative_to(output):
            _fail('INVALID_OUTPUT')
    return spec_path, spec_identity, tuple(sources), tuple(identities), registered, dict(limits), output


def _project(result, segments, limits):
    resources, minutes = result.resources, result.minutes
    if resources.cleanup_status != 'CLEANED':
        _fail('OUTPUT_ERROR')
    receipts = resources.reader_receipts
    populations = []
    for ordinal, segment in enumerate(segments):
        indices = [i for i, identifier in enumerate(minutes.segment_ids) if identifier == segment.id]
        valid = sum(minutes.source_valid[i] for i in indices)
        populations.append(dict(ordinal=ordinal, role=segment.role, calendar_minutes=len(indices),
            valid_minutes=valid, invalid_minutes=len(indices)-valid,
            policies={p: {kind: sum(minutes.label_kinds[i][j] == kind for i in indices)
                for kind in _KINDS} for j,p in enumerate(_POLICIES)}))
    return dict(version=1, source_authentication=minutes.source_authentication,
        time_basis=minutes.time_basis, limits=limits,
        sources=[dict(ordinal=s.source_ordinal, bytes=s.source_bytes, sha256=s.source_sha256,
                      logical_rows=s.logical_rows) for s in receipts.sources],
        **{'global': {**{k: getattr(minutes,k) for k in ('raw_records','eligible_records',
            'excluded_records','outside_records','unplaced_invalid_rows','duplicate_groups')},
            'reason_counts': {k: dict(minutes.reason_counts)[k] for k in REASON_CODES}}},
        segments=populations,
        resources={**{k: getattr(resources,k) for k in ('unique_fingerprints',
            'cross_file_duplicate_groups','database_bytes_at_close',
            'observed_database_high_water_bytes','elapsed_seconds','cleanup_status')},
            'reader': {k: getattr(receipts,k) for k in ('source_content_open_count',
                'source_bytes_consumed','raw_read_count','logical_rows','elapsed_seconds')},
            'database_high_water_observation': 'DISCRETE_SAMPLES'})


def _bytes(value):
    payload = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('utf-8')
    if len(payload) > _CAP:
        _fail('OUTPUT_ERROR')
    return payload


class _Output:
    """Only adopt exclusively created files; retain every failure residue."""
    def __init__(self, path):
        self.path = path
        _output_preflight(path)
        path.mkdir()
        info = path.lstat()
        if not _ordinary(info, True):
            _fail('OUTPUT_ERROR')
        self.identity = _signature(info, directory=True)
        self.owned = {}

    def check(self):
        _ancestors(self.path, 'OUTPUT_ERROR')
        info = self.path.lstat()
        if not _ordinary(info, True) or _signature(info,directory=True) != self.identity:
            _fail('OUTPUT_ERROR')
        if {p.name for p in self.path.iterdir()} != set(self.owned):
            _fail('OUTPUT_ERROR')
        for name, identity in self.owned.items():
            if _file(self.path/name, 'OUTPUT_ERROR') != identity:
                _fail('OUTPUT_ERROR')

    def write(self, name, payload):
        self.check()
        path = self.path/name
        with path.open('xb') as stream:
            before = _signature(os.fstat(stream.fileno()))[:4]
            if stream.write(payload) != len(payload):
                _fail('OUTPUT_ERROR')
        identity = _file(path, 'OUTPUT_ERROR')
        if identity[:4] != before or identity[-2] != len(payload):
            _fail('OUTPUT_ERROR')
        self.owned[name] = identity
        self.check()
        with path.open('rb') as stream:
            if _signature(os.fstat(stream.fileno())) != identity or stream.read(_CAP+1) != payload:
                _fail('OUTPUT_ERROR')
            if _signature(os.fstat(stream.fileno())) != identity:
                _fail('OUTPUT_ERROR')
        self.check()


def run_release_audit(spec, output):
    """Write a new bounded summary; return only after its two-file commit checks."""
    spec_path, spec_identity, sources, identities, segments, limits, destination = _preflight(str(spec),str(output))
    if _file(spec_path,'SPEC_CHANGED') != spec_identity:
        _fail('SPEC_CHANGED')
    for source, expected in zip(sources,identities):
        if _file(source.path,'SOURCE_CHANGED') != expected:
            _fail('SOURCE_CHANGED')
    owner = _Output(destination)
    result = _aggregate_release_files(sources,segments,scratch_directory=destination/'scratch',
        budget=ReleaseDiskBudget(**{k:v for k,v in limits.items() if k!='max_minutes'}))
    owner.check()
    report = _project(result,segments,limits)
    payload = _bytes(report)
    # Ensure both JSON documents are complete before either is published.
    _decode(payload)
    complete = _bytes(dict(version=1,status='COMPLETE',report=dict(
        sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload))))
    _decode(complete)
    owner.write('report.json',payload)
    owner.write('COMPLETE.json',complete)
    owner.check()
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        _fail('INVALID_ARGUMENTS')


def _success_stdout(value):
    print(json.dumps(value,sort_keys=True))


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument('--spec',required=True)
    parser.add_argument('--output',required=True)
    phase = 'preflight'
    cleanup_failed = False
    try:
        args = parser.parse_args(argv)
        phase = 'run'
        run_release_audit(args.spec,args.output)
        phase = 'stdout'
        _success_stdout(dict(version=1,status='COMPLETE'))
        return 0
    except KeyboardInterrupt as exc:
        error = 'INTERRUPTED'
        cleanup_failed = getattr(exc,'cleanup_failed',False) is True
    except _AuditError as exc:
        error = exc.args[0]
        cleanup_failed = getattr(exc,'cleanup_failed',False) is True
    except ValueError as exc:
        error = (_KNOWN.get(exc.args[0],'INTERNAL_ERROR') if type(exc) is ValueError
                 and len(exc.args)==1 and type(exc.args[0]) is str else 'INTERNAL_ERROR')
        cleanup_failed = getattr(exc,'cleanup_failed',False) is True
    except OSError as exc:
        error = 'OUTPUT_ERROR' if phase in ('run','stdout') else 'INVALID_PATH'
        cleanup_failed = getattr(exc,'cleanup_failed',False) is True
    except Exception as exc:
        error = 'INTERNAL_ERROR'
        cleanup_failed = getattr(exc,'cleanup_failed',False) is True
    message = dict(error=error)
    if cleanup_failed:
        message['cleanup_failed'] = True
    print(json.dumps(message,sort_keys=True),file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
