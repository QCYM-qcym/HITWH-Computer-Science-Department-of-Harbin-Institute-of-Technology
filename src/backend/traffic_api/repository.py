"""SQLite task state: one active slot and guarded, durable transitions."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from traffic_anomaly.contracts import RunStatus, can_transition

from .schemas import ApiError, public_error


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class Repository:
    def __init__(self, database: Path):
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, status TEXT NOT NULL,
                evidence_kind TEXT NOT NULL, created_at TEXT NOT NULL,
                started_at TEXT, finished_at TEXT, config TEXT NOT NULL,
                error TEXT, result TEXT,
                CHECK(status IN ('queued','running','succeeded','failed')))''')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_active ON runs((1)) WHERE status IN ('queued','running')")

    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, run_id, config, evidence_kind):
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM runs WHERE status IN ('queued','running')").fetchone():
                raise ApiError(409, 'RUN_BUSY')
            db.execute('INSERT INTO runs(run_id,status,evidence_kind,created_at,config) VALUES (?,?,?,?,?)',
                       (run_id, 'queued', evidence_kind, now(), config.model_dump_json()))

    def get(self, run_id):
        with closing(self.connect()) as db:
            row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
        if row is None:
            raise ApiError(404, 'NOT_FOUND')
        value = dict(row)
        for key in ('config', 'error', 'result'):
            value[key] = json.loads(value[key]) if value[key] is not None else None
        return value

    def status(self, run_id):
        value = self.get(run_id)
        value.pop('result')
        return RunStatus.model_validate(value)

    def queued(self):
        with closing(self.connect()) as db:
            return [r[0] for r in db.execute("SELECT run_id FROM runs WHERE status='queued' ORDER BY created_at,run_id")]

    def transition(self, run_id, following, *, error=None, result=None):
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
            if row is None:
                raise ApiError(404, 'NOT_FOUND')
            if not can_transition(row['status'], following):
                raise ValueError('invalid task transition')
            values = dict(row)
            values.pop('result')
            values['config'] = json.loads(values['config'])
            values['status'] = following
            values['error'] = error.model_dump() if error else None
            stamp = max(now(), row['created_at'], row['started_at'] or row['created_at'])
            if following == 'running':
                values['started_at'] = stamp
            if following in ('failed', 'succeeded'):
                values['finished_at'] = stamp
            state = RunStatus.model_validate(values)
            db.execute('UPDATE runs SET status=?,started_at=?,finished_at=?,error=?,result=? WHERE run_id=?',
                       (state.status, state.started_at, state.finished_at,
                        state.error.model_dump_json() if state.error else None,
                        result.model_dump_json() if result else None, run_id))

    def recover(self):
        # Called only while holding the exclusive service ownership lock.
        with closing(self.connect()) as db:
            interrupted = [r[0] for r in db.execute("SELECT run_id FROM runs WHERE status='running'")]
        for run_id in interrupted:
            self.transition(run_id, 'failed', error=public_error('WORKER_INTERRUPTED'))
