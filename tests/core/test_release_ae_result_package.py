"""Proposed disk-only tests; not installed/collected/executed during preparation.

Independent native hand declarations have N64/four scores/two calibration4s.
Closed filesystem seams exercise observations, not atomicity or real links.
"""
import builtins
from dataclasses import fields, is_dataclass, replace
from datetime import datetime
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


MODULE = 'traffic_anomaly.release_ae_result_package'
CONTRACT = 'traffic_anomaly.release_ae_result_contract'
MEMBERS = ('result.json', 'manifest.json', 'COMPLETE.json')
LIMITS = dict(zip(MEMBERS, (2097152, 65536, 4096)))
UNCHANGED = object()
G13 = ('completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum',
    'fwd_source_length_sum', 'bwd_source_length_sum', 'tcp_source_record_count',
    'udp_source_record_count', 'known_other_source_protocol_record_count',
    'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s',
    'duration_p95_s', 'no_backward_packet_source_record_count')


def _api():
    if importlib.util.find_spec(MODULE) is None:
        pytest.fail('release_ae_result_package public disk API is not implemented')
    api = importlib.import_module(MODULE)
    for name in ('save_release_ae_result_package', 'load_release_ae_result_package'):
        assert callable(getattr(api, name, None)), 'public saved-AE-result disk API is missing'
    return api


@pytest.fixture(autouse=True)
def _no_new_models(monkeypatch):
    roots = {'torch', 'sklearn', 'joblib', 'tensorflow', 'tf', 'jax', 'jaxlib', 'cloudpickle'}
    baseline = {n: m for n, m in sys.modules.items() if n.split('.')[0] in roots}
    attempts = []
    original, dynamic = builtins.__import__, importlib.import_module
    def check(name):
        if name.split('.')[0] in roots:
            attempts.append(name)
            raise AssertionError('disk hand tests must not import model runtimes')
    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None): check(fullname)
    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        full = importlib.util.resolve_name('.'*level+name, globals['__package__']) if level and globals and globals.get('__package__') else name
        check(full)
        return original(name, globals, locals, fromlist, level)
    def imported(name, package=None):
        check(importlib.util.resolve_name(name, package) if name.startswith('.') else name)
        return dynamic(name, package)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, '__import__', guarded)
        patch.setattr(importlib, 'import_module', imported)
        patch.setattr(sys, 'meta_path', [Fence(), *sys.meta_path])
        yield
    assert attempts == []
    current = {n: m for n, m in sys.modules.items() if n.split('.')[0] in roots}
    assert current.keys() == baseline.keys() and all(current[n] is m for n, m in baseline.items())


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)+'\n').encode()


def _projection(view):
    width = 13 if view == 'current13' else 26
    scores, current, history, predictions = ([None]*64 for _ in range(4))
    mask = [False]*64
    for i, score, a, b in ((30,-0.,-0.,-0.), (31,8.,6.,10.), (62,4.,2.,6.), (63,4.,2.,6.)):
        scores[i], current[i], history[i] = score, score if width == 13 else a, None if width == 13 else b
        mask[i], predictions[i] = True, i == 31
    ref = lambda profile,a,b,n:dict(profile_id=profile,context_sha256=a*64,manifest_sha256=b*64,manifest_byte_count=n)
    config = dict(model_profile_id='c17-i1-g13u-ae-synthetic-v1',parameter_status='ENGINEERING_TOY_ONLY',
        method='current_ae' if width == 13 else 'history_ae',input_width=width,history_window=None if width == 13 else 30,
        architecture=[width,8,3,8,width],parameter_count=288 if width == 13 else 509,activation='RELU_HIDDEN_LINEAR_OUTPUT',
        device='cpu',training_dtype='float32',score_dtype='float64',score_rule='FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT',
        epochs=5,batch_strategy='FULL_BATCH',shuffle=False,optimizer='Adam',optimizer_cpu_guard='INSTANCE_LOCAL_HEALTH_CHECK_V1',
        optimizer_healthcheck_api='_accelerator_graph_capture_health_check',learning_rate=.001,adam_betas=[.9,.999],
        adam_epsilon=1e-8,weight_decay=0.,amsgrad=False,random_state=42,fit_scope='TRAIN_NORMAL_COMMON',
        calibration_scope='CALIBRATION_NORMAL_COMMON',quantile=.99,quantile_method='linear',alarm_comparison='STRICT_GREATER',
        preprocessing_fit_provenance='NOT_REESTIMATED')
    return dict(profile_id='c17-release-ae-engineering-v1',scope='IN_MEMORY_ENGINEERING_NUMERICAL_RESULT_ONLY',view=view,
        raw_identity=ref('c17-release-minute-package-v1','a','b',101),
        prepared_identity=ref('c17-release-prepared-input-package-v1','c','d',202),configuration_sha256='e'*64,
        feature_columns=['current:'+n for n in G13]+(['residual_h30:'+n for n in G13] if width == 26 else []),
        scores=scores,predictions=predictions,scored_mask=mask,current_reconstruction_mse=current,
        history_deviation_reconstruction_mse=history,threshold=4.,train_indices=[31],calibration_indices=[62,63],
        preprocessing_fit_indices=[0,29,31],training_losses=[.5,.4,.3,.2,.1],configuration=config,
        calibration=dict(quantile=.99,method='linear',comparison='STRICT_GREATER',sample_count=2,equal_count=2,strictly_above_count=0),
        runtime=dict(python_version='3.14.0',numpy_version='2.5.4',torch_version='2.14.1+cpu',device='cpu',torch_num_threads=2,torch_num_interop_threads=3))


def _context(view):
    p = _projection(view)
    return dict(profile_id='c17-release-ae-result-package-v1',result_profile_id=p['profile_id'],view=view,
        raw_identity=p['raw_identity'],prepared_identity=p['prepared_identity'],configuration_sha256=p['configuration_sha256'],
        source_schema_id='c17-release-91-v1',source_authentication='NOT_AUTHENTICATED',time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',
        policy_status='AUDIT_ONLY',audit_fit_policy='P_U',minute_count=64,score_direction='HIGHER_IS_MORE_ANOMALOUS',segments=[
        dict(ordinal=0,id='train',role='train',start='2026-01-01T00:00:00',end='2026-01-01T00:32:00'),
        dict(ordinal=1,id='cal',role='calibration',start='2026-01-01T02:00:00',end='2026-01-01T02:32:00')])


def reference_members(view='current13', *, context=None):
    context = _context(view) if context is None else context
    digest = hashlib.sha256(canonical(context)).hexdigest()
    result = canonical(dict(schema_version=1,profile_id='c17-release-ae-result-package-v1',context_sha256=digest,result=_projection(view)))
    manifest = canonical(dict(schema_version=1,profile_id='c17-release-ae-result-package-v1',context_sha256=digest,context=context,
        members={'result.json':dict(byte_count=len(result),sha256=hashlib.sha256(result).hexdigest())}))
    complete = canonical(dict(schema_version=1,profile_id='c17-release-ae-result-package-v1',status='COMPLETE',
        manifest=dict(byte_count=len(manifest),sha256=hashlib.sha256(manifest).hexdigest())))
    return dict(zip(MEMBERS,(result,manifest,complete)))


def hand_package(view='current13', *, context=None):
    """Public frozen holders, independently built identity; no setup Q99/codec."""
    contract = importlib.import_module(CONTRACT)
    from traffic_anomaly.release_autoencoder import ReleaseAEResult, ReleaseAEConfiguration, ReleaseAECalibration, ReleaseAERuntime
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackageIdentity
    from traffic_anomaly.release_inputs import ReleaseInputIdentity
    from traffic_anomaly._release_minutes import ReleaseSegment
    p, c = _projection(view), _context(view) if context is None else context
    config = dict(p['configuration']);config['architecture']=tuple(config['architecture']);config['adam_betas']=tuple(config['adam_betas'])
    native = dict(p,raw_identity=ReleaseMinutePackageIdentity(**p['raw_identity']),prepared_identity=ReleaseInputIdentity(**p['prepared_identity']),
        configuration=ReleaseAEConfiguration(**config),calibration=ReleaseAECalibration(**p['calibration']),runtime=ReleaseAERuntime(**p['runtime']))
    for key in ('feature_columns','scores','predictions','scored_mask','current_reconstruction_mse','history_deviation_reconstruction_mse',
                'train_indices','calibration_indices','preprocessing_fit_indices','training_losses'):native[key]=tuple(native[key])
    context_native=dict(c,raw_identity=ReleaseMinutePackageIdentity(**c['raw_identity']),prepared_identity=ReleaseInputIdentity(**c['prepared_identity']),
        segments=tuple(ReleaseSegment(s['id'],s['role'],datetime.fromisoformat(s['start']),datetime.fromisoformat(s['end'])) for s in c['segments']))
    members=reference_members(view,context=c);manifest=members['manifest.json']
    identity=contract.ReleaseAEResultIdentity('c17-release-ae-result-package-v1',hashlib.sha256(canonical(c)).hexdigest(),hashlib.sha256(manifest).hexdigest(),len(manifest))
    report=contract.ReleaseAEResultLoadReport(profile_id='c17-release-ae-result-load-report-v1',scope='SAVED_AE_RESULT_INTERNAL_CONSISTENCY_ONLY',
        byte_integrity='MATCHED',structure='MATCHED',saved_score_q99='MATCHED',input_declaration_binding='MATCHED',input_pair_binding='NOT_PERFORMED',
        derivation_replay='NOT_PERFORMED',source_authentication='NOT_AUTHENTICATED',model_execution='NOT_AUTHENTICATED')
    return contract.ReleaseAEResultPackage(identity,contract.ReleaseAEResultContext(**context_native),ReleaseAEResult(**native),report)


def _wire(value):
    if is_dataclass(value):return {f.name:_wire(getattr(value,f.name)) for f in fields(value)}
    if type(value) is tuple:return [_wire(v) for v in value]
    return value


def _exact(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys()==expected.keys()
        for key in expected:_exact(actual[key],expected[key])
    elif type(expected) in (list,tuple):
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected):_exact(a,b)
    elif type(expected) is float:assert actual.hex()==expected.hex()
    else:assert actual==expected


def _write_hand(directory, view='current13'):
    directory.mkdir()
    for name,data in reference_members(view).items():(directory/name).write_bytes(data)


def _error(code, call):
    owner=importlib.import_module(CONTRACT).ReleaseAEResultPackageError
    record=(False,None,False,False)
    try:call()
    except BaseException as error:
        if type(error) is owner:
            try:
                found,args=error.code,error.args
                record=(True,found if type(found) is str else None,type(args) is tuple and args==(code,),error.__suppress_context__ is True)
            except BaseException:record=(True,None,False,False)
    assert record==(True,code,True,True)


def _spy_math(monkeypatch):
    contract=importlib.import_module(CONTRACT)
    from traffic_anomaly.evaluation import calibration
    original=calibration.calibrate;rows=[]
    def counted(scores,quantile=.99):
        rows.append((tuple(float(v) for v in scores),quantile));return original(scores,quantile)
    monkeypatch.setattr(calibration,'calibrate',counted)
    for name,value in tuple(vars(contract).items()):
        if value is original:monkeypatch.setattr(contract,name,counted)
    return rows


def _fake_math(monkeypatch):
    contract=importlib.import_module(CONTRACT)
    import numpy as np
    rows=[]
    def literal(scores,quantile=.99):rows.append((tuple(float(v) for v in scores),quantile));return 4.
    monkeypatch.setattr(contract,'_dependencies',lambda:(np,literal))
    return rows


def _deny_math(monkeypatch):
    calls=[]
    def denied():calls.append('dependencies');raise AssertionError('disk preflight must precede math')
    monkeypatch.setattr(importlib.import_module(CONTRACT),'_dependencies',denied)
    return calls


class StreamProxy:
    def __init__(self,stream,path,mode,hook):
        self.stream,self.path,self.mode,self.hook=stream,path,mode,hook
        self.close_hook_seen=False
    def __enter__(self):self.stream.__enter__();return self
    def _observe_close_once(self):
        if not self.close_hook_seen:
            self.close_hook_seen=True
            self.hook('close',self,None)
    def close(self):
        try:return self.stream.close()
        finally:self._observe_close_once()
    def __exit__(self,kind,value,tb):
        try:return self.stream.__exit__(kind,value,tb)
        finally:self._observe_close_once()
    def __getattr__(self,name):return getattr(self.stream,name)
    def read(self,count=-1):
        self.hook('read-before',self,count)
        data=self.stream.read(count);value=self.hook('read-after',self,(count,data))
        return data if value is UNCHANGED else value
    def write(self,data):
        self.hook('write-before',self,data)
        count=self.stream.write(data);value=self.hook('write-after',self,(data,count))
        return count if value is UNCHANGED else value
    def flush(self):self.hook('flush',self,None);return self.stream.flush()


def _open_hook(monkeypatch,hook):
    original=Path.open
    def opened(path,mode='r',*args,**kwargs):
        hook('open-before',path,mode)
        return StreamProxy(original(path,mode,*args,**kwargs),path,mode,hook)
    monkeypatch.setattr(Path,'open',opened)
    return original


def _no_path_io(monkeypatch):
    """Invalid lexical arguments must not reach a filesystem boundary."""
    attempts=[]
    def denied(*args,**kwargs):attempts.append('path-io');raise AssertionError('invalid path reached filesystem')
    for name in ('open','mkdir','lstat'):monkeypatch.setattr(Path,name,denied)
    return attempts


class TestPackage:
    @pytest.mark.parametrize('view',('current13','h30_26'))
    def test_save_load_exact_bytes_one_retained_readback_and_q99_ledgers(self,view,tmp_path,monkeypatch):
        api=_api()
        package=hand_package(view);output=tmp_path/'saved';events=[];reads=[]
        math_calls=_spy_math(monkeypatch)
        def hook(event,value,detail):
            if event=='open-before':
                events.append((value.name,detail))
                if value.name=='COMPLETE.json' and detail=='xb':assert {p.name for p in output.iterdir()}=={'result.json','manifest.json'}
            elif event=='read-before':
                assert type(detail) is int and 0<detail<=LIMITS[value.path.name]+1
                reads.append(value.path.name)
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);identity=api.save_release_ae_result_package(package,output)
        assert identity==package.identity and math_calls==[((4.,4.),.99)]*2
        assert [n for n,m in events if m=='xb']==list(MEMBERS)
        assert sorted(n for n,m in events if m=='rb')==sorted(MEMBERS)
        assert sorted(reads)==sorted(MEMBERS)
        assert {p.name:p.read_bytes() for p in output.iterdir()}==reference_members(view)
        events.clear();reads.clear();math_calls.clear()
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);loaded=api.load_release_ae_result_package(output)
        assert [n for n,m in events if m=='rb']==['COMPLETE.json','manifest.json','result.json']
        assert reads==['COMPLETE.json','manifest.json','result.json']
        assert math_calls==[((4.,4.),.99)]
        _exact(_wire(loaded.result),_projection(view))
        assert loaded.identity==identity and loaded.result.scores[30].hex()=='-0x0.0p+0'

    @pytest.mark.parametrize('view',('current13','h30_26'))
    def test_moved_hand_package_reads_only_its_three_members(self,view,tmp_path,monkeypatch):
        api=_api()
        original=tmp_path/'original';_write_hand(original,view);moved=tmp_path/'moved';original.rename(moved)
        calls=_spy_math(monkeypatch);opened=[]
        def hook(event,value,detail):
            if event=='open-before':assert value.parent==moved and detail=='rb';opened.append(value.name)
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);loaded=api.load_release_ae_result_package(moved)
        assert not original.exists() and opened==['COMPLETE.json','manifest.json','result.json']
        _exact(_wire(loaded.result),_projection(view));assert calls==[((4.,4.),.99)]

    @pytest.mark.parametrize('fault',('identity','context'))
    def test_bad_native_package_rejects_before_output_or_math(self,fault,tmp_path,monkeypatch):
        api=_api()
        if fault=='identity':
            package=hand_package();package=replace(package,identity=replace(package.identity,manifest_sha256='f'*64));code='INTEGRITY_MISMATCH'
        else:
            context=_context('current13');context['minute_count']=63;package=hand_package(context=context);code='INCONSISTENT_PACKAGE'
        output=tmp_path/'bad';calls=_deny_math(monkeypatch);opened=[]
        def hook(event,value,detail):
            if event=='open-before':opened.append(value)
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);_error(code,lambda:api.save_release_ae_result_package(package,output))
        assert not output.exists() and calls==[] and opened==[]

    @pytest.mark.parametrize('fault',('missing','extra','hardlink-stat','reparse-stat','alias-stat'))
    def test_load_inventory_rejects_before_open_or_math(self,fault,tmp_path,monkeypatch):
        api=_api()
        directory=tmp_path/'package';_write_hand(directory)
        if fault=='missing':(directory/'manifest.json').unlink()
        elif fault=='extra':(directory/'extra').write_bytes(b'kept')
        code='INVALID_PACKAGE' if fault in ('missing','extra') else 'INVALID_PACKAGE_PATH'
        original=Path.lstat;other=original(directory/'result.json')
        def lstat(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if path==directory/'manifest.json' and fault.endswith('-stat'):
                attrs={n:getattr(value,n) for n in dir(value) if n.startswith('st_')}
                if fault=='hardlink-stat':attrs['st_nlink']=2
                elif fault=='reparse-stat':attrs['st_file_attributes']=1024
                else:attrs.update(st_dev=other.st_dev,st_ino=other.st_ino)
                return SimpleNamespace(**attrs)
            return value
        calls=_deny_math(monkeypatch);opened=[]
        def hook(event,value,detail):
            if event=='open-before':opened.append(value)
            return UNCHANGED
        with monkeypatch.context() as patch:
            patch.setattr(Path,'lstat',lstat);_open_hook(patch,hook)
            _error(code,lambda:api.load_release_ae_result_package(directory))
        assert calls==[] and opened==[]

    @pytest.mark.parametrize('member',MEMBERS)
    def test_member_resource_cap_is_checked_before_any_open(self,member,tmp_path,monkeypatch):
        api=_api()
        directory=tmp_path/'large';_write_hand(directory);(directory/member).write_bytes(b'x'*(LIMITS[member]+1))
        calls=_deny_math(monkeypatch);opened=[]
        def hook(event,value,detail):
            if event=='open-before':opened.append(value)
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);_error('RESOURCE_LIMIT',lambda:api.load_release_ae_result_package(directory))
        assert calls==[] and opened==[]

    @pytest.mark.parametrize('operation',('save','load'))
    @pytest.mark.parametrize('kind',('none','bytes','foreign','text-subclass'))
    def test_path_arguments_reject_foreign_coercion(self,operation,kind,tmp_path,monkeypatch):
        api=_api()
        package=hand_package();touched=[]
        class Foreign:
            def __fspath__(self):touched.append('fspath');raise RuntimeError('private path')
            def __str__(self):touched.append('str');raise RuntimeError('private path')
        class Text(str):
            def __str__(self):touched.append('str');raise RuntimeError('private path')
        argument={'none':None,'bytes':b'not-a-path','foreign':Foreign(),'text-subclass':Text(str(tmp_path/'bad'))}[kind]
        fake=_fake_math(monkeypatch)
        call=(lambda:api.save_release_ae_result_package(package,argument)) if operation=='save' else (lambda:api.load_release_ae_result_package(argument))
        with monkeypatch.context() as patch:
            io=_no_path_io(patch);_error('INVALID_PACKAGE_ARGUMENTS',call)
        assert touched==[] and io==[] and len(fake)<= (1 if operation=='save' else 0)

    @pytest.mark.parametrize('operation',('save','load'))
    @pytest.mark.parametrize('kind',('relative','parent','unc','nul','reserved','ads'))
    def test_unsafe_lexical_paths_never_create_output(self,operation,kind,tmp_path,monkeypatch):
        api=_api()
        if kind in ('reserved','ads') and os.name!='nt':pytest.skip('Windows lexical path rules')
        package=hand_package();fake=_fake_math(monkeypatch)
        choices={'relative':'relative-result','parent':str(tmp_path)+'/../bad-result','unc':'//server/share/result',
            'nul':str(tmp_path)+'/bad\0name','reserved':str(tmp_path/'CON'),'ads':str(tmp_path/'name:stream')}
        before={p.name for p in tmp_path.iterdir()}
        call=(lambda:api.save_release_ae_result_package(package,choices[kind])) if operation=='save' else (lambda:api.load_release_ae_result_package(choices[kind]))
        with monkeypatch.context() as patch:
            io=_no_path_io(patch);_error('INVALID_PACKAGE_PATH',call)
        assert io==[] and {p.name for p in tmp_path.iterdir()}==before and len(fake)<= (1 if operation=='save' else 0)

    @pytest.mark.parametrize('state',('empty','partial','complete'))
    def test_existing_output_is_retained_without_overwrite(self,state,tmp_path,monkeypatch):
        api=_api()
        output=tmp_path/'existing';output.mkdir()
        if state=='partial':(output/'result.json').write_bytes(b'partial-original')
        elif state=='complete':
            for name,data in reference_members().items():(output/name).write_bytes(data)
        before={p.name:p.read_bytes() for p in output.iterdir()};fake=_fake_math(monkeypatch)
        _error('OUTPUT_EXISTS',lambda:api.save_release_ae_result_package(hand_package(),output))
        assert {p.name:p.read_bytes() for p in output.iterdir()}==before and len(fake)<=1

    @pytest.mark.parametrize('fault',('short','grow','signature-double'))
    def test_load_observed_read_or_signature_changes_reject_without_second_read(self,fault,tmp_path,monkeypatch):
        api=_api()
        directory=tmp_path/'raced';_write_hand(directory);reads=[];calls=_deny_math(monkeypatch)
        original=Path.open;original_lstat=Path.lstat;signature=dict(changed=False,observed=0)
        def lstat(path,*args,**kwargs):
            value=original_lstat(path,*args,**kwargs)
            if path==directory/'COMPLETE.json' and signature['changed']:
                attrs={n:getattr(value,n) for n in dir(value) if n.startswith('st_')}
                attrs['st_ino']=value.st_ino+1
                signature['observed']+=1
                return SimpleNamespace(**attrs)
            return value
        def hook(event,value,detail):
            if event=='read-before':
                assert value.path.name=='COMPLETE.json' and 0<detail<=LIMITS['COMPLETE.json']+1;reads.append(detail)
            if event=='read-after':
                count,data=detail
                if fault=='short':return data[:-1]
                if fault=='grow':
                    with original(value.path,'ab') as stream:stream.write(b'x')
                else:
                    # Closed metadata double, not a physical live-handle swap.
                    signature['changed']=True
            return UNCHANGED
        with monkeypatch.context() as patch:
            if fault=='signature-double':patch.setattr(Path,'lstat',lstat)
            _open_hook(patch,hook);_error('PACKAGE_CHANGED',lambda:api.load_release_ae_result_package(directory))
        assert len(reads)==1 and calls==[]
        if fault=='signature-double':assert signature['changed'] and signature['observed']>0

    @pytest.mark.parametrize('kind',('owned','memory'))
    def test_read_primary_survives_later_stream_close_error(self,kind,tmp_path,monkeypatch):
        api=_api()
        directory=tmp_path/'primary';_write_hand(directory);owner=importlib.import_module(CONTRACT).ReleaseAEResultPackageError
        primary=owner('PACKAGE_CHANGED') if kind=='owned' else MemoryError('private memory');calls=_deny_math(monkeypatch);faults=[]
        def hook(event,value,detail):
            if event=='read-before':faults.append('primary-read');raise primary
            if event=='close':faults.append('secondary-close');raise OSError('later private close')
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);_error('PACKAGE_CHANGED' if kind=='owned' else 'RESOURCE_LIMIT',lambda:api.load_release_ae_result_package(directory))
        assert calls==[]
        assert faults==['primary-read','secondary-close']

    @pytest.mark.parametrize('fault',('short','bool','flush','close'))
    def test_failed_member_write_keeps_residue_and_never_writes_complete(self,fault,tmp_path,monkeypatch):
        api=_api()
        output=tmp_path/'partial';package=hand_package();fake=_fake_math(monkeypatch);close_faults=[]
        def hook(event,value,detail):
            if event=='open-before':assert value.name=='result.json'
            if event=='write-after':
                if fault=='short':return detail[1]-1
                if fault=='bool':return True
            if event=='flush' and fault=='flush':raise OSError('private flush')
            if event=='close' and fault=='close':close_faults.append('close');raise OSError('private close')
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);_error('OUTPUT_ERROR',lambda:api.save_release_ae_result_package(package,output))
        assert output.is_dir() and (output/'result.json').exists() and not (output/'COMPLETE.json').exists()
        assert fake==[((4.,4.),.99)]
        assert close_faults==(['close'] if fault=='close' else [])

    def test_same_size_wrong_readback_is_detected_without_resealing_disk(self,tmp_path,monkeypatch):
        api=_api()
        output=tmp_path/'wrong-readback';package=hand_package();fake=_fake_math(monkeypatch)
        def hook(event,value,detail):
            if event=='read-after':
                data=detail[1];return bytes([data[0]^1])+data[1:]
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);_error('INTEGRITY_MISMATCH',lambda:api.save_release_ae_result_package(package,output))
        assert (output/'result.json').read_bytes()==reference_members()['result.json'] and fake==[((4.,4.),.99)]

    def test_final_readback_failure_can_leave_a_complete_loadable_package(self,tmp_path,monkeypatch):
        api=_api()
        output=tmp_path/'complete-residue';package=hand_package();real=_spy_math(monkeypatch);owner=importlib.import_module(CONTRACT).ReleaseAEResultPackageError
        def hook(event,value,detail):
            if event=='read-before' and value.path.name=='COMPLETE.json':raise owner('OUTPUT_ERROR')
            return UNCHANGED
        with monkeypatch.context() as patch:
            fake=_fake_math(patch);_open_hook(patch,hook)
            _error('OUTPUT_ERROR',lambda:api.save_release_ae_result_package(package,output))
        assert {p.name:p.read_bytes() for p in output.iterdir()}==reference_members()
        assert fake==[((4.,4.),.99)] and real==[]
        loaded=api.load_release_ae_result_package(output)
        _exact(_wire(loaded.result),_projection('current13'));assert real==[((4.,4.),.99)]

    def test_write_primary_memory_failure_survives_later_close_failure(self,tmp_path,monkeypatch):
        api=_api()
        output=tmp_path/'memory-residue';package=hand_package();fake=_fake_math(monkeypatch);faults=[]
        def hook(event,value,detail):
            if event=='write-before':faults.append('primary-write');raise MemoryError('first private memory')
            if event=='close':faults.append('secondary-close');raise OSError('later private close')
            return UNCHANGED
        with monkeypatch.context() as patch:
            _open_hook(patch,hook);_error('RESOURCE_LIMIT',lambda:api.save_release_ae_result_package(package,output))
        assert output.exists() and fake==[((4.,4.),.99)]
        assert faults==['primary-write','secondary-close']

    @pytest.mark.parametrize('kind',('ordinary','foreign','memory','keyboard','exit','owned'))
    def test_disk_error_conversion_uses_native_types_without_foreign_getters(self,kind,tmp_path,monkeypatch):
        api=_api()
        directory=tmp_path/'errors';_write_hand(directory);touched=[]
        class Foreign(Exception):
            @property
            def __class__(self):touched.append('class');raise RuntimeError('private class')
            @property
            def code(self):touched.append('code');raise RuntimeError('private code')
        owner=importlib.import_module(CONTRACT).ReleaseAEResultPackageError
        primary={'ordinary':OSError('private path'),'foreign':Foreign('private text'),'memory':MemoryError('private memory'),
            'keyboard':KeyboardInterrupt('private interrupt'),'exit':SystemExit(17),'owned':owner('INPUT_UNAVAILABLE')}[kind]
        calls=_deny_math(monkeypatch)
        def hook(event,value,detail):
            if event=='open-before':raise primary
            return UNCHANGED
        call=lambda:api.load_release_ae_result_package(directory)
        with monkeypatch.context() as patch:
            _open_hook(patch,hook)
            if kind in ('keyboard','exit'):
                same=False
                try:call()
                except BaseException as received:same=received is primary
                assert same is True
            else:_error('RESOURCE_LIMIT' if kind=='memory' else 'INPUT_UNAVAILABLE' if kind in ('ordinary','owned') else 'PACKAGE_ERROR',call)
        assert touched==[] and calls==[]
