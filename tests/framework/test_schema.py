from __future__ import annotations

import pytest

from framework.schema import assert_schema


@pytest.mark.contract
def test_assert_schema_accepts_valid_instance() -> None:
    assert_schema({"id": "p-1", "total": 1}, {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "total": {"type": "integer"}}})


@pytest.mark.contract
def test_assert_schema_reports_invalid_instance() -> None:
    with pytest.raises(AssertionError, match="total"):
        assert_schema({"total": "1"}, {"type": "object", "required": ["total"], "properties": {"total": {"type": "integer"}}})
