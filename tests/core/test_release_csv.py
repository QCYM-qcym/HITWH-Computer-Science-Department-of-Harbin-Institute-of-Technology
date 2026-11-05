"""Only invented 91-column payloads; no real files, models or source receipts."""
import builtins
import csv
from dataclasses import FrozenInstanceError
from datetime import datetime
import hashlib
import importlib
import io
import json
from pathlib import Path
import socket

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'tests/fixtures/release-91-artificial-v1.json').read_text(encoding='utf-8'))
HEADER = FIXTURE['header']
CONFIG = json.loads((ROOT / 'docs/research/2026-10-24-c17-g13u-config.json').read_text(encoding='utf-8'))


def mod():
    return importlib.import_module('traffic_anomaly._release_csv')


def row(**changes):
    values = dict(zip(HEADER, FIXTURE['rows'][0]))
    values.update(changes)
    return [values[name] for name in HEADER]


def encoded(rows=(), *, header=HEADER, quoting=csv.QUOTE_MINIMAL, bom=False):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, quoting=quoting)
    writer.writerow(header)
    writer.writerows(rows)
    return (('\ufeff' if bom else '') + buffer.getvalue()).encode('utf-8')


def parse(rows=None, **budget):
    m = mod()
    return m._parse_release_csv((encoded([row()] if rows is None else rows),), budget=m.ReleaseFixtureBudget(**budget))


def failure(sources, code, **budget):
    m = mod()
    with pytest.raises(ValueError) as error:
        m._parse_release_csv(sources, budget=m.ReleaseFixtureBudget(**budget))
    assert str(error.value) == code
    assert 'artificial-src' not in repr(error.value)
    return error.value


def test_full_schema_bom_escaping_and_exact_parsed_values():
    m = mod()
    assert len(HEADER) == 91 and tuple(CONFIG['expected_header']) == m.EXPECTED_HEADER
    source = encoded([row()], bom=True)
    batch = m._parse_release_csv((source,), budget=m.ReleaseFixtureBudget())
    r = batch.rows[0]
    assert r.raw_fields == tuple(row())
    assert r.start == datetime(2026, 1, 1, 0, 0, 0, 100000)
    assert r.duration_us == 1000000 and r.completion == datetime(2026, 1, 1, 0, 0, 1, 100000)
    assert (r.fwd_packets, r.bwd_packets, r.fwd_length, r.bwd_length) == (2, 1, 40, 10)
    assert r.protocol_channel == 'tcp' and r.reasons == ()
    assert r.unused_field_issues == ()
    assert r.label_kinds == ('normal',) * 3
    assert batch.schema_id == 'c17-release-91-v1'
    assert batch.source_authentication == 'NOT_AUTHENTICATED'
    assert batch.time_basis == 'SOURCE_WALL_CLOCK_COMPLETION_PROXY'
    assert batch.source_bytes == (len(source),)
    assert batch.source_sha256 == (hashlib.sha256(source).hexdigest(),)


def test_header_only_valid_but_empty_batch_and_missing_header_rejected():
    assert parse([]).rows == ()
    failure((), 'empty_batch')
    for source in (b'', b'\xef\xbb\xbf'):
        failure((source,), 'missing_header')


@pytest.mark.parametrize('kind', ['missing', 'reordered', 'duplicate', 'case', 'space', 'extra'])
def test_exact_header_rejects_schema_drift(kind):
    header = HEADER.copy()
    if kind == 'missing': header.pop()
    elif kind == 'reordered': header[0], header[1] = header[1], header[0]
    elif kind == 'duplicate': header[0] = header[1]
    elif kind == 'case': header[0] = header[0].upper()
    elif kind == 'space': header[0] += ' '
    else: header.append('extra')
    failure((encoded([row()], header=header),), 'header_mismatch')


@pytest.mark.parametrize('source,code', [
    (b'\xff', 'invalid_utf8'),
    (encoded() + b'"unterminated', 'invalid_csv'),
    (encoded([row()[:-1]]), 'ragged_row'),
    (encoded([row(**{'Flow ID': 'private\x00payload'})]), 'field_nul'),
    (encoded() + b'\r\n', 'ragged_row'),
])
def test_csv_failures_have_fixed_private_error_shape(source, code):
    error = failure((source,), code)
    assert error.args == (code,)


def test_independent_length_framed_fingerprint_and_lexical_identity():
    values = row()
    # An independent one-shot framing oracle; production must stream every field.
    frame = b''.join(len(s.encode('utf-8')).to_bytes(4, 'little') + s.encode('utf-8') for s in values)
    expected = hashlib.sha256(frame).digest()
    m = mod()
    sources = (encoded([values]), encoded([values], quoting=csv.QUOTE_ALL, bom=True))
    b = m._parse_release_csv(sources, budget=m.ReleaseFixtureBudget())
    assert [r.lexical_fingerprint for r in b.rows] == [expected, expected]
    assert b.source_sha256[0] != b.source_sha256[1]
    assert [(r.source_ordinal, r.record_ordinal) for r in b.rows] == [(0, 1), (1, 1)]
    changed = parse([values, row(**{'Total Fwd Packet': '2.0'}), row(**{'Idle Mean': '1'})]).rows
    assert len({r.lexical_fingerprint for r in changed}) == 3
    assert [r.fwd_packets for r in changed] == [2, 2, 2]


def test_logical_record_ordinals_ignore_embedded_newlines():
    assert [r.record_ordinal for r in parse([row(), row()]).rows] == [1, 2]


@pytest.mark.parametrize('raw,channel,reason', [
    ('0', 'unresolved', None), ('0.0', 'unresolved', None), ('6', 'tcp', None),
    ('17', 'udp', None), ('1', 'known_other', None), ('2', 'known_other', None),
    ('132', 'known_other', None), ('200', 'excluded_protocol', 'invalid_unsupported_protocol'),
    ('255', 'excluded_protocol', 'invalid_unsupported_protocol'),
    ('256', 'excluded_protocol', 'invalid_protocol'), ('-1', 'excluded_protocol', 'invalid_protocol'),
    ('NaN', 'excluded_protocol', 'invalid_protocol'), ('0.5', 'excluded_protocol', 'invalid_protocol'),
])
def test_protocol_classification_preserves_original_portscan(raw, channel, reason):
    r = parse([row(Protocol=raw, Label='Portscan')]).rows[0]
    assert r.protocol_channel == channel
    assert r.reasons == (() if reason is None else (reason,))
    assert r.raw_label == 'Portscan' and r.raw_category == '-1'
    assert r.label_kinds == ('attack',) * 3


@pytest.mark.parametrize('label,category,kinds,anomaly,attempted,definite', [
    ('BENIGN', '-1', ('normal',)*3, None, False, False),
    ('Portscan', '-1', ('attack',)*3, None, False, True),
    ('FTP-Patator - Attempted', '0', ('unknown','normal','attack'), None, True, False),
    ('BENIGN', '0', ('unknown',)*3, 'label_category_conflict', True, False),
    ('Portscan', '0', ('unknown',)*3, 'label_category_conflict', True, True),
    ('FTP-Patator - Attempted', '-1', ('unknown',)*3, 'label_category_conflict', True, False),
    ('unknown', '-1', ('unknown',)*3, 'unknown_label', False, False),
    ('BENIGN', 'unknown', ('unknown',)*3, 'unknown_attempted_category', True, False),
    (' BENIGN', '-1', ('unknown',)*3, 'unknown_label', False, False),
    ('BENIGN', '-1 ', ('unknown',)*3, 'unknown_attempted_category', True, False),
])
def test_joint_label_semantics_do_not_affect_numeric_qualification(label, category, kinds, anomaly, attempted, definite):
    r = parse([row(Label=label, **{'Attempted Category': category})]).rows[0]
    assert r.label_kinds == kinds and r.label_anomaly == anomaly
    assert r.attempted is attempted and r.definite_attack is definite
    assert r.reasons == () and r.raw_label == label and r.raw_category == category


@pytest.mark.parametrize('suffix,expected', [('.1',100000),('.12',120000),('.123456',123456)])
def test_timestamp_fraction_matches_existing_one_to_six_digit_semantics(suffix, expected):
    assert parse([row(Timestamp='2026-01-01 00:00:00'+suffix)]).rows[0].start.microsecond == expected


@pytest.mark.parametrize('stamp', ['2026-01-01 00:00:00', '2026-01-01 00:00:00.1234567',
    '2026-02-30 00:00:00.0', '2026-01-01 24:00:00.0', '2026-01-01 00:00:00.0Z'])
def test_invalid_timestamp_retained_unplaced(stamp):
    r = parse([row(Timestamp=stamp)]).rows[0]
    assert r.start is None and r.completion is None and r.reasons == ('invalid_timestamp',)


@pytest.mark.parametrize('raw', ['-1', '0.5', 'NaN', 'Infinity', 'invalid', ''])
def test_invalid_duration_retained_unplaced(raw):
    r = parse([row(**{'Flow Duration': raw})]).rows[0]
    assert r.duration_us is None and r.completion is None and r.reasons == ('invalid_duration',)


@pytest.mark.parametrize('raw', ['2.0', '2e0', '+2', ' 2 ', '20e-1'])
def test_mathematical_integer_lexemes_are_not_normalized(raw):
    r = parse([row(**{'Total Fwd Packet': raw})]).rows[0]
    assert r.fwd_packets == 2 and r.reasons == ()
    assert r.raw_fields[HEADER.index('Total Fwd Packet')] == raw


@pytest.mark.parametrize('field,attribute,reason', [
    ('Total Fwd Packet','fwd_packets','invalid_fwd_packets'),
    ('Total Bwd packets','bwd_packets','invalid_bwd_packets'),
    ('Total Length of Fwd Packet','fwd_length','invalid_fwd_length'),
    ('Total Length of Bwd Packet','bwd_length','invalid_bwd_length'),
])
def test_bad_required_count_does_not_drop_row(field, attribute, reason):
    r = parse([row(**{field:'1.5'})]).rows[0]
    assert getattr(r, attribute) is None and r.reasons == (reason,)
    assert r.completion is not None


def test_duration_cap_boundary_and_completion_overflow_are_whole_failures():
    rows = parse([row(**{'Flow Duration':'86399999999'}), row(**{'Flow Duration':'86400000000'})]).rows
    assert [r.duration_us for r in rows] == [86399999999,86400000000]
    failure((encoded([row(**{'Flow Duration':'86400000001'})]),), 'duration_cap')
    failure((encoded([row(Timestamp='9999-12-31 23:59:59.999999', **{'Flow Duration':'1'})]),), 'completion_overflow')


@pytest.mark.parametrize('unused', ['NaN', 'Infinity', '', 'not-numeric'])
def test_unused_rate_issues_preserved_without_dropna(unused):
    r = parse([row(**{'Flow Bytes/s':unused,'Total Fwd Packet':'1000000001'})]).rows[0]
    assert r.fwd_packets == 1000000001 and r.reasons == ()
    assert r.unused_field_issues and r.raw_fields[HEADER.index('Flow Bytes/s')] == unused


@pytest.mark.parametrize('raw', ['1e4096', '1e999999999', '1e99999999999999999999999',
    '99e999999999999999999', '9_9e999999999999999999', '٩٩e٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩٩'])
def test_huge_positive_integer_exponents_fail_before_expansion(raw):
    failure((encoded([row(**{'Total Fwd Packet':raw})]),), 'integer_expansion_limit')


@pytest.mark.parametrize('raw', ['0e999999999', '0e-999999999', '-0e999999999', '0e99999999999999999999999'])
def test_zero_large_exponents_do_not_expand_or_misclassify(raw):
    r = parse([row(**{'Total Fwd Packet':raw})]).rows[0]
    assert r.fwd_packets == 0 and r.reasons == ()


@pytest.mark.parametrize('raw,want', [
    ('0e999999999999999999',0), ('-0e999999999999999999',0),
    ('-99e999999999999999999',None), ('99e-999999999999999999',None),
    ('99.5',None), ('9_9e0',99), ('99e-1',None), ('9.90e1',99), ('0.0001e4',1),
])
def test_adjusted_exponent_guard_preserves_zero_negative_fraction_and_underscores(raw,want):
    r=parse([row(**{'Total Fwd Packet':raw})]).rows[0]
    assert r.fwd_packets==want
    assert r.reasons==(() if want is not None else ('invalid_fwd_packets',))


def test_expanded_integer_digit_budget_exact_boundary():
    assert parse([row(**{'Total Fwd Packet':'1e4095'})]).rows[0].fwd_packets == 10**4095
    assert parse([row(**{'Total Fwd Packet':'999','Flow Duration':'0'})], max_expanded_integer_digits=3).rows[0].fwd_packets == 999
    failure((encoded([row(**{'Total Fwd Packet':'1000','Flow Duration':'0'})]),), 'integer_expansion_limit', max_expanded_integer_digits=3)


def test_total_bytes_rows_sources_and_field_length_budget_boundaries():
    m = mod(); source = encoded([row()])
    assert m._parse_release_csv((source,),budget=m.ReleaseFixtureBudget(max_total_input_bytes=len(source))).rows
    failure((source,), 'input_byte_cap', max_total_input_bytes=len(source)-1)
    assert len(parse([row(),row()],max_rows=2).rows)==2
    failure((encoded([row(),row()]),), 'max_rows', max_rows=1)
    assert len(m._parse_release_csv((source,)*5,budget=m.ReleaseFixtureBudget()).rows)==5
    failure((source,)*6,'max_sources')
    failure((source,source),'max_sources',max_sources=1)
    assert parse([row(**{'Idle Mean':'x'*4096})]).rows
    failure((encoded([row(**{'Idle Mean':'x'*4097})]),), 'max_field_chars')


@pytest.mark.parametrize('field,budget_key,code', [
    ('Label','max_label_values','max_label_values'),
    ('Attempted Category','max_category_values','max_category_values'),
    ('Protocol','max_protocol_values','max_protocol_values'),
])
def test_vocabulary_budgets_count_exact_lexical_values_across_sources(field,budget_key,code):
    m=mod(); a=encoded([row(**{field:'0'})]); b=encoded([row(**{field:'0.0'})])
    assert len(m._parse_release_csv((a,b),budget=m.ReleaseFixtureBudget(**{budget_key:2})).rows)==2
    failure((a,b),code,**{budget_key:1})


@pytest.mark.parametrize('key,ceiling', [
    ('max_sources',5),('max_total_input_bytes',8*1024*1024),('max_rows',10000),
    ('max_field_chars',4096),('max_label_values',100),('max_category_values',32),
    ('max_protocol_values',256),('max_expanded_integer_digits',4096),
])
@pytest.mark.parametrize('bad', ['zero','negative','bool','float','string','over'])
def test_budget_rejects_invalid_and_over_ceiling_values_before_sources(key,ceiling,bad):
    m=mod(); value={'zero':0,'negative':-1,'bool':True,'float':1.0,'string':'1','over':ceiling+1}[bad]
    with pytest.raises(ValueError, match='^invalid_budget$'):
        budget=m.ReleaseFixtureBudget(**{key:value})
        m._parse_release_csv((),budget=budget)


@pytest.mark.parametrize('sources', [[], 'private/path', b'private', (bytearray(b'private'),), (io.BytesIO(b'private'),), (v for v in ())])
def test_exact_immutable_input_types_only(sources):
    failure(sources, 'invalid_sources')


def test_budget_exact_type_and_frozen_payload_privacy():
    m=mod()
    with pytest.raises(ValueError,match='^invalid_budget$'):
        m._parse_release_csv((encoded([row()]),),budget={})
    b=parse([row(Label='private-label',**{'Attempted Category':'private-category'})])
    for value in (b,b.rows[0]):
        with pytest.raises(FrozenInstanceError): value.schema_id='changed'
        rendered=repr(value)
        for secret in ('private-label','private-category','artificial-src','quoted','manual,flow'):
            assert secret not in rendered
    assert type(b.rows) is tuple and type(b.rows[0].raw_fields) is tuple
    assert type(b.rows[0].lexical_fingerprint) is bytes


def test_small_artificial_differential_against_existing_pure_rules():
    from tools.data_audit import c17_payload as old
    from tools.data_audit import c17_g13u as g13
    cases=[row(),row(Protocol='0.0',Label='Portscan'),row(Protocol='200'),
           row(**{'Total Fwd Packet':'2e0','Flow Duration':'1.0'}),
           row(Timestamp='invalid',**{'Total Bwd packets':'NaN'}),
           row(Label='FTP-Patator - Attempted',**{'Attempted Category':'0'})]
    for values,r in zip(cases,parse(cases).rows):
        as_dict=dict(zip(HEADER,values))
        assert r.lexical_fingerprint==old._fingerprint(values)
        assert r.start==old._parse_time(as_dict['Timestamp'],CONFIG)
        kinds,attempted,definite,anomaly=old._label_kinds(as_dict['Label'],as_dict['Attempted Category'],CONFIG['labels'])
        assert (r.label_kinds,r.attempted,r.definite_attack,r.label_anomaly)==(kinds,attempted,definite,anomaly)
        bad,duration=old._g12(as_dict,CONFIG)
        assert r.duration_us==duration
        for key in ('duration','protocol','fwd_packets','bwd_packets','fwd_length','bwd_length'):
            assert ('invalid_'+key in r.reasons)==(key in bad)
        assert r.protocol_channel==g13._channel(as_dict['Protocol'])


def test_parser_performs_no_file_network_or_model_calls(monkeypatch):
    m=mod(); source=encoded([row()]); budget=m.ReleaseFixtureBudget()
    datetime.strptime('2026-01-01 00:00:00.1','%Y-%m-%d %H:%M:%S.%f')
    original_import=builtins.__import__
    def guarded_import(name,*args,**kwargs):
        assert name.split('.')[0] not in {'tools','torch','sklearn','numpy','pyarrow'}
        return original_import(name,*args,**kwargs)
    def forbidden(*args,**kwargs):
        pytest.fail('parser attempted external IO')
    with monkeypatch.context() as guard:
        guard.setattr(builtins,'open',forbidden)
        guard.setattr(io,'open',forbidden)
        guard.setattr(socket,'socket',forbidden)
        guard.setattr(builtins,'__import__',guarded_import)
        result=m._parse_release_csv((source,),budget=budget)
    assert result.rows[0].fwd_packets==2


@pytest.mark.parametrize('coefficient,exponent,want', [('1','1',10), ('100','-1',10), ('0','1',0)])
def test_long_unicode_zero_padded_exponents_keep_decimal_semantics(coefficient,exponent,want):
    sign='-' if exponent.startswith('-') else ''
    text=coefficient+'e'+sign+'٠'*32+'١'
    r=parse([row(**{'Total Fwd Packet':text})]).rows[0]
    assert r.fwd_packets==want and r.reasons==()


def test_multibyte_and_internal_bom_remain_in_length_framed_identity():
    values=row(**{'Flow ID':'\ufeff人工,\n"流"'})
    frame=b''.join(len(s.encode('utf-8')).to_bytes(4,'little')+s.encode('utf-8') for s in values)
    r=parse([values]).rows[0]
    assert r.lexical_fingerprint==hashlib.sha256(frame).digest()
    assert r.raw_fields[1]=='\ufeff人工,\n"流"'


def test_hard_row_ceiling_accepts_full_batch_and_rejects_one_more():
    assert len(parse([row()]*10000).rows)==10000
    failure((encoded([row()]*10001),),'max_rows')


def test_hard_byte_ceiling_accepts_exact_eight_mib_and_rejects_one_more():
    m=mod(); cap=8*1024*1024
    header=encoded(); base=encoded([row()])[len(header):]
    wide=encoded([row(**{'Idle Mean':'x'*4096})])[len(header):]
    count=(cap-len(header)-len(base))//len(wide)
    remaining=cap-len(header)-len(wide)*count-len(base)
    first=min(remaining,4095)
    last=encoded([row(**{'Idle Mean':'x'*(first+1),'Idle Std':'x'*(remaining-first+1)})])[len(header):]
    source=header+wide*count+last
    assert len(source)==cap
    assert len(m._parse_release_csv((source,),budget=m.ReleaseFixtureBudget()).rows)==count+1
    failure((source+b'x',),'input_byte_cap')


def test_exact_source_and_budget_subclasses_are_not_accepted():
    m=mod()
    class Sources(tuple): pass
    class Source(bytes): pass
    class Budget(m.ReleaseFixtureBudget): pass
    failure(Sources((encoded(),)),'invalid_sources')
    failure((Source(encoded()),),'invalid_sources')
    with pytest.raises(ValueError,match='^invalid_budget$'):
        m._parse_release_csv((encoded(),),budget=Budget())

