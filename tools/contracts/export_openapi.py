"""Generate OpenAPI from shared contracts; --check detects schema drift."""
import argparse
import json
from pathlib import Path
import sys

import yaml
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/core"))
from traffic_anomaly import contracts as c


def document():
    fixture = json.loads((ROOT / "tests/fixtures/contracts-v1.json").read_text(encoding="utf-8"))
    schemas = {}
    for model in (c.RunRequest, c.RunAccepted, c.RunStatus, c.DatasetList, c.SeriesPage,
                  c.Evaluation, c.MinuteDetail, c.ErrorResponse, c.Manifest, c.RunResult,
                  c.DatasetSchema, c.SplitBoundaries, c.RunSummary, c.ChannelRow, c.LabelRow, c.ModelMetadata,
                  c.PreprocessState):
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        schemas[model.__name__] = schema

    def response(name, error_code=None, alarms_only=False):
        samples = [sample["body"] for sample in fixture["responses"] if sample["schema"] == name]
        if error_code is not None:
            samples = [body for body in samples if body["error"]["code"] == error_code]
        if alarms_only:
            samples = [body | {"items": [row for row in body["items"] if row["valid"] and row["alarm"] is True],
                               "total": sum(row["valid"] and row["alarm"] is True for row in body["items"])}
                       for body in samples]
        media = {"schema": {"$ref": f"#/components/schemas/{name}"}}
        if samples:
            media["examples"] = {f"synthetic_{index + 1}": {"summary": "SYNTHETIC_ONLY", "value": body}
                                 for index, body in enumerate(samples)}
        return {"description": name, "content": {"application/json": media}}

    def errors(submit=False):
        codes = {404: "NOT_FOUND", 409: "RUN_BUSY" if submit else "RESULT_NOT_READY",
                 422: "VALIDATION_ERROR", 500: "EXECUTION_FAILED"}
        return {str(status): response("ErrorResponse", code) for status, code in codes.items()}

    def parameter(name, where, schema, required=False):
        return {"name": name, "in": where, "required": required, "schema": schema}

    run_id = parameter("run_id", "path", {"type": "string", "pattern": "^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$"}, True)
    minute_schema = TypeAdapter(c.UtcMinute).json_schema()
    paging = [parameter("page", "query", {"type": "integer", "minimum": 1, "default": 1}),
              parameter("page_size", "query", {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100}),
              parameter("start", "query", minute_schema),
              parameter("end", "query", minute_schema)]
    paths = {}
    routes = [("/datasets", "get", "DatasetList"), ("/runs", "post", "RunAccepted"),
              ("/runs/{run_id}", "get", "RunStatus"),
              ("/runs/{run_id}/series", "get", "SeriesPage"),
              ("/runs/{run_id}/alarms", "get", "SeriesPage"),
              ("/runs/{run_id}/evaluation", "get", "Evaluation"),
              ("/runs/{run_id}/minutes/{timestamp}", "get", "MinuteDetail")]
    for path, method, model in routes:
        operation = {"operationId": model + ("Alarms" if path.endswith("alarms") else ""),
                     "responses": {"202" if method == "post" else "200": response(model, alarms_only=path.endswith("/alarms")),
                                   **errors(submit=method == "post")}}
        parameters = [run_id] if "{run_id}" in path else []
        if model == "SeriesPage":
            parameters += paging
        if "{timestamp}" in path:
            parameters += [parameter("timestamp", "path", minute_schema, True)]
        if parameters:
            operation["parameters"] = parameters
        if method == "post":
            operation["requestBody"] = {"required": True, "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/RunRequest"}, "example": fixture["request"]}}}
        paths["/api/v1" + path] = {method: operation}
    paths["/api/v1/runs/{run_id}/exports/{kind}"] = {"get": {
        "operationId": "ExportRun", "parameters": [run_id, parameter("kind", "path", {"enum": ["scores", "metrics", "config"], "type": "string"}, True)],
        "responses": {"200": {"description": "Complete-minute Parquet scores, or JSON metrics/config. Content-Disposition attachment.",
                               "content": {"application/vnd.apache.parquet": {"schema": {"type": "string", "format": "binary"}},
                                           "application/json": {"schema": {"oneOf": [{"$ref": "#/components/schemas/Evaluation"}, {"$ref": "#/components/schemas/RunConfig"}]}}}},
                      **errors()}}}
    return {"openapi": "3.1.0", "info": {"title": "Offline Traffic Anomaly API", "version": "1.0"},
            "paths": paths, "components": {"schemas": schemas}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "docs/design/openapi-v1.yaml"
    rendered = yaml.safe_dump(document(), sort_keys=False, allow_unicode=True)
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != rendered:
            raise SystemExit("OpenAPI drift: rerun tools/contracts/export_openapi.py")
        print("OpenAPI matches contracts")
    else:
        target.write_text(rendered, encoding="utf-8")
        print("Wrote docs/design/openapi-v1.yaml")
