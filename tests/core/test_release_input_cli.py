"""Release input CLI checkpoints; bounded artificial snapshots, never models."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def cli():return importlib.import_module('traffic_anomaly.release_input_cli')


_QUALIFICATION_NAMES=('train_full_history_normal','calibration_full_history_normal',
    'validation_current_normal','validation_current_attack','validation_current_unknown',
    'test_current_normal','test_current_attack','test_current_unknown')
_CHECK_NAMES=('status','scope','byte_integrity','structure','upstream_replay',
    'transform_history_replay','fit_parameters')
_PRIVATE_PATH='C:/unopened-private-location/人工输入包'


def _identity(value):
    return {name:getattr(value,name) for name in ('profile_id','context_sha256','manifest_sha256','manifest_byte_count')}


def test_inspect_exact_projection(monkeypatch,capfdbinary):
    m=cli()
    # This one bounded setup performs preprocessing fit; it is not model training.
    from .release_input_cases import make_upstream,make_config
    from traffic_anomaly.release_inputs import prepare_release_inputs
    upstream=make_upstream(label_overrides={170:('unknown','normal','attack')})
    saved=prepare_release_inputs(upstream,make_config(policy='P_U',epsilon=1e-6))
    calls=[]
    def loader(directory):calls.append(directory);return saved
    monkeypatch.setattr(m,'load_release_input_package',loader)
    rc=m.main(['inspect','--prepared-package',_PRIVATE_PATH])
    out,err=capfdbinary.readouterr()
    assert rc==0 and err==b'' and calls==[Path(_PRIVATE_PATH)]
    doc=json.loads(out)
    assert set(doc)=={'version','command','status','summary','replay'}
    assert (doc['version'],doc['command'],doc['status'],doc['replay'])==(1,'inspect','INTERNAL_CONSISTENCY_CHECKED',None)
    config=saved.context.configuration;minutes=saved.minutes;state=saved.preprocessing
    expected={
        'identity':_identity(saved.identity),'upstream_identity':_identity(saved.context.upstream),
        'source_authentication':saved.context.source_authentication,'time_basis':saved.context.time_basis,
        'configuration':dict(schema_version=config.schema_version,numeric_rules_id=config.numeric_rules_id,
            windows=list(config.windows),fit_window=config.fit_window,epsilon=config.epsilon,
            audit_fit_policy=config.audit_fit_policy,policy_status=config.policy_status,feature_count=len(config.feature_names)),
        'configuration_sha256':saved.context.configuration_sha256,
        'minute_counts':dict(total=176,raw_valid=176,prepared_valid=176,common_valid=56,history_h15_valid=116,history_h30_valid=56),
        'fit':dict(count=18,mask_sha256=state.fit_mask_sha256,rows_sha256=state.fit_rows_sha256),
        'qualification_counts':{q.policy:{name:sum(getattr(q,name)) for name in _QUALIFICATION_NAMES}
                                for q in saved.labels.qualification_masks},
        'package_checks':{name:getattr(saved.load_report,name) for name in _CHECK_NAMES},
    }
    assert doc['summary']==expected
    assert expected['minute_counts']==dict(total=saved.context.minute_count,raw_valid=sum(minutes.raw_valid),
        prepared_valid=sum(minutes.prepared_valid),common_valid=sum(minutes.common_valid),
        history_h15_valid=sum(minutes.histories[0].valid),history_h30_valid=sum(minutes.histories[1].valid))
    qualifications=doc['summary']['qualification_counts']
    assert [qualifications[p]['test_current_unknown'] for p in ('P_U','P_B','P_A')]==[1,0,0]
    assert qualifications['P_A']['test_current_attack']==1 and qualifications['P_B']['test_current_normal']==18
    assert qualifications['P_U']['test_current_attack']==0
    assert set(qualifications)=={'P_U','P_B','P_A'} and all(set(q)==set(_QUALIFICATION_NAMES) for q in qualifications.values())
    assert out.endswith(b'\n') and out.count(b'\n')==1 and len(out)<=65536
    assert out==(json.dumps(doc,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
    assert _PRIVATE_PATH.encode('utf-8') not in out
    assert saved.context.segments[0].id.encode('utf-8') not in out
    assert not {'mean','scale','current_values','residual','labels','timestamps'} & set(doc['summary'])


_BAD_INSPECT_ARGUMENTS=(
    (),('inspect',),('inspect','--prepared-package'),('unknown-command',),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--unknown','PRIVATE_ARG'),
    ('inspect','--prepared-pack',_PRIVATE_PATH),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--prepared-package',_PRIVATE_PATH),
    ('inspect','--prepared-package='+_PRIVATE_PATH,'--prepared-package='+_PRIVATE_PATH),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--prepared-package='+_PRIVATE_PATH),
    ('inspect','--prepared-package',_PRIVATE_PATH,'PRIVATE_POSITIONAL'),
    ('inspect','@PRIVATE_ARGS'),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--output','PRIVATE_OUTPUT'),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--raw-package','PRIVATE_RAW'),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--epsilon','1e-6'),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--audit-fit-policy','P_U'),
    ('--prepared-package',_PRIVATE_PATH,'inspect'),('inspect','--help=PRIVATE_ARG'),
)


@pytest.mark.parametrize('argv',_BAD_INSPECT_ARGUMENTS,ids=[f'parse-{i}' for i in range(len(_BAD_INSPECT_ARGUMENTS))])
def test_inspect_parser_rejects_before_load(monkeypatch,capfdbinary,argv):
    m=cli();calls=[]
    def loader(*a,**k):calls.append(True);pytest.fail('parser touched package')
    monkeypatch.setattr(m,'load_release_input_package',loader)
    assert m.main(argv)==2
    out,err=capfdbinary.readouterr()
    assert calls==[] and out==b'' and err==b'{"error":"INVALID_ARGUMENTS"}\n'


@pytest.mark.parametrize('argv',[('-h',),('--help',),('inspect','-h'),('inspect','--help'),
    ('inspect','--prepared-package',_PRIVATE_PATH,'--help')],ids=['root-short','root-long','inspect-short','inspect-long','with-private-path'])
def test_help_is_static_and_no_package_io(monkeypatch,capfdbinary,argv):
    m=cli();calls=[]
    def loader(*a,**k):calls.append(True);pytest.fail('help touched package')
    monkeypatch.setattr(m,'load_release_input_package',loader)
    assert m.main(argv)==0
    out,err=capfdbinary.readouterr()
    assert calls==[] and err==b'' and out.endswith(b'\n') and 0<len(out)<=65536
    assert b'python -m traffic_anomaly.release_input_cli' in out
    assert _PRIVATE_PATH.encode('utf-8') not in out and b'PRIVATE_' not in out


def test_inspect_preserves_equals_at_directory_in_both_option_forms(monkeypatch,capfdbinary,tmp_path):
    m=cli()
    from .release_input_cases import make_upstream,make_config
    from traffic_anomaly.release_inputs import prepare_release_inputs
    saved=prepare_release_inputs(make_upstream(label_overrides={170:('unknown','normal','attack')}),make_config())
    directory=tmp_path/'run=@daily';calls=[];results=[]
    def loader(path):calls.append(path);return saved
    monkeypatch.setattr(m,'load_release_input_package',loader)
    for argv in (['inspect','--prepared-package',str(directory)],['inspect','--prepared-package='+str(directory)]):
        rc=m.main(argv);out,err=capfdbinary.readouterr();results.append((rc,out,err))
    assert [rc for rc,_,_ in results]==[0,0]
    assert calls==[directory,directory]
    assert results[0][1]==results[1][1] and all(err==b'' for _,_,err in results)
    assert json.loads(results[0][1])['summary']['identity']==_identity(saved.identity)
    assert all(str(directory).encode('utf-8') not in out for _,out,_ in results)


@pytest.mark.parametrize('argv',[('inspect','@ARGS'),('inspect','--prepared-package','@ARGS'),
    ('inspect','--prepared-package=@ARGS')],ids=['positional','space-value','equals-value'])
def test_inspect_argument_file_requests_still_rejected_before_load(monkeypatch,capfdbinary,argv):
    m=cli();calls=[]
    def loader(*a,**k):calls.append(True);pytest.fail('argument file reached loader')
    monkeypatch.setattr(m,'load_release_input_package',loader)
    assert m.main(argv)==2
    out,err=capfdbinary.readouterr()
    assert calls==[] and out==b'' and err==b'{"error":"INVALID_ARGUMENTS"}\n'


@pytest.fixture(scope='module')
def command_cases():
    """Three bounded preprocessing fits before spies; never model training."""
    from .release_input_cases import make_upstream,make_config
    from traffic_anomaly.release_inputs import prepare_release_inputs
    upstream=make_upstream(label_overrides={170:('unknown','normal','attack')})
    return upstream,{policy:prepare_release_inputs(upstream,make_config(policy=policy)) for policy in ('P_U','P_B','P_A')}


def _forbidden(attempts,name):
    def blocked(*args,**kwargs):
        attempts.append(name)
        raise AssertionError('forbidden unit action')
    return blocked


def _observe_binary_output(m,monkeypatch,events):
    """Observe the actual _write helper on in-memory binary sinks, not OS pipes."""
    class Sink:
        def __init__(self,observed):self.payload=bytearray();self.observed=observed
        def write(self,payload):
            if self.observed:events.append('write')
            self.payload.extend(payload);return len(payload)
        def flush(self):
            if self.observed:events.append('flush')
    stdout=Sink(True);stderr=Sink(False);writer=m._write;real_stdout=m.sys.stdout
    def capture(stream,payload):
        target=stdout if stream is real_stdout else stderr
        return writer(SimpleNamespace(buffer=target),payload)
    monkeypatch.setattr(m,'_write',capture)
    return stdout,stderr


@pytest.mark.parametrize('policy',['P_U','P_B','P_A'])
def test_prepare_explicit_config_and_call_order(monkeypatch,command_cases,policy):
    m=cli();upstream,cases=command_cases;saved=cases[policy];events=[];attempts=[]
    stdout,stderr=_observe_binary_output(m,monkeypatch,events)
    raw_path=Path('C:/unopened-raw=@daily');output_path=Path('C:/uncreated-output=@daily')
    def raw_load(path):events.append('raw_load');assert path==raw_path;return upstream
    def prepare(raw,config):
        events.append('prepare');assert raw is upstream
        assert type(config.epsilon) is float
        assert config==saved.context.configuration
        assert (config.schema_version,config.numeric_rules_id,config.feature_names,config.windows,config.fit_window,
            config.epsilon,config.audit_fit_policy,config.policy_status)==(
                1,'c17-release-log1p-mad-input-rules-v1',upstream.minutes.feature_names,(15,30),30,1e-6,policy,'AUDIT_ONLY')
        return saved
    encoder=m._json_bytes
    def serialize(doc):events.append('serialize');return encoder(doc)
    def save(value,path):events.append('save');assert value is saved and path==output_path;return saved.identity
    monkeypatch.setattr(m,'load_release_minute_package',raw_load,raising=False)
    monkeypatch.setattr(m,'prepare_release_inputs',prepare,raising=False)
    monkeypatch.setattr(m,'save_release_input_package',save,raising=False)
    monkeypatch.setattr(m,'load_release_input_package',_forbidden(attempts,'prepared_load'))
    monkeypatch.setattr(m,'verify_release_input_derivation',_forbidden(attempts,'verify'),raising=False)
    monkeypatch.setattr(m,'_json_bytes',serialize)
    rc=m.main(['prepare','--raw-package',str(raw_path),'--output',str(output_path),
               '--epsilon=1e-6','--audit-fit-policy',policy])
    assert rc==0 and stderr.payload==b''
    assert events==['raw_load','prepare','serialize','save','write','flush'] and attempts==[]
    doc=json.loads(stdout.payload)
    assert (doc['version'],doc['command'],doc['status'],doc['replay'])==(1,'prepare','SAVED',None)
    assert doc['summary']['configuration']['audit_fit_policy']==policy
    assert doc['summary']['package_checks']['fit_parameters']=='NOT_REESTIMATED'
    assert doc['summary']['identity']==_identity(saved.identity)


def test_prepare_rejects_different_save_identity_without_success_output(monkeypatch,capfdbinary,command_cases):
    from dataclasses import replace
    m=cli();upstream,cases=command_cases;saved=cases['P_U'];events=[]
    def raw_load(path):events.append('raw_load');return upstream
    def prepare(raw,config):events.append('prepare');return saved
    def save(value,path):events.append('save');return replace(saved.identity,manifest_sha256='b'*64)
    monkeypatch.setattr(m,'load_release_minute_package',raw_load,raising=False)
    monkeypatch.setattr(m,'prepare_release_inputs',prepare,raising=False)
    monkeypatch.setattr(m,'save_release_input_package',save,raising=False)
    assert m.main(['prepare','--raw-package','C:/raw','--output','C:/output','--epsilon','1e-6','--audit-fit-policy','P_U'])==2
    out,err=capfdbinary.readouterr()
    assert events==['raw_load','prepare','save'] and out==b'' and err==b'{"error":"INVALID_RESULT"}\n'


_PREPARE_BASE=('prepare','--raw-package','C:/raw','--output','C:/output','--epsilon','1e-6','--audit-fit-policy','P_U')
_BAD_PREPARE=(
    _PREPARE_BASE[:-2],_PREPARE_BASE[:5]+_PREPARE_BASE[7:],
    *(_PREPARE_BASE[:6]+(value,)+_PREPARE_BASE[7:] for value in
      ('NaN','Inf','-Inf','0','-0','-1','1e-9999','not-a-number')),
    _PREPARE_BASE[:-1]+('P_X',),
    _PREPARE_BASE+('--audit-fit-policy=P_A',),_PREPARE_BASE+('--epsilon=1e-6',),
    _PREPARE_BASE+('--window','15'),_PREPARE_BASE+('--fit-window','30'),
    _PREPARE_BASE+('--prepared-package','C:/prepared'),
)


@pytest.mark.parametrize('argv',_BAD_PREPARE,ids=[f'prepare-parse-{i}' for i in range(len(_BAD_PREPARE))])
def test_prepare_policy_epsilon_required(monkeypatch,capfdbinary,argv):
    m=cli();attempts=[]
    for name in ('load_release_minute_package','load_release_input_package','prepare_release_inputs',
                 'save_release_input_package','verify_release_input_derivation'):
        monkeypatch.setattr(m,name,_forbidden(attempts,name),raising=False)
    assert m.main(argv)==2
    out,err=capfdbinary.readouterr()
    assert attempts==[] and out==b'' and err==b'{"error":"INVALID_ARGUMENTS"}\n'


def test_verify_replays_once_without_refit(monkeypatch,capfdbinary,command_cases):
    import traffic_anomaly.release_inputs as core
    m=cli();upstream,cases=command_cases;saved=cases['P_U'];events=[];attempts=[];returned=[]
    def prepared_load(path):events.append('prepared_load');assert path==Path('C:/prepared');return saved
    def raw_load(path):events.append('raw_load');assert path==Path('C:/raw');return upstream
    def verify(raw,value):
        events.append('verify');assert raw is upstream and value is saved
        report=core.verify_release_input_derivation(raw,value);returned.append(report);return report
    monkeypatch.setattr(m,'load_release_input_package',prepared_load)
    monkeypatch.setattr(m,'load_release_minute_package',raw_load,raising=False)
    monkeypatch.setattr(m,'verify_release_input_derivation',verify,raising=False)
    for name in ('prepare_release_inputs','save_release_input_package'):
        monkeypatch.setattr(m,name,_forbidden(attempts,'cli.'+name),raising=False)
    for name in ('prepare_release_inputs','_fit_state','_fit_statistics'):
        monkeypatch.setattr(core,name,_forbidden(attempts,'core.'+name))
    assert m.main(['verify','--raw-package','C:/raw','--prepared-package','C:/prepared'])==0
    out,err=capfdbinary.readouterr();doc=json.loads(out)
    assert events==['prepared_load','raw_load','verify'] and attempts==[] and err==b'' and len(returned)==1
    report=returned[0]
    expected={name:getattr(report,name) for name in ('profile_id','status','scope','minute_count','fit_count')}
    expected.update(upstream_identity=_identity(report.upstream_identity),input_identity=_identity(report.input_identity),
        checks={name:getattr(report.checks,name) for name in ('byte_identity','upstream_fields','fit_selection',
            'saved_transform','history','labels_and_masks','fit_parameters','source_authentication')},
        numerical_tolerance={name:getattr(report.numerical_tolerance,name) for name in ('rtol','atol','reference')})
    assert doc['replay']==expected and doc['command']=='verify' and doc['status']=='MATCHED'
    assert doc['summary']['package_checks']['upstream_replay']=='NOT_PERFORMED'
    assert doc['replay']['checks']['fit_parameters']=='NOT_REESTIMATED'


@pytest.mark.parametrize('command',['inspect','verify'])
def test_inspect_and_verify_action_boundaries(monkeypatch,capfdbinary,command_cases,command):
    import traffic_anomaly.release_inputs as core
    m=cli();upstream,cases=command_cases;saved=cases['P_U'];attempts=[];calls=[];numeric={'transform':0,'history':0}
    def prepared_load(path):calls.append('prepared_load');return saved
    def raw_load(path):calls.append('raw_load');return upstream
    monkeypatch.setattr(m,'load_release_input_package',prepared_load)
    for name in ('prepare_release_inputs','save_release_input_package'):
        monkeypatch.setattr(m,name,_forbidden(attempts,'cli.'+name),raising=False)
    for name in ('prepare_release_inputs','_fit_state','_fit_statistics'):
        monkeypatch.setattr(core,name,_forbidden(attempts,'core.'+name))
    if command=='inspect':
        for name in ('load_release_minute_package','verify_release_input_derivation'):
            monkeypatch.setattr(m,name,_forbidden(attempts,'cli.'+name),raising=False)
        for name in ('_bind_upstream','_transform','_history'):
            monkeypatch.setattr(core,name,_forbidden(attempts,'core.'+name))
        argv=['inspect','--prepared-package','C:/prepared']
    else:
        monkeypatch.setattr(m,'load_release_minute_package',raw_load,raising=False)
        verify=core.verify_release_input_derivation;transform=core._transform;history=core._history
        def verify_spy(raw,value):calls.append('verify');return verify(raw,value)
        def transform_spy(*a,**k):numeric['transform']+=1;return transform(*a,**k)
        def history_spy(*a,**k):numeric['history']+=1;return history(*a,**k)
        monkeypatch.setattr(m,'verify_release_input_derivation',verify_spy,raising=False)
        monkeypatch.setattr(core,'_transform',transform_spy);monkeypatch.setattr(core,'_history',history_spy)
        argv=['verify','--raw-package','C:/raw','--prepared-package','C:/prepared']
    assert m.main(argv)==0
    out,err=capfdbinary.readouterr();assert err==b'' and json.loads(out)['command']==command
    assert attempts==[]
    assert calls==(['prepared_load'] if command=='inspect' else ['prepared_load','raw_load','verify'])
    assert numeric==({'transform':0,'history':0} if command=='inspect' else {'transform':1,'history':2})


def test_action_boundaries_ledger_detects_swallowed_failure():
    attempts=[];forbidden=_forbidden(attempts,'self-check')
    try:forbidden()
    except AssertionError:pass
    assert attempts==['self-check']
    with pytest.raises(AssertionError):assert attempts==[]


_SAFE_RELEASE_CODES=('INVALID_PACKAGE_ARGUMENTS','INVALID_PACKAGE','INCOMPATIBLE_PACKAGE','RESOURCE_LIMIT',
    'INTEGRITY_MISMATCH','INCONSISTENT_PACKAGE','INVALID_PACKAGE_PATH','INPUT_UNAVAILABLE','OUTPUT_EXISTS',
    'PACKAGE_CHANGED','OUTPUT_ERROR','INVALID_PREPARATION_CONFIG','UPSTREAM_IDENTITY_MISMATCH',
    'NO_TRAINING_NORMAL_MINUTES','NONFINITE_FIT_STATE','DERIVATION_MISMATCH')
_PRIVATE_EXCEPTION='/private-sentinel/not-for-output/raw.csv'


@pytest.mark.parametrize('family',['raw','prepared'])
@pytest.mark.parametrize('code',_SAFE_RELEASE_CODES)
def test_safe_error_allowlist_and_no_disclosure(monkeypatch,capfdbinary,family,code):
    m=cli();kind=m.ReleaseMinutePackageError if family=='raw' else m.ReleaseInputPreparationError
    error=kind('INVALID_PACKAGE');error.code=code;error.args=(_PRIVATE_EXCEPTION,)
    error.__cause__=ValueError(_PRIVATE_EXCEPTION)
    def fail(path):raise error
    monkeypatch.setattr(m,'load_release_input_package',fail)
    assert m.main(['inspect','--prepared-package','C:/prepared'])==2
    out,err=capfdbinary.readouterr()
    assert out==b'' and err==('{"error":"'+code+'"}\n').encode('ascii')
    assert _PRIVATE_EXCEPTION.encode() not in err and b'Traceback' not in err and b'usage:' not in err


@pytest.mark.parametrize('family',['raw','prepared'])
@pytest.mark.parametrize('bad',['unknown','dict','list','none','bool','missing'],ids=str)
def test_safe_error_invalid_codes_are_internal_errors(monkeypatch,capfdbinary,family,bad):
    m=cli();kind=m.ReleaseMinutePackageError if family=='raw' else m.ReleaseInputPreparationError
    error=kind('INVALID_PACKAGE');error.args=(_PRIVATE_EXCEPTION,);error.__cause__=RuntimeError(_PRIVATE_EXCEPTION)
    if bad=='missing':del error.code
    else:error.code={'unknown':_PRIVATE_EXCEPTION,'dict':{'private':_PRIVATE_EXCEPTION},
                     'list':[_PRIVATE_EXCEPTION],'none':None,'bool':True}[bad]
    def fail(path):raise error
    monkeypatch.setattr(m,'load_release_input_package',fail)
    assert m.main(['inspect','--prepared-package','C:/prepared'])==2
    out,err=capfdbinary.readouterr()
    assert out==b'' and err==b'{"error":"INTERNAL_ERROR"}\n'


@pytest.mark.parametrize('kind,code',[('exception','INTERNAL_ERROR'),('interrupt','INTERRUPTED')])
def test_safe_error_unknown_exception_and_interrupt(monkeypatch,capfdbinary,kind,code):
    m=cli();error=ValueError(_PRIVATE_EXCEPTION) if kind=='exception' else KeyboardInterrupt(_PRIVATE_EXCEPTION)
    error.__cause__=RuntimeError(_PRIVATE_EXCEPTION)
    def fail(path):raise error
    monkeypatch.setattr(m,'load_release_input_package',fail)
    assert m.main(['inspect','--prepared-package','C:/prepared'])==2
    out,err=capfdbinary.readouterr()
    assert out==b'' and err==('{"error":"'+code+'"}\n').encode('ascii')


@pytest.mark.parametrize('fault',['short','flush','interrupt'])
def test_safe_error_stream_failure_is_not_retried(monkeypatch,capfdbinary,fault):
    m=cli();events=[];writer=m._write
    class Faulty:
        def write(self,payload):
            events.append('write')
            if fault=='interrupt':raise KeyboardInterrupt(_PRIVATE_EXCEPTION)
            return len(payload)-1 if fault=='short' else len(payload)
        def flush(self):events.append('flush');raise OSError(_PRIVATE_EXCEPTION)
    def fail(path):raise m.ReleaseInputPreparationError('INVALID_PACKAGE')
    def output(stream,payload):
        assert stream is m.sys.stderr
        return writer(SimpleNamespace(buffer=Faulty()),payload)
    monkeypatch.setattr(m,'load_release_input_package',fail);monkeypatch.setattr(m,'_write',output)
    assert m.main(['inspect','--prepared-package','C:/prepared'])==2
    out,err=capfdbinary.readouterr()
    assert out==err==b'' and events==(['write','flush'] if fault=='flush' else ['write'])


@pytest.mark.parametrize('size',[65535,65536,65537],ids=['below','exact','over'])
def test_json_output_byte_boundaries(size):
    m=cli();overhead=len((json.dumps({'text':''},ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode())
    value={'text':'中'+'x'*(size-overhead-len('中'.encode('utf-8')))}
    if size<=65536:
        payload=m._json_bytes(value)
        assert len(payload)==size and payload.endswith(b'\n') and b'\r' not in payload
        assert '中'.encode('utf-8') in payload and json.loads(payload)==value
    else:
        with pytest.raises(m._CLIError) as caught:m._json_bytes(value)
        assert caught.value.code=='RESOURCE_LIMIT'


@pytest.mark.parametrize('kind',['nan','non-json','unicode'])
def test_json_output_byte_boundaries_invalid_values(kind):
    m=cli();value={'bad':{'nan':float('nan'),'non-json':{1,2},'unicode':'\ud800'}[kind]}
    with pytest.raises(m._CLIError) as caught:m._json_bytes(value)
    assert caught.value.code=='INVALID_RESULT'


@pytest.mark.parametrize('kind,code',[('nan','INVALID_RESULT'),('over','RESOURCE_LIMIT')])
def test_prepare_serialization_precedes_save(monkeypatch,capfdbinary,command_cases,kind,code):
    m=cli();upstream,cases=command_cases;calls=[];attempts=[]
    def raw_load(path):calls.append('raw_load');return upstream
    def prepare(raw,config):calls.append('prepare');return cases['P_U']
    def summary(saved):calls.append('summary');return {'bad':float('nan')} if kind=='nan' else {'text':'中'+'x'*65536}
    monkeypatch.setattr(m,'load_release_minute_package',raw_load)
    monkeypatch.setattr(m,'prepare_release_inputs',prepare);monkeypatch.setattr(m,'_summary',summary)
    monkeypatch.setattr(m,'save_release_input_package',_forbidden(attempts,'save'))
    assert m.main(_PREPARE_BASE)==2
    out,err=capfdbinary.readouterr()
    assert out==b'' and err==('{"error":"'+code+'"}\n').encode('ascii')
    assert calls==['raw_load','prepare','summary'] and attempts==[]


@pytest.mark.parametrize('fault',['short','flush'])
def test_output_short_write_or_flush_failure(monkeypatch,capfdbinary,command_cases,fault):
    m=cli();saved=command_cases[1]['P_U'];events=[];writer=m._write;delivered=bytearray()
    class Faulty:
        def write(self,payload):
            events.append('write');delivered.extend(payload[:-1] if fault=='short' else payload)
            return len(payload)-1 if fault=='short' else len(payload)
        def flush(self):events.append('flush');raise OSError(_PRIVATE_EXCEPTION)
    def output(stream,payload):
        if stream is m.sys.stdout:return writer(SimpleNamespace(buffer=Faulty()),payload)
        return writer(stream,payload)
    monkeypatch.setattr(m,'load_release_input_package',lambda path:saved)
    monkeypatch.setattr(m,'_write',output)
    assert m.main(['inspect','--prepared-package','C:/prepared'])==2
    out,err=capfdbinary.readouterr()
    assert out==b'' and err==b'{"error":"OUTPUT_ERROR"}\n' and delivered
    assert events==(['write'] if fault=='short' else ['write','flush'])
    # Bytes here reached an injected memory sink; no physical-pipe claim.
    assert delivered.endswith(b'\n') is (fault=='flush')


@pytest.mark.parametrize('fault',['stdout-write','stdout-flush','late-save'])
def test_saved_package_survives_output_failure(monkeypatch,capfdbinary,tmp_path,command_cases,fault):
    from traffic_anomaly.release_input_package import load_release_input_package
    m=cli();upstream,cases=command_cases;saved=cases['P_U'];directory=tmp_path/'saved-residue'
    save=m.save_release_input_package;writer=m._write;events=[]
    def saved_then_maybe_fail(value,path):
        events.append('save');identity=save(value,path)
        if fault=='late-save':raise m.ReleaseInputPreparationError('OUTPUT_ERROR')
        return identity
    class Faulty:
        def write(self,payload):
            events.append('write')
            if fault=='stdout-write':raise OSError(_PRIVATE_EXCEPTION)
            return len(payload)
        def flush(self):events.append('flush');raise OSError(_PRIVATE_EXCEPTION)
    def output(stream,payload):
        if stream is m.sys.stdout:return writer(SimpleNamespace(buffer=Faulty()),payload)
        return writer(stream,payload)
    monkeypatch.setattr(m,'load_release_minute_package',lambda path:upstream)
    monkeypatch.setattr(m,'prepare_release_inputs',lambda raw,config:saved)
    monkeypatch.setattr(m,'save_release_input_package',saved_then_maybe_fail)
    monkeypatch.setattr(m,'_write',output)
    argv=list(_PREPARE_BASE);argv[4]=str(directory)
    assert m.main(argv)==2
    out,err=capfdbinary.readouterr()
    assert out==b'' and err==b'{"error":"OUTPUT_ERROR"}\n'
    assert set(path.name for path in directory.iterdir())=={'preprocess.json','inputs.json','labels.json','manifest.json','COMPLETE.json'}
    assert load_release_input_package(directory)==saved
    assert events==(['save'] if fault=='late-save' else ['save','write'] if fault=='stdout-write' else ['save','write','flush'])


def _package_fingerprint(directory):
    import hashlib
    result={}
    for path in directory.iterdir():
        stat=path.stat();payload=path.read_bytes()
        result[path.name]=(stat.st_ino,stat.st_mtime_ns,stat.st_size,hashlib.sha256(payload).hexdigest())
    return result


def test_real_cli_package_chain_and_negative_boundaries(tmp_path,capfdbinary,command_cases):
    import shutil
    from .release_input_cases import make_upstream
    from traffic_anomaly.release_minute_package import save_release_minute_package
    m=cli();upstream,_=command_cases;raw=tmp_path/'raw=@daily';prepared=tmp_path/'prepared=@daily'
    save_release_minute_package(upstream.minutes,upstream.segments,raw)
    raw_before=_package_fingerprint(raw)
    argv=['prepare','--raw-package',str(raw),'--output',str(prepared),'--epsilon=1e-6','--audit-fit-policy','P_U']
    assert m.main(argv)==0
    out,err=capfdbinary.readouterr();prepare_doc=json.loads(out);assert err==b''
    prepared_before=_package_fingerprint(prepared)
    assert m.main(['inspect','--prepared-package',str(prepared)])==0
    out,err=capfdbinary.readouterr();inspect_doc=json.loads(out);assert err==b''
    assert m.main(['verify','--raw-package',str(raw),'--prepared-package',str(prepared)])==0
    out,err=capfdbinary.readouterr();verify_doc=json.loads(out);assert err==b''
    assert prepare_doc['summary']==inspect_doc['summary']==verify_doc['summary']
    assert prepare_doc['replay'] is inspect_doc['replay'] is None
    assert verify_doc['replay']['input_identity']==prepare_doc['summary']['identity']
    assert verify_doc['replay']['upstream_identity']==prepare_doc['summary']['upstream_identity']
    assert verify_doc['replay']['checks']['fit_parameters']=='NOT_REESTIMATED'
    empty=tmp_path/'already-empty';empty.mkdir();stat=empty.stat()
    duplicate=list(argv);duplicate[4]=str(empty)
    assert m.main(duplicate)==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"OUTPUT_EXISTS"}\n'
    assert list(empty.iterdir())==[] and (empty.stat().st_ino,empty.stat().st_mtime_ns)==(stat.st_ino,stat.st_mtime_ns)
    missing=tmp_path/'missing-marker';shutil.copytree(prepared,missing);(missing/'COMPLETE.json').unlink()
    assert m.main(['inspect','--prepared-package',str(missing)])==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"INVALID_PACKAGE"}\n'
    assert not (missing/'COMPLETE.json').exists() and len(list(missing.iterdir()))==4
    foreign=make_upstream(label_overrides={170:('attack',)*3});foreign_raw=tmp_path/'foreign-raw'
    save_release_minute_package(foreign.minutes,foreign.segments,foreign_raw)
    foreign_before=_package_fingerprint(foreign_raw)
    assert m.main(['verify','--raw-package',str(foreign_raw),'--prepared-package',str(prepared)])==2
    out,err=capfdbinary.readouterr();assert out==b'' and err==b'{"error":"UPSTREAM_IDENTITY_MISMATCH"}\n'
    assert _package_fingerprint(raw)==raw_before and _package_fingerprint(prepared)==prepared_before
    assert _package_fingerprint(foreign_raw)==foreign_before


def _shutdown_streams(m,monkeypatch,*,broken_stdout,broken_stderr):
    """Model retained buffered bytes and shutdown re-flush; no OS descriptors."""
    events=[]
    class Stream:
        def __init__(self,fd,broken):
            self.fd=fd;self.broken=broken;self.redirected=False;self.buffer=self
            self.pending=bytearray();self.visible=bytearray();self.closed=False
        def write(self,payload):self.pending.extend(payload);return len(payload)
        def flush(self):
            if self.pending and self.broken and not self.redirected:raise OSError(22,'PRIVATE_SHUTDOWN_ERROR')
            if not self.redirected:self.visible.extend(self.pending)
            self.pending.clear()
        def fileno(self):return self.fd
        def close(self):self.closed=True;raise AssertionError('host stream must not be closed')
    stdout=Stream(1,broken_stdout);stderr=Stream(2,broken_stderr)
    class FakeOS:
        devnull='UNIT_DEVNULL';O_WRONLY=1
        def open(self,path,flags):
            assert path==self.devnull and flags==self.O_WRONLY
            events.append(('open',));return 17
        def dup2(self,source,target):
            assert source==17 and target in (1,2)
            events.append(('dup2',target));(stdout if target==1 else stderr).redirected=True
        def close(self,fd):assert fd==17;events.append(('close',))
    fake_sys=SimpleNamespace(stdout=stdout,stderr=stderr,argv=['fixed-cli','inspect','--prepared-package','C:/unopened'])
    monkeypatch.setattr(m,'sys',fake_sys);monkeypatch.setattr(m,'os',FakeOS(),raising=False)
    monkeypatch.setattr(m,'load_release_input_package',lambda path:object())
    monkeypatch.setattr(m,'_summary',lambda value:{})
    return stdout,stderr,events


def _execute_module_entry(m):
    """Execute only the actual __main__ AST block under the guarded test process."""
    import ast
    tree=ast.parse(Path(m.__file__).read_text(encoding='utf-8'))
    entry=tree.body[-1]
    assert isinstance(entry,ast.If) and isinstance(entry.test,ast.Compare)
    namespace=dict(vars(m),__name__='__main__')
    exec(compile(ast.Module(body=[entry],type_ignores=[]),m.__file__,'exec'),namespace)


@pytest.mark.parametrize('broken_stderr',[False,True],ids=['stdout-only','stdout-and-stderr'])
def test_owned_module_shutdown_cannot_reflush_failed_stdio(monkeypatch,broken_stderr):
    m=cli();stdout,stderr,events=_shutdown_streams(m,monkeypatch,broken_stdout=True,broken_stderr=broken_stderr)
    with pytest.raises(SystemExit) as caught:_execute_module_entry(m)
    assert caught.value.code==2
    # Simulate the interpreter's final flush AFTER SystemExit was already raised.
    stdout.flush();stderr.flush()
    assert stdout.pending==stderr.pending==b'' and stdout.visible==b''
    assert stderr.visible==(b'' if broken_stderr else b'{"error":"OUTPUT_ERROR"}\n')
    assert sorted(target for action,*rest in events if action=='dup2' for target in rest)==[1,2]
    assert not stdout.closed and not stderr.closed


def test_main_api_preserves_host_stdio_on_output_failure(monkeypatch):
    m=cli();stdout,stderr,events=_shutdown_streams(m,monkeypatch,broken_stdout=True,broken_stderr=False)
    assert m.main(['inspect','--prepared-package','C:/unopened'])==2
    assert events==[] and not stdout.redirected and not stderr.redirected
    assert not stdout.closed and not stderr.closed
    assert stderr.visible==b'{"error":"OUTPUT_ERROR"}\n'
    # main() deliberately leaves ownership with its host; only __main__ may seal it.
    with pytest.raises(OSError):stdout.flush()


def test_owned_module_shutdown_keeps_success_stdio_unchanged(monkeypatch):
    m=cli();stdout,stderr,events=_shutdown_streams(m,monkeypatch,broken_stdout=False,broken_stderr=False)
    with pytest.raises(SystemExit) as caught:_execute_module_entry(m)
    assert caught.value.code==0
    stdout.flush();stderr.flush()
    assert events==[] and not stdout.redirected and not stderr.redirected
    assert json.loads(stdout.visible)==dict(version=1,command='inspect',status='INTERNAL_CONSISTENCY_CHECKED',summary={},replay=None)
    assert stdout.visible.endswith(b'\n') and stderr.visible==b''
