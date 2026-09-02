"""机器标注平台测试数据工厂。"""

from __future__ import annotations

from typing import Any

from framework.data.scope import DataScope
from framework.http.client import ApiClient


def make_project(scope: DataScope, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": scope.unique_name("project", max_length=64)}
    payload.update(overrides)
    return payload


class HawkDataFactory:
    def __init__(self, client: ApiClient, scope: DataScope):
        self.client = client
        self.scope = scope

    def create_project(self, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_project(self.scope, **overrides)
        response = self.client.post("/api/v1/project", json=payload)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"创建测试项目失败: {response.status_code} {body}")
        project_id = body.get("id") or (body.get("data") or {}).get("id")
        if not project_id:
            raise AssertionError(f"创建项目响应缺少 id: {body}")
        self.scope.track(
            f"删除项目 {project_id}",
            lambda: self._delete_project(str(project_id)),
        )
        return str(project_id), payload

    def _delete_project(self, project_id: str) -> None:
        response = self.client.delete(f"/api/v1/project/{project_id}")
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"删除测试项目失败: {response.status_code} {body}")
