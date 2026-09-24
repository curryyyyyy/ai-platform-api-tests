from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.contract_diff import compare_contracts, main


pytestmark = pytest.mark.contract


def _write_contract(path: Path, *, operation: dict) -> None:
    path.write_text(
        yaml.safe_dump(
            {"openapi": "3.0.3", "paths": {"/items": {"get": operation}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_compare_contracts_detects_removed_operation_and_added_endpoint(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.yaml"
    current = tmp_path / "current.yaml"
    _write_contract(baseline, operation={"operationId": "listItems", "responses": {"200": {"description": "ok"}}})
    current.write_text(
        yaml.safe_dump(
            {
                "openapi": "3.0.3",
                "paths": {
                    "/items": {"post": {"operationId": "createItem", "responses": {"201": {"description": "ok"}}}},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = compare_contracts(baseline, current)

    assert result["summary"]["breaking"] == 1
    assert any("operation removed" in item["detail"] for item in result["breaking"])
    assert any("operation added" in item["detail"] for item in result["compatible"])


def test_compare_contracts_detects_required_parameter_and_response_type_change(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.yaml"
    current = tmp_path / "current.yaml"
    operation = {
        "operationId": "listItems",
        "parameters": [{"name": "page", "in": "query", "required": False, "schema": {"type": "integer"}}],
        "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {"type": "array"}}}}},
    }
    changed = {
        **operation,
        "parameters": [{"name": "page", "in": "query", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {"type": "object"}}}}},
    }
    _write_contract(baseline, operation=operation)
    _write_contract(current, operation=changed)

    result = compare_contracts(baseline, current)
    details = " ".join(item["detail"] for item in result["breaking"])
    assert result["summary"]["breaking"] == 3
    assert "parameter became required" in details
    assert "schema type changed" in details


def test_compare_contracts_detects_removed_response_schema(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.yaml"
    current = tmp_path / "current.yaml"
    operation = {
        "operationId": "listItems",
        "responses": {
            "200": {
                "description": "ok",
                "content": {"application/json": {"schema": {"type": "array"}}},
            }
        },
    }
    changed = {
        "operationId": "listItems",
        "responses": {"200": {"description": "ok", "content": {"application/json": {}}}},
    }
    _write_contract(baseline, operation=operation)
    _write_contract(current, operation=changed)

    result = compare_contracts(baseline, current)

    assert any("schema was removed" in item["detail"] for item in result["breaking"])


def test_inventory_diff_is_reported_and_fail_on_breaking_returns_one(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.yaml"
    current = tmp_path / "current.yaml"
    baseline_inventory = tmp_path / "baseline.json"
    current_inventory = tmp_path / "current.json"
    operation = {"operationId": "listItems", "responses": {"200": {"description": "ok"}}}
    _write_contract(baseline, operation=operation)
    _write_contract(current, operation=operation)
    baseline_inventory.write_text(json.dumps({"operations": [{"method": "GET", "path": "/items", "operationId": "listItems"}]}), encoding="utf-8")
    current_inventory.write_text(json.dumps({"operations": []}), encoding="utf-8")
    report = tmp_path / "report.json"

    assert main([
        "--baseline-openapi", str(baseline),
        "--current-openapi", str(current),
        "--baseline-inventory", str(baseline_inventory),
        "--current-inventory", str(current_inventory),
        "--report", str(report),
        "--fail-on-breaking",
    ]) == 1
    assert json.loads(report.read_text(encoding="utf-8"))["summary"]["breaking"] == 1


def test_compare_contracts_follows_shared_schema_references(tmp_path: Path) -> None:
    """验证 compare_contracts 能沿着 OpenAPI 的 $ref 引用，正确识别出“共享 schema 的类型变更"""
    baseline = tmp_path / "baseline.yaml"
    current = tmp_path / "current.yaml"
    base_schema = {
        "openapi": "3.0.3",
        "paths": {
            "/items": {
                "get": {
                    "operationId": "listItems",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Item"}}},
                        }
                    },
                }
            }
        },
        "components": {"schemas": {"Item": {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}}}},
    }
    changed_schema = yaml.safe_load(yaml.safe_dump(base_schema))
    changed_schema["components"]["schemas"]["Item"]["properties"]["id"]["type"] = "string"
    baseline.write_text(yaml.safe_dump(base_schema, sort_keys=False), encoding="utf-8")
    current.write_text(yaml.safe_dump(changed_schema, sort_keys=False), encoding="utf-8")

    result = compare_contracts(baseline, current)

    assert any("schema type changed" in item["detail"] for item in result["breaking"])


def test_compare_contracts_merges_openapi_bundle(tmp_path: Path) -> None:
    baseline_one = tmp_path / "baseline-one.json"
    baseline_two = tmp_path / "baseline-two.json"
    current_one = tmp_path / "current-one.json"
    current_two = tmp_path / "current-two.json"
    first = {"openapi": "3.0.3", "paths": {"/items": {"get": {"operationId": "listItems", "responses": {"200": {"description": "ok"}}}}}}
    second = {"openapi": "3.0.3", "paths": {"/items/{id}": {"get": {"operationId": "getItem", "responses": {"200": {"description": "ok"}}}}}}
    baseline_one.write_text(json.dumps(first), encoding="utf-8")
    baseline_two.write_text(json.dumps(second), encoding="utf-8")
    current_one.write_text(json.dumps(first), encoding="utf-8")
    changed = {"openapi": "3.0.3", "paths": {"/items/{id}": {"delete": {"operationId": "deleteItem", "responses": {"204": {"description": "ok"}}}}}}
    current_two.write_text(json.dumps(changed), encoding="utf-8")

    result = compare_contracts([baseline_one, baseline_two], [current_one, current_two])

    assert result["summary"]["baseline_operations"] == 2
    assert result["summary"]["current_operations"] == 2
    assert any("operation removed" in item["detail"] for item in result["breaking"])


def test_compare_contracts_tracks_business_ids_in_platform_inventory(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.yaml"
    current = tmp_path / "current.yaml"
    baseline_inventory = tmp_path / "baseline.json"
    current_inventory = tmp_path / "current.json"
    operation = {"responses": {"200": {"description": "ok"}}}
    _write_contract(baseline, operation=operation)
    _write_contract(current, operation=operation)
    baseline_inventory.write_text(
        json.dumps({"operations": [{"id": "DOMAIN-01", "method": "GET", "path": "/items"}]}),
        encoding="utf-8",
    )
    current_inventory.write_text(
        json.dumps({"operations": [{"id": "DOMAIN-02", "method": "GET", "path": "/items"}]}),
        encoding="utf-8",
    )

    result = compare_contracts(
        baseline,
        current,
        baseline_inventory=baseline_inventory,
        current_inventory=current_inventory,
    )

    details = " ".join(item["detail"] for item in result["breaking"] + result["compatible"])
    assert "operation removed: DOMAIN-01" in details
    assert "operation added: DOMAIN-02" in details
