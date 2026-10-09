from __future__ import annotations

import os

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map
from platforms.hawk_admin.factories import HawkDataFactory


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
FLOW_READ_CASES = dataset_case_map("hawk_admin", "flow", "read")
FLOW_QUERY_CASES = dataset_case_map("hawk_admin", "flow", "query")


def _existing_flow_id(platform_client) -> str:
    """优先使用环境指定的流程，否则从只读列表取一条已有流程。"""
    configured = os.getenv("HAWK_FLOW_ID", "").strip()
    if configured:
        if not configured.isdigit() or int(configured) <= 0:
            raise AssertionError("HAWK_FLOW_ID 必须是正整数")
        return configured

    body = assert_envelope(
        platform_client.list_flows(page=1, pageSize=1),
        required_keys=("data",),
    )
    items = body["data"].get("list")
    assert isinstance(items, list) and items, "环境中没有可供只读查询的流程"
    flow_id = items[0].get("id")
    assert flow_id, f"流程列表首条记录缺少 id: {items[0]}"
    return str(flow_id)


@pytest.mark.core
def test_hawk_04_03_list_flows_by_stage_status_and_calls(platform_client):
    """只读查询：按 Stage、状态筛选，并按 30 天调用次数倒序。"""
    query = case_payload(FLOW_READ_CASES["stage_status_sort"])
    body = assert_envelope(platform_client.list_flows(**query), required_keys=("data",))
    data = body["data"]
    items = data.get("list")
    assert isinstance(items, list), f"流程列表 data.list 应为数组: {data}"
    assert int(data["total"]) >= len(items)
    # 当前环境可能没有同时满足 stageName + status 的流程；空结果是合法筛选结果。
    if not items:
        return
    expected_stage = query["stageName"]
    expected_statuses = {int(status) for status in query["status"]}
    assert all(int(item["status"]) in expected_statuses for item in items)
    assert all(
        any(relation.get("name") == expected_stage for relation in item.get("stages", []))
        for item in items
    ), f"返回流程中存在不包含 Stage {expected_stage!r} 的记录: {items}"
    calls = [int(item["callCnt30d"]) for item in items]
    assert calls == sorted(calls, reverse=True), "流程列表未按 callCnt30d 倒序返回"


def test_hawk_04_06_get_missing_flow(platform_client):
    """只读查询不存在的流程：应返回非 0 业务码。"""
    assert_rejected(platform_client.get_flow(999999999))


def test_hawk_04_07_get_existing_flow(platform_client):
    """只读查询已有流程详情：不创建、不更新流程。"""
    flow_id = _existing_flow_id(platform_client)
    data = assert_envelope(platform_client.get_flow(flow_id), required_keys=("data",))["data"]
    assert str(data["id"]) == flow_id
    assert data.get("flowName")
    assert "schema" in data
    assert "config" in data


def test_hawk_04_08_list_flows_by_call_count(platform_client):
    """只读查询：按 30 天调用次数倒序分页，显式传入 canOffline=false。"""
    query = case_payload(FLOW_READ_CASES["call_count_sort"])
    body = assert_envelope(platform_client.list_flows(**query), required_keys=("data",))
    data = body["data"]
    items = data.get("list")
    assert isinstance(items, list) and items, f"流程列表为空: {data}"
    assert len(items) <= int(query["pageSize"])
    calls = [int(item["callCnt30d"]) for item in items]
    assert calls == sorted(calls, reverse=True), "流程列表未按 callCnt30d 倒序返回"


@pytest.mark.core
@pytest.mark.requirement(id="REQ-FLOW-QUERY-ENHANCEMENTS", name="flow_query_enhancements")
@pytest.mark.case_id("REQ-FLOW-QUERY-ENHANCEMENTS-API-01", title="流程列表支持多状态数组筛选")
def test_hawk_10_17_list_flows_filters_multiple_statuses(
    platform_client, platform_data_factory: HawkDataFactory
):
    """多值 status 使用 OR 语义，且不能丢失现场创建的草稿状态。"""
    flow_id, _ = platform_data_factory.create_flow()
    query = case_payload(FLOW_QUERY_CASES["status_array"])
    data = assert_envelope(platform_client.list_flows(**query), required_keys=("data",))["data"]
    items = data.get("list")
    assert isinstance(items, list), f"流程列表 data.list 应为数组: {data}"
    expected_statuses = {int(status) for status in query["status"]}
    assert all(int(item["status"]) in expected_statuses for item in items), data
    assert any(str(item.get("id")) == flow_id for item in items), data


@pytest.mark.core
@pytest.mark.requirement(id="REQ-FLOW-QUERY-ENHANCEMENTS", name="flow_query_enhancements")
@pytest.mark.case_id("REQ-FLOW-QUERY-ENHANCEMENTS-API-02", title="流程关键词精确别名优先于描述包含")
def test_hawk_10_18_list_flows_prioritizes_exact_alias(
    platform_client, platform_data_factory: HawkDataFactory, data_scope
):
    """keywords 非空时，别名精确命中必须排在描述包含命中之前。"""
    keyword = data_scope.unique_name("flow-keyword", max_length=36)
    exact_id, _ = platform_data_factory.create_flow(alias=keyword, desc="exact alias")
    metadata_id, _ = platform_data_factory.create_flow(
        alias=data_scope.unique_name("flow-metadata", max_length=40), desc=keyword
    )
    query = {**case_payload(FLOW_QUERY_CASES["keyword_priority"]), "keywords": keyword}
    data = assert_envelope(platform_client.list_flows(**query), required_keys=("data",))["data"]
    items = data.get("list")
    assert isinstance(items, list), f"流程列表 data.list 应为数组: {data}"
    matched = [item for item in items if str(item.get("id")) in {exact_id, metadata_id}]
    assert [str(item.get("id")) for item in matched] == [exact_id, metadata_id], data
