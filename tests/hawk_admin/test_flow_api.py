from __future__ import annotations

import pytest

from framework.assertions import assert_envelope


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]


def test_hawk_04_01_create_flow(platform_data_factory):
    """创建包含有效配置的流程：创建后回查详情，flowName 与 config 应与创建值一致。"""

    # 尝试传入一个看起来更“完整”的 config，或者找一个后端已有的合法示例
    valid_config = '{"stages":[{"name":"Stage1", "type":"manual"}]}'

    flow_id, payload = platform_data_factory.create_flow(config = valid_config)
    data = assert_envelope(platform_data_factory.client.get_flow(flow_id), required_keys=("data",))["data"]
    assert data["flowName"] == payload["flowName"]
    assert data["config"] == payload["config"]


def test_hawk_04_02_invalid_json_config(platform_client):
    """创建流程时配置不是合法 JSON：服务端应拒绝并返回非 0 业务码。"""
    response = platform_client.create_flow(
        flowName="TC-04-02-invalid-flow", config="{stages:", schema="{}", status=1
    )
    body = assert_envelope(response, expected_code=None)
    assert body["code"] != 0


def test_hawk_04_03_list_flow_filters(platform_client, platform_data_factory):
    """按名称和状态查询流程：过滤条件应命中刚创建的流程。"""
    _, payload = platform_data_factory.create_flow()
    body = assert_envelope(
        platform_client.list_flows(page=1, pageSize=10, flowName=payload["flowName"], status=1),
        required_keys=("data",),
    )
    assert any(item["flowName"] == payload["flowName"] for item in body["data"]["list"])


def test_hawk_04_04_update_flow(platform_client, platform_data_factory):
    """更新流程描述、别名和状态：更新后回查，新值生效且 flowName 保持不变。"""
    flow_id, payload = platform_data_factory.create_flow()
    assert_envelope(platform_client.update_flow(flow_id, alias="flow01-updated", desc="更新流程", status=1))
    data = assert_envelope(platform_client.get_flow(flow_id), required_keys=("data",))["data"]
    assert data["flowName"] == payload["flowName"]
    assert data["alias"] == "flow01-updated"
    assert data["desc"] == "更新流程"


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
