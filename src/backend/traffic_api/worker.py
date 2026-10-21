"""One task worker and an explicitly synthetic fixture executor."""
from datetime import datetime
import json
import logging
from pathlib import Path
from threading import Event, Thread
from typing import Protocol

from filelock import FileLock
import pyarrow as pa
import pyarrow.parquet as pq
from traffic_anomaly import contracts as c

from .artifacts import CHANNEL_SCHEMA, LABEL_SCHEMA, SCORE_SCHEMA, SavedArtifacts, digest
from .schemas import ExecutionFailure, public_error

LOG = logging.getLogger(__name__)


class RunExecutor(Protocol):
    def execute(self, config: c.RunConfig, workspace: Path) -> c.RunResult: ...


class Worker:
    def __init__(self, repository, executor, output):
        self.repository, self.executor, self.output = repository, executor, output
        self.lock = FileLock(str(repository.database.resolve()) + '.worker.lock', timeout=0)
        self.wake = Event()
        self.stop = Event()
        self.thread = None
        self.available = Event()
        self.pending_failure = None

    def start(self):
        self.lock.acquire()
        try:
            self.repository.recover()
            self.output.mkdir(parents=True, exist_ok=True)
            self.available.set()
            self.thread = Thread(target=self.run, name='traffic-task-worker', daemon=True)
            self.thread.start()
        except BaseException:
            self.lock.release()
            raise

    def close(self):
        self.available.clear()
        self.stop.set()
        self.wake.set()
        # Keep ownership until execution exits; another service must never
        # recover a task which a still-running thread could later complete.
        if self.thread:
            self.thread.join()
        self.lock.release()

    def run(self):
        while not self.stop.is_set():
            self.wake.clear()
            try:
                self.persist_failure()
                queued = self.repository.queued()
                self.available.set()
                for run_id in queued:
                    if self.stop.is_set():
                        return
                    try:
                        self.repository.transition(run_id, 'running')
                        task = self.repository.get(run_id)
                        workspace = self.output / run_id
                        result = c.RunResult.model_validate(self.executor.execute(c.RunConfig.model_validate(task['config']), workspace))
                        SavedArtifacts(workspace, result, task)
                        self.repository.transition(run_id, 'succeeded', result=result)
                    except BaseException as exc:
                        # An executor may exit its thread with SystemExit. The
                        # HTTP service must stay able to report failure/retry.
                        LOG.exception('Task failed; detailed diagnostics are local only: %s', run_id)
                        reason = exc.reason if isinstance(exc, ExecutionFailure) else ('RESULT_MISSING' if isinstance(exc, FileNotFoundError) else None)
                        self.pending_failure = (run_id, public_error('EXECUTION_FAILED', reason))
                        self.persist_failure()
            except BaseException:
                self.available.clear()
                LOG.exception('Worker storage unavailable; retrying local persistence')
            self.wake.wait(0.25)

    def persist_failure(self):
        if self.pending_failure is not None:
            run_id, error = self.pending_failure
            if self.repository.get(run_id)['status'] in ('queued', 'running'):
                self.repository.transition(run_id, 'failed', error=error)
            self.pending_failure = None


class FakeExecutor:
    """Copy W0's hand-written values into saved artifacts; never fit a model.

    This executor is intentionally restricted to the fixture's registered
    dataset/config/method. It must not generate fake AE research results.
    """
    def __init__(self, fixture_path: Path):
        self.fixture = json.loads(fixture_path.read_text(encoding='utf-8'))

    def execute(self, config, workspace):
        run_id = workspace.name
        responses = self.fixture['responses']
        def sample(name):
            return next(row['body'] for row in responses if row['schema'] == name)
        def write(name, value):
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        def parquet(name, rows, schema):
            rows = [dict(row, timestamp=datetime.fromisoformat(row['timestamp'])) for row in rows]
            pq.write_table(pa.Table.from_pylist(rows, schema=schema), staging / name)

        staging = workspace.with_name('.' + run_id + '.pending')
        staging.mkdir(parents=True)
        scores = sample('SeriesPage')['items']
        summary = c.RunSummary.model_validate(sample('RunSummary')).model_copy(update={
            'run_id': run_id, 'config': config,
        })
        write('summary.json', summary.model_dump())
        write('metrics.json', sample('Evaluation') | {'run_id': run_id})
        write('config.json', config.model_dump())
        parquet('scores.parquet', scores, SCORE_SCHEMA)
        detail = sample('MinuteDetail')
        channels = [{key: detail[key] for key in c.Channels.model_fields} | {'timestamp': row['timestamp']} for row in scores]
        parquet('channels.parquet', channels, CHANNEL_SCHEMA)
        core = self.fixture['core_sample']
        labels = [dict(zip(c.LABEL_NAMES, [core['labels'][key][i] for key in c.LABEL_NAMES]), timestamp=timestamp)
                  for i, timestamp in enumerate(core['timestamps'])]
        if summary.labels_available:
            parquet('labels.parquet', labels, LABEL_SCHEMA)
        write('model/preprocess.json', sample('PreprocessState'))
        # Text payload is only a synthetic placeholder, never a trained model.
        write('model/fixture-payload.json', {'evidence_kind': 'SYNTHETIC_ONLY'})
        metadata = sample('ModelMetadata') | {
            'payload': {'path': 'model/fixture-payload.json', 'sha256': digest(staging / 'model/fixture-payload.json')},
        }
        write('model/metadata.json', metadata)
        files = [{'path': path.relative_to(staging).as_posix(), 'sha256': digest(path)}
                 for path in sorted(staging.rglob('*')) if path.is_file()]
        write('manifest.json', c.Manifest(
            run_id=run_id, evidence_kind='SYNTHETIC_ONLY', config=config,
            code_commit='74f163bf69559f02ad70ae1d5bb730e1f10d15bf',
            dataset_version='manual-v1', feature_version='synthetic-v1', split_version='split-v1',
            seed=config.seed, dependency_lock_sha256=digest(Path(__file__).resolve().parents[1] / 'requirements-lock.txt'),
            files=files,
        ).model_dump())
        result = c.RunResult(run_id=run_id, manifest_path='manifest.json', summary_path='summary.json', scores_path='scores.parquet')
        SavedArtifacts(staging, result, {'run_id': run_id, 'config': config.model_dump(), 'evidence_kind': 'SYNTHETIC_ONLY'})
        staging.rename(workspace)
        return result
