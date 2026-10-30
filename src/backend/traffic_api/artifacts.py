"""Read saved outputs and verify evaluation consistency without running models."""
from hashlib import sha256
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from traffic_anomaly import contracts as c
from traffic_anomaly.evaluation.metrics import evaluate

from .schemas import ExecutionFailure


SCORE_SCHEMA = pa.schema([
    ('timestamp', pa.timestamp('ns', tz='UTC')), ('score', pa.float64()),
    ('threshold', pa.float64()), ('alarm', pa.bool_()), ('valid', pa.bool_()),
    ('invalid_reason', pa.string()), ('flow_count', pa.float64()),
])
CHANNEL_SCHEMA = pa.schema([('timestamp', pa.timestamp('ns', tz='UTC'))] + [
    (key, pa.list_(pa.float32())) for key in c.Channels.model_fields
])
LABEL_SCHEMA = pa.schema([('timestamp', pa.timestamp('ns', tz='UTC'))] + [
    (key, pa.int64()) for key in c.LABEL_NAMES
])


def digest(path):
    checksum = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def safe_path(root, relative):
    # Resolve symlinks/junctions as well as lexical traversal before any read.
    if not relative or relative != str(PurePosixPath(relative)) or '\\' in relative or ':' in relative:
        raise ValueError('noncanonical artifact path')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or '..' in PurePosixPath(relative).parts:
        raise ValueError('artifact outside workspace')
    return path


def read_json(path, model):
    return model.model_validate_json(path.read_bytes())


def read_rows(path, schema, model):
    table = pq.read_table(path)
    if not table.schema.equals(schema, check_metadata=False):
        raise ValueError('artifact column types differ from contract')
    rows = []
    previous = None
    # Read UTC nanoseconds directly: Windows does not bundle an IANA timezone
    # database, and these frozen UTC timestamps do not require one.
    timestamps = table['timestamp'].cast(pa.int64()).to_pylist()
    for timestamp, value in zip(timestamps, table.drop(['timestamp']).to_pylist()):
        if timestamp is None or timestamp % 60_000_000_000:
            raise ValueError('invalid artifact timestamp')
        value['timestamp'] = datetime.fromtimestamp(timestamp // 1_000_000_000, timezone.utc).isoformat().replace('+00:00', 'Z')
        row = model.model_validate(value)
        if previous is not None and previous >= row.timestamp:
            raise ValueError('artifact timestamps not unique and ordered')
        previous = row.timestamp
        rows.append(row)
    return rows


def verify_saved_evaluation(series, label_rows, labels_available, saved):
    """Check complete stored axes; keep the original response and reason text.

    Check six aggregates and the exact interval list from the existing producer.
    High-load semantics are outside this check; never repair the stored result.
    """
    timestamps = lambda rows: np.array([row.timestamp[:-1] for row in rows], dtype='datetime64[ns]')
    labels = c.LabelBatch(timestamps(label_rows), {
        key: np.array([getattr(row, key) for row in label_rows], dtype=np.int64)
        for key in c.LABEL_NAMES
    }) if labels_available else None
    computed = evaluate(saved.run_id, saved.evidence_kind, timestamps(series),
        np.array([row.valid for row in series], dtype=bool),
        np.array([row.alarm is True for row in series], dtype=bool), labels)
    for field in ('available', 'metrics', 'normal_coverage', 'attack_coverage',
                  'excluded_attack_minutes', 'background_only_minutes'):
        if getattr(computed, field) != getattr(saved, field):
            raise ValueError('saved evaluation aggregates differ from scores and labels')
    if computed.intervals != saved.intervals:
        raise ValueError('saved evaluation intervals differ from scores and labels')


class SavedArtifacts:
    def __init__(self, workspace: Path, result: c.RunResult, task):
        self.root = safe_path(workspace, result.manifest_path).parent
        if result.run_id != task['run_id']:
            raise ValueError('executor result identity mismatch')
        manifest = read_json(safe_path(workspace, result.manifest_path), c.Manifest)
        config = c.RunConfig.model_validate(task['config'])
        if manifest.run_id != result.run_id or manifest.config != config or manifest.evidence_kind != task['evidence_kind']:
            raise ValueError('manifest identity mismatch')
        self.files = {}
        for entry in manifest.files:
            path = safe_path(self.root, entry.path)
            if not path.is_file():
                raise ExecutionFailure('MODEL_NOT_FOUND' if entry.path.startswith('model/') else 'RESULT_MISSING')
            if digest(path) != entry.sha256:
                raise ValueError('artifact checksum mismatch')
            self.files[entry.path] = path
        if safe_path(workspace, result.summary_path) != self.files['summary.json'] or safe_path(workspace, result.scores_path) != self.files['scores.parquet']:
            raise ValueError('result files do not match manifest')
        self.summary = read_json(self.files['summary.json'], c.RunSummary)
        saved_config = read_json(self.files['config.json'], c.RunConfig)
        self.evaluation = read_json(self.files['metrics.json'], c.Evaluation)
        metadata = read_json(self.files['model/metadata.json'], c.ModelMetadata)
        preprocess = read_json(self.files['model/preprocess.json'], c.PreprocessState)
        c.validate_model_compatibility(metadata, self.summary.feature_names, preprocess, config)
        payload = next((entry for entry in manifest.files if entry.path == metadata.payload.path), None)
        if payload != metadata.payload:
            raise ValueError('model payload not covered by manifest')
        if self.summary.config != config or saved_config != config:
            raise ValueError('saved config mismatch')
        for obj in (self.summary, self.evaluation):
            if obj.run_id != result.run_id or obj.evidence_kind != manifest.evidence_kind:
                raise ValueError('saved identity mismatch')
        self.series = read_rows(self.files['scores.parquet'], SCORE_SCHEMA, c.SeriesPoint)
        self.channels = read_rows(self.files['channels.parquet'], CHANNEL_SCHEMA, c.ChannelRow)
        self.labels = read_rows(self.files['labels.parquet'], LABEL_SCHEMA, c.LabelRow) if 'labels.parquet' in self.files else []
        if self.summary.labels_available != ('labels.parquet' in self.files):
            raise ValueError('label availability mismatch')
        if not self.summary.labels_available and self.evaluation.available:
            raise ValueError('evaluation without independent labels')
        if self.summary.row_count != len(self.series) or self.summary.valid_count != sum(row.valid for row in self.series):
            raise ValueError('saved row counts mismatch')
        if [row.timestamp for row in self.series] != [row.timestamp for row in self.channels]:
            raise ValueError('channel time axis mismatch')
        for point, channel in zip(self.series, self.channels):
            if point.valid and point.threshold != metadata.threshold:
                raise ValueError('saved threshold mismatch')
            if config.method == 'iforest' and (channel.reconstruction_error_current is not None or channel.reconstruction_error_history is not None):
                raise ValueError('IF cannot provide reconstruction channels')
        verify_saved_evaluation(self.series, self.labels, self.summary.labels_available, self.evaluation)
        self.config = saved_config

    def detail(self, timestamp):
        index = next((i for i, row in enumerate(self.series) if row.timestamp == timestamp), None)
        if index is None:
            return None
        label = next((row for row in self.labels if row.timestamp == timestamp), None)
        return c.MinuteDetail(
            run_id=self.summary.run_id, evidence_kind=self.summary.evidence_kind,
            point=self.series[index], feature_names=list(self.summary.feature_names),
            **self.channels[index].model_dump(exclude={'timestamp'}),
            labels=label.model_dump(exclude={'timestamp'}) if label else None,
        )
