from __future__ import annotations

from typing import Any

import pytest
from requests import Response

from framework.data.scope import DataScope
from platforms.hawk_admin.client import HawkAdminClient
from platforms.hawk_admin.factories import HawkDataFactory


pytestmark = [pytest.mark.contract, pytest.mark.hawk_admin]


def _success_response() -> Response:
    response = Response()
    response.status_code = 200
    return response


def _response_with_body(body: dict[str, Any]) -> Response:
    response = _success_response()
    response._factory_body = body  # type: ignore[attr-defined]
    return response


class FakeClient(HawkAdminClient):
    """继承真实客户端保证类型一致，只重写请求出口以记录调用，不发起网络请求。"""

    def __init__(self) -> None:
        super().__init__("http://hawk.invalid", retries=0)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def post(self, path: str, **kwargs: Any) -> Response:
        self.calls.append(("POST", path, kwargs))
        return _success_response()

    def delete(self, path: str, **kwargs: Any) -> Response:
        self.calls.append(("DELETE", path, kwargs))
        return _success_response()

    @staticmethod
    def json(response: Response) -> dict[str, Any]:
        if hasattr(response, "_factory_body"):
            return response._factory_body  # type: ignore[attr-defined]
        return {"code": 0, "id": "project-1"} if response.status_code == 200 else {}


class FlowSchemaUnavailableClient(FakeClient):
    @staticmethod
    def json(response: Response) -> dict[str, Any]:
        return {"code": 1, "message": "数据库操作失败"}


class MissingFlowDraftClient(FakeClient):
    def delete(self, path: str, **kwargs: Any) -> Response:
        self.calls.append(("DELETE", path, kwargs))
        return _response_with_body({"code": 1, "message": "记录不存在"})


def test_hawk_factory_registers_project_cleanup() -> None:
    """工厂创建项目后应在 DataScope 登记删除动作，保证用例结束自动清理。"""
    client = FakeClient()
    scope = DataScope("TC-HAWK-PROJECT-001")
    factory = HawkDataFactory(client, scope)

    project_id, payload = factory.create_project(description="factory test")
    assert project_id == "project-1"
    assert payload["description"] == "factory test"

    scope.cleanup()
    assert [call[0:2] for call in client.calls] == [
        ("POST", "/api/v1/project"),
        ("DELETE", "/api/v1/project/project-1"),
    ]


def test_hawk_factory_fails_known_flow_schema_failure() -> None:
    """流程创建的数据库错误必须失败，不能被跳过掩盖。"""
    factory = HawkDataFactory(FlowSchemaUnavailableClient(), DataScope("TC-HAWK-FLOW-001"))

    with pytest.raises(AssertionError, match="创建测试流程失败"):
        factory.create_flow(projectId="1")


def test_hawk_factory_treats_missing_deleted_draft_as_cleaned() -> None:
    """用例主动删除草稿后，teardown 的重复删除应满足幂等清理。"""
    client = MissingFlowDraftClient()
    scope = DataScope("TC-HAWK-FLOW-DELETE-001")
    factory = HawkDataFactory(client, scope)

    flow_id, _ = factory.create_flow(projectId="1")
    scope.cleanup()

    assert ("DELETE", f"/api/v1/flow/draft/{flow_id}") == tuple(client.calls[-1][:2])
