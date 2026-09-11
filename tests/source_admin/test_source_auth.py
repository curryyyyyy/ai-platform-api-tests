from __future__ import annotations

import pytest

from framework.data.dataset import dataset_defaults

pytestmark = [pytest.mark.live, pytest.mark.smoke, pytest.mark.source_admin]
AUTH_DEFAULTS = dataset_defaults("source_admin", "auth")


def test_source_01_05_requires_login_token(anonymous_platform_client) -> None:
    """资源管理平台主业务入口缺少总平台 Token 时拒绝访问。"""
    response = anonymous_platform_client.get("/api/v1/collections")
    assert response.status_code in {401, 403}, (
        f"未携带 Token 时应返回 401/403: {response.status_code}, {response.text[:500]}"
    )


def test_source_01_06_invalid_login_token_is_rejected(anonymous_platform_client) -> None:
    """资源管理平台主业务入口使用无效 Token 时拒绝访问。"""
    response = anonymous_platform_client.get(
        "/api/v1/collections",
        headers={"Authorization": f"Bearer {AUTH_DEFAULTS['invalid_token']}"},
    )
    assert response.status_code in {401, 403}, (
        f"无效 Token 时应返回 401/403: {response.status_code}, {response.text[:500]}"
    )
