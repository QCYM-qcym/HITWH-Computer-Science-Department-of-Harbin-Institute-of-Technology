"""FastAPI factory and local synthetic development entry point."""
import argparse
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException
from traffic_anomaly import contracts as c

from .repository import Repository
from .schemas import ApiError, Settings, public_error
from .service import Service
from .worker import FakeExecutor, Worker

LOG = logging.getLogger(__name__)


def create_app(settings: Settings, *, fixture_path: Path, executor=None, registration=None):
    if registration is not None and executor is not None:
        raise ValueError('select one registered core executor or a test executor')
    repository = Repository(settings.database)
    worker = Worker(repository, registration if registration is not None else executor if executor is not None else FakeExecutor(fixture_path), settings.output)
    service = Service(repository, worker, fixture_path, registration)

    @asynccontextmanager
    async def lifespan(app):
        worker.start()
        try:
            yield
        finally:
            worker.close()

    app = FastAPI(title='Offline Traffic Anomaly API', version='1.0', lifespan=lifespan, debug=False,
                  responses={code: {'model': c.ErrorResponse} for code in (404, 409, 422, 500)})
    app.state.service = service

    def error_response(status, error):
        return JSONResponse(status_code=status, content=c.ErrorResponse(error=error).model_dump())

    @app.exception_handler(ApiError)
    async def api_error(request, exc):
        return error_response(exc.status, exc.error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(422, public_error('VALIDATION_ERROR'))

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(exc.status_code, public_error('NOT_FOUND' if exc.status_code == 404 else 'VALIDATION_ERROR'))

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        LOG.error('API failure; diagnostics are local only', exc_info=exc)
        return error_response(500, public_error('EXECUTION_FAILED'))

    @app.get('/api/v1/datasets', response_model=c.DatasetList)
    def datasets():
        return service.datasets

    @app.post('/api/v1/runs', status_code=202, response_model=c.RunAccepted)
    def submit(request: c.RunRequest):
        return service.submit(request)

    @app.get('/api/v1/runs/{run_id}', response_model=c.RunStatus)
    def status(run_id: c.Identifier):
        return repository.status(run_id)

    def points(run_id: c.Identifier, page: Annotated[int, Query(ge=1)] = 1,
               page_size: Annotated[int, Query(ge=1, le=1000)] = 100,
               start: c.UtcMinute | None = None, end: c.UtcMinute | None = None):
        return service.series(run_id, page, page_size, start, end)

    def alarms(run_id: c.Identifier, page: Annotated[int, Query(ge=1)] = 1,
               page_size: Annotated[int, Query(ge=1, le=1000)] = 100,
               start: c.UtcMinute | None = None, end: c.UtcMinute | None = None):
        return service.series(run_id, page, page_size, start, end, alarms=True)

    app.get('/api/v1/runs/{run_id}/series', response_model=c.SeriesPage)(points)
    app.get('/api/v1/runs/{run_id}/alarms', response_model=c.SeriesPage)(alarms)

    @app.get('/api/v1/runs/{run_id}/evaluation', response_model=c.Evaluation)
    def evaluation(run_id: c.Identifier):
        return service.saved(run_id).evaluation

    @app.get('/api/v1/runs/{run_id}/minutes/{timestamp}', response_model=c.MinuteDetail)
    def minute(run_id: c.Identifier, timestamp: c.UtcMinute):
        return service.detail(run_id, timestamp)

    @app.get('/api/v1/runs/{run_id}/exports/{kind}')
    def export(run_id: c.Identifier, kind: Literal['scores', 'metrics', 'config']):
        saved = service.saved(run_id)
        name = {'scores': 'scores.parquet', 'metrics': 'metrics.json', 'config': 'config.json'}[kind]
        media_type = 'application/vnd.apache.parquet' if kind == 'scores' else 'application/json'
        # Return bytes after validation. No response uses user-controlled paths.
        return Response(saved.files[name].read_bytes(), media_type=media_type,
                        headers={'Content-Disposition': f'attachment; filename="{run_id}-{name}"'})

    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description='SYNTHETIC_ONLY W2 development API')
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8101)
    parser.add_argument('--core-workspace', type=Path, help='Local SYNTHETIC_ONLY registry workspace')
    parser.add_argument('--core-config', type=Path, help='Local frozen RunConfig JSON')
    parser.add_argument('--config-id', default='smoke-v1')
    args = parser.parse_args()
    settings = Settings.model_validate_json(args.settings.read_bytes())
    if (args.core_workspace is None) != (args.core_config is None):
        parser.error('--core-workspace and --core-config must be provided together')
    registration = None
    if args.core_workspace is not None:
        from .core_executor import CoreRegistration
        registration = CoreRegistration(args.core_workspace, c.RunConfig.model_validate_json(args.core_config.read_bytes()), config_id=args.config_id)
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(settings, fixture_path=args.fixture, registration=registration), host='127.0.0.1', port=args.port, workers=1)


if __name__ == '__main__':
    main()
