"""Independent saved-score examples for the frozen dual-view transport."""
from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
from importlib import import_module
from io import BytesIO
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


P = 'c17-release-iforest-result-package-v1'
Q = 'c17-release-iforest-view-v1'
SCOPE = 'SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY'
SUMMARY = '/release-if/v1/summary'
SERIES = '/release-if/v1/series'
ASSETS = {'results.html': b'<!doctype html><title>saved results</title>',
          'results.mjs': b'export const resultView = true;',
          'results.css': b'body{color:black}'}
ROUTES = {'/release/results': 'results.html',
          '/release/results/results.mjs': 'results.mjs',
          '/release/results/results.css': 'results.css'}
PRIVATE = '/private-sentinel/not-a-public-result'


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def api():
    try:
        return import_module('traffic_api.release_if_result_view')
    except ModuleNotFoundError as exc:
        if exc.name == 'traffic_api.release_if_result_view':
            pytest.fail('frozen dual-view backend feature has not been implemented')
        raise


def hand_documents(view='current13', *, n=106, segment_id='train', extreme=False):
    """Handwritten contract values; never fit, prepare, or call a product builder."""
    raw = dict(profile_id='c17-release-minute-package-v1', context_sha256='a'*64,
               manifest_sha256='b'*64, manifest_byte_count=700)
    prepared = dict(profile_id='c17-release-prepared-input-package-v1',
                    context_sha256='c'*64, manifest_sha256='d'*64, manifest_byte_count=800)
    start = datetime(2026, 1, 1)
    stamp = lambda i: (start + timedelta(minutes=i)).isoformat(timespec='seconds')
    segments = [dict(ordinal=0, id=segment_id, role='train', start=stamp(0), end=stamp(65)),
                dict(ordinal=1, id='calibration', role='calibration', start=stamp(70), end=stamp(n+5))]
    mask = [31 <= i < 65 or 95 <= i < n for i in range(n)]
    threshold = 2.9699999999999998 if view == 'current13' else 0.0
    scores = [0.0 if ok else None for ok in mask]
    if view == 'current13':
        scores[95:99] = [0.0, 1.0, 2.0, 3.0]
    scores[99] = 4.0 if view == 'current13' else 5.0
    if extreme:
        scores[31:65] = [1.7976931348623157e308]*34
        scores[99:] = [1.7976931348623157e308]*(n-99)
    context = dict(profile_id=P, result_profile_id='c17-release-iforest-engineering-v1',
        view=view, source_schema_id='c17-release-91-v1', source_authentication='NOT_AUTHENTICATED',
        time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY', policy_status='AUDIT_ONLY', audit_fit_policy='P_U',
        raw_identity=raw, prepared_identity=prepared, configuration_sha256='e'*64,
        model_configuration=dict(input_width=13 if view == 'current13' else 26, n_estimators=16,
            max_samples=2, max_features=1.0, bootstrap=False, contamination='auto', random_state=42, n_jobs=1),
        segments=segments, minute_count=n, score_direction='NEGATIVE_SCORE_SAMPLES',
        calibration=dict(quantile=0.99, method='linear', comparison='STRICT_GREATER'))
    result = dict(schema_version=1, profile_id=P, context_sha256='', scores=scores,
        predictions=[None if score is None else score > threshold for score in scores],
        scored_mask=mask, threshold=threshold, train_indices=[31, 32],
        calibration_indices=[95, 96, 97, 98], preprocessing_fit_indices=[30, 31, 32])
    return context, result


def hand_package(view='current13', *, mutate=None, **kwargs):
    """Only the actual codec admits test bytes; no substitute product module."""
    from traffic_anomaly.release_if_result_contract import decode_release_if_result_package
    context, result = hand_documents(view, **kwargs)
    if mutate:
        mutate(context, result)
    digest = sha256(canonical(context)).hexdigest()
    result['context_sha256'] = digest
    body = canonical(result)
    manifest = canonical(dict(schema_version=1, profile_id=P, context_sha256=digest,
        context=context, members={'result.json': dict(byte_count=len(body), sha256=sha256(body).hexdigest())}))
    complete = canonical(dict(schema_version=1, profile_id=P, status='COMPLETE',
        manifest=dict(byte_count=len(manifest), sha256=sha256(manifest).hexdigest())))
    return decode_release_if_result_package({'result.json': body, 'manifest.json': manifest, 'COMPLETE.json': complete})


class ResourceTree:
    def __init__(self, values, reads, parts=()):
        self.values, self.reads, self.parts = values, reads, parts

    def joinpath(self, name):
        return ResourceTree(self.values, self.reads, (*self.parts, name))

    def open(self, mode):
        assert mode == 'rb' and self.parts[0] == 'release_if_static' and len(self.parts) == 2
        name = self.parts[1]
        value = self.values.get(name, FileNotFoundError(PRIVATE))
        if isinstance(value, Exception):
            raise value
        reads = self.reads
        class Stream(BytesIO):
            def read(self, size=-1):
                reads.append((name, size))
                return super().read(size)
        return Stream(value)


def build(monkeypatch, *, current=None, h30=None, assets=None, real_assets=False):
    current = hand_package() if current is None else current
    h30 = hand_package('h30_26') if h30 is None else h30
    m = api()
    reads = []
    if not real_assets:
        monkeypatch.setattr(m.resources, 'files', lambda name: ResourceTree(dict(ASSETS if assets is None else assets), reads))
    return m, m.create_release_if_result_view_app(current, h30), current, h30, reads


def safe_headers(response):
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert 'access-control-allow-origin' not in response.headers


def error(response, status, code, *, head=False):
    assert response.status_code == status
    assert response.content == (b'' if head else canonical({'error': code}))
    safe_headers(response)
    if status == 405:
        assert response.headers['allow'] == 'GET'


def test_saved_population_summary_and_unscored_fit_are_preserved(monkeypatch):
    _, app, current, h30, reads = build(monkeypatch)
    with TestClient(app) as client:
        response = client.get(SUMMARY)
    assert response.status_code == 200
    summary = response.json()
    assert set(summary) == {'version', 'profile_id', 'scope', 'snapshot_sha256', 'source',
        'input_references', 'result_references', 'axis', 'views', 'checks'}
    assert summary['profile_id'] == Q and summary['scope'] == SCOPE
    assert summary['source'] == dict(schema_id='c17-release-91-v1', authentication='NOT_AUTHENTICATED',
        time_basis='SOURCE_WALL_CLOCK_COMPLETION_PROXY', policy_status='AUDIT_ONLY', audit_fit_policy='P_U')
    assert summary['input_references'] == dict(raw=dict(profile_id='c17-release-minute-package-v1',
        context_sha256='a'*64, manifest_sha256='b'*64, manifest_byte_count=700),
        prepared=dict(profile_id='c17-release-prepared-input-package-v1', context_sha256='c'*64,
        manifest_sha256='d'*64, manifest_byte_count=800), configuration_sha256='e'*64)
    assert summary['axis'] == dict(minute_count=106, scored_count=45, unscored_count=61,
        page_size=100, page_count=2, segments=[
            dict(ordinal=0, id='train', role='train', start='2026-01-01T00:00:00', end='2026-01-01T01:05:00', minute_count=65, scored_count=34),
            dict(ordinal=1, id='calibration', role='calibration', start='2026-01-01T01:10:00', end='2026-01-01T01:51:00', minute_count=41, scored_count=11)])
    for view in ('current13', 'h30_26'):
        v = summary['views'][view]
        assert set(v) == {'configuration', 'threshold', 'training_count', 'calibration_count',
            'preprocessing_fit_count', 'equal_threshold_count', 'above_threshold_count'}
        assert (v['training_count'], v['calibration_count'], v['preprocessing_fit_count']) == (2, 4, 3)
        assert v['configuration'] == dict(input_width=13 if view == 'current13' else 26,
            n_estimators=16, max_samples=2, max_features=1.0, bootstrap=False,
            contamination='auto', random_state=42, n_jobs=1)
    assert summary['views']['current13']['threshold'] == 2.9699999999999998
    assert summary['views']['h30_26']['threshold'] == 0.0
    assert summary['views']['current13']['equal_threshold_count'] == 0
    assert summary['views']['current13']['above_threshold_count'] == 1
    assert summary['views']['h30_26']['equal_threshold_count'] == 4
    assert summary['views']['h30_26']['above_threshold_count'] == 0
    assert summary['checks'] == dict(internal_consistency='MATCHED', saved_score_q99='MATCHED',
        cross_view_binding='MATCHED', input_pair_binding='NOT_PERFORMED',
        source_authentication='NOT_AUTHENTICATED', model_execution='NOT_AUTHENTICATED')
    from dataclasses import asdict
    identities = dict(profile_id=Q, current13=asdict(current.identity), h30_26=asdict(h30.identity))
    assert summary['snapshot_sha256'] == sha256(canonical(identities)).hexdigest()
    assert summary['result_references'] == dict(current13=asdict(current.identity), h30_26=asdict(h30.identity))
    assert reads == [(name, 65537) for name in ASSETS]
    safe_headers(response)


def test_pages_preserve_global_indices_source_clock_breaks_and_saved_predictions(monkeypatch):
    _, app, *_ = build(monkeypatch)
    with TestClient(app) as client:
        first = client.get(SERIES).json()
        last = client.get(SERIES+'?page=1').json()
    assert set(first) == {'version', 'profile_id', 'scope', 'snapshot_sha256', 'page', 'page_size', 'total', 'returned', 'items'}
    assert (first['page'], first['returned'], last['page'], last['returned'], last['total']) == (0, 100, 1, 6, 106)
    assert first['items'][0] == dict(index=0, timestamp='2026-01-01T00:00:00', segment_id='train',
        role='train', break_before=True, scored=False, current13=dict(score=None, prediction=None),
        h30_26=dict(score=None, prediction=None), reason='NOT_SCORED_CAUSE_NOT_SAVED')
    assert first['items'][30]['current13'] == dict(score=None, prediction=None)
    assert first['items'][31]['current13'] == dict(score=0.0, prediction=False)
    assert first['items'][31]['break_before'] is True
    assert first['items'][32]['break_before'] is False
    assert first['items'][65]['timestamp'] == '2026-01-01T01:10:00'
    assert first['items'][65]['break_before'] is True
    assert first['items'][99]['current13'] == dict(score=4.0, prediction=True)
    assert first['items'][99]['h30_26'] == dict(score=5.0, prediction=True)
    assert first['items'][99]['reason'] is None
    assert last['items'][0]['index'] == 100 and last['items'][0]['break_before'] is False
    assert first['snapshot_sha256'] == last['snapshot_sha256']


@pytest.mark.parametrize('mutation', ['raw', 'prepared', 'configuration', 'policy', 'segment', 'segment-clock', 'mask', 'train', 'calibration', 'preprocessing'])
def test_same_counts_do_not_admit_a_different_pair(monkeypatch, mutation):
    def change(c, r):
        if mutation in ('raw', 'prepared'):
            c[mutation+'_identity']['manifest_sha256'] = 'f'*64
        elif mutation == 'configuration':
            c['configuration_sha256'] = 'f'*64
        elif mutation == 'policy':
            c['audit_fit_policy'] = 'P_B'
        elif mutation == 'segment':
            c['segments'][0]['id'] = 'different-train'
        elif mutation == 'segment-clock':
            c['segments'][1]['start'] = '2026-01-01T01:11:00'
            c['segments'][1]['end'] = '2026-01-01T01:52:00'
        elif mutation == 'mask':
            r['scored_mask'][34] = False
            r['scores'][34] = r['predictions'][34] = None
        elif mutation == 'train':
            r['train_indices'] = [31, 33]
            r['preprocessing_fit_indices'] = [30, 31, 33]
        elif mutation == 'calibration':
            r['calibration_indices'] = [95, 96, 97, 100]
        else:
            r['preprocessing_fit_indices'] = [31, 32, 33]
    def current_change(c, r):
        if mutation == 'mask':
            r['scored_mask'][33] = False
            r['scores'][33] = r['predictions'][33] = None
    current = hand_package(mutate=current_change)
    # h30 all-zero calibration makes an alternative calibration selection valid.
    h30 = hand_package('h30_26', mutate=change)
    m = api()
    with pytest.raises(m.ReleaseIFResultViewError) as caught:
        build(monkeypatch, current=current, h30=h30)
    assert str(caught.value) == caught.value.code == 'INCOMPATIBLE_RESULT_PAIR'


def test_unexpected_request_failure_uses_frozen_safe_500(monkeypatch):
    m, app, *_ = build(monkeypatch)
    async def broken(scope, receive, send):
        raise RuntimeError(PRIVATE)
    summary_route = next(route for route in app.routes if route.path == SUMMARY)
    monkeypatch.setattr(summary_route, 'app', broken)
    with TestClient(app, raise_server_exceptions=False) as client:
        def forbidden(*args, **kwargs):
            raise AssertionError('request serialization')
        monkeypatch.setattr(m, '_json_bytes', forbidden)
        error(client.get(SUMMARY), 500, 'VIEW_UNAVAILABLE')


@pytest.mark.parametrize('bad', [None, {}, object()])
def test_exact_package_argument_required(monkeypatch, bad):
    m = api()
    with pytest.raises(m.ReleaseIFResultViewError) as caught:
        m.create_release_if_result_view_app(bad, hand_package('h30_26'))
    assert str(caught.value) == 'INVALID_VIEW_ARGUMENTS'


def test_swapped_view_and_forged_declared_identity_rejected(monkeypatch):
    m = api()
    current, h30 = hand_package(), hand_package('h30_26')
    for a, b in ((h30, current), (current, current),
                 (replace(current, identity=replace(current.identity, manifest_sha256='f'*64)), h30)):
        with pytest.raises(m.ReleaseIFResultViewError) as caught:
            m.create_release_if_result_view_app(a, b)
        assert str(caught.value) == 'INCOMPATIBLE_RESULT_PAIR'


def test_factory_rechecks_saved_q99_and_load_report(monkeypatch):
    m = api()
    current, h30 = hand_package(), hand_package('h30_26')
    cases = (
        replace(current, result=replace(current.result, threshold=2.97)),
        replace(current, load_report=replace(current.load_report, model_execution='MATCHED')),
    )
    for package in cases:
        with pytest.raises(m.ReleaseIFResultViewError) as caught:
            m.create_release_if_result_view_app(package, h30)
        assert str(caught.value) == 'INCOMPATIBLE_RESULT_PAIR'


@pytest.mark.parametrize('name', ['_SUMMARY_LIMIT', '_SERIES_LIMIT', '_TOTAL_LIMIT'])
def test_encoding_budget_failure_returns_no_partial_app(monkeypatch, name):
    m = api()
    monkeypatch.setattr(m, name, 1)
    with pytest.raises(m.ReleaseIFResultViewError) as caught:
        build(monkeypatch)
    assert str(caught.value) == 'RESOURCE_LIMIT'


@pytest.mark.parametrize('kind', ['unexpected', 'interrupt'])
def test_unexpected_startup_is_safe_and_interrupt_is_not_swallowed(monkeypatch, kind):
    from traffic_anomaly import release_if_result_contract as codec
    m = api()
    current, h30 = hand_package(), hand_package('h30_26')
    def failure(*args, **kwargs):
        if kind == 'interrupt':
            raise KeyboardInterrupt(PRIVATE)
        raise RuntimeError(PRIVATE)
    monkeypatch.setattr(codec, 'encode_release_if_result_package', failure)
    if kind == 'interrupt':
        with pytest.raises(KeyboardInterrupt):
            m.create_release_if_result_view_app(current, h30)
    else:
        with pytest.raises(m.ReleaseIFResultViewError) as caught:
            m.create_release_if_result_view_app(current, h30)
        assert str(caught.value) == 'VIEW_UNAVAILABLE'


@pytest.mark.parametrize('query', ['page=', 'page=00', 'page=01', 'page=+1', 'page=-1', 'page=1.0',
    'page=100', 'page=2', 'page=١', 'page=1&page=0', 'page=0&%70age=0',
    'x=1', 'page=0&x=1', '&', 'page=%20', 'page=%2B1'])
def test_strict_series_query(monkeypatch, query):
    _, app, *_ = build(monkeypatch)
    with TestClient(app) as client:
        error(client.get(SERIES+'?'+query), 422, 'INVALID_QUERY')


@pytest.mark.parametrize('query,page', [('%70age=%30', 0), ('page=%31', 1)])
def test_percent_decoded_query_aliases_preserve_page_semantics(monkeypatch, query, page):
    _, app, *_ = build(monkeypatch)
    with TestClient(app) as client:
        response = client.get(SERIES+'?'+query)
    assert response.status_code == 200
    assert response.json()['page'] == page


@pytest.mark.parametrize('path', [SUMMARY, *ROUTES])
def test_other_routes_reject_query(monkeypatch, path):
    _, app, *_ = build(monkeypatch)
    with TestClient(app) as client:
        error(client.get(path+'?page=0'), 422, 'INVALID_QUERY')


def test_five_routes_methods_missing_paths_and_static_security(monkeypatch):
    _, app, *_ = build(monkeypatch)
    assert {r.path for r in app.routes} == {SUMMARY, SERIES, *ROUTES}
    assert all(r.methods == {'GET'} for r in app.routes)
    assert app.openapi_url is app.docs_url is app.redoc_url is None
    with TestClient(app) as client:
        for path, name in ROUTES.items():
            response = client.get(path)
            assert response.content == ASSETS[name]
            safe_headers(response)
        assert client.get('/release/results').headers['content-security-policy'] == "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        for path in (SUMMARY, SERIES, *ROUTES):
            for method in ('POST', 'HEAD', 'OPTIONS', 'PUT', 'DELETE', 'PATCH'):
                error(client.request(method, path+'?bad=1'), 405, 'METHOD_NOT_ALLOWED', head=method == 'HEAD')
        for path in ('/docs', '/openapi.json', '/release/results/', '/release-if/v1/series/', '/missing'):
            error(client.get(path, follow_redirects=False), 404, 'NOT_FOUND')


@pytest.mark.parametrize('real_assets', [False, True], ids=['controlled-assets', 'actual-source-assets'])
def test_first_and_repeated_requests_use_only_frozen_bytes(monkeypatch, real_assets):
    import builtins
    import io as file_io
    import os
    from traffic_anomaly import release_if_result_contract as codec, release_iforest, release_inputs
    from traffic_anomaly.evaluation import calibration
    from traffic_anomaly import release_if_result_package as io
    m, app, *_ = build(monkeypatch, real_assets=real_assets)
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append('forbidden request operation')
        raise AssertionError(PRIVATE)
    with TestClient(app) as client:
        with monkeypatch.context() as frozen:
            for module, names in ((codec, ('encode_release_if_result_package', 'decode_release_if_result_package', 'calibrate')),
                (release_iforest, ('_compute', '_validated_inputs')),
                (io, ('load_release_if_result_package', 'save_release_if_result_package')),
                (release_inputs, ('prepare_release_inputs', 'verify_release_input_derivation')),
                (calibration, ('calibrate',))):
                for name in names:
                    frozen.setattr(module, name, forbidden)
            frozen.setattr(m, '_json_bytes', forbidden)
            frozen.setattr(m.resources, 'files', forbidden)
            frozen.setattr(builtins, 'open', forbidden)
            frozen.setattr(file_io, 'open', forbidden)
            frozen.setattr(os, 'open', forbidden)
            frozen.setattr(os, 'stat', forbidden)
            frozen.setattr(os, 'lstat', forbidden)
            frozen.setattr(Path, 'open', forbidden)
            for _ in range(2):
                for path in (SUMMARY, SERIES, SERIES+'?page=1', *ROUTES):
                    assert client.get(path).status_code == 200
                error(client.get(SERIES+'?page=2'), 422, 'INVALID_QUERY')
    assert attempts == []


@pytest.mark.parametrize('kind,code', [('missing', 'VIEW_UNAVAILABLE'), ('oversize', 'RESOURCE_LIMIT'), ('utf8', 'VIEW_UNAVAILABLE')])
def test_static_failures_are_safe_before_app_exists(monkeypatch, kind, code):
    assets = dict(ASSETS)
    if kind == 'missing':
        del assets['results.css']
    else:
        assets['results.css'] = b'x'*65537 if kind == 'oversize' else b'\xff'
    m = api()
    with pytest.raises(m.ReleaseIFResultViewError) as caught:
        build(monkeypatch, assets=assets)
    assert str(caught.value) == code


def test_full_10000_axis_and_unicode_128_codepoints_fit_real_wire_budgets(monkeypatch):
    # Long ID occurs in the larger second segment to exercise every full page.
    def long_cal(c, r):
        c['segments'][1]['id'] = '\U0001f600'*128
    current = hand_package(n=10000, extreme=True, mutate=long_cal)
    h30 = hand_package('h30_26', n=10000, extreme=True, mutate=long_cal)
    _, app, *_ = build(monkeypatch, current=current, h30=h30)
    total = sum(map(len, ASSETS.values()))
    maximum_page_bytes = 0
    with TestClient(app) as client:
        summary = client.get(SUMMARY)
        assert len(summary.content) <= 16384
        assert summary.json()['axis']['page_count'] == 100
        total += len(summary.content)
        for page in range(100):
            response = client.get(SERIES+'?page='+str(page))
            assert response.status_code == 200 and len(response.content) <= 131072
            assert response.json()['returned'] == 100
            if page > 0:
                assert all(item['segment_id'] == '\U0001f600'*128 for item in response.json()['items'])
                assert response.json()['items'][-1]['current13']['score'] == 1.7976931348623157e308
            maximum_page_bytes = max(maximum_page_bytes, len(response.content))
            total += len(response.content)
    assert maximum_page_bytes > 65536
    assert total + sum(len(canonical({'error': code})) for code in
        ('NOT_FOUND', 'METHOD_NOT_ALLOWED', 'INVALID_QUERY', 'VIEW_UNAVAILABLE')) <= 16777216
