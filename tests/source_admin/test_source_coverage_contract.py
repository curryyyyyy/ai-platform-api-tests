from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "contracts/source_admin/api_inventory.json"
COVERAGE = ROOT / "tests/source_admin/coverage.yaml"


def _has_core_marker(test_ref: str) -> bool:
    relative_path, function_name = test_ref.split("::", maxsplit=1)
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != function_name:
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Attribute)
                and decorator.attr == "core"
                and isinstance(decorator.value, ast.Attribute)
                and decorator.value.attr == "mark"
            ):
                return True
    return False


@pytest.mark.contract
@pytest.mark.source_admin
def test_source_coverage_maps_every_inventory_operation() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    coverage = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))
    inventory_ids = {item["id"] for item in inventory["operations"]}
    mapped_ids = {operation for entry in coverage["entries"] for operation in entry["operations"]}
    assert mapped_ids == inventory_ids
    assert all(entry.get("tests") for entry in coverage["entries"])
    assert all(
        entry.get("level") == "full" or entry.get("note") or entry.get("env")
        for entry in coverage["entries"]
    )


@pytest.mark.contract
@pytest.mark.source_admin
def test_source_p0_cases_have_core_tests() -> None:
    coverage = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))
    missing = [
        entry["id"]
        for entry in coverage["entries"]
        if entry.get("priority") == "P0"
        and not any(_has_core_marker(test_ref) for test_ref in entry["tests"])
    ]
    assert not missing, f"P0 用例缺少 core 门禁测试: {missing}"
