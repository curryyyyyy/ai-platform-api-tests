from __future__ import annotations

import pytest

from framework.assertions import assert_envelope


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]


def test_hawk_03_01_create_stage(platform_data_factory):
    """创建阶段并返回编号：创建后回查详情，name 与 alias 应与创建值一致。"""
    stage_id, payload = platform_data_factory.create_stage()
    detail = assert_envelope(platform_data_factory.client.get_stage(stage_id), required_keys=("data",))["data"]
    assert detail["name"] == payload["name"]
    assert detail["alias"] == payload["alias"]


def test_hawk_03_02_list_stage_filters(platform_client, platform_data_factory):
    """查询阶段列表并按条件筛选：按 domain/type/关键词过滤应命中刚创建的阶段。"""
    _, payload = platform_data_factory.create_stage()
    body = assert_envelope(
        platform_client.list_stages(page=1, pageSize=10, domain="vision", type="operator", keywords=payload["name"]),
        required_keys=("data",),
    )
    assert any(item["name"] == payload["name"] for item in body["data"]["list"])


def test_hawk_03_03_update_stage(platform_client, platform_data_factory):
    """更新阶段可编辑属性：更新后回查，新 alias 与 desc 生效且 name 不变。"""
    stage_id, payload = platform_data_factory.create_stage()
    assert_envelope(
        platform_client.update_stage(stage_id, alias="stage01-updated", desc="更新阶段", status=1)
    )
    data = assert_envelope(platform_client.get_stage(stage_id), required_keys=("data",))["data"]
    assert data["name"] == payload["name"]
    assert data["alias"] == "stage01-updated"
    assert data["desc"] == "更新阶段"


def test_hawk_03_04_get_missing_stage(platform_client):
    """查询不存在的阶段：应返回非 0 业务码。"""
    body = assert_envelope(platform_client.get_stage(999999999), expected_code=None)
    assert body["code"] != 0


def test_hawk_03_05_delete_stage_then_get(platform_client, platform_data_factory):
    """删除阶段后详情不可见：删除后再查询应返回非 0 业务码。"""
    stage_id, _ = platform_data_factory.create_stage()
    assert_envelope(platform_client.delete_stage(stage_id))
    body = assert_envelope(platform_client.get_stage(stage_id), expected_code=None)
    assert body["code"] != 0
