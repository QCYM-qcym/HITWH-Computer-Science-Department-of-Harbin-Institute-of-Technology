"""Disposable exact release aggregation with bounded Python state.

The only persistent working files are an owned incomplete marker and a capped
SQLite projection. Nothing is resumable or authenticated. Source content is
consumed once through the frozen reader; no final result escapes before EOF,
qualification, exact ranks, handle closure and ownership-checked cleanup.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time

from ._release_file_reader import (ReleaseFileSource, ReleaseReadBudget,
    ReleaseReadReceipts, _ReleaseFileReader, _ordinary)
from ._release_minutes import (ReleaseSegment, ReleaseMinuteResult, ReleaseBucketCounts,
    REASON_CODES, PROTOCOL_CHANNELS, ELIGIBLE_CHANNELS, LABEL_KINDS, LABEL_ANOMALIES,
    G13U_FEATURE_NAMES, _axis, _fixed)


_PAGE_SIZE = 4096
_SCHEMA = 'c17-release-disposable-projection-v1'
_REASON_BITS = {name: 1 << i for i, name in enumerate(REASON_CODES)}
_CREATE = '''CREATE TABLE records (
digest BLOB PRIMARY KEY, n INTEGER NOT NULL, source_mask INTEGER NOT NULL,
minute_id INTEGER NOT NULL, duration_us INTEGER,
fwd_packets TEXT, bwd_packets TEXT, fwd_length TEXT, bwd_length TEXT,
base_reason_bits INTEGER NOT NULL, channel INTEGER NOT NULL,
p0 INTEGER NOT NULL, p1 INTEGER NOT NULL, p2 INTEGER NOT NULL,
anomaly INTEGER NOT NULL, definite_attack INTEGER NOT NULL,
attempted INTEGER NOT NULL, unused_issue INTEGER NOT NULL) WITHOUT ROWID'''
_INDEX = '''CREATE INDEX duration_order ON records(minute_id,duration_us,digest,n)
WHERE base_reason_bits=0 AND minute_id>=0'''
_INSERT = '''INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(digest) DO UPDATE SET n=records.n+1,
source_mask=records.source_mask|excluded.source_mask'''
_POPULATION = '''SELECT n,source_mask,minute_id,duration_us,
fwd_packets,bwd_packets,fwd_length,bwd_length,base_reason_bits,
channel,p0,p1,p2,anomaly,definite_attack,attempted,unused_issue FROM records'''
_DURATIONS = '''SELECT minute_id,duration_us,n FROM records INDEXED BY duration_order
WHERE base_reason_bits=0 AND minute_id>=0
ORDER BY minute_id,duration_us,digest,n'''


@dataclass(frozen=True, slots=True)
class ReleaseDiskBudget:
    max_total_source_bytes: int
    max_rows: int
    max_database_bytes: int
    max_elapsed_seconds: int


@dataclass(frozen=True, slots=True)
class ReleaseDiskResourceReport:
    reader_receipts: ReleaseReadReceipts
    unique_fingerprints: int
    cross_file_duplicate_groups: int
    database_bytes_at_close: int
    observed_database_high_water_bytes: int
    elapsed_seconds: float
    sqlite_version: str
    cleanup_status: str
    query_plan: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReleaseDiskResult:
    minutes: ReleaseMinuteResult
    resources: ReleaseDiskResourceReport


def _validate_budget(budget: ReleaseDiskBudget) -> None:
    if type(budget) is not ReleaseDiskBudget:
        raise ValueError('invalid_disk_budget')
    for value, maximum in ((budget.max_total_source_bytes, 2**31),
            (budget.max_rows, 2500000), (budget.max_database_bytes, 2**31),
            (budget.max_elapsed_seconds, 1800)):
        if type(value) is not int or not 0 < value <= maximum:
            raise ValueError('invalid_disk_budget')
    if budget.max_database_bytes < 65536 or budget.max_database_bytes % _PAGE_SIZE:
        raise ValueError('invalid_disk_budget')


class _Deadline:
    def __init__(self, seconds: int):
        self.start = time.monotonic()
        self.end = self.start + seconds

    def check(self) -> None:
        if time.monotonic() >= self.end:
            raise ValueError('elapsed_time_cap')

    def progress(self) -> int:
        return int(time.monotonic() >= self.end)


def _identity(path: Path, *, directory: bool) -> tuple[int, ...]:
    info = path.lstat()
    if not _ordinary(info, directory=directory):
        raise ValueError('scratch_ownership_changed')
    return (info.st_dev, info.st_ino, info.st_mode, getattr(info, 'st_file_attributes', 0))


def _ancestors(path: Path) -> None:
    for parent in reversed(path.parents):
        _identity(parent, directory=True)


def _validate_destination(path: Path) -> None:
    if (type(path) is not type(Path()) or not path.is_absolute()
            or '..' in path.parts or path.drive.startswith('\\\\')):
        raise ValueError('invalid_scratch_directory')
    try:
        _ancestors(path)
        try:
            path.lstat()
        except FileNotFoundError:
            return
    except (OSError, ValueError):
        pass
    raise ValueError('invalid_scratch_directory')


class _Scratch:
    def __init__(self, path: Path):
        self.path = path
        self.created = False
        self.directory_identity = None
        self.members = {}
        self.token = secrets.token_hex(32)

    def _marker(self, status: str) -> bytes:
        return json.dumps(dict(schema=_SCHEMA, token=self.token, status=status),
                          sort_keys=True, separators=(',', ':')).encode('ascii')

    def create(self) -> None:
        try:
            self.path.mkdir()
            self.created = True
            self.directory_identity = _identity(self.path, directory=True)
            self.create_file('owner.json', self._marker('INCOMPLETE'))
        except OSError:
            raise ValueError('scratch_io_error') from None

    def create_file(self, name: str, payload: bytes = b'') -> None:
        try:
            # Register only after successful exclusive creation. A failed open
            # must never transfer ownership of an existing/replacement entity.
            with open(self.path / name, 'xb', buffering=0) as handle:
                info = os.fstat(handle.fileno())
                if not _ordinary(info, directory=False):
                    raise ValueError('scratch_ownership_changed')
                self.members[name] = (info.st_dev, info.st_ino, info.st_mode,
                                      getattr(info, 'st_file_attributes', 0))
                if handle.write(payload) != len(payload):
                    raise ValueError('scratch_io_error')
        except OSError:
            raise ValueError('scratch_io_error') from None

    def check(self) -> None:
        try:
            _ancestors(self.path)
            if _identity(self.path, directory=True) != self.directory_identity:
                raise ValueError('scratch_ownership_changed')
            if {p.name for p in self.path.iterdir()} != set(self.members):
                raise ValueError('scratch_ownership_changed')
            for name, identity in self.members.items():
                if _identity(self.path / name, directory=False) != identity:
                    raise ValueError('scratch_ownership_changed')
            if 'owner.json' in self.members:
                with open(self.path / 'owner.json', 'rb', buffering=0) as handle:
                    info = os.fstat(handle.fileno())
                    identity = (info.st_dev, info.st_ino, info.st_mode,
                                getattr(info, 'st_file_attributes', 0))
                    if identity != self.members['owner.json']:
                        raise ValueError('scratch_ownership_changed')
                    raw = handle.read(16385)
                if len(raw) > 16384:
                    raise ValueError('scratch_ownership_changed')
                data = json.loads(raw)
                if (type(data) is not dict or set(data) != {'schema', 'token', 'status'}
                        or data['schema'] != _SCHEMA or data['token'] != self.token
                        or data['status'] not in ('INCOMPLETE', 'ABORTED_SCRATCH_UNUSABLE')):
                    raise ValueError('scratch_ownership_changed')
        except (OSError, ValueError, UnicodeError):
            raise ValueError('scratch_ownership_changed') from None

    def cleanup(self) -> None:
        if not self.created:
            return
        self.check()
        for name in ('scratch.sqlite3', 'owner.json'):
            if name in self.members:
                self.check()
                (self.path / name).unlink()
                del self.members[name]
        self.check()
        self.path.rmdir()
        self.created = False

    def abort_marker(self) -> None:
        # No unknown/replaced entity may be deleted or overwritten, even when
        # attempting to label a failed operation. Never create a new marker.
        self.check()
        if 'owner.json' not in self.members:
            return
        with open(self.path / 'owner.json', 'r+b', buffering=0) as handle:
            info = os.fstat(handle.fileno())
            identity = (info.st_dev, info.st_ino, info.st_mode,
                        getattr(info, 'st_file_attributes', 0))
            if identity != self.members['owner.json']:
                raise ValueError('scratch_ownership_changed')
            self.check()
            payload = self._marker('ABORTED_SCRATCH_UNUSABLE')
            if handle.write(payload) != len(payload):
                raise ValueError('scratch_io_error')
            handle.truncate()


class _Database:
    def __init__(self, scratch: _Scratch, budget: ReleaseDiskBudget, clock: _Deadline):
        self.scratch, self.budget, self.clock = scratch, budget, clock
        self.connection = None
        self.cursor = None
        self.high_water = 0
        self.query_plan = ()

    def _sql_error(self, error: sqlite3.Error) -> None:
        try:
            self.clock.check()
        except ValueError:
            raise ValueError('elapsed_time_cap') from None
        if getattr(error, 'sqlite_errorcode', None) == sqlite3.SQLITE_FULL:
            raise ValueError('database_byte_cap') from None
        raise ValueError('sqlite_error') from None

    @contextmanager
    def query(self, sql: str, parameters=()):
        self.clock.check()
        primary = None
        try:
            self.cursor = self.connection.execute(sql, parameters)
            yield self.cursor
            self.clock.check()
        except sqlite3.Error as error:
            primary = error
            self._sql_error(error)
        except BaseException as error:
            primary = error
            raise
        finally:
            cursor, self.cursor = self.cursor, None
            if cursor is not None:
                try:
                    cursor.close()
                except BaseException as error:
                    if primary is None:
                        if isinstance(error, (KeyboardInterrupt, SystemExit)):
                            raise
                        raise ValueError('sqlite_close_error') from None

    def run(self, sql: str, parameters=()) -> None:
        with self.query(sql, parameters):
            pass

    def scalar(self, sql: str):
        with self.query(sql) as cursor:
            item = cursor.fetchone()
            if item is None:
                raise ValueError('sqlite_environment')
            return item[0]

    def open(self) -> None:
        self.scratch.check()
        self.scratch.create_file('scratch.sqlite3')
        try:
            self.connection = sqlite3.connect(self.scratch.path / 'scratch.sqlite3')
            self.connection.set_progress_handler(self.clock.progress, 10000)
            for category, wanted in ((sqlite3.SQLITE_LIMIT_LENGTH, 32768),
                    (sqlite3.SQLITE_LIMIT_SQL_LENGTH, 8192), (sqlite3.SQLITE_LIMIT_COLUMN, 64)):
                self.connection.setlimit(category, wanted)
                if self.connection.getlimit(category) != wanted:
                    raise ValueError('sqlite_environment')
            settings = (('page_size',4096), ('max_page_count',self.budget.max_database_bytes // _PAGE_SIZE),
                ('cache_size',-32768), ('mmap_size',0), ('journal_mode','OFF'),
                ('synchronous',0), ('temp_store',2), ('automatic_index',0))
            for key, value in settings:
                self.run(f'PRAGMA {key}={value}')
                actual = self.scalar(f'PRAGMA {key}')
                if actual != (value.lower() if type(value) is str else value):
                    raise ValueError('sqlite_environment')
            self.run(_CREATE)
            self.run(_INDEX)
            with self.query('EXPLAIN QUERY PLAN '+_DURATIONS) as cursor:
                self.query_plan = tuple(item[3] for item in cursor)
            if (not any('duration_order' in text for text in self.query_plan)
                    or any('TEMP B-TREE' in text.upper() or 'SORT' in text.upper() for text in self.query_plan)):
                raise ValueError('sqlite_query_plan')
            self.commit()
            self.observe()
        except sqlite3.Error as error:
            self._sql_error(error)

    def commit(self) -> None:
        self.clock.check()
        try:
            self.connection.commit()
        except sqlite3.Error as error:
            self._sql_error(error)
        self.clock.check()

    def observe(self) -> int:
        self.clock.check()
        self.scratch.check()
        try:
            actual = (self.scratch.path / 'scratch.sqlite3').stat().st_size
        except OSError:
            raise ValueError('scratch_io_error') from None
        logical = self.scalar('PRAGMA page_count') * _PAGE_SIZE
        if max(actual, logical) > self.budget.max_database_bytes:
            raise ValueError('database_byte_cap')
        self.high_water = max(self.high_water, actual)
        self.clock.check()
        return actual

    def close(self) -> BaseException | None:
        failure = None
        if self.cursor is not None:
            try:
                self.cursor.close()
            except BaseException as error:
                failure = error
            self.cursor = None
        if self.connection is not None:
            try:
                self.connection.close()
            except BaseException as error:
                if failure is None:
                    failure = error
            self.connection = None
        return failure


def _project(row, owners) -> tuple:
    bad = set(row.reasons)
    if row.completion is None:
        minute_id = -2
        bad.add('unplaced_invalid_row')
    else:
        owner = owners.get(row.completion.replace(second=0, microsecond=0))
        if owner is None:
            minute_id = -1
            bad.add('outside_registered_minutes')
        else:
            minute_id = owner[0]
            origin = owners.get(row.start.replace(second=0, microsecond=0))
            if origin is None or origin[1] != owner[1]:
                bad.add('cross_partition')
    counts = tuple(None if value is None else str(value) for value in
                   (row.fwd_packets,row.bwd_packets,row.fwd_length,row.bwd_length))
    return (row.lexical_fingerprint, 1, 1 << row.source_ordinal, minute_id, row.duration_us,
            *counts, sum(_REASON_BITS[reason] for reason in bad),
            PROTOCOL_CHANNELS.index(row.protocol_channel),
            *(LABEL_KINDS.index(kind) for kind in row.label_kinds),
            -1 if row.label_anomaly is None else LABEL_ANOMALIES.index(row.label_anomaly),
            int(row.definite_attack), int(row.attempted), int(bool(row.unused_field_issues)))


class _Bucket:
    def __init__(self):
        self.raw = self.eligible = self.zero_bwd = self.unused = 0
        self.reasons = Counter()
        self.raw_channels, self.good_channels = Counter(), Counter()
        self.labels = [[0,0,0] for _ in range(3)]
        self.anomalies = Counter()
        self.definite = self.attempted = False
        self.sums = [0,0,0,0]

    def describe(self, n, channel, kinds, anomaly, definite, attempted, unused):
        self.raw += n
        self.raw_channels[PROTOCOL_CHANNELS[channel]] += n
        for policy, kind in enumerate(kinds):
            self.labels[policy][kind] += n
        if anomaly >= 0:
            self.anomalies[LABEL_ANOMALIES[anomaly]] += n
        self.definite |= bool(definite)
        self.attempted |= bool(attempted)
        self.unused += unused*n

    def accept(self, n, channel, counts):
        self.eligible += n
        self.good_channels[PROTOCOL_CHANNELS[channel]] += n
        for i, value in enumerate(counts):
            self.sums[i] += int(value)*n
        self.zero_bwd += n*(int(counts[1]) == 0)

    def freeze(self) -> ReleaseBucketCounts:
        return ReleaseBucketCounts(self.raw,self.eligible,self.raw-self.eligible,
            _fixed(self.reasons,REASON_CODES), _fixed(self.raw_channels,PROTOCOL_CHANNELS),
            _fixed(self.good_channels,ELIGIBLE_CHANNELS), tuple(tuple(k) for k in self.labels),
            _fixed(self.anomalies,LABEL_ANOMALIES),self.definite,self.attempted,self.unused)


def _population(database: _Database, count: int):
    buckets = [_Bucket() for _ in range(count)]
    total = _Bucket()
    unique = duplicate = cross_file = outside = unplaced = 0
    with database.query(_POPULATION) as cursor:
        for item in cursor:
            database.clock.check()
            n, mask, minute_id, _, *rest = item
            counts = rest[:4]
            bits, channel, p0, p1, p2, anomaly, definite, attempted, unused = rest[4:]
            unique += 1
            if n > 1:
                duplicate += 1
                cross_file += int(bool(mask & (mask-1)))
                bits |= _REASON_BITS['duplicate_record']
            bad = tuple(reason for reason in REASON_CODES if bits & _REASON_BITS[reason])
            total.describe(n,channel,(p0,p1,p2),anomaly,definite,attempted,unused)
            total.reasons.update({reason:n for reason in bad})
            if minute_id == -2:
                unplaced += n
            elif minute_id == -1:
                outside += n
            else:
                bucket = buckets[minute_id]
                bucket.describe(n,channel,(p0,p1,p2),anomaly,definite,attempted,unused)
                bucket.reasons.update({reason:n for reason in bad})
                if not bits:
                    bucket.accept(n,channel,counts)
                    total.accept(n,channel,counts)
    for bucket in buckets:
        database.clock.check()
        if unplaced:
            bucket.reasons['unplaced_invalid_row'] = unplaced
        if not bucket.raw:
            bucket.reasons['empty_unconfirmed'] = 1
    if (sum(total.raw_channels.values()) != total.raw
            or sum(total.good_channels.values()) != total.eligible
            or sum(b.raw for b in buckets)+outside+unplaced != total.raw
            or sum(b.eligible for b in buckets) != total.eligible):
        raise ValueError('record_conservation_failure')
    return buckets,total,unique,duplicate,cross_file,outside,unplaced


def _materialize(bucket: _Bucket, captured: dict, maximum: int) -> tuple[float, ...]:
    def quantile(numerator, denominator):
        low, remainder = divmod((bucket.eligible-1)*numerator,denominator)
        value = Fraction(captured[low])
        if remainder:
            value += Fraction((captured[low+1]-captured[low])*remainder,denominator)
        return value/1000000
    numbers = (bucket.eligible,*bucket.sums,
        *(bucket.good_channels[key] for key in ELIGIBLE_CHANNELS),
        Fraction(maximum,1000000),quantile(1,2),quantile(19,20),bucket.zero_bwd)
    try:
        result = tuple(float(value) for value in numbers)
    except OverflowError:
        raise ValueError('numeric_materialization_overflow') from None
    if not all(math.isfinite(value) for value in result):
        raise ValueError('numeric_materialization_overflow')
    return result


def _finish_minutes(database, axis, buckets, total, receipts, duplicate, outside, unplaced):
    timestamps,segment_ids,roles,_ = axis
    valid = tuple(not bucket.reasons for bucket in buckets)
    targets, captured = [], []
    scanned, maxima = [0]*len(buckets), [0]*len(buckets)
    for bucket, usable in zip(buckets,valid):
        ranks = set()
        if usable:
            for numerator, denominator in ((1,2),(19,20)):
                low,remainder = divmod((bucket.eligible-1)*numerator,denominator)
                ranks.add(low)
                if remainder:
                    ranks.add(low+1)
        targets.append(ranks)
        captured.append({})
    with database.query(_DURATIONS) as cursor:
        for minute_id,duration,n in cursor:
            database.clock.check()
            if n > 1 or not valid[minute_id]:
                continue
            rank = scanned[minute_id]
            if rank in targets[minute_id]:
                captured[minute_id][rank] = duration
            scanned[minute_id] += 1
            maxima[minute_id] = duration
    values, kinds, reports = [], [], []
    for i,(bucket,usable) in enumerate(zip(buckets,valid)):
        database.clock.check()
        if usable and (scanned[i] != bucket.eligible or set(captured[i]) != targets[i]):
            raise ValueError('quantile_consistency_failure')
        values.append(_materialize(bucket,captured[i],maxima[i]) if usable else (None,)*13)
        kinds.append(tuple('unknown' if not usable or counts[2]
                           else 'attack' if counts[1] else 'normal' for counts in bucket.labels))
        reports.append(bucket.freeze())
    if total.raw != receipts.logical_rows:
        raise ValueError('record_conservation_failure')
    return ReleaseMinuteResult('c17-release-91-v1',
        tuple(r.source_bytes for r in receipts.sources),tuple(r.source_sha256 for r in receipts.sources),
        'NOT_AUTHENTICATED','SOURCE_WALL_CLOCK_COMPLETION_PROXY',G13U_FEATURE_NAMES,
        timestamps,segment_ids,roles,tuple(values),valid,tuple(kinds),tuple(reports),
        total.raw,total.eligible,total.raw-total.eligible,outside,unplaced,duplicate,
        _fixed(total.reasons,REASON_CODES),_fixed(total.raw_channels,PROTOCOL_CHANNELS),
        _fixed(total.good_channels,ELIGIBLE_CHANNELS),tuple(tuple(k) for k in total.labels),
        _fixed(total.anomalies,LABEL_ANOMALIES))


def _aggregate_release_files(sources: tuple[ReleaseFileSource, ...],
        segments: tuple[ReleaseSegment, ...], *, scratch_directory: Path,
        budget: ReleaseDiskBudget) -> ReleaseDiskResult:
    """Return a complete frozen result only after owned scratch has been removed.

    A failed cleanup preserves the primary failure and adds the fixed
    cleanup_failed note/attribute. If cleanup is the only failure its safe code
    is scratch_cleanup_failed. Unknown/replaced members are left untouched.
    """
    _validate_budget(budget)
    clock = _Deadline(budget.max_elapsed_seconds)
    axis = _axis(segments,10000)
    _validate_destination(scratch_directory)
    if 0 < sys.get_int_max_str_digits() < 4096:
        raise ValueError('integer_string_limit_environment')
    reader = _ReleaseFileReader(sources,budget=ReleaseReadBudget(
        budget.max_total_source_bytes,budget.max_rows,budget.max_elapsed_seconds),deadline=clock.end)
    scratch = _Scratch(scratch_directory)
    database = _Database(scratch,budget,clock)
    primary = None
    result = None
    try:
        with reader:
            clock.check()
            scratch.create()
            database.open()
            ingested = 0
            for row in reader:
                clock.check()
                database.run(_INSERT,_project(row,axis[3]))
                del row
                ingested += 1
                if ingested % 1000 == 0:
                    database.commit()
                    database.observe()
            database.commit()
            database.observe()
        receipts = reader.receipts
        population = _population(database,len(axis[0]))
        buckets,total,unique,duplicate,cross_file,outside,unplaced = population
        if total.raw != receipts.logical_rows:
            raise ValueError('record_conservation_failure')
        minutes = _finish_minutes(database,axis,buckets,total,receipts,duplicate,outside,unplaced)
        database_bytes = database.observe()
        logical = database.scalar('PRAGMA page_count')*_PAGE_SIZE
        if database_bytes != logical:
            raise ValueError('database_size_mismatch')
        clock.check()
        result = (minutes,receipts,unique,cross_file,database_bytes)
    except BaseException as error:
        primary = error
    close_error = database.close()
    close_failed = close_error is not None
    if primary is None and isinstance(close_error, (KeyboardInterrupt, SystemExit)):
        primary = close_error
    if primary is None and not close_failed:
        try:
            scratch.check()
            try:
                closed_bytes = (scratch.path / 'scratch.sqlite3').stat().st_size
            except OSError:
                raise ValueError('scratch_io_error') from None
            if closed_bytes != result[4]:
                raise ValueError('database_size_mismatch')
            clock.check()
        except BaseException as error:
            primary = error
    cleanup_failed = False
    try:
        scratch.cleanup()
    except BaseException as error:
        cleanup_failed = True
        if primary is None and isinstance(error, (KeyboardInterrupt, SystemExit)):
            primary = error
        try:
            scratch.abort_marker()
        except BaseException:
            pass
    if primary is not None:
        if close_failed:
            primary.add_note('close_failed')
        if cleanup_failed:
            primary.add_note('cleanup_failed')
            primary.cleanup_failed = True
        raise primary
    if close_failed:
        error = ValueError('sqlite_close_error')
        if cleanup_failed:
            error.add_note('cleanup_failed')
            error.cleanup_failed = True
        raise error
    if cleanup_failed:
        raise ValueError('scratch_cleanup_failed')
    clock.check()
    minutes,receipts,unique,cross_file,database_bytes = result
    resources = ReleaseDiskResourceReport(receipts,unique,cross_file,database_bytes,
        database.high_water,time.monotonic()-clock.start,sqlite3.sqlite_version,'CLEANED',database.query_plan)
    clock.check()
    return ReleaseDiskResult(minutes,resources)
