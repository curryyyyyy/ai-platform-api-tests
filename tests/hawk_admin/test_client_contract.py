from __future__ import annotations

import inspect
import json
from typing import Any

import pytest
from requests import Response

from platforms.hawk_admin.client import HawkAdminClient


pytestmark = [pytest.mark.contract, pytest.mark.hawk_admin]


def _json_response(body: dict[str, Any]) -> Response:
    response = Response()
    response.status_code = 200
    response._content = json.dumps(body).encode("utf-8")
    return response


class FakeHawkClient(HawkAdminClient):
    def __init__(self, bodies: list[dict[str, Any]]):
        super().__init__("http://hawk.invalid", retries=0)
        self.bodies = iter(bodies)
        self.calls = 0

    def operate_batch(self, batch_id: int, operation: int) -> Response:
        self.calls += 1
        body = next(self.bodies)
        return _json_response(body)


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
    assert response is not None
    assert client.json(response)["code"] == 0


def test_operate_batch_with_retry_does_not_retry_other_business_errors(monkeypatch):
    client = FakeHawkClient([{"code": 1, "message": "invalid operation"}])
    monkeypatch.setattr("platforms.hawk_admin.client.time.sleep", lambda _: pytest.fail("不应等待"))

    response = client.operate_batch_with_retry(123, 3, retries=2)

    assert client.calls == 1
    assert response is not None
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
    cases = dataset_cases("hawk_admin", "transfer_task", "actions")

    for case in cases:
        method_name = case.get("client_method")
        assert isinstance(method_name, str) and method_name.strip()
        method = getattr(client, method_name, None)
        assert callable(method), f"transfer_task/actions 引用了不存在的方法: {method_name}"
        if "step_no" in case:
            assert "step_no" in inspect.signature(method).parameters


def test_project_favorite_and_template_lifecycle_routes_match_openapi(monkeypatch):
    """新增接口必须保留 OpenAPI 的 HTTP 方法、路径和请求体形状。"""
    client = HawkAdminClient("http://hawk.invalid", retries=0)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def record(method: str):
        def request(path: str, **kwargs: Any) -> None:
            calls.append((method, path, kwargs))

        return request

    monkeypatch.setattr(client, "get", record("GET"))
    monkeypatch.setattr(client, "post", record("POST"))
    monkeypatch.setattr(client, "put", record("PUT"))
    monkeypatch.setattr(client, "delete", record("DELETE"))

    client.list_projects(page=2, page_size=5, onlyFavorite=True)
    client.favorite_project(42)
    client.unfavorite_project(42)
    client.batch_get_templates([7, 8])
    client.create_empty_template(name="workflow", description="description")
    client.complete_template(7, tplId=8, info={"name": "workflow"})
    client.done_end_allow_empty_output(9)
    client.list_template_ownership_options()
    client.list_flows_by_project(page=1, pageSize=10, projectId="7")
    client.list_flow_versions(8)
    client.save_flow_draft(8, expected_graph_version=1, graph='{"nodes":[],"edges":[]}')
    client.delete_flow_draft(8)
    client.publish_flow_draft(8)

    assert calls == [
        ("GET", "/api/v1/project", {"params": {"page": 2, "pageSize": 5, "onlyFavorite": True}}),
        ("POST", "/api/v1/project/42/favorite", {"json": {"id": 42}}),
        ("DELETE", "/api/v1/project/42/favorite", {}),
        ("POST", "/api/v1/tpl/wf/batch-get", {"json": {"ids": [7, 8]}}),
        (
            "POST",
            "/api/v1/tpl/wf/empty",
            {"json": {"name": "workflow", "description": "description"}},
        ),
        (
            "POST",
            "/api/v1/tpl/wf/7/complete",
            {"json": {"id": 7, "tplId": 8, "info": {"name": "workflow"}}},
        ),
        ("POST", "/api/v1/hawk/done-end-alert/allow-empty-output/9", {"json": {"batchId": 9}}),
        ("GET", "/api/v1/tpl/ownership-options", {}),
        ("GET", "/api/v1/flow/project/list", {"params": {"page": 1, "pageSize": 10, "projectId": "7"}}),
        ("GET", "/api/v1/flow/draft/8/versions", {}),
        ("PUT", "/api/v1/flow/draft/8", {"json": {"draftId": 8, "expectedGraphVersion": 1, "graph": '{"nodes":[],"edges":[]}'}}),
        ("DELETE", "/api/v1/flow/draft/8", {}),
        ("POST", "/api/v1/flow/draft/8/publish", {"json": {"draftId": 8}}),
    ]
