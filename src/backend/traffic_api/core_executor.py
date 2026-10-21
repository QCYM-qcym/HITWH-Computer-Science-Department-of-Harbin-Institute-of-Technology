"""Trusted local registration for synthetic core integration, never a real-data gate."""
import json
from pathlib import Path

from pydantic import TypeAdapter
from traffic_anomaly import contracts as c
from traffic_anomaly.artifacts import safe_path
from traffic_anomaly.pipeline import execute_run, registered_input


class CoreRegistration:
    """Snapshot one audited synthetic input and one frozen config at startup.

    HTTP supplies identifiers only. Each task receives an independent copy of
    this small synthetic input, with no mutable registry or output sharing.
    """
    def __init__(self, workspace: Path, config: c.RunConfig, *, config_id: str):
        workspace = Path(workspace)
        config_id = TypeAdapter(c.Identifier).validate_python(config_id)
        registry = json.loads((workspace / 'registry.json').read_bytes())
        entry = registry['datasets'][config.dataset_id]
        if entry['evidence_kind'] != 'SYNTHETIC_ONLY':
            raise ValueError('core integration requires synthetic evidence; real Data Gate remains blocked')
        # Audit through the same core entry point. No model is constructed.
        _, _, schema, boundaries, _, _ = registered_input(config, workspace)
        self.source = safe_path(workspace, entry['source']).read_bytes()
        self.registry = json.dumps({'datasets': {config.dataset_id: {
            'source': 'synthetic.csv', 'schema': schema.model_dump(mode='json'),
            'evidence_kind': 'SYNTHETIC_ONLY',
            'splits': {config.split_id: boundaries.model_dump(mode='json')},
        }}}, allow_nan=False).encode('utf-8')
        self.config = config.model_copy(deep=True)
        self.request = c.RunRequest(dataset_id=config.dataset_id, split_id=config.split_id,
                                    method=config.method, config_id=config_id)
        self.datasets = c.DatasetList(items=[c.DatasetInfo(
            dataset_id=config.dataset_id, version=schema.dataset_version,
            evidence_kind='SYNTHETIC_ONLY', available=True, unavailable_reason=None,
            time_range=c.TimeRange(start=boundaries.train.start, end=boundaries.test.end),
            feature_count=134, split_ids=[config.split_id], config_ids=[config_id],
        )])

    def execute(self, config: c.RunConfig, workspace: Path) -> c.RunResult:
        if config != self.config:
            raise ValueError('configuration differs from trusted registration')
        workspace.mkdir(parents=True, exist_ok=False)
        (workspace / 'registry.json').write_bytes(self.registry)
        (workspace / 'synthetic.csv').write_bytes(self.source)
        return execute_run(config, workspace, run_id=workspace.name)
