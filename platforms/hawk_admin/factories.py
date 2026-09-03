"""机器标注平台测试数据工厂。"""

from __future__ import annotations

from typing import Any

import pytest

from framework.data.dataset import dataset_defaults
from framework.data.scope import DataScope
from platforms.hawk_admin.client import HawkAdminClient


def make_project(scope: DataScope, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = dataset_defaults("hawk_admin", "project")
    payload["name"] = scope.unique_name("project", max_length=64)
    payload.update(overrides)
    return payload


def make_stage(scope: DataScope, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = dataset_defaults("hawk_admin", "stage")
    payload["name"] = scope.unique_name("stage", max_length=48)
    payload.update(overrides)
    return payload


def make_flow(scope: DataScope, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = dataset_defaults("hawk_admin", "flow")
    payload["flowName"] = scope.unique_name("flow", max_length=48)
    payload.update(overrides)
    return payload


class HawkDataFactory:
    def __init__(self, client: HawkAdminClient, scope: DataScope):
        self.client = client
        self.scope = scope

    def create_project(self, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_project(self.scope, **overrides)
        response = self.client.create_project(**payload)
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
        response = self.client.delete_project(project_id)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"删除测试项目失败: {response.status_code} {body}")

    def create_stage(self, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_stage(self.scope, **overrides)
        response = self.client.create_stage(**payload)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"创建测试阶段失败: {response.status_code} {body}")
        stage_id = body.get("id") or (body.get("data") or {}).get("id")
        if not stage_id:
            raise AssertionError(f"创建阶段响应缺少 id: {body}")
        self.scope.track(f"删除阶段 {stage_id}", lambda: self._delete_stage(str(stage_id)))
        return str(stage_id), payload

    def _delete_stage(self, stage_id: str) -> None:
        response = self.client.delete_stage(stage_id)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"删除测试阶段失败: {response.status_code} {body}")

    def create_flow(self, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_flow(self.scope, **overrides)
        response = self.client.create_flow(**payload)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            if body.get("code") == 1 and body.get("message") == "数据库操作失败":
                pytest.skip(
                    "Hawk 流程创建依赖的 flow 数据库 schema 不可用（接口返回‘数据库操作失败’）；"
                    "请先执行服务端 flow 表/字段迁移，或使用已有流程运行批次用例"
                )
            raise AssertionError(f"创建测试流程失败: {response.status_code} {body}")
        flow_id = body.get("id") or (body.get("data") or {}).get("id")
        if not flow_id:
            raise AssertionError(f"创建流程响应缺少 id: {body}")
        self.scope.track(f"删除流程 {flow_id}", lambda: self._delete_flow(str(flow_id)))
        return str(flow_id), payload

    def _delete_flow(self, flow_id: str) -> None:
        response = self.client.delete_flow(flow_id)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"删除测试流程失败: {response.status_code} {body}")

    def create_batch(self, *, project_id: str, flow_name: str, input_file_path: str, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = dataset_defaults("hawk_admin", "batch")
        payload.update({
            "name": self.scope.unique_name("batch", max_length=48),
            "projectId": int(project_id),
            "flowName": flow_name,
            "inputFilePath": input_file_path,
        })
        payload.update(overrides)
        response = self.client.create_batch(**payload)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"创建测试批次失败: {response.status_code} {body}")
        batch_id = body.get("id") or (body.get("data") or {}).get("id")
        if not batch_id:
            raise AssertionError(f"创建批次响应缺少 id: {body}")
        self.scope.track(f"删除批次 {batch_id}", lambda: self._delete_batch(str(batch_id)))
        return str(batch_id), payload

    def _delete_batch(self, batch_id: str) -> None:
        response = self.client.delete_batch(batch_id)
        body = self.client.json(response)
        if response.status_code != 200 or body.get("code") != 0:
            raise AssertionError(f"删除测试批次失败: {response.status_code} {body}")
