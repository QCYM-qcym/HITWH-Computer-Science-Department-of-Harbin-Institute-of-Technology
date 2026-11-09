"""Frozen transport for one admitted prepared-input summary, without replay."""
from importlib import resources
import json

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from traffic_anomaly.release_inputs import ReleasePreparedInputs
from traffic_anomaly.release_input_summary import summarize_release_inputs


_PAYLOAD_LIMIT=65536
_ASSET_LIMIT=65536
_TOTAL_ASSET_LIMIT=196608
_ASSETS=(('/release/inputs','inputs.html','text/html'),
    ('/release/inputs.mjs','inputs.mjs','text/javascript'),
    ('/release/inputs.css','inputs.css','text/css'))
_HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
_ERRORS={'NOT_FOUND':b'{"error":"NOT_FOUND"}\n',
    'METHOD_NOT_ALLOWED':b'{"error":"METHOD_NOT_ALLOWED"}\n',
    'INVALID_QUERY':b'{"error":"INVALID_QUERY"}\n',
    'INTERNAL_ERROR':b'{"error":"INTERNAL_ERROR"}\n'}


class ReleaseInputViewError(ValueError):
    def __init__(self,code):
        self.code=code if type(code) is str and code in (
            'INVALID_VIEW_INPUT','INVALID_RESULT','RESOURCE_LIMIT','VIEWER_ASSETS_UNAVAILABLE') else 'INVALID_VIEW_INPUT'
        super().__init__(self.code)


class _InvalidQuery(Exception):pass


def _json_bytes(value):
    try:payload=(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
    except Exception:raise ReleaseInputViewError('INVALID_RESULT') from None
    if len(payload)>_PAYLOAD_LIMIT:raise ReleaseInputViewError('RESOURCE_LIMIT')
    return payload


def _read_assets():
    values=[];total=0
    try:
        root=resources.files('traffic_api').joinpath('release_static')
        for path,name,media_type in _ASSETS:
            with root.joinpath(name).open('rb') as stream:payload=stream.read(_ASSET_LIMIT+1)
            if type(payload) is not bytes or not payload or len(payload)>_ASSET_LIMIT:raise ValueError()
            payload.decode('utf-8')
            total+=len(payload)
            if total>_TOTAL_ASSET_LIMIT:raise ValueError()
            values.append((path,payload,media_type))
    except Exception:raise ReleaseInputViewError('VIEWER_ASSETS_UNAVAILABLE') from None
    return tuple(values)


def _endpoint(payload,media_type):
    async def serve(request: Request):
        if request.scope.get('query_string',b''):raise _InvalidQuery()
        return Response(payload,media_type=media_type,headers=_HEADERS)
    return serve


def create_release_input_view_app(saved: ReleasePreparedInputs) -> FastAPI:
    """Project/encode once and preload assets before a launcher can bind.

    A value's Python type is not source authentication. Admission belongs to
    the trusted caller; this app never loads, decodes or numerically verifies.
    """
    if type(saved) is not ReleasePreparedInputs:raise ReleaseInputViewError('INVALID_VIEW_INPUT')
    try:summary=summarize_release_inputs(saved)
    except Exception:raise ReleaseInputViewError('INVALID_VIEW_INPUT') from None
    payload=_json_bytes(dict(version=1,command='inspect',status='INTERNAL_CONSISTENCY_CHECKED',summary=summary,replay=None))
    assets=_read_assets()
    app=FastAPI(title='Release input summary',debug=False,openapi_url=None,docs_url=None,
        redoc_url=None,redirect_slashes=False)

    def failure(request,status,code):
        headers={**_HEADERS,**({'Allow':'GET'} if status==405 else {})}
        return Response(b'' if request.method=='HEAD' else _ERRORS[code],status_code=status,
            media_type='application/json',headers=headers)

    @app.exception_handler(_InvalidQuery)
    async def invalid_query(request,exc):return failure(request,422,'INVALID_QUERY')

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exc):return failure(request,422,'INVALID_QUERY')

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        if exc.status_code==405:return failure(request,405,'METHOD_NOT_ALLOWED')
        if exc.status_code==404:return failure(request,404,'NOT_FOUND')
        return failure(request,500,'INTERNAL_ERROR')

    @app.exception_handler(Exception)
    async def internal_error(request,exc):return failure(request,500,'INTERNAL_ERROR')

    app.add_api_route('/release/v1/input-summary',_endpoint(payload,'application/json'),methods=['GET'])
    for path,value,media_type in assets:app.add_api_route(path,_endpoint(value,media_type),methods=['GET'])
    # Locked FastAPI 0.156.6 inspects source lazily. Warm only these four
    # endpoint contexts before returning; request handling performs no reads.
    from fastapi.routing import _extract_endpoint_context
    for route in app.routes:_extract_endpoint_context(route.endpoint)
    return app
