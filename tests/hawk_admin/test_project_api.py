from __future__ import annotations

import pytest

from framework.assertions import assert_envelope


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]


def test_hawk_02_01_create_project(platform_data_factory):
    """创建项目并返回编号：创建图片项目后回查，编号、名称、素材类型、交付数量一致。"""
    project_id, payload = platform_data_factory.create_project(
        materialType="图片", description="核心链路项目", deliveryCount=10, notificationLevel=0
    )
    assert int(project_id) > 0
    body = assert_envelope(platform_data_factory.client.get_project(project_id), required_keys=("data",))
    data = body["data"]
    assert data["name"] == payload["name"]
    assert data["materialType"] == "图片"
    # OpenAPI 中 deliveryCount 声明为 string，服务端返回 "10"，统一转 int 后再比较
    assert int(data["deliveryCount"]) == 10


def test_hawk_02_02_get_project_matches_create(platform_data_factory):
    """查询项目详情与创建数据一致：回查名称与描述应与创建值一致。"""
    project_id, payload = platform_data_factory.create_project(
        materialType="图片", description="读写一致性", notificationLevel=0
    )
    body = assert_envelope(platform_data_factory.client.get_project(project_id), required_keys=("data",))
    assert body["data"]["name"] == payload["name"]
    assert body["data"]["description"] == "读写一致性"


def test_hawk_02_03_list_project_filters_and_defaults(platform_client, platform_data_factory):
    """按名称模糊搜索并分页查询项目：page/pageSize 传 0 走默认分页，应命中刚创建的项目。"""
    _, payload = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
    body = assert_envelope(
        platform_client.get("/api/v1/project", params={"page": 0, "pageSize": 0, "name": payload["name"]}),
        required_keys=("data",),
    )
    data = body["data"]
    assert isinstance(data["list"], list)
    assert any(item["name"] == payload["name"] for item in data["list"])


def test_hawk_02_04_update_project(platform_client, platform_data_factory):
    """更新项目资料和负责人：更新后回查，名称、描述、素材类型应变为新值。"""
    project_id, payload = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
    created = assert_envelope(platform_client.get_project(project_id), required_keys=("data",))["data"]
    owner_id = created["users"][0]["userId"]
    body = assert_envelope(
        platform_client.update_project(
            project_id,
            name=f"{payload['name']}-updated",
            materialType="视频",
            description="已更新描述",
            ownerUserId=owner_id,
            notificationLevel=1,
        )
    )
    assert body.get("code") == 0
    detail = assert_envelope(platform_client.get_project(project_id), required_keys=("data",))["data"]
    assert detail["name"] == f"{payload['name']}-updated"
    assert detail["description"] == "已更新描述"
    assert detail["materialType"] == "视频"


def test_hawk_02_05_update_project_without_owner_is_rejected(platform_client, platform_data_factory):
    """更新项目时不指定 OWNER：缺少负责人应被拒绝，报错信息包含 OWNER。"""
    project_id, payload = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
    response = platform_client.update_project(
        project_id,
        name=f"{payload['name']}-no-owner",
        materialType="图片",
        adminUserIds=[],
        developerUserIds=[],
        ownerUserId=0,
        notificationLevel=0,
    )
    body = assert_envelope(response, expected_code=None)
    assert body["code"] != 0
    assert "OWNER" in body.get("message", "")


@pytest.mark.parametrize("level", [-1, 9, 99])
def test_hawk_02_06_invalid_notification_level(level, platform_client):
    """使用非法通知级别创建项目：-1/9/99 均应被拒绝。"""
    response = platform_client.create_project(
        name=f"TC-02-06-invalid-{level}", materialType="图片", notificationLevel=level
    )
    body = assert_envelope(response, expected_code=None)
    assert body["code"] != 0


def test_hawk_02_07_viewer_cannot_write(viewer_platform_client):
    """非超级管理员访问无权限项目：查看者执行写操作应返回 401/403。"""
    response = viewer_platform_client.create_project(
        name="TC-02-07-viewer-project", materialType="图片", notificationLevel=0
    )
    assert response.status_code in {401, 403}


def test_hawk_02_08_delete_project_then_get(platform_client, platform_data_factory):
    """删除项目后不可查询：删除后再查询应返回非 0 业务码。"""
    project_id, _ = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
    assert_envelope(platform_client.delete_project(project_id))
    response = platform_client.get_project(project_id)
    body = assert_envelope(response, expected_code=None)
    assert body["code"] != 0
