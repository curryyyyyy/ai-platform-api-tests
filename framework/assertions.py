"""跨平台通用响应断言。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from framework.http.client import ApiClient


_SUCCESS_LIKE_MESSAGES = (
    "success",
    "操作成功",
    "执行成功",
    "请求成功",
    "批次已删除，后续不再发送结束异常告警",
    "批次已回退到已完成",
)


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


def assert_rejected(
    response: Any,
    *,
    expected_http: int = 200,
    forbidden_messages: Iterable[str] = (),
    allow_error_data: bool = False,
) -> dict[str, Any]:
    """严格校验非法请求确实被业务层拒绝。

    HTTP 200 是本平台的统一传输约定，不能作为成功证据。负向用例必须同时
    返回非零业务码和非空错误消息；错误响应也不能夹带非空的成功数据或已知
    成功文案，否则会把接口的伪成功判成通过。
    """
    body = assert_envelope(response, expected_http=expected_http, expected_code=None)
    assert body["code"] != 0, f"非法或不存在资源请求未被拒绝: {body}"

    # Hawk 的旧接口使用 message，资源管理等新接口使用统一信封的 msg。
    message = body.get("message") or body.get("msg")
    assert isinstance(message, str) and message.strip(), (
        f"拒绝响应缺少有效错误消息: {body}"
    )

    if "data" in body and not allow_error_data:
        data = body["data"]

        def is_empty(value: Any) -> bool:
            if value in (None, {}, [], ""):
                return True
            if isinstance(value, dict):
                return all(is_empty(item) for item in value.values())
            if isinstance(value, list):
                return all(is_empty(item) for item in value)
            return False

        assert is_empty(data), f"拒绝响应携带非空 data: {body}"

    normalized = message.casefold()
    for forbidden in (*_SUCCESS_LIKE_MESSAGES, *forbidden_messages):
        assert forbidden.casefold() not in normalized, (
            f"拒绝响应返回了不相关的成功文案 {message!r}: {body}"
        )
    return body
