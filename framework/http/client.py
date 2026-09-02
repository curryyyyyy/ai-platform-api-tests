"""统一 HTTP 客户端，支持带路径前缀的服务地址。"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOG = logging.getLogger(__name__)


class ApiClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 10.0, retries: int = 1):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
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
        request_path = "/" + path.lstrip("/")
        base_path = urlparse(self.base_url).path.rstrip("/")
        if base_path.endswith("/api/v1") and request_path == "/api/v1":
            request_path = "/"
        elif base_path.endswith("/api/v1") and request_path.startswith("/api/v1/"):
            request_path = request_path[len("/api/v1"):]
        url = urljoin(self.base_url + "/", request_path.lstrip("/"))
        kwargs.setdefault("timeout", self.timeout)
        LOG.debug("%s %s", method.upper(), url)
        response = self.session.request(method.upper(), url, **kwargs)
        LOG.debug("response status=%s", response.status_code)
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    @staticmethod
    def json(response: requests.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError as exc:
            raise AssertionError(
                f"响应不是 JSON: status={response.status_code}, body={response.text[:500]}"
            ) from exc
        if not isinstance(value, dict):
            raise AssertionError(f"响应 JSON 顶层应为对象，实际为 {type(value).__name__}")
        return value
