"""The shared artificial full91 builder; never a source-authentication helper."""
import csv
import hashlib
import io
import json

from traffic_anomaly._release_csv import EXPECTED_HEADER, ReleaseFixtureBudget, _parse_release_csv
from traffic_anomaly._release_minutes import _aggregate_release_minutes


def make_result(rows_by_source, segments):
    if type(rows_by_source) is not tuple or any(type(rows) is not tuple for rows in rows_by_source):
        raise ValueError('artificial_sources_must_be_tuples')
    sources=[]
    for rows in rows_by_source:
        stream=io.StringIO(newline=''); writer=csv.writer(stream,lineterminator='\n')
        writer.writerow(EXPECTED_HEADER)
        for changes in rows:
            if (type(changes) is not dict or not {'id','Timestamp'} <= changes.keys()
                    or not changes.keys() <= set(EXPECTED_HEADER)
                    or any(type(k) is not str or type(v) is not str for k,v in changes.items())):
                raise ValueError('explicit_artificial_id_timestamp_and_string_fields_required')
            row={key:'0' for key in EXPECTED_HEADER}
            row.update({'Flow ID':'artificial','Src IP':'192.0.2.1','Dst IP':'192.0.2.2',
                'Protocol':'6','Timestamp':'2026-01-01 00:00:00.000000','Flow Duration':'0',
                'Total Fwd Packet':'2','Total Bwd packets':'1','Total Length of Fwd Packet':'20',
                'Total Length of Bwd Packet':'10','Label':'BENIGN','Attempted Category':'-1'})
            row.update(changes);writer.writerow([row[key] for key in EXPECTED_HEADER])
        sources.append(stream.getvalue().encode('utf-8'))
    parsed=_parse_release_csv(tuple(sources),budget=ReleaseFixtureBudget())
    return _aggregate_release_minutes(parsed,segments,max_minutes=10000)


def plain_members(result, segments):
    from traffic_anomaly.release_minute_contract import encode_release_minute_package
    return dict(encode_release_minute_package(result,segments))


def canonical(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')+b'\n'


def documents(members):
    return {name:json.loads(payload) for name,payload in members.items()}


def identity(payload):
    return {'byte_count':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}


def reseal(docs):
    """Rebind a deliberate artificial mutation to test semantic checks, not only hashes."""
    context_sha=hashlib.sha256(canonical(docs['manifest.json']['context'])).hexdigest()
    docs['manifest.json']['context_sha256']=context_sha
    members={}
    for name in ('minutes.json','labels.json','diagnostics.json'):
        docs[name]['context_sha256']=context_sha;members[name]=canonical(docs[name])
    docs['manifest.json']['members']={name:identity(payload) for name,payload in members.items()}
    members['manifest.json']=canonical(docs['manifest.json'])
    docs['COMPLETE.json']['manifest']=identity(members['manifest.json'])
    members['COMPLETE.json']=canonical(docs['COMPLETE.json'])
    return members


def replace_member(members,name,payload):
    """Bind arbitrary test bytes without parsing/correcting the mutated member."""
    result=dict(members);result[name]=payload
    if name in ('minutes.json','labels.json','diagnostics.json'):
        manifest=json.loads(result['manifest.json']);manifest['members'][name]=identity(payload)
        result['manifest.json']=canonical(manifest)
    if name!='COMPLETE.json':
        complete=json.loads(result['COMPLETE.json']);complete['manifest']=identity(result['manifest.json'])
        result['COMPLETE.json']=canonical(complete)
    return result
