from __future__ import annotations

import pytest

from framework.schema import assert_schema


@pytest.mark.contract
def test_assert_schema_accepts_valid_instance() -> None:
    """符合 JSON Schema 的实例应通过校验。"""
    assert_schema({"id": "p-1", "total": 1}, {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "total": {"type": "integer"}}})


@pytest.mark.contract
def test_assert_schema_reports_invalid_instance() -> None:
    """不符合 Schema 的实例应抛出带字段名的断言错误。"""
    with pytest.raises(AssertionError, match="total"):
        assert_schema({"total": "1"}, {"type": "object", "required": ["total"], "properties": {"total": {"type": "integer"}}})
