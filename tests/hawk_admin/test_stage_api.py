from __future__ import annotations

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
STAGE_CREATE_CASES = dataset_cases("hawk_admin", "stage", "create")
STAGE_UPDATE_CASES = dataset_case_map("hawk_admin", "stage", "update")
STAGE_QUERY_CASES = dataset_case_map("hawk_admin", "stage", "query")
STAGE_VALIDATION_CASES = dataset_case_map("hawk_admin", "stage", "validation")


def test_hawk_03_01_create_stage(platform_data_factory):
    """创建阶段并返回编号：创建后回查详情，name 与 alias 应与创建值一致。"""
    stage_id, payload = platform_data_factory.create_stage(**case_payload(STAGE_CREATE_CASES[0]))
    detail = assert_envelope(platform_data_factory.client.get_stage(stage_id), required_keys=("data",))["data"]
    assert detail["name"] == payload["name"]
    assert detail["alias"] == payload["alias"]


def test_hawk_03_02_list_stage_filters(platform_client, platform_data_factory):
    """查询阶段列表并按条件筛选：按 domain/type/关键词过滤应命中刚创建的阶段。"""
    _, payload = platform_data_factory.create_stage(**case_payload(STAGE_CREATE_CASES[0]))
    body = assert_envelope(
        platform_client.list_stages(page=1, pageSize=10, domain="vision", type="operator", keywords=payload["name"]),
        required_keys=("data",),
    )
    items = body["data"]["list"]
    assert items, "按唯一阶段名称筛选不应返回空列表"
    assert all(item["domain"] == "vision" for item in items)
    assert all(item["type"] == "operator" for item in items)
    assert all(payload["name"] in item["name"] for item in items)
    assert any(item["name"] == payload["name"] for item in items)


def test_hawk_03_03_update_stage(platform_client, platform_data_factory):
    """更新阶段可编辑属性：更新后回查，新 alias 与 desc 生效且 name 不变。"""
    stage_id, payload = platform_data_factory.create_stage(**case_payload(STAGE_CREATE_CASES[0]))
    assert_envelope(
        platform_client.update_stage(stage_id, **case_payload(STAGE_UPDATE_CASES["standard"]))
    )
    data = assert_envelope(platform_client.get_stage(stage_id), required_keys=("data",))["data"]
    assert data["name"] == payload["name"]
    assert data["alias"] == STAGE_UPDATE_CASES["standard"]["alias"]
    assert data["desc"] == STAGE_UPDATE_CASES["standard"]["desc"]


def test_hawk_03_04_get_missing_stage(platform_client):
    """查询不存在的阶段：应返回非 0 业务码。"""
    assert_rejected(platform_client.get_stage(999999999))


def test_hawk_03_05_delete_stage_then_get(platform_client, platform_data_factory):
    """删除阶段后详情不可见：删除后再查询应返回非 0 业务码。"""
    stage_id, _ = platform_data_factory.create_stage(**case_payload(STAGE_CREATE_CASES[0]))
    assert_envelope(platform_client.delete_stage(stage_id))
    assert_rejected(platform_client.get_stage(stage_id))


@pytest.mark.core
@pytest.mark.requirement(id="REQ-STAGE-ONLINE-VALIDATION", name="stage_online_validation")
@pytest.mark.case_id("REQ-STAGE-ONLINE-VALIDATION-API-01", title="Stage 上线前拒绝缺少必填元数据")
def test_hawk_03_06_online_stage_requires_metadata(platform_client, platform_data_factory):
    """Stage 缺少名称、描述、领域和行为类型时，上线应返回稳定业务码。"""
    stage_id, _ = platform_data_factory.create_stage(
        **case_payload(STAGE_VALIDATION_CASES["missing_online_metadata"])
    )

    response = platform_client.update_stage(stage_id, status=2)
    body = assert_envelope(response, expected_code=None, required_keys=("message",))

    assert body["code"] == 40903, f"Stage 上线校验业务码异常: {body}"
    message = body["message"]
    assert isinstance(message, str) and message.strip()
    for field in ("名称", "描述", "领域", "行为类型"):
        assert field in message, f"上线校验错误信息缺少字段 {field!r}: {body}"


@pytest.mark.core
@pytest.mark.requirement(id="REQ-FLOW-QUERY-ENHANCEMENTS", name="flow_query_enhancements")
@pytest.mark.case_id("REQ-FLOW-QUERY-ENHANCEMENTS-API-03", title="阶段关键词精确别名优先于描述包含")
def test_hawk_10_19_list_stages_prioritizes_exact_alias(
    platform_client, platform_data_factory, data_scope
):
    """keywords 非空时，阶段别名精确命中必须排在描述包含命中之前。"""
    keyword = data_scope.unique_name("stage-keyword", max_length=36)
    exact_id, _ = platform_data_factory.create_stage(alias=keyword, desc="exact alias")
    metadata_id, _ = platform_data_factory.create_stage(
        alias=data_scope.unique_name("stage-metadata", max_length=40), desc=keyword
    )
    query = {**case_payload(STAGE_QUERY_CASES["keyword_priority"]), "keywords": keyword}
    data = assert_envelope(platform_client.list_stages(**query), required_keys=("data",))["data"]
    items = data.get("list")
    assert isinstance(items, list), f"阶段列表 data.list 应为数组: {data}"
    matched = [item for item in items if str(item.get("id")) in {exact_id, metadata_id}]
    assert [str(item.get("id")) for item in matched] == [exact_id, metadata_id], data
