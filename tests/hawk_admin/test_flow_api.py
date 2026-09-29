from __future__ import annotations

import json

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases
from platforms.hawk_admin.factories import HawkDataFactory


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
INVALID_CREATE_CASES = dataset_cases("hawk_admin", "flow", "invalid_create")
FLOW_UPDATE_CASES = dataset_case_map("hawk_admin", "flow", "update")
FLOW_CREATE_CASES = dataset_cases("hawk_admin", "flow", "create")


@pytest.mark.core
@pytest.mark.requirement(id="REQ-FLOW-DRAFT-LIFECYCLE", name="flow_draft_lifecycle")
@pytest.mark.case_id("REQ-FLOW-DRAFT-LIFECYCLE-API-01", title="创建项目关联的流程草稿")
def test_hawk_04_01_create_flow(platform_data_factory: HawkDataFactory):
    """创建草稿后，应返回草稿标识、项目关联和初始图版本。"""
    flow_id, payload = platform_data_factory.create_flow(**case_payload(FLOW_CREATE_CASES[0]))
    data = assert_envelope(
        platform_data_factory.client.get_flow(flow_id), required_keys=("data",)
    )["data"]
    assert str(data["id"]) == flow_id
    assert data["alias"] == payload["alias"]
    assert data["desc"] == payload["desc"]
    assert int(data["status"]) == 99
    assert int(data["source"]) == 1
    assert str(payload["projectId"]) in {str(value) for value in data["projectIds"]}
    assert int(data["graphVersion"]) >= 1
    assert json.loads(data["graph"]) == {"nodes": [], "edges": []}


@pytest.mark.parametrize("case", INVALID_CREATE_CASES, ids=lambda case: case["id"])
def test_hawk_04_02_invalid_project_id_is_rejected(case, platform_client):
    """创建草稿时，projectId 必须是正整数，不得静默落库。"""
    assert_rejected(platform_client.create_flow(**case_payload(case)))


def test_hawk_04_04_update_flow(platform_client, platform_data_factory: HawkDataFactory):
    """草稿允许更新描述和别名，且不应改变草稿状态。"""
    flow_id, payload = platform_data_factory.create_flow()
    assert_envelope(platform_client.update_flow(flow_id, **case_payload(FLOW_UPDATE_CASES["standard"])))
    data = assert_envelope(platform_client.get_flow(flow_id), required_keys=("data",))["data"]
    assert data["flowName"]
    assert data["alias"] == FLOW_UPDATE_CASES["standard"]["alias"]
    assert data["desc"] == FLOW_UPDATE_CASES["standard"]["desc"]
    assert int(data["status"]) == 99
    assert data["desc"] != payload["desc"]


@pytest.mark.requirement(id="REQ-FLOW-DRAFT-LIFECYCLE", name="flow_draft_lifecycle")
@pytest.mark.case_id("REQ-FLOW-DRAFT-LIFECYCLE-API-02", title="草稿图保存使用乐观锁并可回查")
def test_hawk_10_11_save_flow_draft_graph(platform_client, platform_data_factory: HawkDataFactory):
    """保存 graph 后版本递增；旧版本再次保存必须冲突，不能覆盖新数据。"""
    flow_id, _ = platform_data_factory.create_flow()
    before = assert_envelope(platform_client.get_flow(flow_id), required_keys=("data",))["data"]
    version = int(before["graphVersion"])
    graph = '{"nodes": [], "edges": []}'
    saved = assert_envelope(
        platform_client.save_flow_draft(flow_id, expected_graph_version=version, graph=graph),
        required_keys=("data",),
    )["data"]
    assert int(saved["graphVersion"]) == version + 1
    assert int(saved["updatedAt"]) > 0
    after = assert_envelope(platform_client.get_flow(flow_id), required_keys=("data",))["data"]
    assert json.loads(after["graph"]) == json.loads(graph)
    assert int(after["graphVersion"]) == version + 1
    assert_rejected(
        platform_client.save_flow_draft(flow_id, expected_graph_version=version, graph=graph),
        allow_error_data=True,
    )


@pytest.mark.requirement(id="REQ-FLOW-DRAFT-LIFECYCLE", name="flow_draft_lifecycle")
@pytest.mark.case_id("REQ-FLOW-DRAFT-LIFECYCLE-API-05", title="按项目查询仅返回关联草稿")
def test_hawk_10_12_list_flow_drafts_by_project(platform_client, platform_data_factory: HawkDataFactory):
    """按项目查询应命中现场草稿，并以草稿/最新发布版本分组返回。"""
    flow_id, payload = platform_data_factory.create_flow()
    data = assert_envelope(
        platform_client.list_flows_by_project(page=1, pageSize=10, projectId=payload["projectId"]),
        required_keys=("data",),
    )["data"]
    groups = data.get("groups")
    assert isinstance(groups, list)
    matching = [group for group in groups if str(group.get("projectId")) == str(payload["projectId"])]
    assert len(matching) == 1, f"项目草稿分组未命中: {data}"
    drafts = [item.get("draft") or {} for item in matching[0].get("flows", [])]
    assert any(str(item.get("id")) == flow_id for item in drafts), data


@pytest.mark.requirement(id="REQ-FLOW-DRAFT-LIFECYCLE", name="flow_draft_lifecycle")
@pytest.mark.case_id("REQ-FLOW-DRAFT-LIFECYCLE-API-06", title="未发布草稿版本列表为空且非法编号被拒绝")
def test_hawk_10_13_list_flow_draft_versions(platform_client, platform_data_factory: HawkDataFactory):
    """新草稿尚无发布版本；版本接口也必须拒绝无效草稿编号。"""
    flow_id, _ = platform_data_factory.create_flow()
    data = assert_envelope(platform_client.list_flow_versions(flow_id), required_keys=("data",))["data"]
    assert data["list"] == []
    assert int(data["total"]) == 0
    assert_rejected(platform_client.list_flow_versions(0))


@pytest.mark.requirement(id="REQ-FLOW-DRAFT-LIFECYCLE", name="flow_draft_lifecycle")
@pytest.mark.case_id("REQ-FLOW-DRAFT-LIFECYCLE-API-04", title="删除未发布草稿后不可读取")
def test_hawk_04_05_delete_flow_then_get(platform_client, platform_data_factory: HawkDataFactory):
    """删除未发布草稿成功后，详情接口必须拒绝该编号。"""
    flow_id, _ = platform_data_factory.create_flow()
    assert_envelope(platform_client.delete_flow_draft(flow_id), required_keys=("data",))
    assert_rejected(platform_client.get_flow(flow_id))


@pytest.mark.requirement(id="REQ-FLOW-DRAFT-LIFECYCLE", name="flow_draft_lifecycle")
@pytest.mark.case_id("REQ-FLOW-DRAFT-LIFECYCLE-API-03", title="发布接口拒绝非法草稿编号")
def test_hawk_10_14_publish_flow_draft_rejects_invalid_id(platform_client):
    """发布会预热下游 Hawk；非法编号必须在该副作用前被拒绝。"""
    assert_rejected(platform_client.publish_flow_draft(0))
