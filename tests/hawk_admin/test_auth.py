from __future__ import annotations

import pytest

from framework.assertions import assert_envelope
from framework.data.dataset import dataset_defaults


AUTH_DEFAULTS = dataset_defaults("hawk_admin", "auth")


@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.hawk_admin
def test_hawk_project_requires_token(anonymous_platform_client) -> None:
    """缺少 Token 访问 Hawk 接口：未携带 Authorization 应返回 401/403。"""
    response = anonymous_platform_client.get("/api/v1/project")
    assert response.status_code in {401, 403}, f"未携带 Token 时应拒绝访问: {response.status_code}"

@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.hawk_admin
def test_hawk_invalid_token_rejected(anonymous_platform_client) -> None:
    """使用数据集中的无效 Token 访问 Hawk 接口：应返回 401/403。"""
    response = anonymous_platform_client.get(
        "/api/v1/project", headers={"Authorization": f"Bearer {AUTH_DEFAULTS['invalidToken']}"}
    )
    assert response.status_code in {401, 403}, f"无效 Token 时应拒绝访问: {response.status_code}"


@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.hawk_admin
def test_hawk_user_rsa_is_public(anonymous_platform_client) -> None:
    """获取 RSA 公钥：无需鉴权即可访问，data.rsa 应为字符串（登录链路第 1 步）。"""
    payload = assert_envelope(anonymous_platform_client.get("/api/v1/user/rsa"), required_keys=("data",))
    assert isinstance((payload.get("data") or {}).get("rsa"), str)


@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.hawk_admin
def test_hawk_authenticated_project_list(platform_client) -> None:
    """总平台登录后访问 Hawk 项目列表：鉴权通过且返回 data.list / data.total 分页结构。"""
    response = platform_client.list_projects()
    payload = assert_envelope(response, required_keys=("data",))
    assert isinstance((payload.get("data") or {}).get("list"), list)
    assert isinstance((payload.get("data") or {}).get("total"), int)
