"""跨平台通用响应断言。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from framework.http.client import ApiClient


def assert_envelope(response: Any, *, expected_http: int = 200, expected_code: int = 0, required_keys: Iterable[str] = ()) -> dict[str, Any]:
    payload = ApiClient.json(response)
    assert response.status_code == expected_http, f"HTTP 状态异常: {response.status_code}, body={payload}"
    if "code" in payload:
        assert payload.get("code") == expected_code, f"业务码异常: {payload}"
    missing = [key for key in required_keys if key not in payload]
    assert not missing, f"响应缺少字段 {missing}: {payload}"
    return payload
