"""Private service settings; all public types are imported from W0."""
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from traffic_anomaly.contracts import ErrorDetail


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    database: Path
    output: Path


MESSAGES = {
    'RUN_BUSY': 'An active task already exists.',
    'WORKER_INTERRUPTED': 'The worker stopped before task completion.',
    'NOT_FOUND': 'The requested resource was not found.',
    'VALIDATION_ERROR': 'The request is invalid for the registered configuration.',
    'RESULT_NOT_READY': 'The task has no completed result.',
    'EXECUTION_FAILED': 'Task execution or artifact validation failed.',
}


REASONS = {'DATASET_UNAVAILABLE', 'MODEL_NOT_FOUND', 'RESULT_MISSING', 'ARTIFACT_INVALID', 'WORKER_UNAVAILABLE'}


class ExecutionFailure(Exception):
    """Trusted internal failure category; never constructed from exception text."""
    def __init__(self, reason):
        if reason not in REASONS:
            raise ValueError('unknown internal failure category')
        self.reason = reason
        super().__init__(reason)


def public_error(code, reason=None):
    if reason is not None and reason not in REASONS:
        raise ValueError('unknown public failure category')
    return ErrorDetail(code=code, message=MESSAGES[code], details=[reason] if reason else [])


class ApiError(Exception):
    def __init__(self, status, code, reason=None):
        self.status = status
        self.error = public_error(code, reason)
        super().__init__(code)
