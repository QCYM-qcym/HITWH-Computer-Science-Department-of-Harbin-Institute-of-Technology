"""Register six saved declarations and freeze a read-only learned view."""
from dataclasses import fields
from hashlib import sha256
from importlib.resources import files as _resource_files
import json

from fastapi import FastAPI, Request
from fastapi.responses import Response
from traffic_anomaly import release_minute_contract as raw_contract
from traffic_anomaly import release_inputs as prepared_contract
from traffic_anomaly import release_if_result_contract as result_contract
from traffic_anomaly import release_if_learned_contract as learned_contract
from traffic_anomaly.release_iforest import ReleaseIFConfiguration, ReleaseIFResult
from traffic_anomaly.release_model_inputs import pair_release_model_inputs, ReleaseModelInputPairError
from traffic_anomaly.release_if_result_contract import verify_release_if_result_pair
from traffic_anomaly.release_if_learned_summary import summarize_release_if_learned
from traffic_anomaly.release_if_learned_contract import _population_sha256
from .release_if_result_view import create_release_if_result_view_app, ReleaseIFResultViewError

_PROFILE = 'c17-release-iforest-learned-view-v1'
_SCOPE = 'REGISTERED_SAVED_LEARNED_TUPLE_INSPECTION_ONLY'
_SUMMARY_LIMIT = 65536
_ASSET_LIMIT = 65536
_TOTAL_LIMIT = 262144
_ASSETS = (('/release/learned', 'learned.html', 'text/html'),
    ('/release/learned/learned.mjs', 'learned.mjs', 'text/javascript'),
    ('/release/learned/learned.css', 'learned.css', 'text/css'))
_HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
_CSP = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
_ERRORS = {c: ('{"error":"' + c + '"}\n').encode() for c in
    ('NOT_FOUND', 'METHOD_NOT_ALLOWED', 'INVALID_QUERY', 'VIEW_UNAVAILABLE')}
_CODES = ('INVALID_VIEW_ARGUMENTS', 'INPUT_BINDING_MISMATCH', 'RESOURCE_LIMIT', 'VIEW_UNAVAILABLE')


class ReleaseIFLearnedViewError(ValueError):
    def __init__(self, code: str):
        self.code = code if type(code) is str and code in _CODES else 'VIEW_UNAVAILABLE'
        super().__init__(self.code)


def _need(condition, code='INPUT_BINDING_MISMATCH'):
    if not condition: raise ReleaseIFLearnedViewError(code)


def _holder(value, kind, code='INPUT_BINDING_MISMATCH', slots=None):
    _need(type(value) is kind, code)
    try:
        names = (field.name for field in fields(kind)) if slots is None else slots
        for name in names: object.__getattribute__(value, name)
    except AttributeError:
        raise ReleaseIFLearnedViewError(code) from None


def _primitives(value, kinds):
    for name, kind in kinds:
        _need(type(getattr(value, name)) is kind)


def _identity(value, kind):
    _holder(value, kind)
    _primitives(value, (('profile_id', str), ('context_sha256', str),
        ('manifest_sha256', str), ('manifest_byte_count', int)))


def _reference(value):
    return {k: getattr(value, k) for k in
        ('profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count')}


def _configuration(value, kind):
    _holder(value, kind)
    _primitives(value, tuple(zip(('input_width', 'n_estimators', 'max_samples', 'max_features',
        'bootstrap', 'contamination', 'random_state', 'n_jobs'),
        (int, int, int, float, bool, str, int, int))))


def _precheck(raw, prepared, cr, cl, hr, hl):
    for value, kind in ((raw, raw_contract.ReleaseMinutePackage),
        (prepared, prepared_contract.ReleasePreparedInputs),
        (cr, result_contract.ReleaseIFResultPackage), (cl, learned_contract.ReleaseIFLearnedPackage),
        (hr, result_contract.ReleaseIFResultPackage), (hl, learned_contract.ReleaseIFLearnedPackage)):
        _holder(value, kind, 'INVALID_VIEW_ARGUMENTS')
    _identity(raw.identity, raw_contract.ReleaseMinutePackageIdentity)
    _identity(prepared.identity, prepared_contract.ReleaseInputIdentity)
    _holder(prepared.context, prepared_contract.ReleaseInputContext, slots=('upstream', 'configuration'))
    _identity(prepared.context.upstream, raw_contract.ReleaseMinutePackageIdentity)
    config = prepared.context.configuration
    _holder(config, prepared_contract.ReleasePreparationConfig)
    _primitives(config, tuple(zip(('schema_version', 'numeric_rules_id', 'feature_names',
        'windows', 'fit_window', 'epsilon', 'audit_fit_policy', 'policy_status'),
        (int, str, tuple, tuple, int, float, str, str))))
    for result in (cr, hr):
        _identity(result.identity, result_contract.ReleaseIFResultIdentity)
        _holder(result.context, result_contract.ReleaseIFResultContext,
            slots=('raw_identity', 'prepared_identity', 'model_configuration'))
        _holder(result.result, ReleaseIFResult, slots=('configuration',))
        _identity(result.context.raw_identity, raw_contract.ReleaseMinutePackageIdentity)
        _identity(result.context.prepared_identity, prepared_contract.ReleaseInputIdentity)
        _configuration(result.context.model_configuration, ReleaseIFConfiguration)
        _configuration(result.result.configuration, ReleaseIFConfiguration)
    for learned in (cl, hl):
        _identity(learned.identity, learned_contract.ReleaseIFLearnedReference)
        c = learned.context
        _holder(c, learned_contract.ReleaseIFLearnedContext)
        for name in ('raw_identity', 'prepared_identity', 'result_identity'):
            _identity(getattr(c, name), learned_contract.ReleaseIFLearnedReference)
        _configuration(c.model_configuration, learned_contract.ReleaseIFLearnedConfiguration)
        _primitives(c, tuple((k, str) for k in ('profile_id', 'view', 'configuration_sha256',
            'population_sha256', 'input_rules_id', 'fit_runtime_id')) +
            tuple((k, int) for k in ('minute_count', 'train_count', 'calibration_count',
                'preprocessing_fit_count')) + (('feature_columns', tuple),))


def _call(function, expected, allowed, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except MemoryError:
        raise
    except Exception as error:
        if type(error) is expected:
            try:
                code = error.code
            except MemoryError:
                raise
            except Exception:
                raise ReleaseIFLearnedViewError('VIEW_UNAVAILABLE') from None
            if type(code) is str and code in allowed:
                raise ReleaseIFLearnedViewError('RESOURCE_LIMIT' if code == 'RESOURCE_LIMIT'
                    else 'INPUT_BINDING_MISMATCH') from None
        raise ReleaseIFLearnedViewError('VIEW_UNAVAILABLE') from None


def _json_bytes(value, limit):
    result = bytearray()
    for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(',', ':')).iterencode(value):
        encoded = chunk.encode('utf-8')
        _need(len(result) + len(encoded) + 1 <= limit, 'RESOURCE_LIMIT')
        result.extend(encoded)
    result.extend(b'\n')
    return bytes(result)


def _read_assets():
    root = _resource_files('traffic_api').joinpath('release_if_learned_static')
    result = []
    for path, name, mime in _ASSETS:
        with root.joinpath(name).open('rb') as stream: payload = stream.read(_ASSET_LIMIT + 1)
        _need(type(payload) is bytes and bool(payload), 'VIEW_UNAVAILABLE')
        _need(len(payload) <= _ASSET_LIMIT, 'RESOURCE_LIMIT')
        payload.decode('utf-8')
        result.append((path, payload, mime))
    return tuple(result)


def _endpoint(payload, mime):
    headers = {**_HEADERS, **({'Content-Security-Policy': _CSP} if mime == 'text/html' else {})}
    async def serve(request: Request):
        if request.scope.get('query_string', b''):
            return Response(_ERRORS['INVALID_QUERY'], status_code=422,
                media_type='application/json', headers=_HEADERS)
        return Response(payload, media_type=mime, headers=headers)
    return serve


def create_release_if_learned_view_app(raw: raw_contract.ReleaseMinutePackage,
        prepared: prepared_contract.ReleasePreparedInputs,
        current13_result: result_contract.ReleaseIFResultPackage,
        current13_learned: learned_contract.ReleaseIFLearnedPackage,
        h30_26_result: result_contract.ReleaseIFResultPackage,
        h30_26_learned: learned_contract.ReleaseIFLearnedPackage) -> FastAPI:
    """Bind saved content and declarations, without estimation or numerical replay."""
    try:
        _precheck(raw, prepared, current13_result, current13_learned, h30_26_result, h30_26_learned)
        pair = _call(pair_release_model_inputs, ReleaseModelInputPairError,
            ('INVALID_PAIR_ARGUMENTS', 'INVALID_PAIR_STRUCTURE', 'INCOMPATIBLE_PAIR',
             'RESOURCE_LIMIT', 'UPSTREAM_IDENTITY_MISMATCH', 'PAIR_ALIGNMENT_MISMATCH'), raw, prepared)
        results = (current13_result, h30_26_result)
        learned_values = (current13_learned, h30_26_learned)
        for result in results:
            _call(verify_release_if_result_pair, result_contract.ReleaseIFResultPackageError,
                result_contract._CODES, result, pair)
        summaries = [_call(summarize_release_if_learned, learned_contract.ReleaseIFLearnedError,
            learned_contract._CODES, value) for value in learned_values]
        for name, result, learned in zip(('current13', 'h30_26'), results, learned_values):
            c, r = learned.context, result.result
            _need(c.view == name and result.context.view == name)
            for a, b in ((c.raw_identity, raw.identity), (c.prepared_identity, prepared.identity),
                    (c.result_identity, result.identity)):
                _need(_reference(a) == _reference(b))
            _need(c.configuration_sha256 == pair.configuration_sha256)
            _need((c.minute_count, c.train_count, c.calibration_count, c.preprocessing_fit_count) ==
                (len(pair.roles), len(r.train_indices), len(r.calibration_indices), len(r.preprocessing_fit_indices)))
            _need(c.input_rules_id == pair.configuration.numeric_rules_id)
            columns = tuple('current:' + n for n in pair.configuration.feature_names)
            if name == 'h30_26': columns += tuple('residual_h30:' + n for n in pair.configuration.feature_names)
            _need(c.feature_columns == columns and c.fit_runtime_id == learned_contract.LEARNED_FIT_RUNTIME_ID)
            _need(all(getattr(c.model_configuration, f.name) == getattr(r.configuration, f.name)
                for f in fields(ReleaseIFConfiguration)))
            digest = _call(_population_sha256, learned_contract.ReleaseIFLearnedError,
                learned_contract._CODES, minute_count=len(pair.roles), **{k: getattr(r, k) for k in
                    ('scored_mask', 'train_indices', 'calibration_indices', 'preprocessing_fit_indices')})
            _need(digest == c.population_sha256)
        try:
            app = create_release_if_result_view_app(*results)
        except MemoryError:
            raise
        except Exception as error:
            if type(error) is not ReleaseIFResultViewError:
                raise ReleaseIFLearnedViewError('VIEW_UNAVAILABLE') from None
            try:
                code = error.code
            except MemoryError:
                raise
            except Exception:
                raise ReleaseIFLearnedViewError('VIEW_UNAVAILABLE') from None
            if type(code) is not str or code not in ('INVALID_VIEW_ARGUMENTS', 'INCOMPATIBLE_RESULT_PAIR', 'RESOURCE_LIMIT', 'VIEW_UNAVAILABLE'):
                raise ReleaseIFLearnedViewError('VIEW_UNAVAILABLE') from None
            raise ReleaseIFLearnedViewError(code if code in ('RESOURCE_LIMIT', 'VIEW_UNAVAILABLE')
                else 'INPUT_BINDING_MISMATCH') from None
        refs = dict(zip(('current13', 'h30_26'), map(lambda x: _reference(x.identity), results)))
        result_snapshot = sha256(_json_bytes(dict(profile_id='c17-release-iforest-view-v1', **refs), 16384)).hexdigest()
        r = current13_result.result; total = len(pair.roles); common = sum(r.scored_mask)
        body = dict(version=1, profile_id=_PROFILE, scope=_SCOPE, result_snapshot_sha256=result_snapshot,
            input_references=dict(raw=_reference(raw.identity), prepared=_reference(prepared.identity)),
            result_references=refs, learned_references=dict(zip(('current13', 'h30_26'),
                (_reference(x.identity) for x in learned_values))),
            populations=dict(total=total, common=common, unscored=total-common,
                test_total=pair.roles.count('test'), test_common=sum(ok and role == 'test'
                    for ok, role in zip(r.scored_mask, pair.roles)), training=len(r.train_indices),
                calibration=len(r.calibration_indices), preprocessing_fit=len(r.preprocessing_fit_indices)),
            views=dict(zip(('current13', 'h30_26'), summaries)), registration_checks=dict(
                input_pair_binding='MATCHED', result_pair_binding='MATCHED', learned_declarations_binding='MATCHED'),
            replay=None, limits=dict(metadata_bytes=65536, source_axis_minutes=10000,
                result_page_size=100, result_page_bytes=131072))
        body['snapshot_sha256'] = sha256(_json_bytes(body, _SUMMARY_LIMIT)).hexdigest()
        payload = _json_bytes(body, _SUMMARY_LIMIT); assets = _read_assets()
        _need(len(payload) + sum(len(b) for _, b, _ in assets) + sum(map(len, _ERRORS.values())) <= _TOTAL_LIMIT, 'RESOURCE_LIMIT')
        app.add_api_route('/release-if-learned/v1/summary', _endpoint(payload, 'application/json'), methods=['GET'])
        for path, content, mime in assets:
            app.add_api_route(path, _endpoint(content, mime), methods=['GET'])
        from fastapi.routing import _extract_endpoint_context
        for route in app.routes: _extract_endpoint_context(route.endpoint)
        return app
    except MemoryError:
        raise ReleaseIFLearnedViewError('RESOURCE_LIMIT') from None
    except Exception as error:
        if type(error) is ReleaseIFLearnedViewError: raise
        raise ReleaseIFLearnedViewError('VIEW_UNAVAILABLE') from None
