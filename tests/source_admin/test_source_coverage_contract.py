from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml

from framework.requirements import validate_requirement_identifiers


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


def _has_marker(test_ref: str, marker_name: str, marker_id: str) -> bool:
    relative_path, function_name = test_ref.split("::", maxsplit=1)
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != function_name:
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if not (
                isinstance(decorator.func.value, ast.Attribute)
                and decorator.func.value.attr == "mark"
                and decorator.func.attr == marker_name
            ):
                continue
            values = [
                value.value
                for value in decorator.args
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            ]
            values.extend(
                keyword.value.value
                for keyword in decorator.keywords
                if keyword.arg == "id"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            )
            if marker_id in values:
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


@pytest.mark.contract
@pytest.mark.source_admin
def test_source_requirement_cases_have_platform_coverage() -> None:
    """需求级 case 必须归属现有业务域脚本，并可按稳定 ID 追溯。"""
    coverage = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))
    requirements = coverage.get("requirements", [])
    assert isinstance(requirements, list) and requirements, "平台覆盖矩阵至少应登记一个需求包"
    requirement_ids = [item.get("id") for item in requirements]
    assert len(requirement_ids) == len(set(requirement_ids)), "需求覆盖矩阵存在重复需求 ID"
    for requirement in requirements:
        requirement_id = requirement["id"]
        assert isinstance(requirement.get("name"), str) and requirement["name"].strip()
        cases = requirement.get("cases", [])
        assert isinstance(cases, list) and cases
        case_ids = [item.get("id") for item in cases]
        assert len(case_ids) == len(set(case_ids)), f"需求 {requirement_id} 存在重复 case ID"
        for item in cases:
            case_id = item["id"]
            validate_requirement_identifiers(requirement_id, case_id)
            assert item.get("priority") in {"P0", "P1", "P2"}
            assert item.get("level") in {"full", "partial", "blocked"}
            assert item.get("level") == "full" or item.get("note") or item.get("env")
            test_ref = item["test"]
            relative_path, function_name = test_ref.split("::", maxsplit=1)
            path = ROOT / relative_path
            assert path.is_file(), f"需求 case 测试文件不存在: {path}"
            assert f"def {function_name}(" in path.read_text(encoding="utf-8")
            assert _has_marker(test_ref, "requirement", requirement_id), (
                f"需求 case 缺少 requirement marker: {test_ref}"
            )
            assert _has_marker(test_ref, "case_id", case_id), (
                f"需求 case 缺少 case_id marker: {test_ref}"
            )
            assert str(item["endpoint"]).startswith(("GET ", "POST ", "PUT ", "DELETE "))
