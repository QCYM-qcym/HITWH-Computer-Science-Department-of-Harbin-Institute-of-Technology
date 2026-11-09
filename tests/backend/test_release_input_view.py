"""Read-only transport over hand-written values: no prepared package execution."""
from copy import deepcopy
from io import BytesIO
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType

from fastapi.testclient import TestClient
import pytest


FIXTURE=Path(__file__).resolve().parents[1]/'fixtures'/'release-input-view-summary-v1.json'
DATA='/release/v1/input-summary'
ASSETS={'inputs.html':b'<!doctype html><title>inputs</title>',
    'inputs.mjs':b'export const view = true;', 'inputs.css':b'body{color:black}'}
ROUTES={'/release/inputs':('inputs.html','text/html; charset=utf-8'),
    '/release/inputs.mjs':('inputs.mjs','text/javascript; charset=utf-8'),
    '/release/inputs.css':('inputs.css','text/css; charset=utf-8')}
PRIVATE='/private-sentinel/unopened-package/inputs.json'


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')


def api():
    return importlib.import_module('traffic_api.release_input_view')


def hand_saved(envelope):
    """Actual frozen types containing only display inputs, not an authenticated package."""
    from traffic_anomaly import release_inputs as t
    from traffic_anomaly.release_minute_contract import ReleaseMinutePackageIdentity
    s=envelope['summary'];c=s['configuration'];n=s['minute_counts']['total']
    def mask(count):return (True,)*count+(False,)*(n-count)
    identity=t.ReleaseInputIdentity(**s['identity'])
    config=t.ReleasePreparationConfig(c['schema_version'],c['numeric_rules_id'],tuple(f'f{i}' for i in range(13)),
        tuple(c['windows']),c['fit_window'],c['epsilon'],c['audit_fit_policy'],c['policy_status'])
    context=t.ReleaseInputContext(identity.profile_id,'c17-release-91-v1',s['source_authentication'],s['time_basis'],
        ReleaseMinutePackageIdentity(**s['upstream_identity']),config,s['configuration_sha256'],(),n)
    state=t.ReleasePreprocessState((),(),s['fit']['count'],30,c['audit_fit_policy'],s['fit']['mask_sha256'],s['fit']['rows_sha256'])
    counts=s['minute_counts']
    histories=tuple(t.ReleasePreparedHistory(w,(),mask(counts[f'history_h{w}_valid']),()) for w in (15,30))
    minutes=t.ReleasePreparedMinutes((),(),mask(counts['raw_valid']),(),mask(counts['prepared_valid']),(),
        histories,mask(counts['common_valid']))
    qualifications=tuple(t.ReleasePolicyQualification(policy,**{name:mask(count) for name,count in values.items()})
        for policy,values in s['qualification_counts'].items())
    labels=t.ReleaseInputLabels(('P_U','P_B','P_A'),(),(),(),qualifications)
    checks=s['package_checks']
    report=t.ReleaseInputLoadReport(identity.profile_id,checks['status'],checks['scope'],identity,
        checks['byte_integrity'],checks['structure'],checks['upstream_replay'],checks['transform_history_replay'],
        checks['fit_parameters'],s['source_authentication'])
    return t.ReleasePreparedInputs(identity,context,state,minutes,labels,report)


@pytest.fixture(autouse=True)
def no_product_actions(monkeypatch):
    from traffic_anomaly import release_inputs as core,release_input_package as prepared,release_minute_package as raw
    attempts=[]
    def blocked(name):
        def fail(*a,**k):attempts.append(name);raise AssertionError('forbidden product action')
        return fail
    for name in ('prepare_release_inputs','verify_release_input_derivation','_fit_state','_fit_statistics','_transform',
            '_history','_bind_upstream','encode_release_input_package','decode_release_input_package'):
        monkeypatch.setattr(core,name,blocked('core.'+name))
    monkeypatch.setattr(core.ReleasePreparedInputs,'joined',blocked('joined'))
    for module in (prepared,raw):
        for name in ('load_release_input_package','save_release_input_package','load_release_minute_package','save_release_minute_package'):
            if hasattr(module,name):monkeypatch.setattr(module,name,blocked(name))
    yield attempts
    assert attempts==[]


@pytest.fixture
def env(monkeypatch):
    fixture=json.loads(FIXTURE.read_bytes());calls=[]
    stub=ModuleType('traffic_anomaly.release_input_summary')
    def summary(value):calls.append(value);return deepcopy(fixture['cases']['general']['summary'])
    stub.summarize_release_inputs=summary
    monkeypatch.setitem(sys.modules,stub.__name__,stub)
    return fixture,calls,summary,stub


class ResourceTree:
    def __init__(self,values,events,parts=()):self.values=values;self.events=events;self.parts=parts
    def joinpath(self,name):return ResourceTree(self.values,self.events,(*self.parts,name))
    def open(self,mode):
        assert mode=='rb' and self.parts[0]=='release_static' and len(self.parts)==2
        name=self.parts[1];self.events.append(('open',name))
        value=self.values.get(name,FileNotFoundError(PRIVATE))
        if isinstance(value,Exception):raise value
        events=self.events
        class Stream(BytesIO):
            def read(self,size=-1):events.append(('read',name,size));return super().read(size)
        return Stream(value)


def build(monkeypatch,env,*,case='general',assets=None,summary=None):
    fixture,calls,default,stub=env;m=api();values=dict(ASSETS if assets is None else assets);reads=[]
    saved=hand_saved(fixture['cases'][case])
    if summary is None:
        def summary(value):calls.append(value);return deepcopy(fixture['cases'][case]['summary'])
    monkeypatch.setattr(m,'summarize_release_inputs',summary)
    monkeypatch.setattr(m.resources,'files',lambda name:ResourceTree(values,reads) if name=='traffic_api' else pytest.fail('unexpected resource package'))
    app=m.create_release_input_view_app(saved)
    return m,app,saved,values,reads


def safe_headers(response):
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-content-type-options']=='nosniff'
    assert 'etag' not in response.headers and 'access-control-allow-origin' not in response.headers


def fixed_error(response,status,code,*,head=False):
    assert response.status_code==status
    assert response.content==(b'' if head else encoded({'error':code}))
    safe_headers(response)
    if status==405:assert response.headers['allow']=='GET'
    assert PRIVATE.encode() not in response.content


@pytest.mark.parametrize('case',['general','zero_calibration'])
def test_summary_is_frozen_once(monkeypatch,env,case):
    fixture,calls,_,_=env;mutable=deepcopy(fixture['cases'][case]['summary'])
    m=api();encode_calls=[];encoder=m._json_bytes
    def encode(value):encode_calls.append(value);return encoder(value)
    monkeypatch.setattr(m,'_json_bytes',encode)
    def summary(value):calls.append(value);return mutable
    m,app,saved,assets,reads=build(monkeypatch,env,case=case,summary=summary)
    expected=encoded(fixture['cases'][case]);mutable['minute_counts']['total']=9999
    mutable['identity']['manifest_sha256']='f'*64;assets['inputs.css']=b'changed'
    assert calls==[saved] and len(encode_calls)==1
    assert {r.path for r in app.routes}=={DATA,*ROUTES} and all(r.methods=={'GET'} for r in app.routes)
    assert app.openapi_url is app.docs_url is app.redoc_url is None and not app.router.redirect_slashes
    with TestClient(app) as client:
        for _ in range(2):
            response=client.get(DATA);assert response.status_code==200 and response.content==expected;safe_headers(response)
        for path,(name,content_type) in ROUTES.items():
            response=client.get(path);assert response.status_code==200 and response.content==ASSETS[name]
            assert response.headers['content-type']==content_type;safe_headers(response)
    assert calls==[saved] and len(encode_calls)==1
    assert [r for r in reads if r[0]=='read']==[('read',name,65537) for name in ASSETS]


@pytest.mark.parametrize('path',[DATA,*ROUTES])
@pytest.mark.parametrize('query',['?&','?x=','?x=1&x=2','?unknown','?='])
def test_nonempty_raw_query_is_rejected(monkeypatch,env,path,query):
    _,app,*_=build(monkeypatch,env)
    with TestClient(app) as client:fixed_error(client.get(path+query),422,'INVALID_QUERY')


@pytest.mark.parametrize('path',[DATA,*ROUTES])
def test_bare_question_mark_is_allowed(monkeypatch,env,path):
    _,app,*_=build(monkeypatch,env)
    with TestClient(app) as client:
        response=client.get(path+'?');assert response.status_code==200;safe_headers(response)


@pytest.mark.parametrize('path',[DATA,*ROUTES])
@pytest.mark.parametrize('method',['HEAD','POST','PUT','DELETE','OPTIONS','PATCH'])
def test_methods_precede_query_and_head_has_no_body(monkeypatch,env,path,method):
    _,app,*_=build(monkeypatch,env)
    with TestClient(app) as client:fixed_error(client.request(method,path+'?&'),405,'METHOD_NOT_ALLOWED',head=method=='HEAD')


@pytest.mark.parametrize('path',['/missing','/docs','/redoc','/openapi.json','/release/inputs/','/release/v1/input-summary/'])
@pytest.mark.parametrize('method',['GET','POST','HEAD'])
def test_unknown_paths_are_safe_404_without_redirect(monkeypatch,env,path,method):
    _,app,*_=build(monkeypatch,env)
    with TestClient(app) as client:fixed_error(client.request(method,path+'?&',follow_redirects=False),404,'NOT_FOUND',head=method=='HEAD')


@pytest.mark.parametrize('bad',[None,object(),{}],ids=['none','object','mapping'])
def test_wrong_actual_input_type_is_rejected_before_projection(monkeypatch,env,bad):
    m=api();calls=[]
    def forbidden(*a,**k):calls.append('attempt');raise AssertionError()
    monkeypatch.setattr(m,'summarize_release_inputs',forbidden);monkeypatch.setattr(m.resources,'files',forbidden)
    with pytest.raises(m.ReleaseInputViewError) as caught:m.create_release_input_view_app(bad)
    assert caught.value.code=='INVALID_VIEW_INPUT' and str(caught.value)=='INVALID_VIEW_INPUT' and calls==[]


@pytest.mark.parametrize('kind,code',[('projection','INVALID_VIEW_INPUT'),('nan','INVALID_RESULT'),
    ('non-json','INVALID_RESULT'),('unicode','INVALID_RESULT'),('oversize','RESOURCE_LIMIT')])
def test_projection_and_serialization_fail_before_assets(monkeypatch,env,kind,code):
    m=api();saved=hand_saved(env[0]['cases']['general']);attempts=[]
    def summary(value):
        if kind=='projection':raise ValueError(PRIVATE)
        return {'value':{'nan':float('nan'),'non-json':{1},'unicode':'\ud800','oversize':'x'*65536}[kind]}
    def assets(*a):attempts.append('asset');raise AssertionError()
    monkeypatch.setattr(m,'summarize_release_inputs',summary);monkeypatch.setattr(m.resources,'files',assets)
    with pytest.raises(m.ReleaseInputViewError) as caught:m.create_release_input_view_app(saved)
    assert caught.value.code==code and str(caught.value)==code and attempts==[]


@pytest.mark.parametrize('size',[65535,65536,65537])
def test_payload_limit_includes_utf8_and_single_lf(monkeypatch,env,size):
    m=api();overhead=len(encoded(dict(version=1,command='inspect',status='INTERNAL_CONSISTENCY_CHECKED',summary={'text':''},replay=None)))
    summary={'text':'中'+'x'*(size-overhead-3)}
    if size>65536:
        with pytest.raises(m.ReleaseInputViewError) as caught:build(monkeypatch,env,summary=lambda value:summary)
        assert caught.value.code=='RESOURCE_LIMIT'
    else:
        _,app,*_=build(monkeypatch,env,summary=lambda value:summary)
        response=TestClient(app).get(DATA)
        assert len(response.content)==size and response.content.endswith(b'\n') and b'\r' not in response.content


@pytest.mark.parametrize('name',list(ASSETS))
@pytest.mark.parametrize('fault',['missing','empty','oversize','utf8','io'])
def test_assets_are_bounded_utf8_and_all_required(monkeypatch,env,name,fault):
    m=api();assets=dict(ASSETS)
    if fault=='missing':del assets[name]
    else:assets[name]={'empty':b'','oversize':b'x'*65537,'utf8':b'\xff','io':OSError(PRIVATE)}[fault]
    with pytest.raises(m.ReleaseInputViewError) as caught:build(monkeypatch,env,assets=assets)
    assert caught.value.code=='VIEWER_ASSETS_UNAVAILABLE' and str(caught.value)=='VIEWER_ASSETS_UNAVAILABLE'


def test_three_assets_exact_total_limit(monkeypatch,env):
    assets={name:b'x'*65536 for name in ASSETS}
    _,app,_,_,reads=build(monkeypatch,env,assets=assets)
    with TestClient(app) as client:assert sum(len(client.get(path).content) for path in ROUTES)==196608
    assert all(row[2]==65537 for row in reads if row[0]=='read')


@pytest.mark.parametrize('code',['INVALID_VIEW_INPUT','INVALID_RESULT','RESOURCE_LIMIT','VIEWER_ASSETS_UNAVAILABLE',
    PRIVATE,None,True,[],{}],ids=[f'code-{i}' for i in range(9)])
def test_factory_error_constructor_has_safe_code_domain(env,code):
    m=api();error=m.ReleaseInputViewError(code)
    expected=code if type(code) is str and code in ('INVALID_VIEW_INPUT','INVALID_RESULT','RESOURCE_LIMIT','VIEWER_ASSETS_UNAVAILABLE') else 'INVALID_VIEW_INPUT'
    assert error.code==expected and str(error)==expected


def test_factory_prewarms_actual_four_endpoint_cache(monkeypatch,env):
    import fastapi.routing
    _,app,*_=build(monkeypatch,env)
    assert len(app.routes)==4
    assert all(id(route.endpoint) in fastapi.routing._endpoint_context_cache for route in app.routes)


def test_requests_do_not_reload_or_encode(monkeypatch,env):
    m,app,*_=build(monkeypatch,env);attempts=[]
    import builtins
    import io
    import os
    from traffic_anomaly import release_inputs
    roots=(Path(m.__file__).parent,Path(release_inputs.__file__).parent)
    def forbidden(name):
        def stop(*a,**k):attempts.append(name);raise AssertionError('forbidden request action')
        return stop
    def file_guard(original):
        def opened(path,*a,**k):
            if isinstance(path,(str,bytes,os.PathLike)):
                value=Path(os.fsdecode(path)).absolute()
                if any(value.is_relative_to(root) for root in roots):return forbidden('package/source open')()
            return original(path,*a,**k)
        return opened
    # Starting TestClient's ASGI lifespan is not an endpoint request/prewarm.
    with TestClient(app,raise_server_exceptions=False) as client:
        monkeypatch.setattr(m,'summarize_release_inputs',forbidden('summary alias'))
        monkeypatch.setattr(env[3],'summarize_release_inputs',forbidden('summary module'))
        monkeypatch.setattr(m,'_json_bytes',forbidden('payload encode'))
        monkeypatch.setattr(m.resources,'files',forbidden('assets'))
        monkeypatch.setattr(ResourceTree,'open',forbidden('asset open'))
        monkeypatch.setattr(builtins,'open',file_guard(builtins.open))
        monkeypatch.setattr(io,'open',file_guard(io.open))
        for path in (DATA,*ROUTES):
            assert client.get(path).status_code==200
            fixed_error(client.get(path+'?&'),422,'INVALID_QUERY')
            fixed_error(client.head(path),405,'METHOD_NOT_ALLOWED',head=True)
            fixed_error(client.post(path),405,'METHOD_NOT_ALLOWED')
        fixed_error(client.get('/unknown'),404,'NOT_FOUND')
    assert attempts==[]


def test_endpoint_exception_is_fixed_500_with_safe_headers(monkeypatch,env):
    m,app,*_=build(monkeypatch,env);original=m.Response
    def response(content,*a,**k):
        if content==encoded(env[0]['cases']['general']):raise RuntimeError(PRIVATE)
        return original(content,*a,**k)
    monkeypatch.setattr(m,'Response',response)
    with TestClient(app,raise_server_exceptions=False) as client:fixed_error(client.get(DATA),500,'INTERNAL_ERROR')


@pytest.mark.parametrize('case',['general','zero_calibration'])
def test_real_public_summary_cli_api_bytes_and_cold_guards(monkeypatch,capfdbinary,case):
    import builtins
    import io
    import os
    from traffic_anomaly import release_input_summary as shared,release_input_cli as cli,release_inputs
    assert getattr(shared,'__file__',None) and shared.summarize_release_inputs.__module__==shared.__name__
    # Rebind after any earlier isolated-module stub tests, using the real import.
    m=importlib.reload(api());real=shared.summarize_release_inputs
    assert m.summarize_release_inputs is real and cli.summarize_release_inputs is real
    expected=json.loads(FIXTURE.read_bytes())['cases'][case];saved=hand_saved(expected)
    loads=[];calls=[];encodes=[];reads=[];attempts=[]
    def load(path):loads.append(path);return saved
    monkeypatch.setattr(cli,'load_release_input_package',load)
    assert cli.main(['inspect','--prepared-package','C:/handwritten-not-opened'])==0
    cli_bytes,err=capfdbinary.readouterr();assert err==b'' and cli_bytes==encoded(expected) and len(loads)==1
    def summary(value):calls.append(value);return real(value)
    encoder=m._json_bytes
    def encode(value):encodes.append(value);return encoder(value)
    monkeypatch.setattr(m,'summarize_release_inputs',summary);monkeypatch.setattr(m,'_json_bytes',encode)
    monkeypatch.setattr(m.resources,'files',lambda name:ResourceTree(dict(ASSETS),reads))
    app=m.create_release_input_view_app(saved)
    assert calls==[saved] and len(encodes)==1
    roots=(Path(m.__file__).parent,Path(release_inputs.__file__).parent)
    def forbidden(name):
        def stop(*a,**k):attempts.append(name);raise AssertionError('forbidden cold request action')
        return stop
    def file_guard(original):
        def opened(path,*a,**k):
            if isinstance(path,(str,bytes,os.PathLike)) and any(Path(os.fsdecode(path)).absolute().is_relative_to(root) for root in roots):
                return forbidden('source/package open')()
            return original(path,*a,**k)
        return opened
    with TestClient(app,raise_server_exceptions=False) as client:
        monkeypatch.setattr(shared,'summarize_release_inputs',forbidden('real summary'))
        monkeypatch.setattr(m,'summarize_release_inputs',forbidden('backend alias'))
        monkeypatch.setattr(cli,'summarize_release_inputs',forbidden('CLI alias'))
        monkeypatch.setattr(cli,'load_release_input_package',forbidden('CLI loader'))
        monkeypatch.setattr(m,'_json_bytes',forbidden('payload encode'))
        monkeypatch.setattr(m.resources,'files',forbidden('resource files'))
        monkeypatch.setattr(ResourceTree,'open',forbidden('resource open'))
        monkeypatch.setattr(builtins,'open',file_guard(builtins.open));monkeypatch.setattr(io,'open',file_guard(io.open))
        response=client.get(DATA);assert response.status_code==200 and response.content==cli_bytes==encoded(expected)
        for path,(name,_) in ROUTES.items():assert client.get(path).content==ASSETS[name]
    assert calls==[saved] and len(encodes)==1 and len(loads)==1 and attempts==[]


def test_cold_endpoints_do_not_enter_threadpool(monkeypatch,env):
    import fastapi.routing
    _,app,*_=build(monkeypatch,env);attempts=[]
    async def forbidden(*a,**k):
        attempts.append('fastapi.run_in_threadpool')
        raise AssertionError('endpoint must not lazily enter the thread backend')
    with TestClient(app,raise_server_exceptions=False) as client:
        # Portal startup may initialize AnyIO in tests; forbid the actual
        # FastAPI call site before the first endpoint instead of trusting it.
        monkeypatch.setattr(fastapi.routing,'run_in_threadpool',forbidden)
        responses=[client.get(path) for path in (DATA,*ROUTES)]
    expected=[(200,encoded(env[0]['cases']['general']))]+[(200,ASSETS[name]) for name,_ in ROUTES.values()]
    actual=[(response.status_code,response.content) for response in responses]
    assert actual==expected, (actual,attempts)
    assert attempts==[]
