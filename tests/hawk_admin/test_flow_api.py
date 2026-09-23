from __future__ import annotations

import json

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases
from platforms.hawk_admin.factories import HawkDataFactory


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
INVALID_CONFIG_CASES = dataset_cases("hawk_admin", "flow", "invalid_config")
FLOW_UPDATE_CASES = dataset_case_map("hawk_admin", "flow", "update")
FLOW_CREATE_CASES = dataset_cases("hawk_admin", "flow", "create")


def test_hawk_04_01_create_flow(platform_data_factory: HawkDataFactory):
    """创建包含有效配置的流程：创建后回查详情，flowName 与 config 应与创建值一致。"""

    flow_id, payload = platform_data_factory.create_flow(**case_payload(FLOW_CREATE_CASES[0]))
    data = assert_envelope(platform_data_factory.client.get_flow(flow_id), required_keys=("data",))["data"]
    assert data["flowName"] == payload["flowName"]
    assert json.loads(data["config"]) == json.loads(payload["config"])
    assert json.loads(data["configTemplate"]) == json.loads(payload["configTemplate"])


# TC-04-02：配置格式边界
@pytest.mark.parametrize("case", INVALID_CONFIG_CASES, ids=lambda case: case["id"])
def test_hawk_04_02_invalid_json_config(case, platform_client):
    """创建流程时配置不是合法 JSON：每种非法结构均应被拒绝。"""
    response = platform_client.create_flow(**case_payload(case))
    assert_rejected(response)


def test_hawk_04_04_update_flow(platform_client, platform_data_factory: HawkDataFactory):
    """更新流程描述、别名和状态：更新后回查，新值生效且 flowName 保持不变。"""
    flow_id, payload = platform_data_factory.create_flow()
    assert_envelope(platform_client.update_flow(flow_id, **case_payload(FLOW_UPDATE_CASES["standard"])))
    data = assert_envelope(platform_client.get_flow(flow_id), required_keys=("data",))["data"]
    assert data["flowName"] == payload["flowName"]
    assert data["alias"] == FLOW_UPDATE_CASES["standard"]["alias"]
    assert data["desc"] == FLOW_UPDATE_CASES["standard"]["desc"]


def test_hawk_04_05_delete_flow_then_get(platform_client, platform_data_factory: HawkDataFactory):
    """删除被阶段引用的流程：删除后再查询应返回非 0 业务码。"""
    flow_id, _ = platform_data_factory.create_flow()
    assert_envelope(platform_client.delete_flow(flow_id))
    assert_rejected(platform_client.get_flow(flow_id))
