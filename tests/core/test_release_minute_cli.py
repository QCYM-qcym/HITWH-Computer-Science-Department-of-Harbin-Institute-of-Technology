"""Raw CLI admission only: artificial metadata/specs, no source consumption."""
from copy import deepcopy
from datetime import datetime, timedelta
import importlib
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest


def api():
    return importlib.import_module('traffic_anomaly.release_minute_cli')


@pytest.fixture
def case(tmp_path):
    source=tmp_path/'unread.csv';source.write_bytes(b'ARTIFICIAL_UNREAD_SOURCE\n')
    spec=tmp_path/'spec.json'
    doc=dict(version=1,sources=[dict(path=str(source),bytes=source.stat().st_size,sha256='a'*64)],
        segments=[dict(id='人工-train',role='train',start='2026-01-01T00:00:00',end='2026-01-01T00:02:00')],
        budget=dict(max_total_source_bytes=1048576,max_rows=512,max_database_bytes=8388608,
            max_elapsed_seconds=30,max_minutes=240))
    spec.write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8')
    return SimpleNamespace(source=source,spec=spec,scratch=tmp_path/'scratch',output=tmp_path/'raw',doc=doc)


def invoke(m,c,doc=None):
    if doc is not None:c.spec.write_text(json.dumps(doc,ensure_ascii=False),encoding='utf-8')
    return m._preflight(str(c.spec),str(c.scratch),str(c.output))


def failure(m,code,call):
    with pytest.raises(m._CLIError) as caught:call()
    assert caught.value.code==code and str(caught.value)==code


def guards(m,monkeypatch,c):
    """Record first, then throw; never depend on an exception escaping admission."""
    from traffic_anomaly import _release_disk,release_minute_package
    from traffic_anomaly._release_file_reader import _ReleaseFileReader
    attempts=[]
    def blocked(name):
        def stop(*args,**kwargs):attempts.append(name);raise AssertionError('forbidden admission action')
        return stop
    monkeypatch.setattr(_release_disk,'_aggregate_release_files',blocked('aggregate'))
    monkeypatch.setattr(release_minute_package,'save_release_minute_package',blocked('save'))
    monkeypatch.setattr(_ReleaseFileReader,'__enter__',blocked('reader'))
    original_open=Path.open;original_mkdir=Path.mkdir
    def opened(path,*args,**kwargs):
        if path.suffix=='.csv':return blocked('CSV open')(path)
        return original_open(path,*args,**kwargs)
    def mkdir(path,*args,**kwargs):
        if any(path==p or path.is_relative_to(p) for p in (c.scratch,c.output)):
            return blocked('target create')(path)
        return original_mkdir(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened);monkeypatch.setattr(Path,'mkdir',mkdir)
    return attempts


@pytest.mark.parametrize('argv',[
    [],['--spec','x'],['--spec','x','--scratch','y'],['--spec','x','--scratch','y','--output','z','extra'],
    ['--spe','x','--scratch','y','--output','z'],['--spec','x','--scratch','y','--output','z','--other'],
    ['--spec','x','--spec=y','--scratch','y','--output','z'],
    ['--spec=x','--spec=y','--scratch=y','--output=z'],
    ['--spec','@args','--scratch','y','--output','z'],['--spec=@args','--scratch=y','--output=z'],
    ['@args'],['--help','--spec','must-not-be-read'],['-h','--help'],
    ['--spec=x','--scratch=y','--output=z','--help'],['--help=private'],
    '--spec x',b'--spec x',[1],None,
],ids=[f'parse-{i}' for i in range(19)])
def test_safe_parser_help_and_duplicates(monkeypatch,capfdbinary,argv):
    m=api()
    if argv is None:monkeypatch.setattr(m.sys,'argv',['fixed-cli'])
    failure(m,'INVALID_ARGUMENTS',lambda:m._parse_cli(argv))
    out,err=capfdbinary.readouterr();assert out==err==b''


def test_parser_help_and_valid_paths_have_no_io_or_product_import(monkeypatch,capfdbinary):
    m=api();attempts=[]
    import builtins
    original_import=builtins.__import__
    def importing(name,*args,**kwargs):
        if name.startswith('traffic_anomaly') or (args and args[-1] and name.startswith('_release')):
            attempts.append('product import');raise AssertionError('product import')
        return original_import(name,*args,**kwargs)
    def io(*args,**kwargs):attempts.append('I/O');raise AssertionError('I/O')
    monkeypatch.setattr(builtins,'__import__',importing)
    monkeypatch.setattr(Path,'open',io);monkeypatch.setattr(Path,'lstat',io)
    assert m._parse_cli(['-h']) is None and m._parse_cli(['--help']) is None
    args=m._parse_cli(['--spec','run=@daily','--scratch=a','--output=b'])
    assert vars(args)==dict(spec='run=@daily',scratch='a',output='b')
    assert vars(m._parse_cli(['--spec=run=@daily','--scratch','a','--output','b']))==vars(args)
    assert attempts==[]
    out,err=capfdbinary.readouterr();assert out==err==b''


def mutations():
    changes=[]
    def add(name,fn):changes.append((name,fn))
    for field in ('version','sources','segments','budget'):
        add('missing-'+field,lambda d,f=field:d.pop(f))
    add('unknown-top',lambda d:d.update(epsilon=1))
    for value in (0,2,True,'1',None):add('version-'+repr(value),lambda d,v=value:d.update(version=v))
    for value in ([],[{}]*6,None,{},True):add('sources-'+repr(value),lambda d,v=value:d.update(sources=v))
    for key in ('path','bytes','sha256'):add('source-missing-'+key,lambda d,k=key:d['sources'][0].pop(k))
    add('source-extra',lambda d:d['sources'][0].update(policy='P_U'))
    for value in (0,-1,2147483649,True,1.0,'24',None):
        add('bytes-'+repr(value),lambda d,v=value:d['sources'][0].update(bytes=v))
    for value in ('a'*63,'A'*64,'g'*64,1,None):add('sha-'+repr(value),lambda d,v=value:d['sources'][0].update(sha256=v))
    for value in ([],[{}]*8,{},None):add('segments-'+repr(value),lambda d,v=value:d.update(segments=v))
    for key in ('id','role','start','end'):add('segment-missing-'+key,lambda d,k=key:d['segments'][0].pop(k))
    add('segment-extra',lambda d:d['segments'][0].update(epsilon=1))
    for value in ('','x'*129,'nul\0','control\x01','del\x7f','surrogate\ud800',True):
        add('id-'+repr(value),lambda d,v=value:d['segments'][0].update(id=v))
    for value in ('unknown',True,1):add('role-'+repr(value),lambda d,v=value:d['segments'][0].update(role=v))
    for value in ('2026-1-01T00:00:00','2026-01-01T00:00:01','2026-01-01 00:00:00',
                  '2026-01-01T00:00:00Z','2026-02-30T00:00:00','0000-01-01T00:00:00',None):
        add('time-'+repr(value),lambda d,v=value:d['segments'][0].update(start=v))
    add('reverse-time',lambda d:d['segments'][0].update(end='2026-01-01T00:00:00'))
    for key,maximum in (('max_total_source_bytes',2147483648),('max_rows',2500000),
            ('max_database_bytes',2147483648),('max_elapsed_seconds',1800),('max_minutes',10000)):
        add('budget-missing-'+key,lambda d,k=key:d['budget'].pop(k))
        for value in (0,-1,maximum+1,True,1.5,'1'):
            add(key+'-'+repr(value),lambda d,k=key,v=value:d['budget'].update({k:v}))
    add('budget-extra',lambda d:d['budget'].update(resume=1))
    add('db-too-small',lambda d:d['budget'].update(max_database_bytes=61440))
    add('db-unaligned',lambda d:d['budget'].update(max_database_bytes=65537))
    return changes


_MUTATIONS=mutations()
@pytest.mark.parametrize('name,change',_MUTATIONS,ids=[f'spec-{i}' for i in range(len(_MUTATIONS))])
def test_spec_fields_budget_domains_and_strict_types(case,monkeypatch,name,change):
    m=api();doc=deepcopy(case.doc);change(doc)
    # ensure_ascii preserves invalid Unicode for the product decoder to validate.
    case.spec.write_text(json.dumps(doc,ensure_ascii=True),encoding='utf-8')
    attempts=guards(m,monkeypatch,case)
    failure(m,'INVALID_SPEC',lambda:invoke(m,case))
    assert attempts==[] and not case.scratch.exists() and not case.output.exists()


def test_valid_request_uses_original_types_and_retains_order(case,monkeypatch):
    m=api();attempts=guards(m,monkeypatch,case);request=invoke(m,case)
    from traffic_anomaly._release_file_reader import ReleaseFileSource
    from traffic_anomaly._release_minutes import ReleaseSegment
    from traffic_anomaly._release_disk import ReleaseDiskBudget
    from dataclasses import FrozenInstanceError,fields
    assert type(request.sources) is tuple and type(request.sources[0]) is ReleaseFileSource
    assert type(request.segments) is tuple and type(request.segments[0]) is ReleaseSegment
    assert type(request.budget) is ReleaseDiskBudget and request.budget.max_rows==512
    assert request.spec_path==case.spec and request.scratch==case.scratch and request.output==case.output
    assert {f.name for f in fields(request)}=={'sources','segments','budget','spec_path','scratch','output','observations'}
    with pytest.raises(FrozenInstanceError):request.output=case.source
    assert type(request.observations) is tuple
    assert all(type(o) is tuple and len(o)==3 and o[1] in ('file','directory') for o in request.observations)
    m._recheck_request(request)
    assert attempts==[]


@pytest.mark.parametrize('field,value',[
    ('max_total_source_bytes',2147483648),('max_rows',2500000),('max_database_bytes',2147483648),
    ('max_database_bytes',65536),('max_elapsed_seconds',1800),('max_minutes',10000),
    ('max_minutes',2),('max_elapsed_seconds',1),('max_rows',1),
])
def test_configuration_domain_boundaries_are_metadata_only(case,monkeypatch,field,value):
    m=api();doc=deepcopy(case.doc);doc['budget'][field]=value
    case.spec.write_text(json.dumps(doc),encoding='utf-8');attempts=guards(m,monkeypatch,case)
    request=invoke(m,case);assert request.sources[0].expected_bytes==case.source.stat().st_size
    assert attempts==[]


def test_declared_maximum_bytes_metadata_only_no_sparse_or_content_read(case,monkeypatch):
    m=api();doc=deepcopy(case.doc);doc['sources'][0]['bytes']=2147483648
    doc['budget']['max_total_source_bytes']=2147483648
    case.spec.write_text(json.dumps(doc),encoding='utf-8');attempts=guards(m,monkeypatch,case)
    original=Path.lstat
    def lstat(path,*args,**kwargs):
        info=original(path,*args,**kwargs)
        if path==case.source:
            return SimpleNamespace(**{name:(2147483648 if name=='st_size' else getattr(info,name))
                for name in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_nlink','st_file_attributes') if hasattr(info,name)})
        return info
    monkeypatch.setattr(Path,'lstat',lstat)
    assert invoke(m,case).sources[0].expected_bytes==2147483648 and attempts==[]


def test_five_sources_seven_segments_order_and_equal_sha_allowed(case,monkeypatch):
    m=api();doc=deepcopy(case.doc)
    for i in range(1,5):
        path=case.source.with_name(f'unread-{i}.csv');path.write_bytes(b'ARTIFICIAL_UNREAD_SOURCE\n')
        doc['sources'].append(dict(path=str(path),bytes=path.stat().st_size,sha256='a'*64))
    start=datetime(2026,1,1)
    doc['segments']=[dict(id=f'segment-{i}',role=role,start=(start+timedelta(minutes=2*i)).isoformat(),
        end=(start+timedelta(minutes=2*i+1)).isoformat())
        for i,role in enumerate(('train','train','validation','validation','calibration','test','test'))]
    case.spec.write_text(json.dumps(doc),encoding='utf-8');attempts=guards(m,monkeypatch,case)
    request=invoke(m,case)
    assert [str(s.path) for s in request.sources]==[s['path'] for s in doc['sources']]
    assert [s.id for s in request.segments]==[s['id'] for s in doc['segments']] and attempts==[]


@pytest.mark.parametrize('kind,code',[('sum','RESOURCE_LIMIT'),('minutes','RESOURCE_LIMIT'),
    ('duplicate-id','INVALID_SPEC'),('overlap','INVALID_SPEC'),('role-order','INVALID_SPEC')])
def test_source_sum_and_segment_geometry(case,monkeypatch,kind,code):
    m=api();doc=deepcopy(case.doc)
    if kind=='sum':doc['budget']['max_total_source_bytes']=1
    elif kind=='minutes':doc['budget']['max_minutes']=1
    else:
        second=deepcopy(doc['segments'][0]);second.update(id='second',start='2026-01-01T00:02:00',end='2026-01-01T00:03:00')
        if kind=='duplicate-id':second['id']=doc['segments'][0]['id']
        elif kind=='overlap':second['start']='2026-01-01T00:01:00'
        else:doc['segments'][0]['role']='test'
        doc['segments'].append(second)
    case.spec.write_text(json.dumps(doc),encoding='utf-8');attempts=guards(m,monkeypatch,case)
    failure(m,code,lambda:invoke(m,case));assert attempts==[]


@pytest.mark.parametrize('payload',[
    b'\xef\xbb\xbf{}',b'\xff',b'{} {}',b'{"version":1,"version":1}',
    b'{"x":{"same":1,"same":2}}',b'{"version":NaN}',b'{"version":Infinity}',
    b'{"version":1.0}',b'{"version":-0}',b'{"version":10000000000}',b'{"version":01}',
    b'['*1200+b'0'+b']'*1200,
],ids=[f'json-{i}' for i in range(12)])
def test_strict_json_tokens_and_bytes(case,monkeypatch,payload):
    m=api();case.spec.write_bytes(payload);attempts=guards(m,monkeypatch,case)
    failure(m,'INVALID_SPEC',lambda:invoke(m,case));assert attempts==[]


@pytest.mark.parametrize('size',[65536,65537])
def test_spec_bound_and_same_real_handle(case,monkeypatch,size):
    m=api();payload=case.spec.read_bytes();case.spec.write_bytes(payload+b' '*(size-len(payload)))
    attempts=guards(m,monkeypatch,case)
    if size==65536:assert invoke(m,case).spec_path==case.spec
    else:failure(m,'RESOURCE_LIMIT',lambda:invoke(m,case))
    assert attempts==[]


class SpecStream:
    """Wrap a real descriptor; every requested read remains observable."""
    def __init__(self,stream,reads,*,short=None,after_close=None,close_error=False):
        self.stream=stream;self.reads=reads;self.short=short;self.after_close=after_close;self.close_error=close_error
    def __enter__(self):return self
    def __exit__(self,*exc):
        self.stream.close()
        if self.after_close:self.after_close()
        if self.close_error:raise OSError('PRIVATE_CLOSE_DETAIL')
    def fileno(self):return self.stream.fileno()
    def read(self,size):
        self.reads.append(size);data=self.stream.read(size)
        return data if self.short is None else data[:self.short]


def test_spec_opened_B_handle_rejected_while_A_path_stays_stable(case,monkeypatch):
    m=api();other=case.spec.with_name('B.json');other.write_bytes(case.spec.read_bytes())
    original=Path.open;reads=[];before=case.spec.stat()
    def opened(path,*args,**kwargs):
        return SpecStream(original(other,'rb'),reads) if path==case.spec else original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    failure(m,'SPEC_CHANGED',lambda:invoke(m,case))
    assert reads==[] and (case.spec.stat().st_ino,case.spec.stat().st_mtime_ns)==(before.st_ino,before.st_mtime_ns)


def test_spec_short_prefix_cannot_hide_tail(case,monkeypatch):
    m=api();prefix=case.spec.read_bytes();case.spec.write_bytes(prefix+b' trailing-invalid-json')
    original=Path.open;reads=[]
    monkeypatch.setattr(Path,'open',lambda path,*a,**k:SpecStream(original(path,'rb'),reads,short=len(prefix))
        if path==case.spec else original(path,*a,**k))
    failure(m,'SPEC_CHANGED',lambda:invoke(m,case));assert reads==[65537]


@pytest.mark.parametrize('kind,code',[('close','INPUT_UNAVAILABLE'),('replace','SPEC_CHANGED')])
def test_spec_close_or_replace_fails(case,monkeypatch,kind,code):
    m=api();other=case.spec.with_name('replacement.json');other.write_bytes(case.spec.read_bytes())
    original=Path.open;reads=[]
    def opened(path,*args,**kwargs):
        if path!=case.spec:return original(path,*args,**kwargs)
        return SpecStream(original(path,'rb'),reads,close_error=kind=='close',
            after_close=(lambda:os.replace(other,case.spec)) if kind=='replace' else None)
    monkeypatch.setattr(Path,'open',opened)
    failure(m,code,lambda:invoke(m,case));assert reads==[65537]


@pytest.mark.parametrize('target', ['same','case','distinct','different-parent'])
def test_targets_same_parent_entity_and_native_leaf_are_rejected(case,monkeypatch,target):
    m=api()
    if target=='same':case.output=case.scratch
    elif target=='case':case.output=case.scratch.with_name(case.scratch.name.upper())
    elif target=='different-parent':
        parent=case.source.parent/'other';parent.mkdir();case.output=parent/case.scratch.name
    attempts=guards(m,monkeypatch,case)
    if target=='same' or target=='case' and os.name=='nt':
        failure(m,'INVALID_PATH_LAYOUT',lambda:invoke(m,case))
    else:assert invoke(m,case).output==case.output
    assert attempts==[]


def test_simulated_parent_entity_alias_is_not_real_83_evidence(case,monkeypatch):
    m=api();parent=case.source.parent/'simulated-parent';parent.mkdir();case.output=parent/case.scratch.name
    original=Path.lstat;actual=case.scratch.parent.lstat()
    def lstat(path,*args,**kwargs):return actual if path==parent else original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',lstat);attempts=guards(m,monkeypatch,case)
    failure(m,'INVALID_PATH_LAYOUT',lambda:invoke(m,case));assert attempts==[]


def short_parent(path):
    if os.name!='nt':pytest.skip('actual Windows 8.3 alias requires Windows')
    import ctypes
    from ctypes import wintypes
    function=ctypes.WinDLL('kernel32',use_last_error=True).GetShortPathNameW
    function.argtypes=(wintypes.LPCWSTR,wintypes.LPWSTR,wintypes.DWORD);function.restype=wintypes.DWORD
    buffer=ctypes.create_unicode_buffer(32768);length=function(str(path),buffer,len(buffer))
    if not 0<length<len(buffer):pytest.skip('GetShortPathNameW did not return an available alias')
    short=Path(buffer.value)
    if os.path.normcase(str(short))==os.path.normcase(str(path)):
        pytest.skip('host exposes no distinct effective 8.3 name for this directory')
    if not short.is_dir() or not os.path.samefile(path,short):pytest.skip('returned 8.3 alias is not a verified same directory')
    return short


@pytest.mark.parametrize('nested',[False,True])
def test_actual_long_and_83_parent_alias(case,monkeypatch,nested):
    m=api();parent=case.source.parent/'Actual long parent for alias';parent.mkdir();short=short_parent(parent)
    case.scratch=parent/'new-target';case.output=short/'new-target'
    if nested:case.output=case.output/'nested'
    attempts=guards(m,monkeypatch,case)
    failure(m,'INVALID_PATH_LAYOUT',lambda:invoke(m,case));assert attempts==[]


@pytest.mark.parametrize('domain,code',[('spec','INVALID_SPEC_PATH'),('source','INVALID_SOURCE_PATH'),
    ('scratch','INVALID_SCRATCH_DIRECTORY'),('output','INVALID_PACKAGE_PATH')])
@pytest.mark.parametrize('part',['NUL','CON.txt','COM1.log','bad.','bad ','bad?name','bad:name'])
@pytest.mark.parametrize('parent',[False,True])
def test_reserved_windows_component_before_aggregate(case,monkeypatch,domain,code,part,parent):
    m=api()
    if os.name!='nt':pytest.skip('Windows reserved component domain is platform-specific')
    value=case.source.parent/part
    if parent:value=value/'child'
    if domain=='source':case.doc['sources'][0]['path']=str(value);invoke_doc=case.doc
    else:setattr(case,'spec' if domain=='spec' else domain,value);invoke_doc=None
    attempts=guards(m,monkeypatch,case)
    failure(m,code,lambda:invoke(m,case,invoke_doc));assert attempts==[]


@pytest.mark.parametrize('domain,code',[('spec','INVALID_SPEC_PATH'),('source','INVALID_SOURCE_PATH'),
    ('scratch','INVALID_SCRATCH_DIRECTORY'),('output','INVALID_PACKAGE_PATH')])
@pytest.mark.parametrize('value',['relative','C:drive-relative','\\root-relative','\\\\server\\share\\name','//device/path','bad\0name'])
def test_invalid_path_forms(case,monkeypatch,domain,code,value):
    m=api();doc=deepcopy(case.doc)
    if domain=='source':doc['sources'][0]['path']=value;case.spec.write_text(json.dumps(doc),encoding='utf-8')
    args=[str(case.spec),str(case.scratch),str(case.output)]
    if domain!='source':args[{'spec':0,'scratch':1,'output':2}[domain]]=value
    attempts=guards(m,monkeypatch,case)
    failure(m,code,lambda:m._preflight(*args));assert attempts==[]


@pytest.mark.parametrize('which',['source-alias','spec-alias'])
def test_same_entity_source_and_spec_hardlink_aliases(case,monkeypatch,which):
    m=api();alias=case.source.with_name('alias.csv')
    try:os.link(case.source if which=='source-alias' else case.spec,alias)
    except OSError:pytest.skip('hardlink creation unavailable')
    if which=='source-alias':case.doc['sources'].append(dict(case.doc['sources'][0],path=str(alias)))
    else:
        case.doc['sources']=[dict(path=str(alias),bytes=1,sha256='b'*64)]
        # Rewriting the same spec inode also updates its hardlink, without reading it.
    case.spec.write_text(json.dumps(case.doc),encoding='utf-8')
    attempts=guards(m,monkeypatch,case)
    failure(m,'DUPLICATE_SOURCE',lambda:invoke(m,case));assert attempts==[]


@pytest.mark.parametrize('domain,code',[('spec','INVALID_SPEC_PATH'),('source','INVALID_SOURCE_PATH'),
    ('scratch-parent','INVALID_SCRATCH_DIRECTORY'),('output-parent','INVALID_PACKAGE_PATH')])
def test_symlink_file_and_directory_ancestors(case,monkeypatch,domain,code):
    m=api();link=case.source.parent/'link'
    original=case.spec if domain=='spec' else case.source if domain=='source' else case.source.parent
    try:link.symlink_to(original,target_is_directory=domain.endswith('parent'))
    except OSError:pytest.skip('symlink creation privilege unavailable')
    if domain=='spec':case.spec=link
    elif domain=='source':case.doc['sources'][0]['path']=str(link);case.spec.write_text(json.dumps(case.doc),encoding='utf-8')
    else:setattr(case,domain.split('-')[0],link/'new-target')
    attempts=guards(m,monkeypatch,case)
    failure(m,code,lambda:invoke(m,case));assert attempts==[]


def test_reparse_attribute_injection_is_rejected(case,monkeypatch):
    m=api();original=Path.lstat
    def lstat(path,*a,**k):
        info=original(path,*a,**k)
        if path==case.source:
            names=('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_nlink')
            return SimpleNamespace(**{n:getattr(info,n) for n in names},st_file_attributes=0x400)
        return info
    monkeypatch.setattr(Path,'lstat',lstat);attempts=guards(m,monkeypatch,case)
    failure(m,'INVALID_SOURCE_PATH',lambda:invoke(m,case));assert attempts==[]


@pytest.mark.parametrize('kind,code',[('source-size','SOURCE_SIZE_MISMATCH'),('output-exists','OUTPUT_EXISTS'),
    ('scratch-exists','INVALID_SCRATCH_DIRECTORY'),('nested','INVALID_PATH_LAYOUT'),
    ('missing-parent','INVALID_PACKAGE_PATH')])
def test_existing_targets_layout_and_source_size(case,monkeypatch,kind,code):
    m=api()
    if kind=='source-size':case.doc['sources'][0]['bytes']+=1;case.spec.write_text(json.dumps(case.doc),encoding='utf-8')
    elif kind=='output-exists':case.output.mkdir()
    elif kind=='scratch-exists':case.scratch.mkdir()
    elif kind=='nested':case.output=case.scratch/'nested'
    else:case.output=case.output/'missing-parent'/'child'
    attempts=guards(m,monkeypatch,case)
    failure(m,code,lambda:invoke(m,case));assert attempts==[]


@pytest.mark.parametrize('kind,code',[('source','INPUT_UNAVAILABLE'),('spec','SPEC_CHANGED'),
    ('parent','INVALID_PATH_LAYOUT'),('output','OUTPUT_EXISTS'),('scratch','INVALID_SCRATCH_DIRECTORY')])
def test_recheck_request_observes_replacement_without_directory_mtime_false_alarm(case,monkeypatch,kind,code):
    m=api();parent=case.source.parent/'target-parent';parent.mkdir();case.output=parent/'raw'
    request=invoke(m,case)
    unrelated=parent/'unrelated';unrelated.write_bytes(b'harmless')
    m._recheck_request(request)  # directory mtime changes do not change its entity.
    if kind in ('source','spec'):
        path=case.source if kind=='source' else case.spec
        replacement=path.with_name('replacement');replacement.write_bytes(b'x');os.replace(replacement,path)
    elif kind=='parent':parent.rename(parent.with_name('retained-old-parent'));parent.mkdir()
    elif kind=='output':case.output.mkdir()
    else:case.scratch.mkdir()
    attempts=guards(m,monkeypatch,case)
    failure(m,code,lambda:m._recheck_request(request));assert attempts==[]


def test_attempt_ledger_detects_swallowed_forbidden_action():
    attempts=[]
    def forbidden():attempts.append('attempt');raise AssertionError('forbidden')
    try:forbidden()
    except AssertionError:pass
    assert attempts==['attempt']
    with pytest.raises(AssertionError):assert attempts==[]


@pytest.fixture
def pipeline(case,monkeypatch):
    """Controlled core seams, not an aggregate or a preprocessing calculation."""
    m=api()
    from traffic_anomaly import _release_disk,release_minute_package,_release_minutes
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackageIdentity
    request=invoke(m,case);events=[];attempts=[]
    real_save=release_minute_package.save_release_minute_package;real_load=release_minute_package.load_release_minute_package
    identity=ReleaseMinutePackageIdentity('c17-release-minute-package-v1','b'*64,'c'*64,987)
    minutes=SimpleNamespace(source_authentication='NOT_AUTHENTICATED',time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',
        timestamps=(datetime(2026,1,1),datetime(2026,1,1,0,1)),source_valid=(True,False),
        raw_records=77,eligible_records=60,excluded_records=17,outside_records=9,unplaced_invalid_rows=2)
    receipts=SimpleNamespace(sources=(SimpleNamespace(source_ordinal=0,source_bytes=123,source_sha256='d'*64),),
        source_content_open_count=1,source_bytes_consumed=123,logical_rows=77)
    result=SimpleNamespace(minutes=minutes,resources=SimpleNamespace(reader_receipts=receipts,
        database_bytes_at_close=65536,observed_database_high_water_bytes=69632,cleanup_status='CLEANED'))
    recheck=m._recheck_request
    def preflight(*args):
        assert args==(str(case.spec),str(case.scratch),str(case.output));events.append('preflight');return request
    def check(value):assert value is request;events.append('recheck');return recheck(value)
    def aggregate(sources,segments,*,scratch_directory,budget):
        assert sources is request.sources and segments is request.segments
        assert scratch_directory==case.scratch and budget is request.budget
        events.append('aggregate');return result
    def save(value,segments,path):
        assert value is result.minutes and segments is request.segments and path==case.output
        assert not path.exists() and not case.scratch.exists();events.append('save');return identity
    def forbidden(*a,**k):attempts.append('unrequested action');raise AssertionError('unrequested action')
    monkeypatch.setattr(m,'_preflight',preflight);monkeypatch.setattr(m,'_recheck_request',check)
    monkeypatch.setattr(_release_disk,'_aggregate_release_files',aggregate)
    monkeypatch.setattr(release_minute_package,'save_release_minute_package',save)
    monkeypatch.setattr(release_minute_package,'load_release_minute_package',forbidden)
    monkeypatch.setattr(_release_minutes,'_aggregate_release_minutes',forbidden)
    return SimpleNamespace(m=m,c=case,request=request,result=result,identity=identity,events=events,attempts=attempts,
        disk=_release_disk,raw=release_minute_package,real_save=real_save,real_load=real_load,
        argv=['--spec',str(case.spec),'--scratch',str(case.scratch),'--output',str(case.output)])


def test_one_aggregate_cleanup_then_one_save(pipeline,capfdbinary):
    p=pipeline;assert p.m.main(p.argv)==0
    out,err=capfdbinary.readouterr();assert err==b''
    assert p.events==['preflight','recheck','aggregate','recheck','save'] and p.attempts==[]
    assert json.loads(out)['status']=='SAVED' and not p.c.scratch.exists()


def test_success_projection_uses_reader_identity_and_fixed_fields(pipeline,capfdbinary):
    p=pipeline;assert p.m.main(p.argv)==0
    out,err=capfdbinary.readouterr();assert err==b''
    expected=dict(version=1,command='aggregate',status='SAVED',identity=dict(profile_id=p.identity.profile_id,
        context_sha256='b'*64,manifest_sha256='c'*64,manifest_byte_count=987),source_authentication='NOT_AUTHENTICATED',
        time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',source_identities=[dict(ordinal=0,byte_count=123,sha256='d'*64)],
        counts=dict(source_count=1,minute_count=2,source_valid_minutes=1,raw_records=77,eligible_records=60,
            excluded_records=17,outside_records=9,unplaced_invalid_rows=2),
        resources=dict(source_content_open_count=1,source_bytes_consumed=123,logical_rows=77,
            database_bytes_at_close=65536,observed_database_high_water_bytes=69632,cleanup_status='CLEANED'))
    assert json.loads(out)==expected
    assert out==(json.dumps(expected,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    assert str(p.c.source).encode() not in out and '人工-train'.encode() not in out
    assert p.attempts==[]


@pytest.mark.parametrize('kind,code',[('status','SCRATCH_CLEANUP_FAILED'),('residue','SCRATCH_CLEANUP_FAILED'),
    ('source','INPUT_UNAVAILABLE'),('parent','INVALID_PATH_LAYOUT'),('reader-close','SOURCE_CLOSE_ERROR'),
    ('sqlite-close','SQLITE_CLOSE_ERROR'),('cleanup-error','SCRATCH_CLEANUP_FAILED')])
def test_failed_cleanup_never_saves(pipeline,monkeypatch,capfdbinary,kind,code):
    p=pipeline;original=p.disk._aggregate_release_files
    def aggregate(*a,**k):
        result=original(*a,**k)
        if kind=='status':result.resources.cleanup_status='FAILED'
        elif kind=='residue':p.c.scratch.mkdir();(p.c.scratch/'foreign').write_bytes(b'keep')
        elif kind=='source':p.c.source.write_bytes(b'changed')
        elif kind=='parent':
            # Change only the observed target parent identity, without touching files.
            parent=p.c.output.parent
            old=p.m._observe
            def observe(path,category,observations,error):
                signature=old(path,category,observations,error)
                return (signature[0],signature[1]+1,*signature[2:]) if path==parent and category=='directory' else signature
            monkeypatch.setattr(p.m,'_observe',observe)
        else:raise ValueError({'reader-close':'source_close_error','sqlite-close':'sqlite_close_error','cleanup-error':'scratch_cleanup_failed'}[kind])
        return result
    monkeypatch.setattr(p.disk,'_aggregate_release_files',aggregate)
    assert p.m.main(p.argv)==2
    out,err=capfdbinary.readouterr();assert out==b'' and json.loads(err)=={'error':code}
    assert p.events.count('aggregate')==1 and 'save' not in p.events and p.attempts==[]
    if kind=='residue':assert (p.c.scratch/'foreign').read_bytes()==b'keep'


@pytest.mark.parametrize('argv',[['--help'],['-h'],[],['--help','--spec','PRIVATE'],['--spec','PRIVATE']])
def test_help_and_invalid_arguments_do_not_import_product(monkeypatch,capfdbinary,argv):
    m=api();attempts=[]
    import builtins
    original=builtins.__import__
    def importing(name,*args,**kwargs):
        if name.startswith('traffic_anomaly') or name.startswith(('_release','release_')):
            attempts.append('import');raise AssertionError('product import')
        return original(name,*args,**kwargs)
    def io(*a,**k):attempts.append('I/O');raise AssertionError('I/O')
    monkeypatch.setattr(builtins,'__import__',importing);monkeypatch.setattr(Path,'open',io);monkeypatch.setattr(Path,'lstat',io)
    assert m.main(argv)==(0 if len(argv)==1 and argv[0] in ('-h','--help') else 2)
    out,err=capfdbinary.readouterr()
    if len(argv)==1 and argv[0] in ('-h','--help'):assert out.startswith(b'usage: python -m traffic_anomaly.release_minute_cli') and err==b''
    else:assert out==b'' and err==b'{"error":"INVALID_ARGUMENTS"}\n'
    assert attempts==[] and b'PRIVATE' not in out+err


@pytest.mark.parametrize('field,value',[('profile_id','other'),('context_sha256','A'*64),
    ('manifest_sha256',[]),('manifest_byte_count',True),('manifest_byte_count',0),('manifest_byte_count',65537),('type',None)])
def test_bad_save_identity_cannot_report_saved(pipeline,monkeypatch,capfdbinary,field,value):
    p=pipeline
    if field=='type':bad=value
    else:
        bad=object.__new__(type(p.identity))
        for name in ('profile_id','context_sha256','manifest_sha256','manifest_byte_count'):
            object.__setattr__(bad,name,value if name==field else getattr(p.identity,name))
    monkeypatch.setattr(p.raw,'save_release_minute_package',lambda *a:bad)
    assert p.m.main(p.argv)==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"INVALID_RESULT"}\n' and p.attempts==[]


_RAW_ERROR_CODES=('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE','OUTPUT_EXISTS','PACKAGE_CHANGED','OUTPUT_ERROR')
_READER_ERROR_CODES=('invalid_budget','invalid_sources','invalid_source','invalid_source_path','duplicate_source',
    'source_size_mismatch','source_hash_mismatch','source_changed','source_io_error','source_close_error',
    'input_byte_cap','max_rows','database_byte_cap','elapsed_time_cap','scratch_cleanup_failed',
    'scratch_ownership_changed','scratch_io_error','invalid_scratch_directory','invalid_disk_budget',
    'integer_string_limit_environment','csv_field_limit_environment','logical_record_char_cap','invalid_utf8',
    'invalid_csv','missing_header','header_mismatch','ragged_row','field_nul','max_field_chars','max_label_values',
    'max_category_values','max_protocol_values','integer_expansion_limit','duration_cap','completion_overflow',
    'invalid_segments','invalid_max_minutes','minute_cap','sqlite_environment','sqlite_error','sqlite_query_plan',
    'sqlite_close_error','database_size_mismatch','record_conservation_failure','quantile_consistency_failure',
    'numeric_materialization_overflow','reader_state','invalid_deadline','incomplete_read')
_PRIVATE_DETAIL='/private-artificial-sentinel/not-public/source.csv'


@pytest.mark.parametrize('family,code', [('raw',c) for c in _RAW_ERROR_CODES]+[('reader',c) for c in _READER_ERROR_CODES],
    ids=[f'raw-{i}' for i in range(len(_RAW_ERROR_CODES))]+[f'reader-{i}' for i in range(len(_READER_ERROR_CODES))])
def test_known_error_vocabulary_is_exact_and_safe(pipeline,monkeypatch,capfdbinary,family,code):
    p=pipeline
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackageError
    error=ReleaseMinutePackageError(code) if family=='raw' else ValueError(code)
    if family=='raw':error.args=(_PRIVATE_DETAIL,)
    error.__cause__=RuntimeError(_PRIVATE_DETAIL)
    def fail(*a,**k):raise error
    monkeypatch.setattr(p.disk,'_aggregate_release_files',fail)
    assert p.m.main(p.argv)==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==('{"error":"'+code.upper()+'"}\n').encode()
    assert p.attempts==[] and 'save' not in p.events


@pytest.mark.parametrize('kind',['raw-missing','raw-list','raw-dict','raw-bool','raw-none','raw-unknown',
    'subclass','two-args','prefix','exception','interrupt','system-exit'])
def test_unknown_errors_and_interrupt_are_safe(pipeline,monkeypatch,capfdbinary,kind):
    p=pipeline
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackageError
    if kind.startswith('raw-'):
        error=ReleaseMinutePackageError('INVALID_PACKAGE')
        if kind=='raw-missing':del error.code
        else:error.code={'raw-list':[],'raw-dict':{},'raw-bool':True,'raw-none':None,'raw-unknown':_PRIVATE_DETAIL}[kind]
        error.args=(_PRIVATE_DETAIL,)
    elif kind=='subclass':
        class Derived(ValueError):pass
        error=Derived('source_io_error')
    elif kind=='two-args':error=ValueError('source_io_error',_PRIVATE_DETAIL)
    elif kind=='prefix':error=ValueError('source_io_error:'+_PRIVATE_DETAIL)
    elif kind=='interrupt':error=KeyboardInterrupt(_PRIVATE_DETAIL)
    elif kind=='system-exit':error=SystemExit(_PRIVATE_DETAIL)
    else:error=RuntimeError(_PRIVATE_DETAIL)
    error.__cause__=RuntimeError(_PRIVATE_DETAIL)
    def fail(*a,**k):raise error
    monkeypatch.setattr(p.disk,'_aggregate_release_files',fail)
    assert p.m.main(p.argv)==2
    out,err=capfdbinary.readouterr();assert out==b''
    assert err==(b'{"error":"INTERRUPTED"}\n' if kind=='interrupt' else b'{"error":"INTERNAL_ERROR"}\n')
    assert 'save' not in p.events and p.attempts==[]


@pytest.mark.parametrize('flag',[True,1,'true',False,None])
@pytest.mark.parametrize('interrupt',[False,True])
def test_cleanup_flag_is_strict_bool_and_keeps_primary(pipeline,monkeypatch,capfdbinary,flag,interrupt):
    p=pipeline;error=KeyboardInterrupt(_PRIVATE_DETAIL) if interrupt else ValueError('source_close_error')
    error.cleanup_failed=flag
    def fail(*a,**k):raise error
    monkeypatch.setattr(p.disk,'_aggregate_release_files',fail)
    assert p.m.main(p.argv)==2
    out,err=capfdbinary.readouterr();expected={'error':'INTERRUPTED' if interrupt else 'SOURCE_CLOSE_ERROR'}
    if flag is True:expected['cleanup_failed']=True
    assert out==b'' and json.loads(err)==expected and 'save' not in p.events and p.attempts==[]


@pytest.mark.parametrize('size',[65535,65536,65537])
def test_output_encoding_limit_short_write_and_flush_bytes(size):
    m=api();overhead=len((json.dumps({'text':''},separators=(',',':'))+'\n').encode())
    value={'text':'中'+'x'*(size-overhead-3)}
    if size>65536:failure(m,'RESOURCE_LIMIT',lambda:m._json_bytes(value))
    else:
        payload=m._json_bytes(value);assert len(payload)==size and payload.endswith(b'\n') and b'\r' not in payload
        assert json.loads(payload)==value


@pytest.mark.parametrize('value',[float('nan'),{1,2},'\ud800'],ids=['nan','non-json','unicode'])
def test_output_encoding_limit_short_write_and_flush_invalid_values(value):
    m=api();failure(m,'INVALID_RESULT',lambda:m._json_bytes({'bad':value}))


@pytest.mark.parametrize('fault',['short','bool','none','flush','write-interrupt','flush-interrupt'])
def test_output_encoding_limit_short_write_and_flush_stream(pipeline,monkeypatch,capfdbinary,fault):
    p=pipeline;events=[];delivered=[]
    class Sink:
        def write(self,payload):
            events.append('write');delivered.append(payload)
            if fault=='write-interrupt':raise KeyboardInterrupt(_PRIVATE_DETAIL)
            return {'short':len(payload)-1,'bool':True,'none':None}.get(fault,len(payload))
        def flush(self):
            events.append('flush')
            if fault=='flush-interrupt':raise KeyboardInterrupt(_PRIVATE_DETAIL)
            if fault=='flush':raise OSError(_PRIVATE_DETAIL)
    fake_sys=SimpleNamespace(stdout=SimpleNamespace(buffer=Sink()),stderr=p.m.sys.stderr)
    monkeypatch.setattr(p.m,'sys',fake_sys)
    assert p.m.main(p.argv)==2
    out,err=capfdbinary.readouterr();assert out==b'' and delivered
    expected='INTERRUPTED' if fault.endswith('interrupt') else 'OUTPUT_ERROR'
    assert json.loads(err)=={'error':expected}
    assert events==(['write','flush'] if fault in ('flush','flush-interrupt') else ['write'])
    assert p.events.count('aggregate')==p.events.count('save')==1 and p.attempts==[]


@pytest.mark.parametrize('fault',['short','flush','interrupt'])
def test_error_stream_failure_is_not_retried(pipeline,monkeypatch,capfdbinary,fault):
    p=pipeline;events=[]
    class Sink:
        def write(self,payload):
            events.append('write')
            if fault=='interrupt':raise KeyboardInterrupt(_PRIVATE_DETAIL)
            return len(payload)-1 if fault=='short' else len(payload)
        def flush(self):events.append('flush');raise OSError(_PRIVATE_DETAIL)
    monkeypatch.setattr(p.m,'sys',SimpleNamespace(stdout=p.m.sys.stdout,stderr=SimpleNamespace(buffer=Sink())))
    assert p.m.main([])==2
    out,err=capfdbinary.readouterr();assert out==err==b''
    assert events==(['write','flush'] if fault=='flush' else ['write'])


@pytest.mark.parametrize('fault',['write','flush','late-save'])
def test_saved_package_survives_output_failure(pipeline,monkeypatch,capfdbinary,fault):
    p=pipeline
    from dataclasses import replace
    from .release_input_cases import make_upstream
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackageError
    upstream=make_upstream(lengths=(2,),roles=('train',))  # direct value objects; no aggregate/fit.
    p.result.minutes=upstream.minutes
    p.request=replace(p.request,segments=upstream.segments)
    # Replace the preflight/check spy closures to bind this explicitly artificial result.
    monkeypatch.setattr(p.m,'_preflight',lambda *a:p.request)
    monkeypatch.setattr(p.m,'_recheck_request',lambda r:None)
    def aggregate(*a,**k):p.events.append('aggregate');return p.result
    def save(minutes,segments,path):
        p.events.append('save');identity=p.real_save(minutes,segments,path)
        if fault=='late-save':raise ReleaseMinutePackageError('OUTPUT_ERROR')
        return identity
    class Sink:
        def write(self,payload):
            if fault=='write':raise OSError(_PRIVATE_DETAIL)
            return len(payload)
        def flush(self):raise OSError(_PRIVATE_DETAIL)
    def write(payload):p.m._write_stream(SimpleNamespace(buffer=Sink()),payload)
    monkeypatch.setattr(p.disk,'_aggregate_release_files',aggregate)
    monkeypatch.setattr(p.raw,'save_release_minute_package',save);monkeypatch.setattr(p.m,'_write_stdout',write)
    assert p.m.main(p.argv)==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"OUTPUT_ERROR"}\n'
    assert p.real_load(p.c.output)==upstream
    assert {f.name for f in p.c.output.iterdir()}=={'minutes.json','labels.json','diagnostics.json','manifest.json','COMPLETE.json'}
    assert p.events.count('aggregate')==p.events.count('save')==1 and p.attempts==[]


@pytest.mark.parametrize('status,dup_failure',[(0,False),(2,False),(2,True)])
def test_owned_module_failure_exit_seals_fds_only_at_entry(monkeypatch,status,dup_failure):
    m=api();events=[]
    class FakeOS:
        devnull='UNIT_NULL';O_WRONLY=1
        def open(self,path,flags):assert path==self.devnull and flags==1;events.append('open');return 17
        def dup2(self,source,target):
            assert source==17 and target in (1,2);events.append(('dup',target))
            if dup_failure:raise OSError('unavailable')
        def close(self,fd):assert fd==17;events.append('close')
    monkeypatch.setattr(m,'os',FakeOS());monkeypatch.setattr(m,'main',lambda:status)
    monkeypatch.setattr(m,'sys',SimpleNamespace(stdout=SimpleNamespace(fileno=lambda:1),stderr=SimpleNamespace(fileno=lambda:2)))
    import ast
    tree=ast.parse(Path(m.__file__).read_text(encoding='utf-8'));entry=tree.body[-1]
    assert isinstance(entry,ast.If)
    with pytest.raises(SystemExit) as caught:
        exec(compile(ast.Module(body=[entry],type_ignores=[]),m.__file__,'exec'),dict(vars(m),__name__='__main__'))
    assert caught.value.code==status
    assert events==([] if status==0 else ['open',('dup',1),'close','open',('dup',2),'close'])


def test_real_full91_32_minute_source_chain_once(tmp_path,monkeypatch,capfdbinary):
    """One bounded file-reader/disk/save seam; the literal raw13 oracle is independent."""
    import builtins
    import csv
    import hashlib
    import io
    from traffic_anomaly._release_csv import EXPECTED_HEADER
    from traffic_anomaly import _release_disk,release_minute_package,_release_minutes
    m=api();stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(EXPECTED_HEADER)
    for i in range(32):
        row={key:'0' for key in EXPECTED_HEADER}
        row.update({'id':str(i),'Flow ID':'artificial','Src IP':'192.0.2.1','Dst IP':'192.0.2.2','Protocol':'6',
            'Timestamp':f'2026-01-01 00:{i:02d}:10.000000','Flow Duration':'1000000',
            'Total Fwd Packet':'2','Total Bwd packets':'1','Total Length of Fwd Packet':'20',
            'Total Length of Bwd Packet':'10','Label':'BENIGN','Attempted Category':'-1'})
        writer.writerow([row[key] for key in EXPECTED_HEADER])
    payload=stream.getvalue().encode('utf-8');digest=hashlib.sha256(payload).hexdigest()
    assert len(EXPECTED_HEADER)==91 and len(payload)<=1048576
    source=tmp_path/'artificial.csv';source.write_bytes(payload)
    spec=tmp_path/'spec.json';scratch=tmp_path/'scratch';output=tmp_path/'raw'
    document=dict(version=1,sources=[dict(path=str(source),bytes=len(payload),sha256=digest)],
        segments=[dict(id='artificial-train',role='train',start='2026-01-01T00:00:00',end='2026-01-01T00:32:00')],
        budget=dict(max_total_source_bytes=1048576,max_rows=512,max_database_bytes=8388608,max_elapsed_seconds=30,max_minutes=240))
    spec.write_text(json.dumps(document),encoding='utf-8')
    before=tuple((p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in (source,spec))
    actual_aggregate=_release_disk._aggregate_release_files;actual_save=release_minute_package.save_release_minute_package
    actual_load=release_minute_package.load_release_minute_package;events=[];attempts=[];results=[]
    def aggregate(*a,**k):events.append('aggregate');result=actual_aggregate(*a,**k);results.append(result);return result
    def save(*a,**k):events.append('save');return actual_save(*a,**k)
    def forbidden(*a,**k):attempts.append('unrequested action');raise AssertionError('unrequested action')
    importing=builtins.__import__
    def safe_import(name,*a,**k):
        if name.startswith(('traffic_anomaly.release_inputs','traffic_anomaly.release_audit_cli','release_inputs','release_audit_cli')):
            return forbidden()
        return importing(name,*a,**k)
    monkeypatch.setattr(builtins,'__import__',safe_import)
    monkeypatch.setattr(_release_disk,'_aggregate_release_files',aggregate)
    monkeypatch.setattr(release_minute_package,'save_release_minute_package',save)
    monkeypatch.setattr(release_minute_package,'load_release_minute_package',forbidden)
    monkeypatch.setattr(_release_minutes,'_aggregate_release_minutes',forbidden)
    assert m.main(['--spec',str(spec),'--scratch',str(scratch),'--output',str(output)])==0
    out,err=capfdbinary.readouterr();assert err==b'';doc=json.loads(out)
    assert events==['aggregate','save'] and len(results)==1 and attempts==[]
    assert doc['source_identities']==[dict(ordinal=0,byte_count=len(payload),sha256=digest)]
    assert doc['counts']==dict(source_count=1,minute_count=32,source_valid_minutes=32,raw_records=32,
        eligible_records=32,excluded_records=0,outside_records=0,unplaced_invalid_rows=0)
    assert doc['resources']['source_content_open_count']==1 and doc['resources']['source_bytes_consumed']==len(payload)
    assert doc['resources']['logical_rows']==32 and doc['resources']['cleanup_status']=='CLEANED'
    assert 0<doc['resources']['database_bytes_at_close']<=8388608
    assert doc['resources']['observed_database_high_water_bytes']<=8388608
    with pytest.raises(FileNotFoundError):scratch.lstat()
    saved=actual_load(output)
    # Fixed recipe oracle: no parser, aggregate, or saved output computes these values.
    expected=(1.,2.,1.,20.,10.,1.,0.,0.,0.,1.,1.,1.,0.)
    assert saved.minutes.values==(expected,)*32 and saved.minutes.source_valid==(True,)*32
    assert saved.minutes.timestamps==tuple(datetime(2026,1,1)+timedelta(minutes=i) for i in range(32))
    assert saved.minutes.label_kinds==(('normal',)*3,)*32
    assert saved.minutes==results[0].minutes
    assert doc['identity']=={key:getattr(saved.identity,key) for key in ('profile_id','context_sha256','manifest_sha256','manifest_byte_count')}
    assert {p.name for p in output.iterdir()}=={'minutes.json','labels.json','diagnostics.json','manifest.json','COMPLETE.json'}
    assert before==tuple((p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in (source,spec))
    assert str(source).encode() not in out and b'artificial-train' not in out and attempts==[]
