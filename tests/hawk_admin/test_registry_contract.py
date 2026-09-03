from __future__ import annotations

import pytest


pytestmark = [pytest.mark.contract, pytest.mark.hawk_admin]


def test_marker_bound_anonymous_platform_client_has_no_token(anonymous_platform_client) -> None:
    """平台 marker 应绑定无鉴权客户端，不依赖 Hawk 专属 fixture 名称。"""
    assert anonymous_platform_client.base_url
    assert "Authorization" not in anonymous_platform_client.session.headers
