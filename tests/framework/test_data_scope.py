from __future__ import annotations

import pytest

from framework.data.scope import DataScope


@pytest.mark.contract
def test_data_scope_generates_bounded_unique_names() -> None:
    scope = DataScope("tests/hawk_admin/test_project.py::TC-001")
    first = scope.unique_name("project", max_length=24)
    second = scope.unique_name("project", max_length=24)
    assert len(first) <= 24
    assert len(second) <= 24
    assert first != second


@pytest.mark.contract
def test_data_scope_cleans_in_reverse_registration_order() -> None:
    calls: list[str] = []
    scope = DataScope("TC-002")
    scope.track("first", lambda: calls.append("first"))
    scope.track("second", lambda: calls.append("second"))
    scope.cleanup()
    assert calls == ["second", "first"]
