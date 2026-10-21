"""python -m traffic_anomaly.cli: local trusted workspace entry points."""
import argparse
import json
from pathlib import Path
import sys
from .contracts import RunConfig

def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline minute detection; real Data Gate remains blocked in this release")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo"); demo.add_argument("--workspace", type=Path, required=True)
    for command in ("run", "score"):
        p = commands.add_parser(command)
        p.add_argument("--config", type=Path, required=True)
        p.add_argument("--workspace", type=Path, required=True)
        p.add_argument("--run-id", help="Optional execution identifier; existing identifiers are refused")
        if command == "score": p.add_argument("--model", type=Path, required=True)
    verify = commands.add_parser("verify"); verify.add_argument("--run", type=Path, required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--source", type=Path, required=True); audit.add_argument("--schema", type=Path, required=True)
    audit.add_argument("--report", type=Path, required=True)
    provider = commands.add_parser("audit-provider")
    provider.add_argument("--mat", type=Path, required=True); provider.add_argument("--csv-root", type=Path)
    provider.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from .synthetic import create_demo_workspace
            create_demo_workspace(args.workspace)
            output = {"evidence_kind": "SYNTHETIC_ONLY", "registry": "registry.json"}
        elif args.command in ("run", "score"):
            from .pipeline import execute_run, score_run
            config = RunConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
            output = (execute_run(config, args.workspace, run_id=args.run_id) if args.command == "run" else score_run(config, args.workspace, args.model, run_id=args.run_id)).model_dump(mode="json")
        elif args.command == "verify":
            from .artifacts import verify_run
            manifest, summary = verify_run(args.run)
            output = {"run_id": manifest.run_id, "evidence_kind": manifest.evidence_kind, "row_count": summary.row_count, "valid_count": summary.valid_count}
        elif args.command == "audit-provider":
            from .data.provider import profile_provider
            from .artifacts import write_json
            output = profile_provider(args.mat, args.csv_root)
            args.report.parent.mkdir(parents=True, exist_ok=True); write_json(args.report, output)
            print(json.dumps(output, ensure_ascii=False)); return 0 if output["gate_passed"] else 2
        else:
            from .contracts import DatasetSchema
            from .data.audit import audit_dataset
            from .artifacts import write_json
            schema = DatasetSchema.model_validate_json(args.schema.read_text(encoding="utf-8"))
            report = audit_dataset(args.source, schema)
            args.report.parent.mkdir(parents=True, exist_ok=True); write_json(args.report, report)
            print(report.model_dump_json()); return 0 if report.passed else 2
        print(json.dumps(output, ensure_ascii=False)); return 0
    except (ValueError, OSError, KeyError) as exc:
        # CLI is local; API consumers must keep these diagnostics in local logs.
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr); return 1

if __name__ == "__main__":
    raise SystemExit(main())
