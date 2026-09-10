from __future__ import annotations

import pytest

from framework.http.client import ApiClient


pytestmark = [pytest.mark.live, pytest.mark.source_admin]


def _assert_source_success(response, *, required_any: tuple[str, ...]) -> dict:
    payload = ApiClient.json(response)
    assert response.status_code == 200, f"HTTP 状态异常: {response.status_code}, body={payload}"
    code = payload.get("code")
    if code is None and isinstance(payload.get("base"), dict):
        code = payload["base"].get("code")
    assert code == 0, f"业务码异常: {payload}"
    assert any(key in payload for key in required_any), f"响应缺少业务数据字段 {required_any}: {payload}"
    return payload


@pytest.mark.smoke
@pytest.mark.core
def test_source_01_01_authenticated_collection_list(platform_client) -> None:
    """总平台 SSO Token 可访问资源管理平台圈选集列表。"""
    response = platform_client.list_collections(limit=1, offset=0)
    _assert_source_success(response, required_any=("data", "collections"))


@pytest.mark.smoke
@pytest.mark.core
def test_source_01_02_authenticated_schema_list(platform_client) -> None:
    """总平台 SSO Token 可访问资源管理平台 Schema 列表。"""
    response = platform_client.list_schemas(page=1, page_size=1)
    _assert_source_success(response, required_any=("data",))


@pytest.mark.smoke
def test_source_01_03_authenticated_share_link_list(platform_client) -> None:
    """总平台 SSO Token 可访问资源管理平台分享链接列表。"""
    response = platform_client.list_share_links(limit=1, offset=0)
    _assert_source_success(response, required_any=("data",))


@pytest.mark.smoke
def test_source_01_04_authenticated_audit_log_list(platform_client) -> None:
    """总平台 SSO Token 可访问资源管理平台审计日志列表。"""
    response = platform_client.list_audit_logs(limit=1, offset=0)
    _assert_source_success(response, required_any=("logs", "data"))
