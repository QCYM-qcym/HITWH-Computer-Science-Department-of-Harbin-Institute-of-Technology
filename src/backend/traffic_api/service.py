"""Resolve trusted registration IDs and expose saved task outputs."""
import json
import logging
from uuid import uuid4

from traffic_anomaly import contracts as c

from .artifacts import SavedArtifacts
from .schemas import ApiError, ExecutionFailure

LOG = logging.getLogger(__name__)


class Service:
    def __init__(self, repository, worker, fixture_path):
        self.repository, self.worker = repository, worker
        fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
        self.datasets = c.DatasetList.model_validate(next(row['body'] for row in fixture['responses'] if row['schema'] == 'DatasetList'))
        self.request = c.RunRequest.model_validate(fixture['request'])
        summary = c.RunSummary.model_validate(next(row['body'] for row in fixture['responses'] if row['schema'] == 'RunSummary'))
        self.config = summary.config
        if fixture['evidence_kind'] != 'SYNTHETIC_ONLY' or summary.evidence_kind != 'SYNTHETIC_ONLY':
            raise ValueError('W2-01 registry requires the synthetic fixture')

    def submit(self, request):
        dataset = next((d for d in self.datasets.items if d.dataset_id == request.dataset_id), None)
        if dataset is None:
            raise ApiError(404, 'NOT_FOUND')
        if not dataset.available:
            raise ApiError(422, 'VALIDATION_ERROR', 'DATASET_UNAVAILABLE')
        if request != self.request:
            raise ApiError(422, 'VALIDATION_ERROR')
        if not self.worker.available.is_set() or self.worker.thread is None or not self.worker.thread.is_alive():
            raise ApiError(500, 'EXECUTION_FAILED', 'WORKER_UNAVAILABLE')
        run_id = 'run-' + uuid4().hex
        self.repository.create(run_id, self.config, 'SYNTHETIC_ONLY')
        self.worker.wake.set()
        return c.RunAccepted(run_id=run_id, status='queued')

    def saved(self, run_id):
        task = self.repository.get(run_id)
        if task['status'] != 'succeeded':
            raise ApiError(409, 'RESULT_NOT_READY')
        try:
            result = c.RunResult.model_validate(task['result'])
            return SavedArtifacts(self.worker.output / run_id, result, task)
        except Exception as exc:
            LOG.exception('Saved artifact validation failed for %s', run_id)
            reason = exc.reason if isinstance(exc, ExecutionFailure) else ('RESULT_MISSING' if isinstance(exc, FileNotFoundError) else 'ARTIFACT_INVALID')
            raise ApiError(500, 'EXECUTION_FAILED', reason) from None

    def series(self, run_id, page, page_size, start, end, alarms=False):
        if start is not None and end is not None and start >= end:
            raise ApiError(422, 'VALIDATION_ERROR')
        saved = self.saved(run_id)
        rows = [row for row in saved.series if (start is None or row.timestamp >= start)
                and (end is None or row.timestamp < end) and (not alarms or row.valid and row.alarm)]
        offset = (page - 1) * page_size
        return c.SeriesPage(run_id=run_id, evidence_kind=saved.summary.evidence_kind,
                            items=rows[offset:offset + page_size], total=len(rows), page=page, page_size=page_size)

    def detail(self, run_id, timestamp):
        detail = self.saved(run_id).detail(timestamp)
        if detail is None:
            raise ApiError(404, 'NOT_FOUND')
        return detail
