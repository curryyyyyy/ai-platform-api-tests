from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
import requests

from framework.http.client import ApiClient


@pytest.mark.contract
def test_api_client_reuses_a_session_for_no_retry_requests(monkeypatch) -> None:
    client = ApiClient("https://example.test/api/v1", retries=0)
    sessions: list[requests.Session] = []

    original = requests.Session.request

    def record(session, method, url, **kwargs):
        sessions.append(session)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(requests.Session, "request", record)
    try:
        client.get("/api/v1/probe", _retry=False)
        client.get("/api/v1/probe", _retry=False)
    finally:
        client.close()
        monkeypatch.setattr(requests.Session, "request", original)

    assert len(sessions) == 2
    assert sessions[0] is sessions[1]
    assert sessions[0] is not client.session


@pytest.mark.contract
def test_api_client_close_is_idempotent_and_rejects_new_requests(monkeypatch) -> None:
    client = ApiClient("https://example.test")
    close_calls: list[object] = []
    monkeypatch.setattr(client.session, "close", lambda: close_calls.append("main"))

    client.close()
    client.close()

    assert close_calls == ["main"]
    with pytest.raises(RuntimeError, match="已关闭"):
        client.get("/health")


@pytest.mark.contract
def test_api_client_accepts_split_connect_and_read_timeout(monkeypatch) -> None:
    client = ApiClient("https://example.test", timeout=(1.5, 7.5), retries=0)
    captured: dict[str, object] = {}

    def record(method, url, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(client.session, "request", record)
    client.get("/health")

    assert captured["timeout"] == (1.5, 7.5)
    client.close()


@pytest.mark.contract
def test_api_client_logs_actual_retry_count(monkeypatch, caplog) -> None:
    client = ApiClient("https://example.test", retries=0)
    response = SimpleNamespace(
        status_code=200,
        raw=SimpleNamespace(retries=SimpleNamespace(history=(object(), object()))),
    )
    monkeypatch.setattr(client.session, "request", lambda *args, **kwargs: response)

    with caplog.at_level(logging.DEBUG, logger="framework.http.client"):
        client.get("/health")

    assert "retries=2" in caplog.text
    client.close()
