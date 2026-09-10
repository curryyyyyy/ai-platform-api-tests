from __future__ import annotations

import pytest


pytestmark = [pytest.mark.live, pytest.mark.smoke, pytest.mark.source_admin]


def test_source_01_05_requires_login_token(anonymous_platform_client) -> None:
    """资源管理平台主业务入口缺少总平台 Token 时拒绝访问。"""
    response = anonymous_platform_client.get("/api/v1/collections")
    assert response.status_code in {401, 403}, (
        f"未携带 Token 时应返回 401/403: {response.status_code}, {response.text[:500]}"
    )
