from __future__ import annotations

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import dataset_defaults

pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
AUTH_DEFAULTS = dataset_defaults("hawk_admin", "auth")


@pytest.mark.smoke
def test_hawk_project_requires_token(anonymous_platform_client) -> None:
    """缺少 Token 访问 Hawk 接口：未携带 Authorization 应返回 401/403。"""
    response = anonymous_platform_client.get("/api/v1/project")
    assert response.status_code == 401, f"未携带 Token 时应返回 HTTP 401: {response.status_code}"

@pytest.mark.smoke
def test_hawk_invalid_token_rejected(anonymous_platform_client) -> None:
    """使用数据集中的无效 Token 访问 Hawk 接口：应返回 401/403。"""
    response = anonymous_platform_client.get(
        "/api/v1/project", headers={"Authorization": f"Bearer {AUTH_DEFAULTS['invalidToken']}"}
    )
    assert response.status_code == 401, f"无效 Token 时应返回 HTTP 401: {response.status_code}"


@pytest.mark.smoke
def test_hawk_user_rsa_is_public(anonymous_platform_client) -> None:
    """获取 RSA 公钥：无需鉴权即可访问，data.rsa 应为字符串（登录链路第 1 步）。"""
    payload = assert_envelope(anonymous_platform_client.get("/api/v1/user/rsa"), required_keys=("data",))
    rsa = (payload.get("data") or {}).get("rsa")
    assert isinstance(rsa, str) and rsa.strip(), "RSA 公钥不能为空"


@pytest.mark.smoke
@pytest.mark.core
def test_hawk_authenticated_project_list(platform_client) -> None:
    """总平台登录后访问 Hawk 项目列表：鉴权通过且返回 data.list / data.total 分页结构。"""
    response = platform_client.list_projects()
    payload = assert_envelope(response, required_keys=("data",))
    assert isinstance((payload.get("data") or {}).get("list"), list)
    assert isinstance((payload.get("data") or {}).get("total"), int)


def test_hawk_09_01_user_auth_accepts_central_token(platform_client, central_token):
    body = assert_envelope(platform_client.user_auth(token=central_token), required_keys=("data",))
    assert isinstance(body["data"], dict)


def test_hawk_09_02_user_rsa_returns_public_key(anonymous_platform_client):
    body = assert_envelope(anonymous_platform_client.get("/api/v1/user/rsa"), required_keys=("data",))
    rsa = body["data"].get("rsa")
    assert isinstance(rsa, str) and rsa.strip()


def test_hawk_09_03_user_login_rejects_empty_credentials(platform_client):
    assert_rejected(platform_client.user_login())


def test_hawk_09_04_user_logout_invalid_token_is_idempotent(platform_client, central_token):
    body = assert_envelope(platform_client.user_logout(token=AUTH_DEFAULTS["invalidUserToken"]))
    assert body.get("data") in (None, {}, [], "")
    auth_body = assert_envelope(platform_client.user_auth(token=central_token), required_keys=("data",))
    assert isinstance(auth_body["data"], dict)
