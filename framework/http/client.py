"""统一 HTTP 客户端，支持带路径前缀的服务地址。"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from framework.types import ResponseEnvelope, Timeout

LOG = logging.getLogger(__name__)


def _retry_count(response: requests.Response) -> int:
    retries = getattr(getattr(response, "raw", None), "retries", None)
    history = getattr(retries, "history", ())
    return len(history) if history is not None else 0


class ApiClient:
    def __init__(self, base_url: str, token: str = "", timeout: Timeout = 10.0, retries: int = 1):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self._direct_session: requests.Session | None = None
        self._closed = False
        self.session.headers.update({"Accept": "application/json"})
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        if retries:
            retry = Retry(
                total=retries,
                connect=retries,
                read=retries,
                backoff_factor=0.2,
                status_forcelist=(502, 503, 504),
                allowed_methods=frozenset({"GET", "HEAD"}),
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if self._closed:
            raise RuntimeError("ApiClient 已关闭，不能继续发起请求")
        retry_request = kwargs.pop("_retry", True)
        request_path = "/" + path.lstrip("/")
        base_path = urlparse(self.base_url).path.rstrip("/")
        if base_path.endswith("/api/v1") and request_path == "/api/v1":
            request_path = "/"
        elif base_path.endswith("/api/v1") and request_path.startswith("/api/v1/"):
            request_path = request_path[len("/api/v1"):]
        url = urljoin(self.base_url + "/", request_path.lstrip("/"))
        kwargs.setdefault("timeout", self.timeout)
        started = time.monotonic()
        LOG.debug("request method=%s path=%s retry=%s", method.upper(), path, retry_request)
        if retry_request:
            response = self.session.request(method.upper(), url, **kwargs)
        else:
            # Discovery/probing requests should not inherit the session adapter's
            # retry policy, but must still reuse a Session and its connection pool.
            if self._direct_session is None:
                self._direct_session = requests.Session()
                self._direct_session.headers.update(self.session.headers)
            response = self._direct_session.request(method.upper(), url, **kwargs)
        elapsed_ms = (time.monotonic() - started) * 1000
        LOG.debug(
            "response method=%s path=%s status=%s elapsed_ms=%.1f retries=%s",
            method.upper(),
            path,
            response.status_code,
            elapsed_ms,
            _retry_count(response),
        )
        return response

    def close(self) -> None:
        """关闭连接池；可重复调用，便于由 session fixture 统一清理。"""
        if self._closed:
            return
        self.session.close()
        if self._direct_session is not None:
            self._direct_session.close()
        self._closed = True

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    @staticmethod
    def json(response: requests.Response) -> ResponseEnvelope:
        try:
            value = response.json()
        except ValueError as exc:
            raise AssertionError(
                f"响应不是 JSON: status={response.status_code}, body={response.text[:500]}"
            ) from exc
        if not isinstance(value, dict):
            raise AssertionError(f"响应 JSON 顶层应为对象，实际为 {type(value).__name__}")
        return value
