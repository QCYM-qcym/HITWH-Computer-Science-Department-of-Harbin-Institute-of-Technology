"""Frozen A10 recipes and an independent stdlib reference, artificial only."""
import ast
import builtins
from dataclasses import fields, is_dataclass
from datetime import datetime
from functools import cache
import hashlib
import importlib
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TABLE = json.loads((ROOT / 'tests/fixtures/release-input-hand-cases-v1.json').read_text(encoding='utf-8'))
CASES = {case['name']: case for case in TABLE['cases']}
PAIRS = [(name, cfg['audit_fit_policy']) for name, case in CASES.items() for cfg in case['configurations']]
SUCCESS = [pair for pair in PAIRS if pair[0] != 'D']
POLICIES = ('P_U','P_B','P_A')
MASKS = ('train_full_history_normal','calibration_full_history_normal','validation_current_normal',
    'validation_current_attack','validation_current_unknown','test_current_normal','test_current_attack','test_current_unknown')
REF_PATH = Path(__file__).with_name('release_input_reference.py')


def reference_module():
    return importlib.import_module('.release_input_reference', __package__)


@cache
def reference(name, policy):
    return reference_module().reference_case(CASES[name], policy)


def product():
    return importlib.import_module('traffic_anomaly.release_inputs')


@cache
def upstream(name):
    # Existing raw memory parser/aggregator only, not the formal installed A10 run.
    helper = importlib.import_module('.release_minute_package_cases', __package__)
    raw = importlib.import_module('traffic_anomaly.release_minute_contract')
    types = importlib.import_module('traffic_anomaly._release_minutes')
    case = CASES[name]
    segments = tuple(types.ReleaseSegment(item['id'],item['role'],datetime.fromisoformat(item['start']),
                                        datetime.fromisoformat(item['end'])) for item in case['segments'])
    result = helper.make_result(tuple(tuple(dict(row) for row in source) for source in case['sources']), segments)
    return raw.decode_release_minute_package(dict(raw.encode_release_minute_package(result, segments)))


def configuration(name, policy):
    cfg = dict(next(item for item in CASES[name]['configurations'] if item['audit_fit_policy'] == policy))
    cfg['feature_names'] = tuple(cfg['feature_names']); cfg['windows'] = tuple(cfg['windows'])
    return product().ReleasePreparationConfig(**cfg)


@cache
def prepared(name, policy):
    return product().prepare_release_inputs(upstream(name), configuration(name, policy))


def project(value):
    if isinstance(value, datetime): return value.isoformat()
    if is_dataclass(value): return {field.name: project(getattr(value,field.name)) for field in fields(value)}
    if isinstance(value, tuple): return tuple(project(child) for child in value)
    if isinstance(value, dict): return {key: project(child) for key,child in value.items()}
    return value


def equivalent(saved, expected, path='result'):
    if type(expected) is float:
        assert type(saved) is float and math.isfinite(saved) and math.isfinite(expected), path
        difference = abs(saved-expected)
        assert math.isfinite(difference) and difference <= 1e-12 + 1e-12*abs(expected), path
    elif type(expected) is dict:
        assert type(saved) is dict and saved.keys() == expected.keys(), path
        for key in expected: equivalent(saved[key],expected[key],path+'.'+key)
    elif type(expected) is tuple:
        assert type(saved) is tuple and len(saved)==len(expected), path
        for i,(a,b) in enumerate(zip(saved,expected)): equivalent(a,b,f'{path}[{i}]')
    else:
        assert type(saved) is type(expected) and saved==expected, path


def true_indices(values): return [i for i,value in enumerate(values) if value]


def test_fixture_has_one_explicit_schema_and_six_source_contents():
    assert set(TABLE)=={'fixture_version','evidence_kind','cases'}
    assert TABLE['fixture_version']==1 and TABLE['evidence_kind']=='SYNTHETIC_ONLY'
    assert list(CASES)==['A','A-L','A-V','B','C','D']
    assert [sum(map(len,case['sources'])) for case in CASES.values()]==[176,176,176,197,80,33]
    expected_keys={'error','minute_count','source_record_count','eligible_record_count','excluded_record_count',
        'unplaced_record_count','raw_valid_count','fit_indices','fit_forward_packet_frequencies','history_valid_indices',
        'history_ready_failure_indices','common_indices','qualification_true_indices','raw_value_checks'}
    row_keys={'id','Timestamp','Protocol','Flow Duration','Total Fwd Packet','Total Bwd packets',
              'Total Length of Fwd Packet','Total Length of Bwd Packet','Label','Attempted Category'}
    for case in CASES.values():
        assert set(case)=={'name','sources','segments','configurations','expected'}
        assert len(case['sources'])==1
        for row in case['sources'][0]:
            assert set(row)==row_keys and all(type(value) is str for value in row.values())
            assert row['id'].isascii() and row['id'].isdecimal() and row['id']==str(int(row['id']))
        assert len({row['id'] for row in case['sources'][0]})==len(case['sources'][0])
        assert set(case['expected'])=={cfg['audit_fit_policy'] for cfg in case['configurations']}
        for answer in case['expected'].values():
            assert set(answer)==expected_keys
            if answer['qualification_true_indices'] is not None:
                assert tuple(answer['qualification_true_indices'])==POLICIES
                assert all(tuple(item)==MASKS for item in answer['qualification_true_indices'].values())
    assert '159' not in {row['id'] for row in CASES['B']['sources'][0]}
    assert CASES['D']['sources'][0][-1]['id']=='32'
    assert CASES['C']['sources'][0][33]['Total Fwd Packet']=='2'
    assert CASES['C']['sources'][0][33]['Flow Duration']=='1000000'
    assert CASES['C']['sources'][0][33]['Total Length of Fwd Packet']=='10'


@pytest.mark.parametrize('name,policy',PAIRS,ids=[f'{a}-{b}' for a,b in PAIRS])
def test_a10_independent_reference_and_masks(name,policy):
    ref=reference(name,policy); answer=CASES[name]['expected'][policy]; raw=ref['raw']
    assert set(ref)=={'schema_version','audit_fit_policy','error','configuration','raw','preprocessing','minutes','labels'}
    assert ref['error']==answer['error'] and ref['audit_fit_policy']==policy
    assert len(raw['timestamps'])==answer['minute_count']
    for key,source_key in [('raw_records','source_record_count'),('eligible_records','eligible_record_count'),
                           ('excluded_records','excluded_record_count'),('unplaced_invalid_rows','unplaced_record_count')]:
        assert raw['counts'][key]==answer[source_key]
    assert raw['counts']['outside_records']==raw['counts']['duplicate_groups']==0
    assert sum(raw['source_valid'])==answer['raw_valid_count']
    assert list(ref['labels']['fit_indices'])==answer['fit_indices']
    assert [sum(raw['values'][i][1]==float(p) for i in ref['labels']['fit_indices']) for p in (1,2,3)]==answer['fit_forward_packet_frequencies']
    for index,row in answer['raw_value_checks'].items(): assert raw['values'][int(index)]==tuple(row)
    assert not any(raw['unused_field_issue_records'])
    if ref['error']:
        assert ref['preprocessing'] is ref['minutes'] is ref['labels']['qualification_masks'] is None
        assert raw['bucket_eligible_records']==(1,)*32
        return
    for hist in ref['minutes']['histories']:
        key=str(hist['window'])
        assert true_indices(hist['valid'])==answer['history_valid_indices'][key]
        # Ready failures exclude pending warmup rows with the same reason string.
        assert list(reference_module().ready_failure_indices(ref['minutes'],hist['window']))==answer['history_ready_failure_indices'][key]
    assert true_indices(ref['minutes']['common_valid'])==answer['common_indices']
    for group in ref['labels']['qualification_masks']:
        assert tuple(group)==('policy',*MASKS)
        for mask in MASKS:
            assert true_indices(group[mask])==answer['qualification_true_indices'][group['policy']][mask]


def test_reference_c_closed_form_and_failed_target_exclusion():
    ref=reference('C','P_U'); state=ref['preprocessing']; d=math.log(3.0)-math.log(2.0)
    equivalent(state['mean'][1],math.log(2.0)+d/50)
    equivalent(state['scale'][1],7*d/50)
    equivalent(ref['minutes']['current_values'][0][1],-1/7)
    equivalent(ref['minutes']['current_values'][33][1],7.0)
    for hist,recover in zip(ref['minutes']['histories'],(49,64)):
        assert hist['invalid_reason'][33]=='nonfinite_history' and not hist['valid'][recover-1]
        assert hist['valid'][recover] and hist['residual'][recover]==(0.0,)*13
    assert state['n_samples_seen']==50 and sum(ref['minutes']['common_valid'])==19


def test_reference_is_stdlib_no_io_and_no_import_time_computation(monkeypatch):
    assert REF_PATH.is_file()
    tree=ast.parse(REF_PATH.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): assert all(alias.name.split('.')[0] in {'math','json','hashlib'} for alias in node.names)
        if isinstance(node,ast.ImportFrom): assert node.module in {'__future__','datetime'}
    for node in tree.body:
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            assert not any(isinstance(child,ast.Call) for child in ast.walk(node.value))
        elif isinstance(node,ast.Expr): assert isinstance(node.value,ast.Constant) and type(node.value.value) is str
        else: assert isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef))
    module=reference_module()
    def forbidden(*args,**kwargs): pytest.fail('independent reference attempted file I/O')
    with monkeypatch.context() as patch:
        patch.setattr(builtins,'open',forbidden);patch.setattr(Path,'open',forbidden)
        given=dict(CASES['A']);given['expected']=None
        actual=module.reference_case(given,'P_U')
    equivalent(actual,reference('A','P_U'))


@pytest.mark.parametrize('name',list(CASES),ids=list(CASES))
def test_actual_raw_memory_stage_matches_independent_source_recipe(name):
    raw=upstream(name).minutes;ref=reference(name,CASES[name]['configurations'][0]['audit_fit_policy'])['raw']
    for key in ('feature_names','timestamps','segment_ids','roles','values','source_valid','label_kinds'):
        equivalent(project(getattr(raw,key)),ref[key],key)
    for key,value in ref['counts'].items(): assert getattr(raw,key)==value
    assert tuple(bucket.eligible_records for bucket in raw.bucket_counts)==ref['bucket_eligible_records']
    assert tuple(bucket.unused_field_issue_records for bucket in raw.bucket_counts)==ref['unused_field_issue_records']
    definite={'A':[158],'A-L':[133,158],'A-V':[158],'B':[],'C':[],'D':[]}
    attempted={'A':[159],'A-L':[159],'A-V':[159],'B':[10],'C':[],'D':[]}
    assert [i for i,bucket in enumerate(raw.bucket_counts) if bucket.definite_attack_present]==definite[name]
    assert [i for i,bucket in enumerate(raw.bucket_counts) if bucket.attempted_present]==attempted[name]


@pytest.mark.parametrize('name,policy',SUCCESS,ids=[f'{a}-{b}' for a,b in SUCCESS])
def test_reference_matches_real_prepare_save_load_verify(name,policy,tmp_path):
    ref=reference(name,policy);snapshot=prepared(name,policy);api=product()
    equivalent(project(snapshot.preprocessing),ref['preprocessing'],'preprocessing')
    equivalent(project(snapshot.minutes),ref['minutes'],'minutes')
    equivalent(project(snapshot.labels),ref['labels'],'labels')
    equivalent(project(snapshot.context.configuration),ref['configuration'],'configuration')
    for h in snapshot.minutes.histories:
        expected=tuple(current+residual if valid else (None,)*26 for current,residual,valid in
                       zip(ref['minutes']['current_values'],ref['minutes']['histories'][0 if h.window==15 else 1]['residual'],h.valid))
        equivalent(snapshot.joined(h.window),expected,'joined')
    storage=importlib.import_module('traffic_anomaly.release_input_package')
    directory=tmp_path/(name+'-'+policy)
    identity=storage.save_release_input_package(snapshot,directory)
    reopened=storage.load_release_input_package(directory)
    assert reopened.identity==identity==snapshot.identity
    equivalent(project(reopened.preprocessing),ref['preprocessing'])
    equivalent(project(reopened.minutes),ref['minutes'])
    equivalent(project(reopened.labels),ref['labels'])
    assert reopened.load_report.scope=='SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY'
    assert reopened.load_report.fit_parameters=='NOT_REESTIMATED'
    replay=api.verify_release_input_derivation(upstream(name),reopened)
    assert replay.status=='MATCHED' and replay.scope=='SAVED_PARAMETER_DERIVATION_REPLAY'
    assert replay.checks.fit_parameters=='NOT_REESTIMATED'
    assert replay.checks.source_authentication=='NOT_AUTHENTICATED'
    encoded=dict(api.encode_release_input_package(snapshot))
    assert {path.name:path.read_bytes() for path in directory.iterdir()}==encoded
    assert hashlib.sha256(encoded['manifest.json']).hexdigest()==identity.manifest_sha256


def test_d_rejects_empty_raw_fit_without_prepared_output():
    assert reference('D','P_U')['error']=='NO_TRAINING_NORMAL_MINUTES'
    api=product()
    with pytest.raises(api.ReleaseInputPreparationError) as caught:
        api.prepare_release_inputs(upstream('D'),configuration('D','P_U'))
    assert caught.value.code==str(caught.value)=='NO_TRAINING_NORMAL_MINUTES'


def test_a_l_and_a_v_have_scoped_invariance():
    base=prepared('A','P_U'); labels=prepared('A-L','P_U'); values=prepared('A-V','P_U')
    for changed in (labels,values):
        assert changed.preprocessing==base.preprocessing
        assert changed.labels.fit_mask==base.labels.fit_mask
        assert changed.context.upstream!=base.context.upstream
        assert changed.identity!=base.identity
    assert labels.minutes==base.minutes
    assert labels.labels.label_kinds!=base.labels.label_kinds
    assert labels.labels.qualification_masks==base.labels.qualification_masks
    assert values.minutes.current_values[:83]==base.minutes.current_values[:83]
    assert values.minutes.current_values[128:168]==base.minutes.current_values[128:168]
    for changed,original in zip(values.minutes.histories,base.minutes.histories):
        assert changed.residual[:83]==original.residual[:83]
        assert changed.residual[128:168]==original.residual[128:168]
    assert values.minutes.current_values[83]!=base.minutes.current_values[83]


def test_prepared_profile_stays_outside_old_candidate_fixture_gate(tmp_path):
    api=product();snapshot=prepared('A','P_U')
    old=importlib.import_module('traffic_anomaly.candidate_cli')
    for name,raw in api.encode_release_input_package(snapshot):
        doc=json.loads(raw)
        assert doc['profile_id']=='c17-release-prepared-input-package-v1' and 'evidence_kind' not in doc
        path=tmp_path/name;path.write_bytes(raw)
        with pytest.raises(old._SafeError,match='^INVALID_FIXTURE$'): old._read_fixture(path)
