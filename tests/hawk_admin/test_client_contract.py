from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any, cast

import pytest
from requests import Response

from platforms.hawk_admin.client import HawkAdminClient


pytestmark = [pytest.mark.contract, pytest.mark.hawk_admin]


class FakeHawkClient(HawkAdminClient):
    def __init__(self, bodies: list[dict[str, Any]]):
        super().__init__("http://hawk.invalid", retries=0)
        self.bodies = iter(bodies)
        self.calls = 0

    def operate_batch(self, batch_id: int, operation: int) -> Response:
        self.calls += 1
        body = next(self.bodies)
        return cast(Response, SimpleNamespace(status_code=200, json=lambda: body, text=str(body)))


def test_operate_batch_with_retry_retries_transient_node_lock(monkeypatch):
    client = FakeHawkClient([
        {"code": 1, "message": "lock already taken, locked nodes: [0]"},
        {"code": 0, "message": "success"},
    ])
    sleeps: list[float] = []
    monkeypatch.setattr("platforms.hawk_admin.client.time.sleep", sleeps.append)

    response = client.operate_batch_with_retry(123, 3, retries=2, backoff=0.1)

    assert client.calls == 2
    assert sleeps == [0.1]
    assert client.json(response)["code"] == 0


def test_operate_batch_with_retry_does_not_retry_other_business_errors(monkeypatch):
    client = FakeHawkClient([{"code": 1, "message": "invalid operation"}])
    monkeypatch.setattr("platforms.hawk_admin.client.time.sleep", lambda _: pytest.fail("不应等待"))

    response = client.operate_batch_with_retry(123, 3, retries=2)

    assert client.calls == 1
    assert client.json(response)["message"] == "invalid operation"


def test_upload_file_sends_json_string_body(monkeypatch):
    """UploadFile 的 body 必须按 OpenAPI 绑定为字符串，不能退回对象。"""
    client = HawkAdminClient("http://hawk.invalid", retries=0)
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_post(path: str, **kwargs: Any) -> None:
        calls.append((path, kwargs))

    monkeypatch.setattr(client, "post", fake_post)

    client.upload_file()
    client.upload_file(payload="input.csv")

    assert calls == [
        ("/api/v1/batch/upload", {"json": ""}),
        ("/api/v1/batch/upload", {"json": "input.csv"}),
    ]


def test_transfer_action_dataset_methods_have_matching_client_signatures():
    """传输动作由 YAML 选择客户端方法，并校验步骤动作的 step_no 契约。"""
    from framework.data.dataset import dataset_cases

    client = HawkAdminClient("http://hawk.invalid", retries=0)
    cases = dataset_cases("hawk_admin", "extended", "transfer_actions")

    for case in cases:
        method_name = case.get("client_method")
        assert isinstance(method_name, str) and method_name.strip()
        method = getattr(client, method_name, None)
        assert callable(method), f"transfer_actions 引用了不存在的方法: {method_name}"
        if "step_no" in case:
            assert "step_no" in inspect.signature(method).parameters
