from __future__ import annotations

import os

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
FLOW_READ_CASES = dataset_case_map("hawk_admin", "flow", "read")


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
    assert isinstance(items, list) and items, f"Stage 筛选未命中已有流程: {data}"
    assert int(data["total"]) >= len(items)
    expected_stage = query["stageName"]
    assert all(int(item["status"]) == int(query["status"]) for item in items)
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
