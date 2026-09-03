from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.contract
@pytest.mark.hawk_admin
def test_hawk_openapi_snapshot_is_valid() -> None:
    """契约快照是合法的 OpenAPI 3.0.3 文档，且包含非空 paths。"""
    with (ROOT / "contracts/hawk_admin/openapi.yaml").open(encoding="utf-8") as stream:
        spec = yaml.safe_load(stream)
    assert isinstance(spec, dict)
    assert spec.get("openapi") == "3.0.3"
    assert isinstance(spec.get("paths"), dict) and spec["paths"]


@pytest.mark.contract
@pytest.mark.hawk_admin
def test_hawk_inventory_matches_openapi() -> None:
    """接口清单与 OpenAPI 快照一致：method + path + operationId 一一对应。"""
    with (ROOT / "contracts/hawk_admin/openapi.yaml").open(encoding="utf-8") as stream:
        spec = yaml.safe_load(stream)
    inventory = json.loads((ROOT / "contracts/hawk_admin/api_inventory.json").read_text(encoding="utf-8"))
    expected = {
        (method.upper(), path, operation.get("operationId"))
        for path, path_item in spec["paths"].items()
        for method, operation in path_item.items()
        if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
    }
    actual = {(item["method"], item["path"], item["operationId"]) for item in inventory["operations"]}
    assert actual == expected
