from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from framework.requirements import validate_requirement_identifiers


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "test-cases/hawk_admin/机器标注平台_测试用例.schema.yaml"
COVERAGE = ROOT / "tests/hawk_admin/coverage.yaml"


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
                and isinstance(decorator.value.value, ast.Name)
                and decorator.value.value.id == "pytest"
            ):
                return True
    return False


def _has_requirement_marker(test_ref: str, requirement_id: str) -> bool:
    relative_path, function_name = test_ref.split("::", maxsplit=1)
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != function_name:
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if not (isinstance(decorator.func.value, ast.Attribute) and decorator.func.value.attr == "mark"):
                continue
            if decorator.func.attr != "requirement":
                continue
            for keyword in decorator.keywords:
                if keyword.arg == "id" and isinstance(keyword.value, ast.Constant):
                    return keyword.value.value == requirement_id
    return False


@pytest.mark.contract
@pytest.mark.hawk_admin
def test_hawk_schema_cases_have_coverage_entries() -> None:
    """Schema 中每条 Hawk case 都必须登记自动化映射，防止新增 case 静默漏测。"""
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    coverage = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))
    schema_ids = {item["id"] for item in schema["cases"]}
    entries = coverage["entries"]
    coverage_ids = [item["id"] for item in entries]
    assert len(coverage_ids) == len(set(coverage_ids)), "覆盖表存在重复 case id"
    assert set(coverage_ids) == schema_ids
    assert all(item.get("tests") for item in entries)
    assert {item.get("level") for item in entries} <= {"full", "partial", "blocked"}
    assert all(
        item.get("level") == "full" or item.get("note") or item.get("env")
        for item in entries
    ), "partial/blocked 覆盖项必须说明原因或环境前置"


@pytest.mark.contract
@pytest.mark.hawk_admin
def test_hawk_p0_cases_are_in_core_gate() -> None:
    """每条 P0 手工用例至少映射到一个 core 自动化测试，避免脱离 CI 门禁。"""
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    coverage = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))
    p0_ids = {item["id"] for item in schema["cases"] if item["priority"] == "P0"}
    mappings = {item["id"]: item["tests"] for item in coverage["entries"]}

    missing = [
        case_id for case_id in sorted(p0_ids)
        if not any(_has_core_marker(test_ref) for test_ref in mappings[case_id])
    ]
    assert not missing, f"P0 用例缺少 core 门禁测试: {missing}"


@pytest.mark.contract
@pytest.mark.hawk_admin
def test_requirement_cases_have_platform_coverage() -> None:
    """所有需求包都必须在平台总覆盖矩阵中追溯到 Schema、源码和 API。"""
    coverage = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))
    requirements = coverage.get("requirements", [])
    assert isinstance(requirements, list) and requirements, "平台覆盖矩阵至少应登记一个需求包"
    requirement_ids = [item.get("id") for item in requirements]
    assert len(requirement_ids) == len(set(requirement_ids)), "需求覆盖矩阵存在重复需求 ID"
    for requirement in requirements:
        source_schema = requirement.get("source_schema")
        assert isinstance(source_schema, str) and source_schema.strip()
        schema_path = ROOT / source_schema
        assert schema_path.is_file(), f"需求 Schema 不存在: {schema_path}"
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        assert schema["meta"]["requirement_id"] == requirement["id"]
        assert schema["meta"]["requirement_name"] == requirement["name"]
        schema_cases = {item["id"]: item for item in schema["cases"]}
        coverage_cases = requirement.get("cases", [])
        coverage_ids = [item["id"] for item in coverage_cases]
        assert len(coverage_ids) == len(set(coverage_ids))
        assert set(coverage_ids) == set(schema_cases)
        for item in coverage_cases:
            validate_requirement_identifiers(requirement["id"], item["id"])
            assert item["priority"] == "P0"
            assert item["source_id"] == schema_cases[item["id"]]["source_id"]
            relative_path, function_name = item["test"].split("::", maxsplit=1)
            path = ROOT / relative_path
            assert path.is_file(), f"需求 case 测试文件不存在: {path}"
            assert f"def {function_name}(" in path.read_text(encoding="utf-8")
            assert _has_requirement_marker(item["test"], requirement["id"]), (
                f"需求 case 缺少 requirement marker: {item['test']}"
            )
            assert item["endpoint"].startswith(("GET ", "POST "))
