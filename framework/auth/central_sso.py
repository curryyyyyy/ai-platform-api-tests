"""总平台 SSO：获取 RSA 公钥、加密密码并换取统一 Token。"""

from __future__ import annotations

from typing import Any

from framework.http.client import ApiClient
from framework.auth.crypto import rsa_encrypt


class CentralSSO:
    def __init__(self, base_url: str, rsa_path: str, login_path: str, timeout: float = 10.0, retries: int = 1):
        self.client = ApiClient(base_url, timeout=timeout, retries=retries)
        self.rsa_path = rsa_path
        self.login_path = login_path

    def login(self, username: str, password: str) -> str:
        rsa_response = self.client.get(self.rsa_path)
        rsa_payload = self.client.json(rsa_response)
        if rsa_response.status_code != 200:
            raise AssertionError(f"总平台 RSA 接口 HTTP 状态异常: {rsa_response.status_code} {rsa_payload}")
        if "code" in rsa_payload and rsa_payload.get("code") != 0:
            raise AssertionError(f"总平台 RSA 接口业务失败: {rsa_payload}")
        data = rsa_payload.get("data") if isinstance(rsa_payload.get("data"), dict) else {}
        public_key = data.get("rsa") or data.get("publicKey") or data.get("public_key")
        if not isinstance(public_key, str) or not public_key.strip():
            raise AssertionError(f"总平台 RSA 响应缺少公钥: {rsa_payload}")

        response = self.client.post(
            self.login_path,
            json={"username": username, "password": rsa_encrypt(public_key, password)},
        )
        payload = self.client.json(response)
        if response.status_code not in {200, 201}:
            raise AssertionError(f"总平台登录 HTTP 状态异常: {response.status_code} {payload}")
        if "code" in payload and payload.get("code") != 0:
            raise AssertionError(f"总平台登录业务失败: {payload}")
        login_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        token = (
            login_data.get("token")
            or login_data.get("accessToken")
            or login_data.get("access_token")
            or payload.get("token")
            or payload.get("accessToken")
            or payload.get("access_token")
        )
        if not token:
            raise AssertionError(f"总平台登录响应缺少 token/accessToken: {payload}")
        return str(token)
