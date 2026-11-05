"""Tiny newly invented 91-column sources; reference is the frozen Task7 API."""
import builtins
import csv
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest

from traffic_anomaly._release_csv import _parse_release_csv, ReleaseFixtureBudget
from traffic_anomaly._release_file_reader import ReleaseFileSource
from traffic_anomaly._release_minutes import ReleaseSegment, _aggregate_release_minutes

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tests/fixtures/release-91-artificial-v1.json').read_text(encoding='utf-8'))
HEADER = FIXTURE['header']
T = datetime(2026, 1, 1)
MINUTE = timedelta(minutes=1)


def mod():
    return importlib.import_module('traffic_anomaly._release_disk')


def row(i=0, **changes):
    values = dict(zip(HEADER, FIXTURE['rows'][0]))
    values.update(id=str(i), Timestamp='2026-01-01 00:00:00.000001')
    values['Flow Duration'] = '0'
    values.update(changes)
    return [values[name] for name in HEADER]


def encoded(rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(HEADER)
    writer.writerows(rows)
    return ('\ufeff'+stream.getvalue()).encode()


def segment(name='s', role='train', start=T, minutes=2):
    return ReleaseSegment(name, role, start, start+minutes*MINUTE)


def sources(tmp_path, populations):
    result = []
    payloads = []
    for i, rows in enumerate(populations):
        payload = encoded(rows)
        path = tmp_path / f'invented-{i}.csv'
        path.write_bytes(payload)
        payloads.append(payload)
        result.append(ReleaseFileSource(path, len(payload), hashlib.sha256(payload).hexdigest()))
    return tuple(result), tuple(payloads)


def budget(**changes):
    values = dict(max_total_source_bytes=2**21, max_rows=5000,
                  max_database_bytes=2**21, max_elapsed_seconds=60)
    values.update(changes)
    return mod().ReleaseDiskBudget(**values)


def execute(tmp_path, populations, segments=None, **changes):
    src, payloads = sources(tmp_path, populations)
    segments = (segment(),) if segments is None else segments
    result = mod()._aggregate_release_files(src, segments, scratch_directory=tmp_path/'scratch', budget=budget(**changes))
    assert result.minutes == _aggregate_release_minutes(
        _parse_release_csv(payloads, budget=ReleaseFixtureBudget()), segments, max_minutes=10000)
    assert not (tmp_path/'scratch').exists()
    assert result.resources.reader_receipts.source_content_open_count == len(src)
    assert result.resources.reader_receipts.source_bytes_consumed == sum(map(len, payloads))
    assert result.resources.cleanup_status == 'CLEANED'
    assert result.resources.sqlite_version == sqlite3.sqlite_version
    assert result.resources.database_bytes_at_close <= result.resources.observed_database_high_water_bytes <= changes.get('max_database_bytes', 2**21)
    assert any('duration_order' in detail for detail in result.resources.query_plan)
    assert not any('TEMP B-TREE' in detail.upper() for detail in result.resources.query_plan)
    return result


def failure(tmp_path, populations, code, **changes):
    src, _ = sources(tmp_path, populations)
    with pytest.raises(ValueError) as caught:
        mod()._aggregate_release_files(src, (segment(),), scratch_directory=tmp_path/'scratch', budget=budget(**changes))
    assert str(caught.value) == code
    assert 'invented-' not in repr(caught.value)
    assert not (tmp_path/'scratch').exists()
    for item in src:
        item.path.unlink()
    return caught.value


def test_exact_four_row_vector_and_frozen_resources(tmp_path):
    rows = [row(i, Protocol=str(p), **{'Flow Duration': str(i*1000000),
        'Total Fwd Packet': str(i), 'Total Bwd packets': str(b),
        'Total Length of Fwd Packet': str(i*10), 'Total Length of Bwd Packet': str(b*5), 'Label': label})
        for i,p,b,label in [(1,6,0,'BENIGN'),(2,17,1,'BENIGN'),(3,1,2,'BENIGN'),(4,0,0,'Portscan')]]
    result = execute(tmp_path, [rows])
    assert result.minutes.values[0] == (4.,10.,3.,100.,15.,1.,1.,1.,1.,4.,2.5,3.85,2.)
    assert result.resources.unique_fingerprints == 4
    assert result.resources.cross_file_duplicate_groups == 0
    assert result.minutes.source_authentication == 'NOT_AUTHENTICATED'
    for obj, key in [(result, 'minutes'), (result.resources, 'unique_fingerprints')]:
        with pytest.raises(FrozenInstanceError):
            setattr(obj, key, 0)


@pytest.mark.parametrize('case', ['empty', 'late_duplicate', 'outside_duplicate', 'lexical',
    'invalid_same_bucket', 'late_unplaced', 'all_unplaced', 'labels', 'same_role_crossing', 'gaps'])
def test_all_reference_fields_for_adversarial_small_populations(tmp_path, case):
    segments = (segment(),)
    populations = [[row(1)]]
    if case == 'empty': populations = [[]]
    elif case == 'late_duplicate': populations = [[row(1), row(2)], [row(3), row(1)]]
    elif case == 'outside_duplicate':
        outside = row(4, Timestamp='2026-01-02 00:00:00.000000')
        populations = [[row(1), outside], [outside]]
    elif case == 'lexical':
        populations = [[row(1), row(1, **{'Total Fwd Packet':'2.0'}),
            row(1, **{'Flow Bytes/s':'NaN'}), row(1, **{'Flow ID':'new'})]]
    elif case == 'invalid_same_bucket': populations = [[row(1), row(2, Protocol='200')]]
    elif case == 'late_unplaced': populations = [[row(1), row(2, Timestamp='2026-01-01 00:01:00.0')], [row(3, Timestamp='bad')]]
    elif case == 'all_unplaced': populations = [[row(1, Timestamp='bad'), row(2, **{'Flow Duration':'bad'})]]
    elif case == 'labels':
        populations = [[row(1, Protocol='0', Label='Portscan', **{'Flow Bytes/s':'NaN'}),
            row(2, Label='unknown'), row(3, Label='Botnet - Attempted', **{'Attempted Category':'0'}),
            row(4, Label='BENIGN', **{'Attempted Category':'0'})]]
    elif case == 'same_role_crossing':
        segments = (segment('a', minutes=1), segment('b', start=T+MINUTE, minutes=1))
        populations = [[row(1, Timestamp='2026-01-01 00:00:59.9', **{'Flow Duration':'100000'})]]
    elif case == 'gaps':
        segments = (segment('a', minutes=1), segment('b', 'test', T+3*MINUTE, 1))
        populations = [[row(1), row(2, Timestamp='2026-01-01 00:02:00.0'), row(3, Timestamp='2026-01-01 00:03:00.0')]]
    result = execute(tmp_path, populations, segments)
    if case == 'invalid_same_bucket':
        assert result.minutes.eligible_records == 1 and result.minutes.values[0] == (None,)*13
    if case == 'outside_duplicate':
        assert result.resources.cross_file_duplicate_groups == 1 and result.minutes.source_valid[0]


@pytest.mark.parametrize('durations', [[1], [1,2], [1,2,4], [0,0,1,1], [4,3,2,1], [21,1,21,2,21,3]])
def test_exact_rank_quantiles_without_float_or_histogram(tmp_path, durations):
    execute(tmp_path, [[row(i, **{'Flow Duration':str(value)}) for i,value in enumerate(durations)]])


@pytest.mark.parametrize('value', [str(2**63+5), str(2**53+1), '1e307'])
def test_counts_stay_python_integer_until_final_float(tmp_path, value):
    execute(tmp_path, [[row(1, **{'Total Fwd Packet': value}), row(2, **{'Total Fwd Packet': value})]])


def test_finite_materialization_overflow_aborts_entire_call(tmp_path):
    failure(tmp_path, [[row(1, **{'Total Fwd Packet':'1e4095'})]], 'numeric_materialization_overflow')


@pytest.mark.parametrize('name,value', [('max_rows', True), ('max_rows', 0), ('max_rows',2500001),
    ('max_total_source_bytes',2**31+1), ('max_database_bytes',65535), ('max_database_bytes',65537),
    ('max_database_bytes',2**31+4096), ('max_elapsed_seconds',1801), ('max_elapsed_seconds',0.5)])
def test_exact_budget_validation_before_files_or_scratch(tmp_path, name, value):
    with pytest.raises(ValueError, match='^invalid_disk_budget$'):
        mod()._aggregate_release_files((), (segment(),), scratch_directory=tmp_path/'scratch', budget=budget(**{name:value}))
    assert not (tmp_path/'scratch').exists()


@pytest.mark.parametrize('kind', ['existing', 'relative', 'string', 'parent_traversal', 'missing_parent'])
def test_new_explicit_scratch_only(tmp_path, kind):
    src, _ = sources(tmp_path, [[row()]])
    path = tmp_path/'scratch'
    if kind == 'existing': path.mkdir()
    elif kind == 'relative': path = Path('relative')
    elif kind == 'string': path = str(path)
    elif kind == 'parent_traversal': path = tmp_path/'x'/'..'/'scratch'
    else: path = tmp_path/'absent'/'scratch'
    with pytest.raises(ValueError, match='^invalid_scratch_directory$'):
        mod()._aggregate_release_files(src, (segment(),), scratch_directory=path, budget=budget())
    assert src[0].path.exists()


def test_all_source_preflight_before_scratch_creation(tmp_path):
    src, _ = sources(tmp_path, [[row()]])
    src[0].path.unlink()
    with pytest.raises(ValueError, match='^invalid_source_path$'):
        mod()._aggregate_release_files(src, (segment(),), scratch_directory=tmp_path/'scratch', budget=budget())
    assert not (tmp_path/'scratch').exists()


def test_late_hash_failure_has_no_result_and_removes_owned_scratch(tmp_path):
    src, _ = sources(tmp_path, [[row(1)], [row(2)]])
    src = (src[0], replace(src[1], expected_sha256='0'*64))
    with pytest.raises(ValueError, match='^source_hash_mismatch$'):
        mod()._aggregate_release_files(src, (segment(),), scratch_directory=tmp_path/'scratch', budget=budget())
    assert not (tmp_path/'scratch').exists()
    for item in src: item.path.unlink()


def test_hard_row_budget_does_not_return_truncated_minutes(tmp_path):
    failure(tmp_path, [[row(1),row(2)]], 'max_rows', max_rows=1)


def test_database_page_budget_is_actual_hard_main_file_limit(tmp_path):
    rows = [row(i, **{name:'1e3999' for name in ['Total Fwd Packet','Total Bwd packets',
        'Total Length of Fwd Packet','Total Length of Bwd Packet']}) for i in range(10)]
    failure(tmp_path, [rows], 'database_byte_cap', max_database_bytes=65536)


def test_sqlite_settings_limits_index_and_commit_are_real(tmp_path, monkeypatch):
    m = mod()
    original = sqlite3.connect
    captured = []
    class Connection(sqlite3.Connection):
        def close(self):
            settings = {key:self.execute('PRAGMA '+key).fetchone()[0] for key in
                ['page_size','max_page_count','cache_size','mmap_size','journal_mode','synchronous','temp_store','automatic_index']}
            limits = [self.getlimit(key) for key in [sqlite3.SQLITE_LIMIT_LENGTH,sqlite3.SQLITE_LIMIT_SQL_LENGTH,sqlite3.SQLITE_LIMIT_COLUMN]]
            captured.append((settings,limits))
            super().close()
    monkeypatch.setattr(m.sqlite3, 'connect', lambda path, **kwargs: original(path, factory=Connection, **kwargs))
    execute(tmp_path, [[row(i) for i in range(1001)]])
    settings, limits = captured[0]
    assert settings == dict(page_size=4096,max_page_count=512,cache_size=-32768,mmap_size=0,
        journal_mode='off',synchronous=0,temp_store=2,automatic_index=0)
    assert limits == [32768,8192,64]


@pytest.mark.parametrize('phase', ['insert','commit','phase2','phase3','progress','close'])
def test_sql_failures_discard_operation_and_release_handles(tmp_path, monkeypatch, phase):
    m = mod()
    original = sqlite3.connect
    handles = []
    class Connection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if ((phase == 'insert' and sql.startswith('INSERT'))
                    or (phase == 'phase2' and sql.startswith('SELECT n,'))
                    or (phase == 'phase3' and sql.startswith('SELECT minute_id,'))):
                raise sqlite3.OperationalError('private SQL details')
            return super().execute(sql, parameters)
        def commit(self):
            if phase == 'commit': raise sqlite3.OperationalError('private commit details')
            return super().commit()
        def set_progress_handler(self, callback, count):
            if phase == 'progress': raise sqlite3.OperationalError('private progress details')
            return super().set_progress_handler(callback,count)
        def close(self):
            super().close()
            if phase == 'close': raise sqlite3.OperationalError('private close details')
    def connect(path, **kwargs):
        handle = original(path,factory=Connection,**kwargs)
        handles.append(handle)
        return handle
    monkeypatch.setattr(m.sqlite3, 'connect', connect)
    failure(tmp_path, [[row(1)]], 'sqlite_close_error' if phase == 'close' else 'sqlite_error')
    assert len(handles) == 1
    with pytest.raises(sqlite3.ProgrammingError): handles[0].execute('SELECT 1')


def test_elapsed_deadline_shared_with_ingest_and_cleanup_still_runs(tmp_path, monkeypatch):
    m = mod()
    now = [0.0]
    monkeypatch.setattr(m.time, 'monotonic', lambda: now[0])
    original = sqlite3.connect
    class Connection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            value = super().execute(sql,parameters)
            if sql.startswith('INSERT'): now[0] = 61.0
            return value
    monkeypatch.setattr(m.sqlite3, 'connect',lambda path,**kwargs: original(path,factory=Connection,**kwargs))
    failure(tmp_path, [[row(1)]], 'elapsed_time_cap')


@pytest.mark.parametrize('kind', ['unknown_member','marker_token','database_replace','directory_replace'])
def test_changed_scratch_ownership_prevents_delete_and_marker_overwrite(tmp_path, monkeypatch, kind):
    m = mod()
    src, _ = sources(tmp_path, [[row(1)]])
    scratch = tmp_path/'scratch'
    original = sqlite3.connect
    replacement = None
    class Connection(sqlite3.Connection):
        def commit(self):
            super().commit()
            if not (scratch/'owner.json').exists(): return
            if getattr(self,'changed',False): return
            self.changed = True
            if kind == 'unknown_member': (scratch/'unexpected').write_bytes(b'keep')
            elif kind == 'marker_token':
                data=json.loads((scratch/'owner.json').read_text()); data['token']='changed'
                (scratch/'owner.json').write_text(json.dumps(data))
            elif kind == 'database_replace':
                try:
                    (scratch/'scratch.sqlite3').rename(scratch/'moved.sqlite3')
                except PermissionError: pytest.skip('host denies replacement of open database')
                (scratch/'scratch.sqlite3').write_bytes(b'keep')
            else:
                try: scratch.rename(tmp_path/'moved-scratch')
                except PermissionError: pytest.skip('host denies replacement of open directory')
                scratch.mkdir(); (scratch/'replacement').write_bytes(b'keep')
    monkeypatch.setattr(m.sqlite3, 'connect', lambda path,**kwargs: original(path,factory=Connection,**kwargs))
    with pytest.raises(ValueError) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=scratch,budget=budget())
    assert str(caught.value)=='scratch_ownership_changed'
    assert getattr(caught.value,'cleanup_failed',False)
    assert scratch.exists()
    if kind == 'marker_token': assert json.loads((scratch/'owner.json').read_text())['token']=='changed'
    if kind == 'unknown_member': assert (scratch/'unexpected').read_bytes()==b'keep'
    if kind == 'directory_replace': assert (scratch/'replacement').read_bytes()==b'keep'


def test_cleanup_failure_prevents_success_marks_owned_scratch_aborted(tmp_path, monkeypatch):
    m = mod()
    src, _ = sources(tmp_path, [[row(1)]])
    original = Path.unlink
    def blocked(path, *args, **kwargs):
        if path.name == 'scratch.sqlite3': raise PermissionError('private path')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',blocked)
    with pytest.raises(ValueError, match='^scratch_cleanup_failed$'):
        m._aggregate_release_files(src,(segment(),),scratch_directory=tmp_path/'scratch',budget=budget())
    marker=json.loads((tmp_path/'scratch'/'owner.json').read_text())
    assert marker['status']=='ABORTED_SCRATCH_UNUSABLE' and 'COMPLETE' not in marker.values()


def test_primary_error_preserved_when_cleanup_also_fails(tmp_path, monkeypatch):
    m = mod()
    src,_ = sources(tmp_path,[[row(1)]])
    src=(replace(src[0],expected_sha256='0'*64),)
    original=Path.unlink
    def blocked(path,*args,**kwargs):
        if path.name=='scratch.sqlite3': raise OSError('private')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',blocked)
    with pytest.raises(ValueError) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=tmp_path/'scratch',budget=budget())
    assert str(caught.value)=='source_hash_mismatch'
    assert caught.value.cleanup_failed and 'cleanup_failed' in caught.value.__notes__


def test_low_integer_string_limit_in_isolated_process(tmp_path):
    # No parent-global setting mutation and no source content open is permitted.
    code = """import builtins,pathlib
from traffic_anomaly._release_disk import _aggregate_release_files,ReleaseDiskBudget
from traffic_anomaly._release_file_reader import ReleaseFileSource
from traffic_anomaly._release_minutes import ReleaseSegment
from datetime import datetime,timedelta
p=pathlib.Path(__import__('sys').argv[1])
def blocked(*a,**k): raise AssertionError('content open')
builtins.open=blocked
try:
 _aggregate_release_files((ReleaseFileSource(p/'absent.csv',0,'0'*64),),(ReleaseSegment('s','train',datetime(2026,1,1),datetime(2026,1,1,0,1)),),scratch_directory=p/'scratch',budget=ReleaseDiskBudget(10000,10,65536,10))
except ValueError as error:
 assert str(error)=='integer_string_limit_environment',str(error)
else: raise AssertionError('success')
assert not (p/'scratch').exists()
"""
    completed=subprocess.run([sys.executable,'-X','utf8','-X','int_max_str_digits=640','-c',code,str(tmp_path)],capture_output=True,text=True)
    assert completed.returncode==0,completed.stderr


@pytest.mark.parametrize('member,replace_file', [('owner.json',False),('owner.json',True),('scratch.sqlite3',True)])
def test_failed_exclusive_create_does_not_own_replacement_file(tmp_path,monkeypatch,member,replace_file):
    m=mod()
    src,_=sources(tmp_path,[[row(1)]])
    original=builtins.open
    scratch=tmp_path/'scratch'
    def blocked(path,mode='r',*args,**kwargs):
        if Path(path).name==member and mode=='xb':
            if replace_file:
                with original(path,'wb') as handle: handle.write(b'keep replacement')
            raise OSError('private create details')
        return original(path,mode,*args,**kwargs)
    monkeypatch.setattr(builtins,'open',blocked)
    with pytest.raises(ValueError) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=scratch,budget=budget())
    assert str(caught.value)=='scratch_io_error'
    if replace_file:
        assert caught.value.cleanup_failed
        assert (scratch/member).read_bytes()==b'keep replacement'
        if member=='scratch.sqlite3':
            assert json.loads((scratch/'owner.json').read_text())['status']=='INCOMPLETE'
    else:
        assert not scratch.exists()


@pytest.mark.parametrize('phase',['phase2','phase3'])
def test_same_deadline_applies_to_post_ingest_phases(tmp_path,monkeypatch,phase):
    m=mod()
    now=[0.0]
    monkeypatch.setattr(m.time,'monotonic',lambda:now[0])
    original=sqlite3.connect
    class Connection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            cursor=super().execute(sql,parameters)
            if ((phase=='phase2' and sql.startswith('SELECT n,'))
                    or (phase=='phase3' and sql.startswith('SELECT minute_id,'))): now[0]=61.0
            return cursor
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    failure(tmp_path,[[row(1)]],'elapsed_time_cap')


def test_actual_sqlite_progress_callback_interrupts_expired_operation(tmp_path,monkeypatch):
    m=mod()
    now=[0.0]
    called=[]
    original=m._Deadline.progress
    monkeypatch.setattr(m.time,'monotonic',lambda:now[0])
    def progress(clock):
        called.append(True)
        now[0]=61.0
        return original(clock)
    monkeypatch.setattr(m._Deadline,'progress',progress)
    failure(tmp_path,[[row(i) for i in range(300)]],'elapsed_time_cap')
    assert called


@pytest.mark.parametrize('phase,code',[('phase2','record_conservation_failure'),('phase3','quantile_consistency_failure')])
def test_missing_cursor_record_fails_conservation_or_rank_check(tmp_path,monkeypatch,phase,code):
    m=mod()
    original=sqlite3.connect
    class Cursor:
        def __init__(self,original): self.original=original
        def __iter__(self):
            next(self.original,None)
            yield from self.original
        def close(self): self.original.close()
    class Connection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            cursor=super().execute(sql,parameters)
            if ((phase=='phase2' and sql.startswith('SELECT n,'))
                    or (phase=='phase3' and sql.startswith('SELECT minute_id,'))): return Cursor(cursor)
            return cursor
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    failure(tmp_path,[[row(1),row(2)]],code)


@pytest.mark.parametrize('kind',['limit','pragma','plan'])
def test_incompatible_sqlite_environment_rejected_before_source_content(tmp_path,monkeypatch,kind):
    m=mod()
    src,_=sources(tmp_path,[[row(1)]])
    original=sqlite3.connect
    real_open=builtins.open
    class WrongCursor:
        def __init__(self,cursor,sql): self.cursor,self.sql=cursor,sql
        def fetchone(self): return (1,)
        def __iter__(self): return iter([(0,0,0,'USE TEMP B-TREE FOR ORDER BY')])
        def close(self): self.cursor.close()
    class Connection(sqlite3.Connection):
        def getlimit(self,category):
            actual=super().getlimit(category)
            return actual-1 if kind=='limit' else actual
        def execute(self,sql,parameters=()):
            cursor=super().execute(sql,parameters)
            if ((kind=='pragma' and sql=='PRAGMA mmap_size')
                    or (kind=='plan' and sql.startswith('EXPLAIN QUERY PLAN'))): return WrongCursor(cursor,sql)
            return cursor
    def guarded(path,*args,**kwargs):
        assert Path(path)!=src[0].path,'source opened before environment preflight'
        return real_open(path,*args,**kwargs)
    monkeypatch.setattr(builtins,'open',guarded)
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    with pytest.raises(ValueError) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=tmp_path/'scratch',budget=budget())
    assert str(caught.value)==('sqlite_query_plan' if kind=='plan' else 'sqlite_environment')
    assert not (tmp_path/'scratch').exists()


def test_database_size_is_checked_after_connection_close(tmp_path,monkeypatch):
    m=mod()
    original=sqlite3.connect
    path=tmp_path/'scratch'/'scratch.sqlite3'
    class Connection(sqlite3.Connection):
        def close(self):
            super().close()
            with path.open('ab') as handle: handle.write(b'x')
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    failure(tmp_path,[[row(1)]],'database_size_mismatch')


def test_post_close_replacement_is_preserved(tmp_path,monkeypatch):
    m=mod()
    src,_=sources(tmp_path,[[row(1)]])
    original=sqlite3.connect
    scratch=tmp_path/'scratch'
    class Connection(sqlite3.Connection):
        def close(self):
            super().close()
            path=scratch/'scratch.sqlite3'
            replacement=tmp_path/'replacement'
            replacement.write_bytes(b'keep replacement')
            os.replace(replacement,path)
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    with pytest.raises(ValueError) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=scratch,budget=budget())
    assert str(caught.value) in ('scratch_ownership_changed','scratch_cleanup_failed')
    assert (scratch/'scratch.sqlite3').read_bytes()==b'keep replacement'
    assert json.loads((scratch/'owner.json').read_text())['status']=='INCOMPLETE'


def test_no_tools_models_network_and_no_raw_result_values(tmp_path,monkeypatch):
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        assert name.split('.')[0] not in {'tools','torch','sklearn','pyarrow'},name
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    monkeypatch.setattr(socket,'socket',lambda *a,**k:pytest.fail('network attempt'))
    result=execute(tmp_path,[[row(1,Label='private-label',**{'Flow ID':'private-flow'})]])
    assert 'private-label' not in repr(result) and 'private-flow' not in repr(result)
    assert str(tmp_path) not in repr(result)


def test_deep_invalid_marker_is_fixed_ownership_error_and_never_overwritten(tmp_path,monkeypatch):
    m=mod()
    src,_=sources(tmp_path,[[row(1)]])
    original=sqlite3.connect
    marker=tmp_path/'scratch'/'owner.json'
    malformed=b'['*7000+b'0'+b']'*7000
    class Connection(sqlite3.Connection):
        def commit(self):
            super().commit()
            marker.write_bytes(malformed)
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    with pytest.raises(ValueError) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=tmp_path/'scratch',budget=budget())
    assert str(caught.value)=='scratch_ownership_changed'
    assert caught.value.cleanup_failed and marker.read_bytes()==malformed


def test_expired_sql_error_suppresses_original_private_exception_context(tmp_path,monkeypatch):
    m=mod()
    src,_=sources(tmp_path,[[row(1)]])
    now=[0.0]
    original=sqlite3.connect
    monkeypatch.setattr(m.time,'monotonic',lambda:now[0])
    class Connection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            if sql.startswith('INSERT'):
                now[0]=61.0
                raise sqlite3.OperationalError('private payload')
            return super().execute(sql,parameters)
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    with pytest.raises(ValueError) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=tmp_path/'scratch',budget=budget())
    assert str(caught.value)=='elapsed_time_cap'
    assert caught.value.__suppress_context__
    assert not (tmp_path/'scratch').exists()


def test_keyboard_interrupt_during_reduction_preserved_after_cleanup(tmp_path,monkeypatch):
    m=mod()
    src,_=sources(tmp_path,[[row(1)]])
    original=sqlite3.connect
    primary=KeyboardInterrupt('consumer interrupt')
    class Connection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            if sql.startswith('SELECT n,'): raise primary
            return super().execute(sql,parameters)
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    with pytest.raises(KeyboardInterrupt) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=tmp_path/'scratch',budget=budget())
    assert caught.value is primary and not (tmp_path/'scratch').exists()


def test_cursor_close_failure_prevents_success(tmp_path,monkeypatch):
    m=mod()
    original=sqlite3.connect
    class Cursor:
        def __init__(self,cursor): self.cursor=cursor
        def close(self):
            self.cursor.close()
            raise sqlite3.OperationalError('private close details')
    class Connection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            cursor=super().execute(sql,parameters)
            return Cursor(cursor) if sql=='PRAGMA page_size=4096' else cursor
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    failure(tmp_path,[[row(1)]],'sqlite_close_error')


def test_commit_every_thousand_rows_across_source_boundaries(tmp_path,monkeypatch):
    m=mod()
    original=sqlite3.connect
    observed=[]
    inserted=[0]
    class Connection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            cursor=super().execute(sql,parameters)
            if sql.startswith('INSERT'): inserted[0]+=1
            return cursor
        def commit(self):
            observed.append(inserted[0])
            return super().commit()
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    execute(tmp_path,[[row(i) for i in range(601)],[row(i) for i in range(601,1001)]])
    assert observed==[0,1000,1001]


def test_isolated_sqlite_temp_and_import_boundaries(tmp_path):
    src,_=sources(tmp_path,[[row(i) for i in range(50)]])
    dedicated=tmp_path/'dedicated-temp'
    dedicated.mkdir()
    code="""import builtins,json,pathlib,socket,sqlite3,sys
root=pathlib.Path(sys.argv[1]); temporary=root/'dedicated-temp'; scratch=root/'scratch'
original_import=builtins.__import__
def guarded_import(name,*a,**k):
 assert name.split('.')[0] not in {'tools','torch','sklearn','pyarrow'},name
 return original_import(name,*a,**k)
builtins.__import__=guarded_import
def network(*a,**k): raise AssertionError('network attempt')
socket.socket=network
from traffic_anomaly._release_disk import _aggregate_release_files,ReleaseDiskBudget
from traffic_anomaly._release_file_reader import ReleaseFileSource
from traffic_anomaly._release_minutes import ReleaseSegment
from datetime import datetime
real_connect=sqlite3.connect
statements=[]
class Connection(sqlite3.Connection):
 def execute(self,sql,parameters=()):
  statements.append(sql)
  cursor=super().execute(sql,parameters)
  assert {p.name for p in scratch.iterdir()}=={'owner.json','scratch.sqlite3'}
  assert list(temporary.iterdir())==[]
  return cursor
sqlite3.connect=lambda path,**kwargs:real_connect(path,factory=Connection,**kwargs)
source=ReleaseFileSource(root/'invented-0.csv',int(sys.argv[2]),sys.argv[3])
result=_aggregate_release_files((source,),(ReleaseSegment('s','train',datetime(2026,1,1),datetime(2026,1,1,0,2)),),scratch_directory=scratch,budget=ReleaseDiskBudget(2**21,5000,2**21,60))
assert result.minutes.raw_records==50 and result.minutes.eligible_records==50
assert not scratch.exists() and list(temporary.iterdir())==[]
assert not any(part in sql.upper() for sql in statements for part in (' GROUP BY ',' DISTINCT ',' SUM(', ' CAST(', ' ATTACH ', 'VACUUM','ANALYZE',' JOIN '))
assert sum(sql.startswith('CREATE INDEX') for sql in statements)==1
assert next(i for i,sql in enumerate(statements) if sql.startswith('CREATE INDEX')) < next(i for i,sql in enumerate(statements) if sql.startswith('INSERT'))
print(json.dumps({'sqlite_version':sqlite3.sqlite_version,'query_plan':result.resources.query_plan,'statement_count':len(statements),'temporary_members':0}))
"""
    environment=os.environ.copy()
    environment.update(TMP=str(dedicated),TEMP=str(dedicated),SQLITE_TMPDIR=str(dedicated))
    completed=subprocess.run([sys.executable,'-X','utf8','-c',code,str(tmp_path),
        str(src[0].expected_bytes),src[0].expected_sha256],env=environment,capture_output=True,text=True)
    assert completed.returncode==0,completed.stderr
    evidence=json.loads(completed.stdout)
    assert evidence['temporary_members']==0 and evidence['sqlite_version']==sqlite3.sqlite_version


@pytest.mark.parametrize('phase',['cursor_close','connection_close','cleanup'])
def test_first_keyboard_interrupt_during_close_or_cleanup_keeps_identity(tmp_path,monkeypatch,phase):
    m=mod()
    src,_=sources(tmp_path,[[row(1)]])
    original=sqlite3.connect
    primary=KeyboardInterrupt('stop')
    real_unlink=Path.unlink
    class Cursor:
        def __init__(self,cursor): self.cursor=cursor
        def close(self):
            self.cursor.close()
            raise primary
    class Connection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            cursor=super().execute(sql,parameters)
            return Cursor(cursor) if phase=='cursor_close' and sql=='PRAGMA page_size=4096' else cursor
        def close(self):
            super().close()
            if phase=='connection_close': raise primary
    def interrupted(path,*args,**kwargs):
        if phase=='cleanup' and path.name=='scratch.sqlite3': raise primary
        return real_unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',interrupted)
    monkeypatch.setattr(m.sqlite3,'connect',lambda path,**kwargs:original(path,factory=Connection,**kwargs))
    with pytest.raises(KeyboardInterrupt) as caught:
        m._aggregate_release_files(src,(segment(),),scratch_directory=tmp_path/'scratch',budget=budget())
    assert caught.value is primary
    if phase=='cleanup':
        assert primary.cleanup_failed
        assert json.loads((tmp_path/'scratch'/'owner.json').read_text())['status']=='ABORTED_SCRATCH_UNUSABLE'
    else:
        assert not (tmp_path/'scratch').exists()
