"""跨平台通用响应断言。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from framework.http.client import ApiClient


def assert_envelope(response: Any, *, expected_http: int = 200, expected_code: int | None = 0, required_keys: Iterable[str] = ()) -> dict[str, Any]:
    """校验响应信封。

    `expected_code=None` 表示跳过业务码校验，供"异常输入应被拒绝"的反向用例使用。
    """
    payload = ApiClient.json(response)
    assert response.status_code == expected_http, f"HTTP 状态异常: {response.status_code}, body={payload}"
    assert "code" in payload, f"响应缺少业务码 code: {payload}"
    if expected_code is not None:
        assert payload.get("code") == expected_code, f"业务码异常: {payload}"
    missing = [key for key in required_keys if key not in payload]
    assert not missing, f"响应缺少字段 {missing}: {payload}"
    return payload
