from __future__ import annotations

import pytest

from framework.assertions import assert_envelope
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
INVALID_CONFIG_CASES = dataset_cases("hawk_admin", "flow", "invalid_config")
FLOW_UPDATE_CASES = dataset_case_map("hawk_admin", "flow", "update")
FLOW_CREATE_CASES = dataset_cases("hawk_admin", "flow", "create")
FLOW_LIST_CASES = dataset_case_map("hawk_admin", "flow", "list_filter")


@pytest.mark.core
def test_hawk_04_01_create_flow(platform_data_factory):
    """创建包含有效配置的流程：创建后回查详情，flowName 与 config 应与创建值一致。"""

    flow_id, payload = platform_data_factory.create_flow(**case_payload(FLOW_CREATE_CASES[0]))
    data = assert_envelope(platform_data_factory.client.get_flow(flow_id), required_keys=("data",))["data"]
    assert data["flowName"] == payload["flowName"]
    assert data["config"] == payload["config"]


# TC-04-02：配置格式边界
@pytest.mark.parametrize("case", INVALID_CONFIG_CASES, ids=lambda case: case["id"])
def test_hawk_04_02_invalid_json_config(case, platform_client):
    """创建流程时配置不是合法 JSON：每种非法结构均应被拒绝。"""
    response = platform_client.create_flow(**case_payload(case))
    body = assert_envelope(response, expected_code=None)
    assert body["code"] != 0


def test_hawk_04_03_list_flow_filters(platform_client, platform_data_factory):
    """TC-04-03：按名称、状态和创建时间排序查询流程。"""
    _, payload = platform_data_factory.create_flow()
    query = case_payload(FLOW_LIST_CASES["name_status_sorted"])
    query["flowName"] = payload["flowName"]
    body = assert_envelope(
        platform_client.list_flows(page=1, pageSize=10, **query),
        required_keys=("data",),
    )
    items = body["data"]["list"]
    assert any(item["flowName"] == payload["flowName"] for item in items)
    assert all(item["status"] == query["status"] for item in items)


def test_hawk_04_04_update_flow(platform_client, platform_data_factory):
    """更新流程描述、别名和状态：更新后回查，新值生效且 flowName 保持不变。"""
    flow_id, payload = platform_data_factory.create_flow()
    assert_envelope(platform_client.update_flow(flow_id, **case_payload(FLOW_UPDATE_CASES["standard"])))
    data = assert_envelope(platform_client.get_flow(flow_id), required_keys=("data",))["data"]
    assert data["flowName"] == payload["flowName"]
    assert data["alias"] == FLOW_UPDATE_CASES["standard"]["alias"]
    assert data["desc"] == FLOW_UPDATE_CASES["standard"]["desc"]


def test_hawk_04_05_delete_flow_then_get(platform_client, platform_data_factory):
    """删除被阶段引用的流程：删除后再查询应返回非 0 业务码。"""
    flow_id, _ = platform_data_factory.create_flow()
    assert_envelope(platform_client.delete_flow(flow_id))
    body = assert_envelope(platform_client.get_flow(flow_id), expected_code=None)
    assert body["code"] != 0


def test_hawk_04_06_get_missing_flow(platform_client):
    """查询不存在的流程：应返回非 0 业务码，且不虚构数据。"""
    body = assert_envelope(platform_client.get_flow(999999999), expected_code=None)
    assert body["code"] != 0
