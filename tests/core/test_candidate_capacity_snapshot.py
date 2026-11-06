"""Immutable delivery and exact bounded encoding; snapshots are not credentials."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import importlib
import json

import pytest

from .test_candidate_capacity_contract import report
from .test_candidate_capacity_comparison import packages, SOURCE, SLOTS
from .test_candidate_ae_capacity_artifacts import upstream
from traffic_anomaly.candidate_capacity_contract import CandidateCapacityComparisonError


def api():
    return importlib.import_module('traffic_anomaly.candidate_capacity_snapshot')


def test_encoding_is_deterministic_full_json_utf8_and_one_lf(report, capsys):
    original=deepcopy(report)
    encoded=api().encode_capacity_report(report)
    reordered={key:report[key] for key in reversed(report)}
    assert encoded==api().encode_capacity_report(reordered)
    assert encoded.endswith(b'\n') and not encoded.endswith(b'\n\n') and b'\r' not in encoded
    assert b': ' not in encoded and b', ' not in encoded
    assert json.loads(encoded)==original and report==original
    assert capsys.readouterr().out==''
    # Mutating a source alias cannot change the already encoded bytes.
    report['runs'][0]['policies']['P_U']['metrics']['fpr']=1.
    report['runs'][0]['run_id']='changed-alias'
    assert json.loads(encoded)==original


@pytest.mark.parametrize('path,value',[
    (('extra',),True), (('schema_version',),True), (('runs',0,'parameter_count'),True),
    (('runs',0,'model_profile_id'),'unknown'), (('runs',0,'configuration','epochs'),5.),
    (('shared_context','preprocessing_state','fit_window'),15),
    (('runs',0,'threshold'),float('nan')), (('runs',0,'threshold'),float('inf')),
    (('runs',0,'run_id'),'不可信'), (('runs',0,'slot'),'history_ae26_h30'),
])
def test_encoder_rejects_invalid_contract_before_return_or_output(report,capsys,path,value):
    target=report
    for key in path[:-1]:target=target[key]
    target[path[-1]]=value
    with pytest.raises(CandidateCapacityComparisonError):api().encode_capacity_report(report)
    captured=capsys.readouterr()
    assert captured.out==captured.err==''


@pytest.mark.parametrize('value',[None,[],{},'report',True])
def test_encoder_rejects_invalid_report_container(value):
    with pytest.raises(CandidateCapacityComparisonError):api().encode_capacity_report(value)


def test_encoder_exact_byte_limit_counts_lf_and_not_codepoints(monkeypatch,capsys):
    module=api()
    # Isolate the real serializer's byte budget; these padding objects are NOT
    # valid capacity reports and are never admitted in production.
    monkeypatch.setattr(module,'validate_capacity_report',lambda report:None)
    overhead=len(b'{"padding":""}\n')
    result=module.encode_capacity_report({'padding':'x'*(1048576-overhead)})
    assert len(result)==1048576 and result.endswith(b'\n')
    with pytest.raises(CandidateCapacityComparisonError,match='RESOURCE_LIMIT'):
        module.encode_capacity_report({'padding':'x'*(1048577-overhead)})
    assert module.encode_capacity_report({'padding':'界'})==b'{"padding":"\xe7\x95\x8c"}\n'
    assert len('界'*400000)<1048576
    with pytest.raises(CandidateCapacityComparisonError,match='RESOURCE_LIMIT'):
        module.encode_capacity_report({'padding':'界'*400000})
    assert capsys.readouterr().out==''


def test_serializer_error_is_fixed_and_never_prints_private_text(monkeypatch):
    module=api();monkeypatch.setattr(module,'validate_capacity_report',lambda report:None)
    with pytest.raises(CandidateCapacityComparisonError,match='INVALID_CAPACITY_REPORT'):
        module.encode_capacity_report({'private':'\ud800'})


def test_load_once_detaches_report_aliases_without_authentication_upgrade(report,monkeypatch):
    module=api();calls=[];original=deepcopy(report)
    def admitted(*args,**kwargs):
        calls.append((args,kwargs));return report
    monkeypatch.setattr(module,'compare_candidate_ae_capacity_runs',admitted)
    snapshot=module.load_verified_candidate_capacity_comparison(['a','b'],'records','inputs',source_fixture='source')
    assert calls==[((['a','b'],'records','inputs'),{'source_fixture':'source'})]
    assert snapshot.payload==module.encode_capacity_report(original)
    assert snapshot.run_ids==tuple(row['run_id'] for row in original['runs'])
    report['runs'][0]['run_id']='changed';report.clear()
    assert json.loads(snapshot.payload)==original
    with pytest.raises((FrozenInstanceError,AttributeError)):snapshot.payload=b'changed'
    with pytest.raises((FrozenInstanceError,AttributeError)):snapshot.run_ids=('changed',)


def test_real_fabricated_admission_is_once_per_package_and_keeps_identities(packages,monkeypatch):
    module=api()
    from traffic_anomaly import candidate_capacity_comparison as comparison
    actual=comparison.load_verified_candidate_ae_run;calls=[]
    def counted(*args,**kwargs):
        calls.append(args[0]);return actual(*args,**kwargs)
    monkeypatch.setattr(comparison,'load_verified_candidate_ae_run',counted)
    runs=list(packages[0].values())
    snapshot=module.load_verified_candidate_capacity_comparison(runs,*packages[1:],source_fixture=SOURCE)
    assert calls==[path.resolve() for path in runs]
    saved=json.loads(snapshot.payload)
    assert saved['included_slots']==list(SLOTS)
    assert snapshot.run_ids==tuple(row['run_id'] for row in saved['runs'])
    assert saved['shared_context']['five_provenance']['source_fixture']['byte_count'] in (213497,205567)
    assert saved['limitations']['model_origin']=='NOT_AUTHENTICATED'


def test_source_required_and_duplicate_aliases_keep_existing_safe_rejection(packages):
    module=api();runs=list(packages[0].values())
    with pytest.raises(TypeError):module.load_verified_candidate_capacity_comparison(runs,*packages[1:])
    with pytest.raises(CandidateCapacityComparisonError,match='SOURCE_REQUIRED'):
        module.load_verified_candidate_capacity_comparison(runs,*packages[1:],source_fixture=None)
    path=runs[0]
    with pytest.raises(CandidateCapacityComparisonError,match='DUPLICATE_RUN_DIRECTORY'):
        module.load_verified_candidate_capacity_comparison([path,path/'..'/path.name],*packages[1:],source_fixture=SOURCE)


@pytest.mark.parametrize('payload,ids',[
    (bytearray(b'{}\n'),('a','b')), ('{}\n',('a','b')), (b'{}\n',['a','b']),
    (b'{}\n',('a',True)), (b'{}\n',('a','a')), (b'{}\n',('a',)),
    (b'',('a','b')), (b'x'*1048577,('a','b')),
],ids=['mutable-payload','text-payload','mutable-ids','typed-id','duplicate-id','one-id','empty-payload','oversize'])
def test_snapshot_cannot_retain_mutable_or_unbounded_fields(payload,ids):
    with pytest.raises(CandidateCapacityComparisonError):api().CandidateCapacitySnapshot(payload,ids)


def test_direct_snapshot_construction_is_only_a_bounded_value():
    snapshot=api().CandidateCapacitySnapshot(b'not-an-authenticated-report\n',('a','b'))
    assert snapshot.payload==b'not-an-authenticated-report\n' and snapshot.run_ids==('a','b')
