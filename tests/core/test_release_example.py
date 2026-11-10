"""Independent fixed-recipe checks for a pure source/example bytes builder."""
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta
import builtins
import csv
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePath
import time

import pytest

from traffic_anomaly._release_csv import EXPECTED_HEADER


def api():
    try:
        module = importlib.import_module('traffic_anomaly.release_example')
    except ModuleNotFoundError as error:
        if error.name != 'traffic_anomaly.release_example':
            raise
        pytest.fail('public pure example builder is missing')
    assert callable(getattr(module, 'build_release_example', None)), 'public builder is missing'
    return module


def test_builder_returns_three_bounded_immutable_members(tmp_path):
    c = api()
    source = tmp_path / 'future-not-created' / 'artificial.csv'
    example = c.build_release_example(source_csv_path=source)
    assert type(example) is c.ReleaseExample
    assert example.profile_id == c.EXAMPLE_PROFILE_ID == 'release-artificial-example-v1'
    assert tuple(name for name, _ in example.members) == c.EXAMPLE_MEMBER_NAMES == (
        'artificial.csv', 'aggregate-spec.json', 'recipe.json')
    assert type(example.members) is tuple and all(type(pair) is tuple and len(pair) == 2
        and type(pair[0]) is str and type(pair[1]) is bytes for pair in example.members)
    assert c.EXAMPLE_MEMBER_BYTE_LIMITS == (('artificial.csv', 1048576),
        ('aggregate-spec.json', 65536), ('recipe.json', 16384))
    assert all(len(payload) <= dict(c.EXAMPLE_MEMBER_BYTE_LIMITS)[name]
        for name, payload in example.members)
    assert c.EXAMPLE_TOTAL_BYTE_LIMIT == 1130496
    assert sum(len(payload) for _, payload in example.members) <= c.EXAMPLE_TOTAL_BYTE_LIMIT
    assert [field.name for field in fields(example)] == ['profile_id', 'members']
    assert not hasattr(example, '__dict__')
    with pytest.raises(FrozenInstanceError):
        example.members = ()
    assert not source.parent.exists()


SEGMENTS = [
    dict(id='artificial-train', role='train', start='2026-01-01T00:00:00', end='2026-01-01T00:48:00'),
    dict(id='artificial-validation', role='validation', start='2026-01-01T01:00:00', end='2026-01-01T01:40:00'),
    dict(id='artificial-calibration', role='calibration', start='2026-01-01T02:00:00', end='2026-01-01T02:40:00'),
    dict(id='artificial-test', role='test', start='2026-01-01T03:00:00', end='2026-01-01T03:48:00'),
]
BUDGET = dict(max_total_source_bytes=1048576, max_rows=512,
              max_database_bytes=8388608, max_elapsed_seconds=30, max_minutes=240)


def canonical(document):
    return (json.dumps(document, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(',', ':')) + '\n').encode('utf-8')


def test_csv_records_match_fixed_recipe(tmp_path):
    c = api()
    members = dict(c.build_release_example(source_csv_path=tmp_path / 'artificial.csv').members)
    payload = members['artificial.csv']
    assert payload.endswith(b'\n') and not payload.endswith(b'\n\n')
    assert b'\r' not in payload and not payload.startswith(b'\xef\xbb\xbf')
    rows = list(csv.reader(io.StringIO(payload.decode('ascii'), newline=''), strict=True))
    assert tuple(rows[0]) == EXPECTED_HEADER and len(rows[0]) == 91
    assert len(rows) == 177 and all(len(row) == 91 for row in rows)
    values = [dict(zip(EXPECTED_HEADER, row)) for row in rows[1:]]
    assert [row['id'] for row in values] == [str(index) for index in range(176)]
    assert [row['Flow ID'] for row in values] == [f'artificial-{index:04d}' for index in range(176)]
    assert len({tuple(row) for row in rows[1:]}) == 176
    assert [values[i]['Timestamp'] for i in (0, 47, 48, 87, 88, 127, 128, 175)] == [
        '2026-01-01 00:00:10.000000', '2026-01-01 00:47:10.000000',
        '2026-01-01 01:00:10.000000', '2026-01-01 01:39:10.000000',
        '2026-01-01 02:00:10.000000', '2026-01-01 02:39:10.000000',
        '2026-01-01 03:00:10.000000', '2026-01-01 03:47:10.000000']
    changed_columns = {'id', 'Flow ID', 'Src IP', 'Dst IP', 'Timestamp', 'Flow Duration',
        'Total Fwd Packet', 'Total Bwd packets', 'Total Length of Fwd Packet',
        'Total Length of Bwd Packet', 'Protocol', 'Label', 'Attempted Category'}
    offset = 0
    # Literal cycles derive expected values from the written recipe, rather
    # than importing a production row builder or parser/qualification helper.
    packets = (1, 2, 3) * 16
    backwards = (0, 1, 1, 1, 1) * 10
    protocols = ('6', '17', '0') * 16
    for segment, length in zip(SEGMENTS, (48, 40, 40, 48)):
        start = datetime.fromisoformat(segment['start'])
        for local, row in enumerate(values[offset:offset + length]):
            p = {36: 8, 40: 16}.get(local, packets[local]) if segment['role'] == 'test' else packets[local]
            expected_protocol = '0' if segment['role'] == 'test' and local in (36, 40) else protocols[local]
            expected_label = {36: ('DoS Hulk', '-1'), 40: ('SSH-Patator - Attempted', '0'),
                              44: ('ARTIFICIAL_UNKNOWN', '-1')}.get(local, ('BENIGN', '-1')) \
                if segment['role'] == 'test' else ('BENIGN', '-1')
            assert row['Src IP'] == 'ARTIFICIAL_SRC' and row['Dst IP'] == 'ARTIFICIAL_DST'
            assert row['Timestamp'] == (start + timedelta(minutes=local, seconds=10)).strftime('%Y-%m-%d %H:%M:%S.%f')
            assert row['Flow Duration'] == '1000000'
            assert row['Total Fwd Packet'] == str(p)
            assert row['Total Bwd packets'] == str(backwards[local])
            assert row['Total Length of Fwd Packet'] == str(10 * p)
            assert row['Total Length of Bwd Packet'] == str(10 * backwards[local])
            assert row['Protocol'] == expected_protocol
            assert (row['Label'], row['Attempted Category']) == expected_label
            assert all(row[name] == '0' for name in EXPECTED_HEADER if name not in changed_columns)
        offset += length


def test_paths_change_only_aggregate_spec_and_bind_exact_csv_bytes(tmp_path):
    c = api()
    paths = (tmp_path / 'first-root' / 'artificial.csv', tmp_path / '中文 第二处' / 'artificial.csv')
    first, second = (dict(c.build_release_example(source_csv_path=path).members) for path in paths)
    assert first['artificial.csv'] == second['artificial.csv']
    assert first['recipe.json'] == second['recipe.json']
    assert first['aggregate-spec.json'] != second['aggregate-spec.json']
    csv_bytes = first['artificial.csv']
    digest = hashlib.sha256(csv_bytes).hexdigest()
    for path, members in zip(paths, (first, second)):
        spec = json.loads(members['aggregate-spec.json'])
        assert spec == dict(version=1, sources=[dict(path=str(path), bytes=len(csv_bytes), sha256=digest)],
                            segments=SEGMENTS, budget=BUDGET)
        recipe = json.loads(members['recipe.json'])
        assert recipe == dict(version=1, profile_id='release-artificial-example-v1',
            evidence_kind='ARTIFICIAL_ENGINEERING_EXAMPLE', format_schema_id='c17-release-91-v1',
            source_authentication='NOT_AUTHENTICATED', time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY',
            policy_status='AUDIT_ONLY', generation='FIXED_RECIPE_NO_RANDOMNESS',
            notice='Artificial format-compatible example; not an official CICIDS2017 dataset.',
            source=dict(member='artificial.csv', byte_count=len(csv_bytes), sha256=digest, row_count=176),
            segments=SEGMENTS)
        assert members['aggregate-spec.json'] == canonical(spec)
        assert members['recipe.json'] == canonical(recipe)
        assert str(path).encode('utf-8') not in members['recipe.json']
        assert hashlib.sha256(members['aggregate-spec.json']).hexdigest().encode('ascii') not in members['recipe.json']
    assert c.build_release_example(source_csv_path=paths[0]).members == tuple(first.items())


def reject(call, code):
    c = api()
    with pytest.raises(c.ReleaseExampleError) as error:
        call()
    assert error.value.code == code and str(error.value) == code


@pytest.mark.parametrize('kind', ['string', 'none', 'pure', 'relative', 'parent', 'basename',
    'unc', 'nul', 'surrogate', 'reserved', 'ads', 'root_only', 'path_subclass'])
def test_builder_rejects_wrong_type_or_unsafe_lexical_path(tmp_path, kind):
    c = api()
    if kind == 'string': path = str(tmp_path / 'artificial.csv')
    elif kind == 'none': path = None
    elif kind == 'pure': path = PurePath(tmp_path / 'artificial.csv')
    elif kind == 'relative': path = Path('future/artifical.csv')
    elif kind == 'parent': path = tmp_path / '..' / 'artificial.csv'
    elif kind == 'basename': path = tmp_path / 'other.csv'
    elif kind == 'unc': path = Path('//server/share/artificial.csv')
    elif kind == 'nul': path = tmp_path / 'nul\x00name' / 'artificial.csv'
    elif kind == 'surrogate': path = tmp_path / 'bad\ud800name' / 'artificial.csv'
    elif kind == 'path_subclass':
        class OtherPath(type(tmp_path)):
            pass
        path = OtherPath(tmp_path / 'artificial.csv')
    else:
        if os.name != 'nt': pytest.skip('Windows path semantics')
        path = {'reserved': Path('C:/nul/artificial.csv'), 'ads': Path('C:/folder:name/artificial.csv'),
                'root_only': Path('/artificial.csv')}[kind]
    reject(lambda: c.build_release_example(source_csv_path=path), 'INVALID_EXAMPLE_ARGUMENTS')


def test_builder_is_pure_under_filesystem_clock_environment_and_business_guards(tmp_path, monkeypatch):
    c = api()
    path = tmp_path / '未来 目录' / 'artificial.csv'
    def forbidden(*args, **kwargs):
        raise AssertionError('pure builder attempted external action')
    products = (
        ('traffic_anomaly._release_disk', ('_aggregate_release_files',)),
        ('traffic_anomaly.release_inputs', ('prepare_release_inputs', 'verify_release_input_derivation')),
        ('traffic_anomaly.release_iforest', ('fit_release_iforest', '_compute')),
    )
    modules = [(importlib.import_module(name), functions) for name, functions in products]
    with monkeypatch.context() as guard:
        for module, functions in modules:
            for function in functions:
                guard.setattr(module, function, forbidden)
        for name in ('open', 'stat', 'lstat', 'resolve', 'cwd', 'absolute'):
            guard.setattr(Path, name, forbidden)
        for name in ('stat', 'lstat', 'open', 'scandir', 'getenv'):
            guard.setattr(os, name, forbidden)
        guard.setattr(builtins, 'open', forbidden)
        guard.setattr(io, 'open', forbidden)
        guard.setattr(time, 'time', forbidden)
        first = c.build_release_example(source_csv_path=path)
        second = c.build_release_example(source_csv_path=path)
    assert first == second
    assert not path.parent.exists()


@pytest.mark.parametrize('member', ['artificial.csv', 'aggregate-spec.json', 'recipe.json', 'total'])
def test_builder_enforces_exact_member_and_total_cap_including_lf(tmp_path, monkeypatch, member):
    c = api()
    path = tmp_path / 'artificial.csv'
    members = dict(c.build_release_example(source_csv_path=path).members)
    size = sum(map(len, members.values())) if member == 'total' else len(members[member])
    if member == 'total':
        monkeypatch.setattr(c, 'EXAMPLE_TOTAL_BYTE_LIMIT', size - 1)
    else:
        monkeypatch.setattr(c, 'EXAMPLE_MEMBER_BYTE_LIMITS', tuple(
            (name, size - 1 if name == member else limit) for name, limit in c.EXAMPLE_MEMBER_BYTE_LIMITS))
    reject(lambda: c.build_release_example(source_csv_path=path), 'RESOURCE_LIMIT')
    if member == 'total':
        monkeypatch.setattr(c, 'EXAMPLE_TOTAL_BYTE_LIMIT', size)
    else:
        monkeypatch.setattr(c, 'EXAMPLE_MEMBER_BYTE_LIMITS', tuple(
            (name, size if name == member else limit) for name, limit in c.EXAMPLE_MEMBER_BYTE_LIMITS))
    assert dict(c.build_release_example(source_csv_path=path).members) == members


def test_legal_but_extreme_future_path_hits_spec_budget_without_filesystem(tmp_path):
    c = api()
    path = tmp_path / ('long-future-' * 7000) / 'artificial.csv'
    reject(lambda: c.build_release_example(source_csv_path=path), 'RESOURCE_LIMIT')


def test_unknown_error_codes_and_construction_failure_are_safe_while_interrupt_propagates(tmp_path, monkeypatch):
    c = api()
    assert str(c.ReleaseExampleError('private-details')) == 'EXAMPLE_ERROR'
    assert str(c.ReleaseExampleError(['RESOURCE_LIMIT'])) == 'EXAMPLE_ERROR'
    path = tmp_path / 'artificial.csv'
    def fail(*args, **kwargs):
        raise RuntimeError('private construction details')
    with monkeypatch.context() as guard:
        guard.setattr(c.csv, 'writer', fail)
        reject(lambda: c.build_release_example(source_csv_path=path), 'EXAMPLE_ERROR')
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt('private interruption')
    monkeypatch.setattr(c.csv, 'writer', interrupted)
    with pytest.raises(KeyboardInterrupt):
        c.build_release_example(source_csv_path=path)
