from __future__ import annotations

from types import SimpleNamespace

import pytest

from framework.assertions import assert_envelope, assert_rejected


@pytest.mark.contract
def test_assert_envelope_requires_business_code() -> None:
    response = SimpleNamespace(status_code=200, json=lambda: {"data": {}})

    with pytest.raises(AssertionError, match="业务码 code"):
        assert_envelope(response)


@pytest.mark.contract
def test_assert_envelope_allows_explicit_failure_code() -> None:
    response = SimpleNamespace(status_code=200, json=lambda: {"code": 1, "message": "rejected"})

    body = assert_envelope(response, expected_code=None)

    assert body["code"] == 1


@pytest.mark.contract
@pytest.mark.parametrize(
    "payload",
    [
        {"code": 1, "message": "", "data": {}},
        {"code": 1, "message": "操作成功"},
        {"code": 1, "message": "批次已删除，后续不再发送结束异常告警"},
        {"code": 1, "message": "资源不存在", "data": {"id": 1}},
    ],
)
def test_assert_rejected_does_not_accept_ambiguous_or_success_like_errors(payload) -> None:
    response = SimpleNamespace(status_code=200, json=lambda: payload)

    with pytest.raises(AssertionError):
        assert_rejected(
            response,
            forbidden_messages=("success", "批次已删除，后续不再发送结束异常告警"),
        )


@pytest.mark.contract
def test_assert_rejected_accepts_non_empty_business_error() -> None:
    response = SimpleNamespace(status_code=200, json=lambda: {"code": 1, "message": "资源不存在"})

    body = assert_rejected(response, forbidden_messages=("success",))

    assert body["code"] == 1
