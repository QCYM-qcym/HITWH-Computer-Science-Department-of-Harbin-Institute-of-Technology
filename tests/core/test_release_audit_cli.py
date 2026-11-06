"""New tiny artificial CSVs only; no source fixture or model execution."""
import csv
from datetime import datetime, timedelta
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sys

import pytest

from traffic_anomaly._release_csv import EXPECTED_HEADER


def mod():
    return importlib.import_module('traffic_anomaly.release_audit_cli')


def setup_case(tmp_path, *, rows=1, minutes=2):
    source = tmp_path/'人工 source.csv'
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(EXPECTED_HEADER)
    for i in range(rows):
        row = dict.fromkeys(EXPECTED_HEADER, '0')
        row.update({'id': str(i), 'Flow ID': 'SECRET-FLOW', 'Src IP': '192.0.2.1',
                    'Dst IP': '198.51.100.1', 'Timestamp': '2026-01-01 00:00:01.000000',
                    'Flow Duration': '1000000', 'Protocol': '6', 'Label': 'BENIGN',
                    'Attempted Category': '-1'})
        writer.writerow([row[k] for k in EXPECTED_HEADER])
    payload = stream.getvalue().encode()
    source.write_bytes(payload)
    spec = dict(version=1, sources=[dict(path=source.name, bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest())],
        segments=[dict(id='SECRET-SEGMENT', role='train', start='2026-01-01T00:00',
                       end=(datetime(2026,1,1)+timedelta(minutes=minutes)).isoformat())],
        budget=dict(max_total_source_bytes=8*1024*1024, max_rows=10000,
                    max_database_bytes=32*1024*1024, max_elapsed_seconds=30, max_minutes=10000))
    path = tmp_path/'audit spec.json'
    path.write_text(json.dumps(spec), 'utf-8')
    return path, source, spec, tmp_path/'new 输出'


def save(path, spec):
    path.write_text(json.dumps(spec), 'utf-8')


def invoke(path, output, capsys):
    code = mod().main(['--spec', str(path), '--output', str(output)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_complete_summary_has_checked_receipts_minutes_and_no_identifiers(tmp_path, capsys, monkeypatch):
    path, source, spec, output = setup_case(tmp_path)
    monkeypatch.chdir(tmp_path.parent)  # relative sources are relative to spec, not cwd
    before = source.read_bytes()
    code, stdout, stderr = invoke(path, output, capsys)
    assert code == 0 and stderr == ''
    assert json.loads(stdout) == dict(status='COMPLETE', version=1)
    assert {p.name for p in output.iterdir()} == {'report.json', 'COMPLETE.json'}
    report = json.loads((output/'report.json').read_text('utf-8'))
    marker = json.loads((output/'COMPLETE.json').read_text('utf-8'))
    payload = (output/'report.json').read_bytes()
    assert marker == dict(version=1, status='COMPLETE', report=dict(
        sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload)))
    assert report['source_authentication'] == 'NOT_AUTHENTICATED'
    assert report['time_basis'] == 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'
    assert report['limits'] == spec['budget']
    assert report['sources'] == [dict(ordinal=0, bytes=len(before),
        sha256=hashlib.sha256(before).hexdigest(), logical_rows=1)]
    assert report['global']['raw_records'] == report['global']['eligible_records'] == 1
    assert report['segments'] == [dict(ordinal=0, role='train', calendar_minutes=2,
        valid_minutes=1, invalid_minutes=1, policies={p: dict(normal=1, attack=0, unknown=1)
                                                   for p in ('P_U','P_B','P_A')})]
    assert report['resources']['cleanup_status'] == 'CLEANED'
    assert report['resources']['database_high_water_observation'] == 'DISCRETE_SAMPLES'
    text = json.dumps(report)
    for secret in ('SECRET', str(tmp_path), source.name, 'Timestamp', 'query_plan',
                   'feature_names', '192.0.2.1', 'values', '2026-01-01'):
        assert secret not in text
    assert source.read_bytes() == before


@pytest.mark.parametrize('field,value', [
    ('max_rows',10001),('max_rows',True),('max_rows',1.0),('max_rows',0),
    ('max_minutes',10001),('max_minutes',0),('max_elapsed_seconds',31),
    ('max_total_source_bytes',8*1024*1024+1),('max_database_bytes',65535),
    ('max_database_bytes',65537),('max_database_bytes',32*1024*1024+4096)])
def test_budget_rejected_before_output_creation(tmp_path, capsys, field, value):
    path, _, spec, output = setup_case(tmp_path)
    spec['budget'][field] = value
    save(path,spec)
    code, _, stderr = invoke(path,output,capsys)
    assert code == 2 and json.loads(stderr)['error'] == 'INVALID_SPEC'
    assert not output.exists()


@pytest.mark.parametrize('mutation', ['unknown','duplicate','nan','oversize','utf8','empty'])
def test_invalid_spec_is_bounded_and_private(tmp_path,capsys,mutation):
    path,_,spec,output=setup_case(tmp_path)
    if mutation=='unknown': spec['SECRET']='x';save(path,spec)
    elif mutation=='duplicate': path.write_text('{"version":1,"version":1}', 'utf-8')
    elif mutation=='nan': path.write_text('{"version":NaN}', 'utf-8')
    elif mutation=='oversize': path.write_bytes(b' '*65537)
    elif mutation=='utf8': path.write_bytes(b'\xff')
    else: path.write_bytes(b'')
    code,stdout,stderr=invoke(path,output,capsys)
    assert code==2 and stdout=='' and 'SECRET' not in stderr and str(tmp_path) not in stderr
    assert not output.exists()


@pytest.mark.parametrize('bad', ['../source.csv','C:relative.csv','\\\\host\\share\\x',
    '\\\\?\\C:\\x','file.csv:stream','\\rooted.csv'])
def test_unsafe_source_lexical_paths_rejected(tmp_path,capsys,bad):
    path,_,spec,output=setup_case(tmp_path);spec['sources'][0]['path']=bad;save(path,spec)
    assert invoke(path,output,capsys)[0]==2
    assert not output.exists()


@pytest.mark.parametrize('kind',['same_source','hardlink','spec_as_source','wrong_size',
    'existing_output','relative_output','output_contains_source','minute_cap','segment_order'])
def test_preflight_aliases_paths_sizes_and_axis_stop_before_mkdir(tmp_path,capsys,kind):
    path,source,spec,output=setup_case(tmp_path)
    if kind=='same_source': spec['sources']*=2
    elif kind=='hardlink':
        alias=tmp_path/'alias.csv'
        try: os.link(source,alias)
        except OSError: pytest.skip('host hardlink unavailable')
        spec['sources'].append(dict(spec['sources'][0],path=alias.name))
    elif kind=='spec_as_source':
        spec['sources'][0]['path']=path.name
    elif kind=='wrong_size': spec['sources'][0]['bytes']+=1
    elif kind=='existing_output': output.mkdir()
    elif kind=='relative_output': output=Path('relative output')
    elif kind=='output_contains_source': output=tmp_path
    elif kind=='minute_cap': spec['budget']['max_minutes']=1
    elif kind=='segment_order': spec['segments']*=2
    save(path,spec)
    code,_,_=invoke(path,output,capsys)
    assert code==2
    if kind not in ('existing_output','output_contains_source'): assert not output.exists()


def test_hash_mismatch_leaves_incomplete_output_and_no_scratch(tmp_path,capsys):
    path,_,spec,output=setup_case(tmp_path);spec['sources'][0]['sha256']='0'*64;save(path,spec)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']=='SOURCE_HASH_MISMATCH'
    assert output.is_dir() and list(output.iterdir())==[]


@pytest.mark.parametrize('field,value,error',[('max_rows',1,'MAX_ROWS'),
    ('max_total_source_bytes',1,'INPUT_BYTE_CAP')])
def test_tightened_resource_limits_are_enforced(tmp_path,capsys,field,value,error):
    path,_,spec,output=setup_case(tmp_path,rows=2)
    spec['budget'][field]=value;save(path,spec)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']==error
    assert not (output/'COMPLETE.json').exists()


@pytest.mark.parametrize('failure,expected',[(ValueError('source_secret'), 'INTERNAL_ERROR'),
    (ValueError('source_hash_mismatch','SECRET'),'INTERNAL_ERROR'),
    (RuntimeError('SECRET'),'INTERNAL_ERROR'),(KeyboardInterrupt('SECRET'),'INTERRUPTED')])
def test_error_mapping_never_echoes_unknown_arguments(tmp_path,capsys,monkeypatch,failure,expected):
    path,_,_,output=setup_case(tmp_path)
    def fail(*a,**kw): raise failure
    monkeypatch.setattr(mod(),'_aggregate_release_files',fail)
    code,stdout,stderr=invoke(path,output,capsys)
    assert code==2 and stdout=='' and json.loads(stderr)==dict(error=expected)
    assert 'SECRET' not in stderr and not (output/'COMPLETE.json').exists()


def test_report_write_failure_preserves_incomplete_file(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    original=Path.open
    def injected(self,*a,**kw):
        if self==output/'COMPLETE.json' and a and a[0]=='xb': raise OSError('SECRET')
        return original(self,*a,**kw)
    monkeypatch.setattr(Path,'open',injected)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']=='OUTPUT_ERROR'
    assert (output/'report.json').is_file() and not (output/'COMPLETE.json').exists()


def test_post_commit_stdout_failure_keeps_valid_complete_report(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    def fail(value): raise BrokenPipeError('SECRET')
    monkeypatch.setattr(mod(),'_success_stdout',fail)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']=='OUTPUT_ERROR'
    assert {p.name for p in output.iterdir()}=={'report.json','COMPLETE.json'}
    assert json.loads((output/'COMPLETE.json').read_text())['status']=='COMPLETE'


def test_unknown_output_member_blocks_completion(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    original=mod()._aggregate_release_files
    def injected(*a,**kw):
        result=original(*a,**kw)
        (output/'unknown').write_text('SECRET')
        return result
    monkeypatch.setattr(mod(),'_aggregate_release_files',injected)
    code,_,_=invoke(path,output,capsys)
    assert code==2 and (output/'unknown').read_text()=='SECRET'
    assert not (output/'COMPLETE.json').exists()


def test_cleanup_failure_flag_is_explicit_bool_only(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    error=ValueError('source_hash_mismatch')
    error.cleanup_failed=True
    error.add_note('SECRET PATH')
    def fail(*a,**kw): raise error
    monkeypatch.setattr(mod(),'_aggregate_release_files',fail)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)==dict(error='SOURCE_HASH_MISMATCH',cleanup_failed=True)


def test_unknown_primary_failure_retains_safe_cleanup_flag(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    error=RuntimeError('SECRET');error.cleanup_failed=True
    def fail(*a,**kw): raise error
    monkeypatch.setattr(mod(),'_aggregate_release_files',fail)
    assert json.loads(invoke(path,output,capsys)[2])==dict(cleanup_failed=True,error='INTERNAL_ERROR')


def test_source_content_is_opened_only_once_by_reader(tmp_path,capsys,monkeypatch):
    import builtins
    path,source,_,output=setup_case(tmp_path)
    original=builtins.open
    opens=[]
    def observed(file,*args,**kwargs):
        if isinstance(file,(str,Path)) and Path(file)==source: opens.append(args)
        return original(file,*args,**kwargs)
    monkeypatch.setattr(builtins,'open',observed)
    assert invoke(path,output,capsys)[0]==0
    assert len(opens)==1


def test_source_metadata_change_during_spec_read_rejected(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    original=mod()._read_spec
    def changed(p):
        data,identity=original(p)
        p.write_bytes(p.read_bytes()+b' ')
        return data,identity
    monkeypatch.setattr(mod(),'_read_spec',changed)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']=='SPEC_CHANGED'
    assert not output.exists()


def test_seven_segments_have_minute_populations_and_no_ids(tmp_path,capsys):
    path,_,spec,output=setup_case(tmp_path)
    base=datetime(2026,1,1)
    spec['segments']=[dict(id='PRIVATE-%d'%i,role=('train','train','validation','validation',
        'calibration','test','test')[i],start=(base+timedelta(minutes=i*2)).isoformat(),
        end=(base+timedelta(minutes=i*2+1)).isoformat()) for i in range(7)]
    save(path,spec)
    assert invoke(path,output,capsys)[0]==0
    report=json.loads((output/'report.json').read_text('utf-8'))
    assert len(report['segments'])==7
    assert [s['ordinal'] for s in report['segments']]==list(range(7))
    assert sum(s['valid_minutes'] for s in report['segments'])==1
    assert sum(s['calendar_minutes'] for s in report['segments'])==7
    assert 'PRIVATE' not in json.dumps(report)


def test_symlink_source_is_rejected_without_following(tmp_path,capsys):
    path,source,spec,output=setup_case(tmp_path)
    link=tmp_path/'linked.csv'
    try: link.symlink_to(source)
    except OSError: pytest.skip('host symlink privilege unavailable')
    spec['sources'][0]['path']=link.name;save(path,spec)
    assert invoke(path,output,capsys)[0]==2 and not output.exists()


def test_real_cli_fresh_process_blocks_model_and_network_imports(tmp_path):
    import subprocess
    path,_,_,output=setup_case(tmp_path)
    code='''import importlib.abc,runpy,socket,sys
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'torch','sklearn','joblib'}: raise AssertionError('MODEL')
sys.meta_path.insert(0,Guard())
def deny(*a,**kw): raise AssertionError('NETWORK')
socket.socket=deny
runpy.run_module('traffic_anomaly.release_audit_cli',run_name='__main__')
'''
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[2]/'src/core'),
             PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,'-X','utf8','-c',code,'--spec',str(path),
        '--output',str(output)],cwd=tmp_path,env=env,capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==dict(version=1,status='COMPLETE')


@pytest.mark.parametrize('where',['spec','source','segment','budget'])
def test_unknown_fields_rejected_at_each_spec_level(tmp_path,capsys,where):
    path,_,spec,output=setup_case(tmp_path)
    target={'spec':spec,'source':spec['sources'][0], 'segment':spec['segments'][0],
            'budget':spec['budget']}[where]
    target['SECRET-UNKNOWN']=1;save(path,spec)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']=='INVALID_SPEC'
    assert not output.exists()


@pytest.mark.parametrize('field,value',[('bytes',True),('bytes',1.0),('bytes',-1),
    ('sha256','A'*64),('sha256',None),('path',7)])
def test_source_descriptor_types_are_strict(tmp_path,capsys,field,value):
    path,_,spec,output=setup_case(tmp_path)
    spec['sources'][0][field]=value;save(path,spec)
    assert invoke(path,output,capsys)[0]==2 and not output.exists()


def test_spec_same_handle_mutation_rejects_before_mkdir(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    original=Path.open
    mutated=False
    def injected(self,*args,**kwargs):
        nonlocal mutated
        stream=original(self,*args,**kwargs)
        if self==path and args and args[0]=='rb' and not mutated:
            mutated=True
            with original(path,'ab') as other: other.write(b' ')
        return stream
    monkeypatch.setattr(Path,'open',injected)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']=='SPEC_CHANGED' and not output.exists()


def test_short_report_write_has_no_complete_marker(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    original=Path.open
    class Short:
        def __init__(self,stream): self.stream=stream
        def __enter__(self): return self
        def __exit__(self,*args): return self.stream.__exit__(*args)
        def fileno(self): return self.stream.fileno()
        def write(self,payload): return self.stream.write(payload[:7])
    def injected(self,*args,**kwargs):
        stream=original(self,*args,**kwargs)
        if self==output/'report.json' and args and args[0]=='xb': return Short(stream)
        return stream
    monkeypatch.setattr(Path,'open',injected)
    code,_,stderr=invoke(path,output,capsys)
    assert code==2 and json.loads(stderr)['error']=='OUTPUT_ERROR'
    assert (output/'report.json').stat().st_size==7 and not (output/'COMPLETE.json').exists()


def test_tampered_report_before_marker_cannot_form_valid_completion(tmp_path,capsys,monkeypatch):
    path,_,_,output=setup_case(tmp_path)
    original=Path.open
    def injected(self,*args,**kwargs):
        if self==output/'COMPLETE.json' and args and args[0]=='xb':
            with original(output/'report.json','ab') as stream: stream.write(b'SECRET')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',injected)
    assert invoke(path,output,capsys)[0]==2
    # Retained marker alone is insufficient: actual report bytes no longer match.
    marker=json.loads((output/'COMPLETE.json').read_text('utf-8'))
    assert hashlib.sha256((output/'report.json').read_bytes()).hexdigest()!=marker['report']['sha256']


def test_duplicate_rows_and_unknown_labels_use_minute_not_record_denominators(tmp_path,capsys):
    path,source,spec,output=setup_case(tmp_path,rows=2)
    data=list(csv.reader(io.StringIO(source.read_text('utf-8'))))
    data[2]=list(data[1])
    data[1][EXPECTED_HEADER.index('Label')]='SECRET-LABEL'
    data[2][EXPECTED_HEADER.index('Label')]='SECRET-LABEL'
    stream=io.StringIO(newline='');csv.writer(stream).writerows(data)
    payload=stream.getvalue().encode();source.write_bytes(payload)
    spec['sources'][0].update(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest());save(path,spec)
    assert invoke(path,output,capsys)[0]==0
    report=json.loads((output/'report.json').read_text('utf-8'))
    assert report['global']['raw_records']==2 and report['global']['excluded_records']==2
    assert report['global']['reason_counts']['duplicate_record']==2
    assert report['global']['duplicate_groups']==1
    assert report['segments'][0]['policies']['P_U']==dict(normal=0,attack=0,unknown=2)
    assert 'SECRET' not in json.dumps(report)


@pytest.mark.parametrize('column,count,expected', [
    ('Label',101,'MAX_LABEL_VALUES'),
    ('Attempted Category',33,'MAX_CATEGORY_VALUES'),
    ('Protocol',257,'MAX_PROTOCOL_VALUES'),
])
def test_real_vocabulary_caps_have_safe_specific_errors_and_clean_scratch(
        tmp_path,capsys,column,count,expected):
    path,source,spec,output=setup_case(tmp_path,rows=count)
    data=list(csv.reader(io.StringIO(source.read_text('utf-8'))))
    index=EXPECTED_HEADER.index(column)
    for i,row in enumerate(data[1:]):
        row[index]=str(i) if column=='Protocol' else 'SECRET-VOCAB-%d'%i
    stream=io.StringIO(newline='')
    csv.writer(stream).writerows(data)
    payload=stream.getvalue().encode('utf-8')
    source.write_bytes(payload)
    spec['sources'][0].update(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
    save(path,spec)
    code,stdout,stderr=invoke(path,output,capsys)
    assert code==2 and stdout==''
    assert json.loads(stderr)==dict(error=expected)
    assert 'SECRET' not in stderr and str(tmp_path) not in stderr
    assert source.read_bytes()==payload
    assert output.is_dir() and list(output.iterdir())==[]
    assert not (output/'COMPLETE.json').exists() and not (output/'scratch').exists()


def test_windows_root_relative_is_rejected_before_simulated_host_parsing(monkeypatch):
    from pathlib import PurePosixPath
    monkeypatch.setattr(mod(),'Path',PurePosixPath)
    with pytest.raises(ValueError,match='^INVALID_PATH$'):
        mod()._lexical('\\rooted.csv')


@pytest.mark.parametrize('host,value',[
    ('posix','/absolute/source.csv'),('windows','C:\\absolute\\source.csv')])
def test_host_appropriate_absolute_paths_stay_legal_in_parser_simulation(monkeypatch,host,value):
    from pathlib import PurePosixPath,PureWindowsPath
    path_type=PurePosixPath if host=='posix' else PureWindowsPath
    monkeypatch.setattr(mod(),'Path',path_type)
    assert mod()._lexical(value,absolute=True)==path_type(value)
