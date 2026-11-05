"""Fresh invented full-91 files only; no real payload or existing index."""
import builtins
import csv
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib
import io
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tests/fixtures/release-91-artificial-v1.json').read_text(encoding='utf-8'))
HEADER = FIXTURE['header']


def mod():
    return importlib.import_module('traffic_anomaly._release_file_reader')


def row(**changes):
    values = dict(zip(HEADER, FIXTURE['rows'][0]))
    values.update(changes)
    return [values[key] for key in HEADER]


def encoded(rows=(), *, newline='\r\n', bom=False, header=HEADER):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator=newline)
    writer.writerow(header)
    writer.writerows(rows)
    return (('\ufeff' if bom else '') + stream.getvalue()).encode('utf-8')


def source(tmp_path, payload, name='invented.csv'):
    path = tmp_path / name
    path.write_bytes(payload)
    return mod().ReleaseFileSource(path, len(payload), hashlib.sha256(payload).hexdigest())


def reader(sources, **budget):
    defaults = dict(max_total_source_bytes=2**21, max_rows=1000, max_elapsed_seconds=60)
    defaults.update(budget)
    return mod()._ReleaseFileReader(sources, budget=mod().ReleaseReadBudget(**defaults))


def read(sources, **budget):
    with reader(sources, **budget) as stream:
        rows = tuple(stream)
        receipt = stream.receipts
    return rows, receipt


def fail(sources, code, **budget):
    with pytest.raises(ValueError) as caught:
        read(sources, **budget)
    assert str(caught.value) == code
    assert 'invented.csv' not in repr(caught.value)


@pytest.mark.parametrize('newline', ['\r', '\n', '\r\n'])
@pytest.mark.parametrize('bom', [False, True])
def test_matches_reference_multiline_and_same_stream_sha(tmp_path, newline, bom):
    payload = encoded([row(**{'Flow ID': 'invented,"\nflow', 'Src IP': '测试'}),
                       row(Protocol='200'), row(**{'Total Fwd Packet': '1.5'})], newline=newline, bom=bom)
    items, receipt = read((source(tmp_path, payload),))
    reference = importlib.import_module('traffic_anomaly._release_csv')
    expected = reference._parse_release_csv((payload,), budget=reference.ReleaseFixtureBudget())
    assert items == expected.rows
    assert [item.record_ordinal for item in items] == [1, 2, 3]
    assert receipt.source_bytes_consumed == len(payload)
    assert receipt.source_content_open_count == 1
    assert receipt.logical_rows == 3
    assert receipt.sources[0].source_sha256 == hashlib.sha256(payload).hexdigest()
    assert receipt.sources[0].source_bytes == len(payload)
    assert receipt.sources[0].logical_rows == 3
    assert receipt.sources[0].source_ordinal == 0
    assert receipt.source_authentication == 'NOT_AUTHENTICATED'
    assert 0 <= receipt.elapsed_seconds <= 60
    assert 'invented' not in repr(receipt)
    for obj, key in [(receipt, 'logical_rows'), (receipt.sources[0], 'source_bytes')]:
        with pytest.raises(FrozenInstanceError):
            setattr(obj, key, 0)


def test_lazy_one_unbuffered_content_open_per_source_and_chunk_requests(tmp_path, monkeypatch):
    m = mod()
    payload = encoded([row(**{'Flow ID': str(i), 'Src IP': '界'*1000}) for i in range(25)], bom=True)
    sources = tuple(source(tmp_path, payload, f'copy{i}.csv') for i in range(5))
    original = builtins.open
    opened, requests, consumed = [], [], []
    class Spy(io.FileIO):
        def readinto(self, buffer):
            requests.append(len(buffer))
            n = super().readinto(buffer)
            consumed.append(n)
            return n
    def guarded(path, mode='r', buffering=-1, *args, **kwargs):
        if Path(path) in [s.path for s in sources]:
            assert mode == 'rb' and buffering == 0
            handle = Spy(path, mode)
            opened.append(handle)
            return handle
        return original(path, mode, buffering, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded)
    stream = reader(sources)
    with stream:
        assert opened == []
        items = tuple(stream)
        receipt = stream.receipts
        assert len(items) == 125
        assert receipt.source_content_open_count == len(opened) == 5
        assert receipt.raw_read_count == len(requests)
        assert receipt.source_bytes_consumed == sum(consumed) == 5*len(payload)
        assert max(requests) <= 65536
    assert all(handle.closed for handle in opened)
    assert {item.source_ordinal for item in items} == set(range(5))


def test_header_only_and_missing_header(tmp_path):
    assert read((source(tmp_path, encoded()),))[0] == ()
    for payload in (b'', b'\xef\xbb\xbf'):
        fail((source(tmp_path, payload),), 'missing_header')


@pytest.mark.parametrize('payload,code', [
    (b'wrong\n', 'header_mismatch'),
    (encoded([row()[:-1]]), 'ragged_row'),
    (encoded([row(**{'Flow ID': 'x\x00y'})]), 'field_nul'),
    (encoded([row(**{'Flow ID': 'x'*4097})]), 'max_field_chars'),
    (encoded()+b'"unterminated', 'invalid_csv'),
    (encoded()+b'\xff', 'invalid_utf8'),
    (encoded([row(**{'Total Fwd Packet': '1e4096'})]), 'integer_expansion_limit'),
    (encoded([row(Timestamp='9999-12-31 23:59:59.999999')]), 'completion_overflow'),
    (encoded([row(**{'Flow Duration': '86400000001'})]), 'duration_cap'),
], ids=['header', 'ragged', 'nul', 'field_length', 'csv', 'utf8', 'integer', 'completion', 'duration'])
def test_structural_and_operation_failures_are_safe(tmp_path, payload, code):
    fail((source(tmp_path, payload),), code)


def test_exact_field_and_integer_expansion_boundary(tmp_path):
    payload = encoded([row(**{'Flow ID': 'x'*4096, 'Total Fwd Packet': '1e4095'})])
    assert read((source(tmp_path, payload),))[0][0].fwd_packets == 10**4095


@pytest.mark.parametrize('column,limit,code', [('Label', 100, 'max_label_values'),
    ('Attempted Category', 32, 'max_category_values'), ('Protocol', 256, 'max_protocol_values')])
def test_global_vocabulary_exact_and_one_over(tmp_path, column, limit, code):
    first = source(tmp_path, encoded([row(**{column: str(i)}) for i in range(limit)]), 'a.csv')
    assert len(read((first,))[0]) == limit
    second = source(tmp_path, encoded([row(**{column: str(limit)})]), 'b.csv')
    fail((first, second), code)


def test_exact_row_and_byte_budgets(tmp_path):
    payload = encoded([row(), row()])
    src = source(tmp_path, payload)
    assert len(read((src,), max_rows=2, max_total_source_bytes=len(payload))[0]) == 2
    fail((src,), 'max_rows', max_rows=1)
    fail((src,), 'input_byte_cap', max_total_source_bytes=len(payload)-1)


@pytest.mark.parametrize('change,code', [({'expected_sha256': '0'*64}, 'source_hash_mismatch'),
    ({'expected_bytes': 1}, 'source_size_mismatch')])
def test_expected_receipts_required(tmp_path, change, code):
    fail((replace(source(tmp_path, encoded([row()])), **change),), code)


def test_same_size_altered_content_fails_digest(tmp_path):
    src = source(tmp_path, encoded([row()]))
    altered = encoded([row(Protocol='7')])
    assert len(altered) == src.expected_bytes
    src.path.write_bytes(altered)
    fail((src,), 'source_hash_mismatch')


@pytest.mark.parametrize('kind', ['list', 'empty', 'too_many', 'wrong_item'])
def test_sources_exact_immutable_shape(tmp_path, kind):
    src = source(tmp_path, encoded())
    sources = {'list': [src], 'empty': (), 'too_many': (src,)*6, 'wrong_item': (object(),)}[kind]
    with pytest.raises(ValueError, match='^invalid_sources$'):
        reader(sources)


@pytest.mark.parametrize('field,value', [('max_total_source_bytes', 0), ('max_total_source_bytes', 2**31+1),
    ('max_rows', True), ('max_rows', 2500001), ('max_elapsed_seconds', 1801),
    ('max_elapsed_seconds', 0.5)])
def test_budget_exact_types_and_hard_bounds(tmp_path, field, value):
    with pytest.raises(ValueError, match='^invalid_budget$'):
        reader((source(tmp_path, encoded()),), **{field: value})


@pytest.mark.parametrize('field,value', [('path', 'relative.csv'), ('path', Path('relative.csv')),
    ('expected_bytes', True), ('expected_bytes', -1), ('expected_sha256', 'A'*64),
    ('expected_sha256', []), ('expected_sha256', '0'*63)])
def test_source_fields_rejected_without_content_open(tmp_path, monkeypatch, field, value):
    src = replace(source(tmp_path, encoded()), **{field: value})
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: pytest.fail('content open before validation'))
    with pytest.raises(ValueError, match='^invalid_source$'):
        with reader((src,)):
            pass


def test_invalid_budget_object(tmp_path):
    with pytest.raises(ValueError, match='^invalid_budget$'):
        mod()._ReleaseFileReader((source(tmp_path, encoded()),), budget={})


def test_state_receipts_exhaustion_and_reuse(tmp_path):
    stream = reader((source(tmp_path, encoded([row()])),))
    for operation in [lambda: next(stream), lambda: iter(stream), lambda: stream.receipts]:
        with pytest.raises(ValueError, match='^reader_state$'):
            operation()
    with stream:
        assert next(stream).record_ordinal == 1
        with pytest.raises(ValueError, match='^reader_state$'):
            _ = stream.receipts
        with pytest.raises(ValueError, match='^reader_state$'):
            stream.__enter__()
        assert list(stream) == []
        assert list(stream) == []
    assert stream.receipts.logical_rows == 1
    for operation in [lambda: stream.__enter__(), lambda: next(stream), lambda: iter(stream)]:
        with pytest.raises(ValueError, match='^reader_state$'):
            operation()


def test_early_normal_exit_is_incomplete_and_releases_handle(tmp_path):
    src = source(tmp_path, encoded([row(), row()]))
    stream = reader((src,))
    with pytest.raises(ValueError, match='^incomplete_read$'):
        with stream:
            next(stream)
    with pytest.raises(ValueError, match='^reader_state$'):
        _ = stream.receipts
    src.path.unlink()


def test_consumer_exception_preserved_and_no_reuse(tmp_path):
    src = source(tmp_path, encoded([row()]))
    stream = reader((src,))
    primary = KeyboardInterrupt('consumer')
    with pytest.raises(KeyboardInterrupt) as caught:
        with stream:
            next(stream)
            raise primary
    assert caught.value is primary
    with pytest.raises(ValueError, match='^reader_state$'):
        next(stream)
    src.path.unlink()


def test_low_csv_field_environment_fails_before_open(tmp_path, monkeypatch):
    src = source(tmp_path, encoded())
    monkeypatch.setattr(mod().csv, 'field_size_limit', lambda: 4095)
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: pytest.fail('content read'))
    fail((src,), 'csv_field_limit_environment')


def test_duplicate_paths_and_hardlinks_rejected_copies_allowed(tmp_path):
    src = source(tmp_path, encoded([row()]))
    fail((src, src), 'duplicate_source')
    copy = source(tmp_path, encoded([row()]), 'copy.csv')
    assert len(read((src, copy))[0]) == 2
    link = tmp_path / 'hard.csv'
    try:
        os.link(src.path, link)
    except OSError:
        pytest.skip('host cannot create hard links')
    fail((src, replace(src, path=link)), 'duplicate_source')


@pytest.mark.parametrize('kind', ['directory', 'missing', 'symlink', 'ancestor_symlink'])
def test_paths_must_remain_ordinary(tmp_path, kind):
    src = source(tmp_path, encoded())
    path = tmp_path / 'bad'
    if kind == 'directory':
        path.mkdir()
    elif kind in ('symlink', 'ancestor_symlink'):
        try:
            if kind == 'symlink':
                path.symlink_to(src.path)
            else:
                target = tmp_path / 'ordinary'
                target.mkdir()
                path.symlink_to(target, target_is_directory=True)
                src.path.replace(target / src.path.name)
                path = path / src.path.name
        except OSError:
            pytest.skip('host lacks symbolic-link privilege')
    fail((replace(src, path=path),), 'invalid_source_path')


def test_elapsed_check_each_record_and_before_final_success(tmp_path, monkeypatch):
    src = source(tmp_path, encoded([row(), row()]))
    now = [0.0]
    monkeypatch.setattr(mod().time, 'monotonic', lambda: now[0])
    stream = reader((src,), max_elapsed_seconds=1)
    with pytest.raises(ValueError, match='^elapsed_time_cap$'):
        with stream:
            next(stream)
            now[0] = 2.0
            next(stream)
    src.path.unlink()


@pytest.mark.parametrize('kind', ['metadata', 'replace'])
def test_source_changes_detected_even_when_payload_prefetched(tmp_path, kind):
    src = source(tmp_path, encoded([row(), row()]))
    stream = reader((src,))
    with pytest.raises(ValueError, match='^source_changed$'):
        with stream:
            next(stream)
            if kind == 'metadata':
                current = src.path.stat()
                os.utime(src.path, ns=(current.st_atime_ns, current.st_mtime_ns+1000000000))
            else:
                other = tmp_path / 'replacement.csv'
                other.write_bytes(encoded([row(), row()]))
                try:
                    os.replace(other, src.path)
                except PermissionError:
                    pytest.skip('host denies replacement of open files')
            tuple(stream)
    src.path.unlink()


def test_open_failure_is_safe_and_closes_state(tmp_path, monkeypatch):
    src = source(tmp_path, encoded())
    def broken(*args, **kwargs):
        raise OSError('private invented.csv')
    monkeypatch.setattr(builtins, 'open', broken)
    fail((src,), 'source_io_error')


@pytest.mark.parametrize('extra', [0, 1])
def test_logical_record_character_boundary_includes_physical_newlines(tmp_path, monkeypatch, extra):
    # Lower only the test's record cap to exercise the exact guard without a megabyte fixture.
    payload = encoded([row(**{'Flow ID': 'a\nb\nc'})])
    data_record = payload[len(encoded()):].decode('utf-8')
    monkeypatch.setattr(mod(), '_MAX_RECORD_CHARS', len(data_record)-extra)
    # Header is longer than the tiny row, so independently widen this invented row.
    payload = encoded([row(**{'Flow ID': 'a\nb\nc'+'x'*2000})])
    data_record = payload[len(encoded()):].decode('utf-8')
    monkeypatch.setattr(mod(), '_MAX_RECORD_CHARS', len(data_record)-extra)
    if extra:
        fail((source(tmp_path, payload),), 'logical_record_char_cap')
    else:
        assert len(read((source(tmp_path, payload),))[0]) == 1


@pytest.mark.parametrize('deadline', [True, '10', [], object(), float('nan'), float('inf'), -float('inf')])
def test_invalid_shared_deadline_rejected(tmp_path, deadline):
    m = mod()
    with pytest.raises(ValueError, match='^invalid_deadline$'):
        m._ReleaseFileReader((source(tmp_path, encoded()),),
            budget=m.ReleaseReadBudget(10000, 100, 10), deadline=deadline)


@pytest.mark.parametrize('deadline,budget_seconds,expiry', [(11.0, 100, 11.1), (1000.0, 1, 11.1)])
def test_shared_deadline_cannot_extend_reader_budget(tmp_path, monkeypatch, deadline, budget_seconds, expiry):
    m = mod()
    src = source(tmp_path, encoded([row()]))
    now = [10.0]
    monkeypatch.setattr(m.time, 'monotonic', lambda: now[0])
    stream = m._ReleaseFileReader((src,), budget=m.ReleaseReadBudget(10000, 100, budget_seconds), deadline=deadline)
    with pytest.raises(ValueError, match='^elapsed_time_cap$'):
        with stream:
            next(stream)
            now[0] = expiry
            next(stream)


def test_expired_deadline_fails_before_content_open(tmp_path, monkeypatch):
    m = mod()
    src = source(tmp_path, encoded())
    monkeypatch.setattr(m.time, 'monotonic', lambda: 10.0)
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: pytest.fail('content read'))
    with pytest.raises(ValueError, match='^elapsed_time_cap$'):
        with m._ReleaseFileReader((src,), budget=m.ReleaseReadBudget(10000, 100, 10), deadline=9.0):
            pass


@pytest.mark.parametrize('read_size', [1, 2, 7, 65536])
def test_bom_unicode_and_crlf_decoder_cross_raw_boundaries(tmp_path, monkeypatch, read_size):
    payload = encoded([row(**{'Flow ID': '☃界\r\n"跨界', 'Src IP': '界'*1000}) for _ in range(25)], bom=True)
    src = source(tmp_path, payload)
    original = builtins.open
    handles = []
    class Short(io.FileIO):
        def readinto(self, buffer):
            return super().readinto(memoryview(buffer)[:read_size])
    def guarded(path, *args, **kwargs):
        if Path(path) == src.path:
            handle = Short(path, 'rb')
            handles.append(handle)
            return handle
        return original(path, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded)
    items, receipt = read((src,))
    assert len(items) == 25 and items[0].raw_fields[1] == '☃界\r\n"跨界'
    assert receipt.sources[0].source_sha256 == hashlib.sha256(payload).hexdigest()
    assert receipt.source_bytes_consumed == len(payload)
    assert len(handles) == 1 and handles[0].closed


def test_actual_byte_overread_is_at_most_one_before_buffering(tmp_path, monkeypatch):
    src = source(tmp_path, encoded([row()]))
    original = builtins.open
    observed, handles = [], []
    class Growing(io.FileIO):
        def readinto(self, buffer):
            if not observed:
                with original(src.path, 'ab', buffering=0) as output:
                    output.write(b'x'*100)
            n = super().readinto(buffer)
            observed.append((len(buffer), n))
            return n
    def guarded(path, *args, **kwargs):
        handle = Growing(path, 'rb')
        handles.append(handle)
        return handle
    monkeypatch.setattr(builtins, 'open', guarded)
    fail((src,), 'input_byte_cap', max_total_source_bytes=src.expected_bytes)
    assert sum(n for _, n in observed) == src.expected_bytes+1
    assert max(request for request, _ in observed) <= min(65536, src.expected_bytes+1)
    assert handles[0].closed


@pytest.mark.parametrize('extra,code', [(0, 'ragged_row'), (1, 'logical_record_char_cap')])
def test_fixed_megachar_record_guard_exact_and_over(tmp_path, extra, code):
    # 1024 short fields total exactly 1 MiB including separators and LF.
    malformed = (('x'*1023+',')*1023+'x'*1023+'x'*extra+'\n').encode()
    assert len(malformed) == 1048576+extra
    fail((source(tmp_path, encoded()+malformed),), code)


@pytest.mark.parametrize('failure', ['read', 'decode', 'hash', 'close'])
def test_every_stream_failure_releases_handles_and_suppresses_receipts(tmp_path, monkeypatch, failure):
    payload = encoded([row()])+(b'\xff' if failure == 'decode' else b'')
    src = source(tmp_path, payload)
    if failure == 'hash':
        src = replace(src, expected_sha256='0'*64)
    handles = []
    class Fault(io.FileIO):
        def readinto(self, buffer):
            if failure == 'read':
                raise OSError('private source details')
            return super().readinto(buffer)
        def close(self):
            super().close()
            if failure == 'close':
                raise OSError('private close details')
    def guarded(path, *args, **kwargs):
        handle = Fault(path, 'rb')
        handles.append(handle)
        return handle
    monkeypatch.setattr(builtins, 'open', guarded)
    stream = reader((src,))
    code = {'read': 'source_io_error', 'decode': 'invalid_utf8', 'hash': 'source_hash_mismatch',
            'close': 'source_close_error'}[failure]
    with pytest.raises(ValueError, match=f'^{code}$'):
        with stream:
            tuple(stream)
    assert len(handles) == 1 and handles[0].closed
    with pytest.raises(ValueError, match='^reader_state$'):
        _ = stream.receipts
    src.path.unlink()


def test_consumer_failure_wins_over_close_failure(tmp_path, monkeypatch):
    src = source(tmp_path, encoded([row()]))
    handles = []
    class BadClose(io.FileIO):
        def close(self):
            super().close()
            raise OSError('private close details')
    def guarded(path, *args, **kwargs):
        handle = BadClose(path, 'rb')
        handles.append(handle)
        return handle
    monkeypatch.setattr(builtins, 'open', guarded)
    primary = RuntimeError('consumer')
    with pytest.raises(RuntimeError) as caught:
        with reader((src,)) as stream:
            next(stream)
            raise primary
    assert caught.value is primary and handles[0].closed


def test_receipts_wait_for_all_sources_and_close(tmp_path, monkeypatch):
    first = source(tmp_path, encoded([row()]), 'a.csv')
    second = source(tmp_path, encoded([row()]), 'b.csv')
    handles = []
    class Spy(io.FileIO):
        pass
    def guarded(path, *args, **kwargs):
        assert not handles or handles[-1].closed
        handle = Spy(path, 'rb')
        handles.append(handle)
        return handle
    monkeypatch.setattr(builtins, 'open', guarded)
    with reader((first, second)) as stream:
        next(stream)
        next(stream)
        assert handles[0].closed and not handles[1].closed
        with pytest.raises(ValueError, match='^reader_state$'):
            _ = stream.receipts
        assert list(stream) == []
        assert all(handle.closed for handle in handles)
        assert len(stream.receipts.sources) == 2


def test_swallowed_read_failure_still_rejects_normal_incomplete_exit(tmp_path):
    src = replace(source(tmp_path, encoded([row()])), expected_sha256='0'*64)
    stream = reader((src,))
    with pytest.raises(ValueError, match='^incomplete_read$'):
        with stream:
            with pytest.raises(ValueError, match='^source_hash_mismatch$'):
                tuple(stream)
    with pytest.raises(ValueError, match='^reader_state$'):
        _ = stream.receipts


def test_context_exit_without_entry_or_repeated_exit_is_state_error(tmp_path):
    stream = reader((source(tmp_path, encoded()),))
    with pytest.raises(ValueError, match='^reader_state$'):
        stream.__exit__(None, None, None)
    with stream:
        tuple(stream)
    with pytest.raises(ValueError, match='^reader_state$'):
        stream.__exit__(None, None, None)
    assert stream.receipts.logical_rows == 0


def test_source_repr_never_exposes_unknown_metadata_values(tmp_path):
    m = mod()
    src = m.ReleaseFileSource(tmp_path / 'private-source.csv', 'private-count', 'private-raw-hash')
    assert 'private' not in repr(src)


def test_reparse_attribute_rejected_before_open_when_exposed(tmp_path, monkeypatch):
    src = source(tmp_path, encoded())
    original = Path.lstat
    class Reparse:
        st_mode = 0o100644
        st_file_attributes = 0x400
    def patched(path):
        return Reparse() if path == src.path else original(path)
    monkeypatch.setattr(Path, 'lstat', patched)
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: pytest.fail('content open'))
    fail((src,), 'invalid_source_path')


def test_deadline_checked_after_actual_read_before_yield(tmp_path, monkeypatch):
    m = mod()
    src = source(tmp_path, encoded([row()]))
    now = [0.0]
    handles = []
    monkeypatch.setattr(m.time, 'monotonic', lambda: now[0])
    class Slow(io.FileIO):
        def readinto(self, buffer):
            n = super().readinto(buffer)
            now[0] = 2.0
            return n
    def guarded(path, *args, **kwargs):
        handle = Slow(path, 'rb')
        handles.append(handle)
        return handle
    monkeypatch.setattr(builtins, 'open', guarded)
    fail((src,), 'elapsed_time_cap', max_elapsed_seconds=1)
    assert handles[0].closed


def test_not_yet_open_source_replacement_detected_without_opening_it(tmp_path, monkeypatch):
    first = source(tmp_path, encoded([row()]), 'a.csv')
    second = source(tmp_path, encoded([row()]), 'b.csv')
    original = builtins.open
    opened = []
    def guarded(path, *args, **kwargs):
        opened.append(Path(path))
        return original(path, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guarded)
    stream = reader((first, second))
    with pytest.raises(ValueError, match='^source_changed$'):
        with stream:
            next(stream)
            replacement = tmp_path / 'replacement.csv'
            replacement.write_bytes(encoded([row()]))
            os.replace(replacement, second.path)
            tuple(stream)
    assert opened == [first.path]
    with pytest.raises(ValueError, match='^reader_state$'):
        _ = stream.receipts
    first.path.unlink()
    second.path.unlink()


def test_last_source_hash_failure_discards_all_receipts(tmp_path):
    first = source(tmp_path, encoded([row()]), 'a.csv')
    second = replace(source(tmp_path, encoded([row()]), 'b.csv'), expected_sha256='0'*64)
    stream = reader((first, second))
    with pytest.raises(ValueError, match='^source_hash_mismatch$'):
        with stream:
            assert next(stream).source_ordinal == 0
            assert next(stream).source_ordinal == 1
            tuple(stream)
    with pytest.raises(ValueError, match='^reader_state$'):
        _ = stream.receipts
    first.path.unlink()
    second.path.unlink()
