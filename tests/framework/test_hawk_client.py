from __future__ import annotations

from types import SimpleNamespace

import pytest

from platforms.hawk_admin.client import HawkAdminClient


class FakeHawkClient(HawkAdminClient):
    def __init__(self, bodies: list[dict]):
        super().__init__("http://hawk.invalid", retries=0)
        self.bodies = iter(bodies)
        self.calls = 0

    def operate_batch(self, batch_id, operation):
        self.calls += 1
        body = next(self.bodies)
        return SimpleNamespace(status_code=200, json=lambda: body, text=str(body))


@pytest.mark.contract
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


@pytest.mark.contract
def test_operate_batch_with_retry_does_not_retry_other_business_errors(monkeypatch):
    client = FakeHawkClient([{"code": 1, "message": "invalid operation"}])
    monkeypatch.setattr("platforms.hawk_admin.client.time.sleep", lambda _: pytest.fail("不应等待"))

    response = client.operate_batch_with_retry(123, 3, retries=2)

    assert client.calls == 1
    assert client.json(response)["message"] == "invalid operation"
