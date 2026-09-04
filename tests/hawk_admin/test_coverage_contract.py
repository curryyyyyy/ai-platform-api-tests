from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "test-cases/hawk_admin/机器标注平台_测试用例.schema.yaml"
COVERAGE = ROOT / "tests/hawk_admin/coverage.yaml"


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
