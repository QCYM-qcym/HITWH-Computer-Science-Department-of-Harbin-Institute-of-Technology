"""Version 1 contracts. Importing this module never loads a training runtime."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path, PurePosixPath
import re
from typing import Annotated, Literal, Protocol

import numpy as np
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"
LABEL_NAMES = ("dos", "scan11", "scan44", "botnet", "blacklist", "udpscan", "sshscan", "spam")
Method = Literal["iforest", "current_ae", "history_ae"]
TaskState = Literal["queued", "running", "succeeded", "failed"]
EvidenceKind = Literal["SYNTHETIC_ONLY", "REAL_DATA"]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$")]
def _calendar_timestamp(value: str) -> str:
    datetime.fromisoformat(value)
    return value


UtcMinute = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00Z$"),
                      AfterValidator(_calendar_timestamp), Field(json_schema_extra={"format": "date-time"})]
UtcTimestamp = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"),
                         AfterValidator(_calendar_timestamp), Field(json_schema_extra={"format": "date-time"})]
Vector = Annotated[list[float], Field(min_length=134, max_length=134)]


def _time_axis(timestamps: np.ndarray) -> int:
    if not isinstance(timestamps, np.ndarray) or timestamps.dtype != np.dtype("datetime64[ns]"):
        raise ValueError("timestamps must be datetime64[ns]")
    if timestamps.ndim != 1 or np.isnat(timestamps).any():
        raise ValueError("invalid timestamp axis")
    if len(timestamps) > 1 and np.any(np.diff(timestamps) <= np.timedelta64(0, "ns")):
        raise ValueError("timestamps must be strictly increasing")
    if np.any(timestamps != timestamps.astype("datetime64[m]").astype("datetime64[ns]")):
        raise ValueError("timestamps must identify whole minutes")
    return len(timestamps)


def _feature_names(names: tuple[str, ...]) -> None:
    if len(names) != 134 or len(set(names)) != 134 or any(not n for n in names):
        raise ValueError("exactly 134 unique feature names required")
    for name in names:
        tokens = set(re.split(r"[^a-z0-9]+", name.lower()))
        if tokens & (set(LABEL_NAMES) | {"label", "labels", "attack", "target", "timestamp"}):
            raise ValueError("labels and metadata must not enter feature columns")


@dataclass(frozen=True)
class MinuteBatch:
    timestamps: np.ndarray
    features: np.ndarray
    feature_names: tuple[str, ...]
    row_valid: np.ndarray
    segment_ids: np.ndarray

    def __post_init__(self) -> None:
        n = _time_axis(self.timestamps)
        _feature_names(self.feature_names)
        for value, shape, dtype in ((self.features, (n, 134), np.float32),
                                    (self.row_valid, (n,), bool), (self.segment_ids, (n,), np.int64)):
            if not isinstance(value, np.ndarray) or value.shape != shape or value.dtype != np.dtype(dtype):
                raise ValueError(f"expected {shape} {np.dtype(dtype)}")
        if not np.isfinite(self.features[self.row_valid]).all():
            raise ValueError("valid rows must contain finite features")
        if (self.segment_ids < 0).any() or (np.diff(self.segment_ids) < 0).any():
            raise ValueError("segment ids must be nonnegative and nondecreasing")
        if n > 1:
            reset = (np.diff(self.timestamps) != np.timedelta64(1, "m")) | ~self.row_valid[:-1] | ~self.row_valid[1:]
            if np.any(reset & (np.diff(self.segment_ids) == 0)):
                raise ValueError("gaps and invalid inputs must reset segments")


@dataclass(frozen=True)
class LabelBatch:
    timestamps: np.ndarray
    labels: dict[str, np.ndarray]

    def __post_init__(self) -> None:
        n = _time_axis(self.timestamps)
        if set(self.labels) != set(LABEL_NAMES):
            raise ValueError("all eight labels must be stored separately")
        for values in self.labels.values():
            if values.shape != (n,) or values.dtype.kind not in "iu" or (values < 0).any():
                raise ValueError("labels must be nonnegative integer vectors")


@dataclass(frozen=True)
class HistoryBatch:
    timestamps: np.ndarray
    current: np.ndarray
    residual: np.ndarray
    valid: np.ndarray
    invalid_reason: tuple[str | None, ...]

    def __post_init__(self) -> None:
        n = _time_axis(self.timestamps)
        if self.valid.shape != (n,) or self.valid.dtype != bool or len(self.invalid_reason) != n:
            raise ValueError("history masks must align")
        for values in (self.current, self.residual):
            if values.shape != (n, 134) or values.dtype != np.float32 or not np.isfinite(values[self.valid]).all():
                raise ValueError("history channels must be finite float32(n,134) on valid rows")
        if any((reason is None) != bool(valid) for reason, valid in zip(self.invalid_reason, self.valid)):
            raise ValueError("invalid history needs a reason")
        if any(reason not in (None, "warmup", "gap", "invalid_input") for reason in self.invalid_reason):
            raise ValueError("unknown history invalid reason")


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_default=True)


class DatasetSchema(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Identifier
    dataset_version: str = Field(min_length=1)
    feature_names: tuple[str, ...]
    source_timezone: str = Field(min_length=1)
    time_basis_source: str = Field(min_length=1)
    label_names: tuple[str, ...] = LABEL_NAMES

    @model_validator(mode="after")
    def check_fields(self):
        _feature_names(self.feature_names)
        if self.label_names != LABEL_NAMES:
            raise ValueError("label order must match v1")
        return self


class TimeRange(ContractModel):
    start: UtcMinute
    end: UtcMinute

    @model_validator(mode="after")
    def ordered(self):
        start, end = (datetime.fromisoformat(t) for t in (self.start, self.end))
        if start >= end:
            raise ValueError("start must precede exclusive end")
        return self


class SplitBoundaries(ContractModel):
    split_id: Identifier
    train: TimeRange
    validation: TimeRange
    calibration: TimeRange
    test: TimeRange

    @model_validator(mode="after")
    def chronological(self):
        spans = (self.train, self.validation, self.calibration, self.test)
        if any(left.end > right.start for left, right in zip(spans, spans[1:])):
            raise ValueError("splits must not overlap or reverse time")
        return self


class PreprocessConfig(ContractModel):
    version: Literal["log1p-standard-v1"] = "log1p-standard-v1"
    epsilon: float = Field(default=1e-6, gt=0)
    quantile: Literal[0.99] = 0.99
    quantile_method: Literal["linear"] = "linear"


class PreprocessState(ContractModel):
    version: Literal["log1p-standard-v1"] = "log1p-standard-v1"
    feature_names: tuple[str, ...]
    mean: Vector
    scale: Vector
    n_samples_seen: int = Field(gt=0)

    @model_validator(mode="after")
    def aligned(self):
        _feature_names(self.feature_names)
        if any(value <= 0 for value in self.scale):
            raise ValueError("scales must be strictly positive")
        return self


class ModelConfig(ContractModel):
    hidden_widths: list[int] = Field(default_factory=lambda: [64, 16], min_length=1)
    epochs: int = Field(default=10, gt=0)
    batch_size: int = Field(default=128, gt=0)
    learning_rate: float = Field(default=0.001, gt=0)
    n_estimators: int = Field(default=100, gt=0)
    max_samples: int = Field(default=256, gt=0)

    @model_validator(mode="after")
    def widths_positive(self):
        if any(width <= 0 for width in self.hidden_widths):
            raise ValueError("hidden widths must be positive")
        return self


class RunConfig(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Identifier
    split_id: Identifier
    method: Method
    window_minutes: int = Field(default=15, gt=0)
    seed: int = Field(default=42, ge=0)
    preprocess: PreprocessConfig = Field(default_factory=PreprocessConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)


class RunResult(ContractModel):
    run_id: Identifier
    manifest_path: str
    summary_path: str
    scores_path: str

    @model_validator(mode="after")
    def relative_artifacts(self):
        for value in (self.manifest_path, self.summary_path, self.scores_path):
            if not value or "\\" in value or ":" in value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
                raise ValueError("artifact paths must be workspace-relative POSIX paths")
        return self


class AuditReport(ContractModel):
    dataset_id: Identifier
    passed: bool
    evidence_kind: EvidenceKind
    row_count: int = Field(ge=0)
    findings: list[str]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Detector(Protocol):
    def fit(self, x_train: np.ndarray, x_val: np.ndarray | None = None) -> None: ...
    def score(self, x: np.ndarray) -> np.ndarray: ...
    def save(self, directory: Path) -> None: ...
    @classmethod
    def load(cls, directory: Path) -> Detector: ...


class CorePipeline(Protocol):
    def load_minutes(self, source: Path, schema: DatasetSchema) -> MinuteBatch: ...
    def load_labels(self, source: Path, schema: DatasetSchema) -> LabelBatch: ...
    def audit_dataset(self, source: Path, schema: DatasetSchema) -> AuditReport: ...
    def split_minutes(self, batch: MinuteBatch, boundaries: SplitBoundaries) -> dict[str, MinuteBatch]: ...
    def build_history(self, batch: MinuteBatch, window: int, epsilon: float) -> HistoryBatch: ...
    def calibrate(self, scores: np.ndarray, quantile: float = 0.99) -> float: ...
    def execute_run(self, config: RunConfig, workspace: Path) -> RunResult: ...


def can_transition(previous: TaskState, following: TaskState) -> bool:
    return following in {"queued": {"running", "failed"}, "running": {"succeeded", "failed"}}.get(previous, set())


class RunRequest(ContractModel):
    dataset_id: Identifier
    split_id: Identifier
    method: Method
    config_id: Identifier


class ErrorDetail(ContractModel):
    code: Literal["RUN_BUSY", "WORKER_INTERRUPTED", "NOT_FOUND", "VALIDATION_ERROR", "RESULT_NOT_READY", "EXECUTION_FAILED"]
    message: str = Field(min_length=1)
    details: list[str] = Field(default_factory=list)


class ErrorResponse(ContractModel):
    error: ErrorDetail


class RunAccepted(ContractModel):
    run_id: Identifier
    status: Literal["queued"]


class RunStatus(ContractModel):
    run_id: Identifier
    status: TaskState
    evidence_kind: EvidenceKind
    created_at: UtcTimestamp
    started_at: UtcTimestamp | None
    finished_at: UtcTimestamp | None
    config: RunConfig
    error: ErrorDetail | None

    @model_validator(mode="after")
    def lifecycle(self):
        if (self.status == "failed") != (self.error is not None):
            raise ValueError("only failed tasks carry errors")
        if (self.status in ("failed", "succeeded")) != (self.finished_at is not None):
            raise ValueError("terminal state requires finish time")
        if self.status in ("running", "succeeded") and self.started_at is None:
            raise ValueError("execution requires start time")
        if self.status == "queued" and self.started_at is not None:
            raise ValueError("queued task cannot have started")
        timeline = [datetime.fromisoformat(t) for t in (self.created_at, self.started_at, self.finished_at) if t is not None]
        if any(a > b for a, b in zip(timeline, timeline[1:])):
            raise ValueError("task timestamps must follow lifecycle order")
        return self


class DatasetInfo(ContractModel):
    dataset_id: Identifier
    version: str
    evidence_kind: EvidenceKind
    available: bool
    unavailable_reason: str | None
    time_range: TimeRange | None
    feature_count: Literal[134]
    split_ids: list[Identifier]
    config_ids: list[Identifier]


class DatasetList(ContractModel):
    items: list[DatasetInfo]


class SeriesPoint(ContractModel):
    timestamp: UtcMinute
    score: float | None
    threshold: float | None
    alarm: bool | None
    valid: bool
    invalid_reason: Literal["warmup", "gap", "invalid_input", "not_common", "nonfinite_score"] | None
    flow_count: float | None = Field(ge=0)

    @model_validator(mode="after")
    def score_semantics(self):
        if self.valid:
            if self.score is None or self.threshold is None or self.alarm is None or self.invalid_reason is not None:
                raise ValueError("valid score needs finite values and no invalid reason")
            if self.alarm != (self.score > self.threshold):
                raise ValueError("alarm must be score strictly above threshold")
        elif self.invalid_reason is None or any(v is not None for v in (self.score, self.threshold, self.alarm)):
            raise ValueError("invalid score must use null values and an explicit reason")
        return self


class SeriesPage(ContractModel):
    run_id: Identifier
    evidence_kind: EvidenceKind
    items: list[SeriesPoint]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=1000)


class Coverage(ContractModel):
    eligible: int = Field(ge=0)
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_count(self):
        if self.eligible > self.total:
            raise ValueError("eligible count exceeds total")
        return self


class Metrics(ContractModel):
    tp: int = Field(ge=0)
    fp: int = Field(ge=0)
    tn: int = Field(ge=0)
    fn: int = Field(ge=0)
    precision: float | None = Field(ge=0, le=1)
    recall: float | None = Field(ge=0, le=1)
    f1: float | None = Field(ge=0, le=1)
    fpr: float | None = Field(ge=0, le=1)
    undefined_reasons: list[str]

    @model_validator(mode="after")
    def check_denominators(self):
        ratios = {"precision": (self.tp, self.tp + self.fp), "recall": (self.tp, self.tp + self.fn),
                  "f1": (2 * self.tp, 2 * self.tp + self.fp + self.fn), "fpr": (self.fp, self.fp + self.tn)}
        undefined = []
        for name, (numerator, denominator) in ratios.items():
            value = getattr(self, name)
            if denominator == 0:
                undefined.append(name)
                if value is not None:
                    raise ValueError(f"{name} has zero denominator and must be null")
            elif value is None or not math.isclose(value, numerator / denominator, rel_tol=1e-9, abs_tol=1e-12):
                raise ValueError(f"{name} disagrees with confusion counts")
        if sorted(self.undefined_reasons) != sorted(undefined):
            raise ValueError("undefined_reasons must name exactly the zero-denominator metrics")
        return self


class EvaluationInterval(TimeRange):
    kind: Literal["false_positive", "missed_attack"]
    minute_count: int = Field(gt=0)


class Evaluation(ContractModel):
    run_id: Identifier
    evidence_kind: EvidenceKind
    available: bool
    reason: str | None
    metrics: Metrics | None
    normal_coverage: Coverage
    attack_coverage: Coverage
    excluded_attack_minutes: int = Field(ge=0)
    background_only_minutes: int = Field(ge=0)
    intervals: list[EvaluationInterval]
    high_load_metrics: Metrics | None
    high_load_unavailable_reason: str | None

    @model_validator(mode="after")
    def availability(self):
        if self.available != (self.metrics is not None) or (not self.available and not self.reason):
            raise ValueError("unavailable evaluation needs reason and null metrics")
        if self.high_load_metrics is None and not self.high_load_unavailable_reason:
            raise ValueError("unavailable high-load group needs reason")
        if self.metrics is not None:
            if self.normal_coverage.eligible != self.metrics.tn + self.metrics.fp or self.attack_coverage.eligible != self.metrics.tp + self.metrics.fn:
                raise ValueError("coverage disagrees with confusion counts")
            if self.excluded_attack_minutes != self.attack_coverage.total - self.attack_coverage.eligible:
                raise ValueError("excluded attack count disagrees with coverage")
        return self


class Channels(ContractModel):
    current: Vector | None
    history_residual: Vector | None
    reconstruction_error_current: Vector | None
    reconstruction_error_history: Vector | None


class ChannelRow(Channels):
    timestamp: UtcMinute


class LabelRow(ContractModel):
    timestamp: UtcMinute
    dos: int = Field(ge=0)
    scan11: int = Field(ge=0)
    scan44: int = Field(ge=0)
    botnet: int = Field(ge=0)
    blacklist: int = Field(ge=0)
    udpscan: int = Field(ge=0)
    sshscan: int = Field(ge=0)
    spam: int = Field(ge=0)


class MinuteDetail(Channels):
    run_id: Identifier
    evidence_kind: EvidenceKind
    point: SeriesPoint
    feature_names: list[str] = Field(min_length=134, max_length=134)
    labels: dict[str, int] | None

    @model_validator(mode="after")
    def feature_alignment(self):
        _feature_names(tuple(self.feature_names))
        if self.labels is not None and (set(self.labels) != set(LABEL_NAMES) or any(v < 0 for v in self.labels.values())):
            raise ValueError("detail labels must contain eight nonnegative counts")
        return self


class ArtifactFile(ContractModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def relative_path(self):
        RunResult(run_id="check", manifest_path=self.path, summary_path=self.path, scores_path=self.path)
        if self.path != str(PurePosixPath(self.path)):
            raise ValueError("artifact paths must be canonical")
        if self.path == "manifest.json":
            raise ValueError("manifest cannot hash itself")
        return self


class Manifest(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    evidence_kind: EvidenceKind
    config: RunConfig
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    dataset_version: str
    feature_version: str
    split_version: str
    seed: int = Field(ge=0)
    dependency_lock_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: list[ArtifactFile] = Field(min_length=1)

    @model_validator(mode="after")
    def complete(self):
        paths = [entry.path for entry in self.files]
        required = {"summary.json", "scores.parquet", "metrics.json", "config.json", "channels.parquet",
                    "model/metadata.json", "model/preprocess.json"}
        if len(set(paths)) != len(paths) or not required.issubset(paths):
            raise ValueError("manifest must list unique paths and all required artifacts")
        if not any(path.startswith("model/") and path not in required for path in paths):
            raise ValueError("manifest must include a saved detector payload")
        if self.seed != self.config.seed:
            raise ValueError("manifest seed must match config")
        return self


class ModelMetadata(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    method: Method
    input_width: Literal[134, 268]
    feature_names: tuple[str, ...]
    preprocess_version: Literal["log1p-standard-v1"]
    threshold: float
    parameter_count: int = Field(ge=0)
    payload: ArtifactFile

    @model_validator(mode="after")
    def shape(self):
        _feature_names(self.feature_names)
        if self.input_width != (268 if self.method == "history_ae" else 134):
            raise ValueError("method and input width disagree")
        if not self.payload.path.startswith("model/"):
            raise ValueError("detector payload must be in model/")
        return self


class RunSummary(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    evidence_kind: EvidenceKind
    config: RunConfig
    feature_names: tuple[str, ...]
    row_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    peak_memory_bytes: int = Field(ge=0)
    labels_available: bool

    @model_validator(mode="after")
    def aligned(self):
        _feature_names(self.feature_names)
        if self.valid_count > self.row_count:
            raise ValueError("valid rows exceed total")
        return self
