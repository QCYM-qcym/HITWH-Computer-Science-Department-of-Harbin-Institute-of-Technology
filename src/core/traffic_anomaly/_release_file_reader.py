"""Bounded one-pass internal CSV reader; receipts do not authenticate sources.

Only explicit ordinary files are accepted. Completion requires CSV EOF and a
same-stream hash/size check for every source, followed by closing its handles.
The time guard is cooperative; metadata checks are not immutable snapshots.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
import hashlib
import io
import math
import os
from pathlib import Path
import re
import stat
import time

from ._release_csv import EXPECTED_HEADER, ParsedReleaseRow, _parse_row


_CHUNK_BYTES = 65536
_MAX_RECORD_CHARS = 1048576
_VOCAB_SPECS = ((EXPECTED_HEADER.index('Label'), 100, 'max_label_values'),
                (EXPECTED_HEADER.index('Attempted Category'), 32, 'max_category_values'),
                (EXPECTED_HEADER.index('Protocol'), 256, 'max_protocol_values'))


@dataclass(frozen=True, slots=True)
class ReleaseFileSource:
    path: Path = field(repr=False)
    expected_bytes: int = field(repr=False)
    expected_sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReleaseReadBudget:
    max_total_source_bytes: int
    max_rows: int
    max_elapsed_seconds: int


@dataclass(frozen=True, slots=True)
class ReleaseFileReceipt:
    source_ordinal: int
    source_bytes: int
    source_sha256: str
    logical_rows: int


@dataclass(frozen=True, slots=True)
class ReleaseReadReceipts:
    sources: tuple[ReleaseFileReceipt, ...]
    source_content_open_count: int
    source_bytes_consumed: int
    raw_read_count: int
    logical_rows: int
    elapsed_seconds: float
    source_authentication: str = 'NOT_AUTHENTICATED'


def _validate_inputs(sources: tuple[ReleaseFileSource, ...], budget: ReleaseReadBudget) -> None:
    if type(budget) is not ReleaseReadBudget:
        raise ValueError('invalid_budget')
    for value, limit in ((budget.max_total_source_bytes, 2**31),
                         (budget.max_rows, 2500000), (budget.max_elapsed_seconds, 1800)):
        if type(value) is not int or not 0 < value <= limit:
            raise ValueError('invalid_budget')
    if type(sources) is not tuple or not 1 <= len(sources) <= 5:
        raise ValueError('invalid_sources')
    if any(type(source) is not ReleaseFileSource for source in sources):
        raise ValueError('invalid_sources')
    for source in sources:
        path = source.path
        if (type(path) is not type(Path()) or not path.is_absolute()
                or '..' in path.parts or path.drive.startswith('\\\\')
                or type(source.expected_bytes) is not int or source.expected_bytes < 0
                or type(source.expected_sha256) is not str
                or re.fullmatch('[0-9a-f]{64}', source.expected_sha256) is None):
            raise ValueError('invalid_source')


def _signature(info: os.stat_result) -> tuple[int, ...]:
    # Windows path and handle stats can expose different ctime semantics.
    # Compare only metadata with consistent meanings across these two APIs.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, getattr(info, 'st_file_attributes', 0))


def _ordinary(info: os.stat_result, *, directory: bool) -> bool:
    return (not stat.S_ISLNK(info.st_mode)
            and not getattr(info, 'st_file_attributes', 0) & 0x400
            and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)))


def _path_signature(path: Path, code: str) -> tuple[int, ...]:
    try:
        # Do not resolve links before checking each lexical ancestor.
        for parent in reversed(path.parents):
            if not _ordinary(parent.lstat(), directory=True):
                raise ValueError(code)
        info = path.lstat()
        if not _ordinary(info, directory=False):
            raise ValueError(code)
        return _signature(info)
    except (OSError, ValueError):
        raise ValueError(code) from None


class _HashingRaw(io.RawIOBase):
    """Own FileIO; guard actual requests below all buffering and decoding."""

    def __init__(self, file: io.FileIO, owner: _ReleaseFileReader):
        super().__init__()
        self.file = file
        self.owner = owner
        self.digest = hashlib.sha256()
        self.byte_count = 0
        self.eof = False

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        self.owner._check_time()
        remaining = self.owner._budget.max_total_source_bytes - self.owner._bytes
        size = min(len(buffer), _CHUNK_BYTES, remaining + 1)
        count = self.file.readinto(memoryview(buffer)[:size])
        self.owner._reads += 1
        self.byte_count += count
        self.owner._bytes += count
        self.digest.update(memoryview(buffer)[:count])
        self.owner._check_time()
        if self.owner._bytes > self.owner._budget.max_total_source_bytes:
            raise ValueError('input_byte_cap')
        if count == 0:
            self.eof = True
        return count

    def close(self) -> None:
        try:
            if not self.file.closed:
                self.file.close()
        finally:
            super().close()


class _RecordLines:
    """A CSV next() may request many physical lines; share one char allowance."""

    def __init__(self, text: io.TextIOWrapper):
        self.text = text
        self.chars = 0

    def __iter__(self):
        return self

    def __next__(self) -> str:
        value = self.text.readline(_MAX_RECORD_CHARS - self.chars + 1)
        self.chars += len(value)
        if self.chars > _MAX_RECORD_CHARS:
            raise ValueError('logical_record_char_cap')
        if not value:
            raise StopIteration
        return value


class _ReleaseFileReader:
    """Single-use context iterator yielding the shared final ParsedReleaseRow.

    No receipt is exposed until all sources have reached verified EOF and all
    their handles have closed. Normal early exit fails; consumer exceptions
    retain their identity while owned handles are closed best-effort.
    """

    def __init__(self, sources: tuple[ReleaseFileSource, ...], *, budget: ReleaseReadBudget,
                 deadline: float | None = None):
        _validate_inputs(sources, budget)
        if deadline is not None:
            try:
                valid_deadline = type(deadline) in (int, float) and math.isfinite(deadline)
            except OverflowError:
                valid_deadline = False
            if not valid_deadline:
                raise ValueError('invalid_deadline')
        self._sources = sources
        self._budget = budget
        self._state = 'NEW'
        self._in_context = False
        self._snapshots = ()
        self._start = 0.0
        self._supplied_deadline = deadline
        self._deadline = 0.0
        self._source_index = 0
        self._source_rows = 0
        self._rows = 0
        self._opens = 0
        self._reads = 0
        self._bytes = 0
        self._file = self._raw = self._buffer = self._text = None
        self._lines = self._csv = None
        self._file_receipts = []
        self._receipts = None
        self._vocabularies = [set(), set(), set()]

    def __repr__(self) -> str:
        return f'<_ReleaseFileReader state={self._state}>'

    @property
    def receipts(self) -> ReleaseReadReceipts:
        if self._state not in ('COMPLETE', 'CLOSED') or self._receipts is None:
            raise ValueError('reader_state')
        return self._receipts

    def __enter__(self):
        if self._state != 'NEW':
            raise ValueError('reader_state')
        self._state = 'ACTIVE'
        self._start = time.monotonic()
        self._deadline = self._start + self._budget.max_elapsed_seconds
        if self._supplied_deadline is not None:
            self._deadline = min(self._deadline, self._supplied_deadline)
        try:
            self._check_time()
            if csv.field_size_limit() < 4096:
                raise ValueError('csv_field_limit_environment')
            paths, entities, snapshots = set(), set(), []
            for source in self._sources:
                self._check_time()
                path_key = os.path.normcase(str(source.path))
                signature = _path_signature(source.path, 'invalid_source_path')
                entity = signature[:2] if signature[1] else None
                if path_key in paths or entity is not None and entity in entities:
                    raise ValueError('duplicate_source')
                paths.add(path_key)
                if entity is not None:
                    entities.add(entity)
                if signature[3] != source.expected_bytes:
                    raise ValueError('source_size_mismatch')
                snapshots.append(signature)
            if sum(source.expected_bytes for source in self._sources) > self._budget.max_total_source_bytes:
                raise ValueError('input_byte_cap')
            self._snapshots = tuple(snapshots)
            self._check_time()
        except BaseException:
            self._state = 'FAILED'
            raise
        self._in_context = True
        return self

    def __iter__(self):
        if self._state not in ('ACTIVE', 'COMPLETE'):
            raise ValueError('reader_state')
        return self

    def __next__(self) -> ParsedReleaseRow:
        if self._state == 'COMPLETE':
            raise StopIteration
        if self._state != 'ACTIVE':
            raise ValueError('reader_state')
        try:
            return self._advance()
        except StopIteration:
            raise
        except BaseException:
            self._state = 'FAILED'
            self._receipts = None
            self._close_active(suppress=True)
            raise

    def __exit__(self, exc_type, exc, traceback):
        if not self._in_context:
            raise ValueError('reader_state')
        self._in_context = False
        complete = self._state == 'COMPLETE'
        if exc_type is not None:
            self._state = 'FAILED'
            self._receipts = None
            self._close_active(suppress=True)
            return False
        try:
            self._close_active(suppress=False)
        except BaseException:
            self._state = 'FAILED'
            self._receipts = None
            raise
        if not complete:
            self._state = 'FAILED'
            raise ValueError('incomplete_read')
        self._state = 'CLOSED'
        return False

    def _check_time(self) -> None:
        if time.monotonic() >= self._deadline:
            raise ValueError('elapsed_time_cap')

    def _close_active(self, *, suppress: bool) -> None:
        failed = False
        # Keep independent ownership references for a close that raises partway.
        for handle in (self._text, self._buffer, self._raw, self._file):
            if handle is not None:
                try:
                    if not handle.closed:
                        handle.close()
                except BaseException:
                    failed = True
        self._file = self._raw = self._buffer = self._text = None
        self._lines = self._csv = None
        if failed and not suppress:
            raise ValueError('source_close_error') from None

    def _open_source(self) -> None:
        source = self._sources[self._source_index]
        if _path_signature(source.path, 'source_changed') != self._snapshots[self._source_index]:
            raise ValueError('source_changed')
        self._check_time()
        try:
            self._file = open(source.path, 'rb', buffering=0)
            self._opens += 1
            info = os.fstat(self._file.fileno())
            if not _ordinary(info, directory=False) or _signature(info) != self._snapshots[self._source_index]:
                raise ValueError('source_changed')
            self._raw = _HashingRaw(self._file, self)
            self._buffer = io.BufferedReader(self._raw, buffer_size=_CHUNK_BYTES)
            self._text = io.TextIOWrapper(self._buffer, encoding='utf-8-sig', errors='strict', newline='')
            self._lines = _RecordLines(self._text)
            self._csv = csv.reader(self._lines, strict=True)
            self._source_rows = 0
            header = self._record()
            if header is None:
                raise ValueError('missing_header')
            if tuple(header) != EXPECTED_HEADER:
                raise ValueError('header_mismatch')
        except OSError:
            raise ValueError('source_io_error') from None

    def _record(self) -> list[str] | None:
        self._check_time()
        self._lines.chars = 0
        try:
            values = next(self._csv, None)
        except UnicodeError:
            raise ValueError('invalid_utf8') from None
        except csv.Error:
            raise ValueError('invalid_csv') from None
        except OSError:
            raise ValueError('source_io_error') from None
        self._check_time()
        return values

    def _finish_source(self) -> None:
        source = self._sources[self._source_index]
        raw = self._raw
        try:
            signature = _signature(os.fstat(self._file.fileno()))
        except OSError:
            raise ValueError('source_io_error') from None
        expected = self._snapshots[self._source_index]
        if signature != expected or _path_signature(source.path, 'source_changed') != expected:
            raise ValueError('source_changed')
        if not raw.eof or raw.byte_count != source.expected_bytes:
            raise ValueError('source_size_mismatch')
        digest = raw.digest.hexdigest()
        if digest != source.expected_sha256:
            raise ValueError('source_hash_mismatch')
        receipt = ReleaseFileReceipt(self._source_index, raw.byte_count, digest, self._source_rows)
        self._close_active(suppress=False)
        self._check_time()
        self._file_receipts.append(receipt)
        self._source_index += 1

    def _advance(self) -> ParsedReleaseRow:
        while self._source_index < len(self._sources):
            self._check_time()
            if self._csv is None:
                self._open_source()
            values = self._record()
            if values is None:
                self._finish_source()
                continue
            if self._rows >= self._budget.max_rows:
                raise ValueError('max_rows')
            if len(values) != len(EXPECTED_HEADER):
                raise ValueError('ragged_row')
            if any('\x00' in value for value in values):
                raise ValueError('field_nul')
            if any(len(value) > 4096 for value in values):
                raise ValueError('max_field_chars')
            for vocabulary, (index, limit, code) in zip(self._vocabularies, _VOCAB_SPECS):
                vocabulary.add(values[index])
                if len(vocabulary) > limit:
                    raise ValueError(code)
            parsed = _parse_row(tuple(values), self._source_index, self._source_rows + 1, 4096)
            self._check_time()
            self._rows += 1
            self._source_rows += 1
            return parsed
        self._check_time()
        self._receipts = ReleaseReadReceipts(tuple(self._file_receipts), self._opens,
                                           self._bytes, self._reads, self._rows,
                                           time.monotonic() - self._start)
        self._check_time()
        self._state = 'COMPLETE'
        raise StopIteration
