from __future__ import annotations

import pytest


@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.core
def test_central_login_returns_token(central_token: str) -> None:
    """使用总平台账号登录获取 Token（主链路）：返回的 Token 应非空。"""
    assert central_token
