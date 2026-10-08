from __future__ import annotations

import pytest

from framework.data.scope import DataScope, DataScopeCleanupError


@pytest.mark.contract
def test_data_scope_generates_bounded_unique_names() -> None:
    """生成的资源名有长度上限、包含用例编号，且两次生成互不相同。"""
    scope = DataScope("tests/sample/test_project.py::TC-001")
    first = scope.unique_name("project", max_length=24)
    second = scope.unique_name("project", max_length=24)
    assert len(first) <= 24
    assert len(second) <= 24
    assert first != second


@pytest.mark.contract
def test_data_scope_cleans_in_reverse_registration_order() -> None:
    """清理动作按注册的逆序执行，保证先创建的资源后删除。"""
    calls: list[str] = []
    scope = DataScope("TC-002")
    scope.track("first", lambda: calls.append("first"))
    scope.track("second", lambda: calls.append("second"))
    scope.cleanup()
    assert calls == ["second", "first"]


@pytest.mark.contract
def test_data_scope_reports_cleanup_failures_after_running_remaining_actions() -> None:
    """清理失败必须使 pytest teardown 失败，且不能阻断其他已登记资源的清理。"""
    calls: list[str] = []
    scope = DataScope("TC-003")
    scope.track("first", lambda: calls.append("first"))

    def failing_cleanup() -> None:
        calls.append("second")
        raise RuntimeError("delete rejected")

    scope.track("second", failing_cleanup)

    with pytest.raises(DataScopeCleanupError, match="second.*delete rejected") as exc_info:
        scope.cleanup()

    assert calls == ["second", "first"]
    assert exc_info.value.case_id == "TC-003"
