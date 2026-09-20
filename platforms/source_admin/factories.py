"""资源管理平台测试数据工厂。"""

from __future__ import annotations

import time
from typing import Any, Mapping

from framework.assertions import assert_envelope
from framework.data.dataset import dataset_defaults
from framework.data.scope import DataScope
from platforms.source_admin.client import SourceAdminClient


def _payload_data(body: Mapping[str, Any]) -> Any:
    """兼容当前服务 Wrap 产生的 ``data.data`` 和文档中的 ``data``。"""
    value = body.get("data")
    if isinstance(value, Mapping) and set(value) == {"data"}:
        return value["data"]
    return value


def _resource_id(body: Mapping[str, Any], resource_name: str) -> str:
    value = _payload_data(body)
    if isinstance(value, Mapping) and value.get("id") is not None:
        return str(value["id"])
    raise AssertionError(f"创建 {resource_name} 响应缺少 id: {body}")


def make_schema(scope: DataScope, **overrides: Any) -> dict[str, Any]:
    payload = dataset_defaults("source_admin", "schema")
    payload["name"] = scope.unique_name("schema", max_length=48)
    payload.update(overrides)
    return payload


def make_schema_field(scope: DataScope, *, schema_id: int | str, **overrides: Any) -> dict[str, Any]:
    payload = dataset_defaults("source_admin", "schema_field")
    payload["schema_id"] = int(schema_id)
    payload["qualifier"] = scope.unique_name("field", max_length=32).replace("-", "_")
    payload.update(overrides)
    return payload


def make_folder(scope: DataScope, *, parent_id: int | str, **overrides: Any) -> dict[str, Any]:
    payload = dataset_defaults("source_admin", "node")
    for key in ("root_id", "missing_node_id", "missing_parent_id"):
        payload.pop(key, None)
    payload["name"] = scope.unique_name("folder", max_length=48)
    payload["parent_id"] = int(parent_id)
    payload.update(overrides)
    return payload


def make_project_node(scope: DataScope, **overrides: Any) -> dict[str, Any]:
    payload = {"node_name": scope.unique_name("project", max_length=48)}
    payload.update(overrides)
    return payload


def make_share_link(scope: DataScope, *, collection_id: int | str, **overrides: Any) -> dict[str, Any]:
    payload = dataset_defaults("source_admin", "share")
    payload["name"] = scope.unique_name("share", max_length=48)
    payload["collection_id"] = int(collection_id)
    payload["expire_at"] = int(time.time() * 1000) + 60 * 60 * 1000
    payload.update(overrides)
    return payload


def make_collection_from_rowkeys(
    scope: DataScope,
    *,
    parent_node_id: int | str,
    source_collection_id: int | str,
    rowkeys: list[str],
    **overrides: Any,
) -> dict[str, Any]:
    payload = {
        "parent_node_id": int(parent_node_id),
        "name": scope.unique_name("rowkey-collection", max_length=48),
        "cid": int(source_collection_id),
        "rowkeys": rowkeys,
    }
    payload.update(overrides)
    return payload


def _collection_node_id(body: Mapping[str, Any], *, expected_name: str) -> str:
    value = _payload_data(body)
    path = value.get("path") if isinstance(value, Mapping) else None
    if not isinstance(path, list) or not path:
        raise AssertionError(f"圈选集节点路径为空，无法登记清理: {body}")
    node = path[-1]
    if not isinstance(node, Mapping) or node.get("id") is None:
        raise AssertionError(f"圈选集节点路径末尾缺少 node.id: {body}")
    if node.get("name") != expected_name:
        raise AssertionError(
            f"圈选集节点路径末尾不是新建集合节点: expected={expected_name!r}, body={body}"
        )
    return str(node["id"])


class SourceAdminDataFactory:
    """创建资源并将逆序清理动作登记到单条用例的 DataScope。"""

    def __init__(self, client: SourceAdminClient, scope: DataScope):
        self.client = client
        self.scope = scope

    def create_schema(self, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_schema(self.scope, **overrides)
        body = assert_envelope(self.client.create_schema(**payload), required_keys=("data",))
        schema_id = _resource_id(body, "Schema")
        self.scope.track(f"删除 Schema {schema_id}", lambda: self._delete_schema(schema_id))
        return schema_id, payload

    def _delete_schema(self, schema_id: str) -> None:
        assert_envelope(self.client.delete_schema(schema_id))

    def create_schema_field(self, *, schema_id: int | str, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_schema_field(self.scope, schema_id=schema_id, **overrides)
        body = assert_envelope(self.client.create_schema_field(**payload), required_keys=("data",))
        field_id = _resource_id(body, "Schema 字段")
        self.scope.track(f"删除 Schema 字段 {field_id}", lambda: self._delete_schema_field(field_id))
        return field_id, payload

    def _delete_schema_field(self, field_id: str) -> None:
        assert_envelope(self.client.delete_schema_field(field_id))

    def create_folder(self, *, parent_id: int | str, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_folder(self.scope, parent_id=parent_id, **overrides)
        body = assert_envelope(self.client.create_node(**payload), required_keys=("data",))
        value = _payload_data(body)
        node = value.get("node") if isinstance(value, Mapping) else value
        if not isinstance(node, Mapping) or node.get("id") is None:
            raise AssertionError(f"创建文件夹响应缺少 node.id: {body}")
        node_id = str(node["id"])
        self.scope.track(f"删除文件夹节点 {node_id}", lambda: self._delete_node(node_id))
        return node_id, payload

    def _delete_node(self, node_id: str) -> None:
        assert_envelope(self.client.delete_node(node_id))

    def create_collection_from_rowkeys(
        self,
        *,
        parent_node_id: int | str,
        source_collection_id: int | str,
        rowkeys: list[str],
        **overrides: Any,
    ) -> tuple[str, dict[str, Any], Mapping[str, Any]]:
        payload = make_collection_from_rowkeys(
            self.scope,
            parent_node_id=parent_node_id,
            source_collection_id=source_collection_id,
            rowkeys=rowkeys,
            **overrides,
        )
        body = assert_envelope(
            self.client.create_collection_from_rowkeys(**payload), required_keys=("data",)
        )
        value = _payload_data(body)
        if not isinstance(value, Mapping) or value.get("collection_id") is None:
            raise AssertionError(f"创建 rowkeys 圈选集响应缺少 collection_id: {body}")
        collection_id = str(value["collection_id"])

        path_body = assert_envelope(
            self.client.get_collection_node_path(collection_id), required_keys=("data",)
        )
        node_id = _collection_node_id(path_body, expected_name=str(payload["name"]))
        self.scope.track(f"删除 rowkeys 圈选集节点 {node_id}", lambda: self._delete_node(node_id))
        return collection_id, payload, value

    def create_project_node(self, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_project_node(self.scope, **overrides)
        body = assert_envelope(self.client.create_project_node(**payload), required_keys=("data",))
        value = _payload_data(body)
        if not isinstance(value, Mapping) or value.get("node_id") is None:
            raise AssertionError(f"创建项目节点响应缺少 node_id: {body}")
        node_id = str(value["node_id"])
        self.scope.track(f"删除项目节点 {node_id}", lambda: self._delete_node(node_id))
        return node_id, payload

    def create_share_link(self, *, collection_id: int | str, **overrides: Any) -> tuple[str, dict[str, Any]]:
        payload = make_share_link(self.scope, collection_id=collection_id, **overrides)
        body = assert_envelope(self.client.create_share_link(**payload), required_keys=("data",))
        link_id = _resource_id(body, "分享链接")
        self.scope.track(f"终止分享链接 {link_id}", lambda: self._terminate_share_link(link_id))
        return link_id, payload

    def _terminate_share_link(self, link_id: str) -> None:
        assert_envelope(self.client.terminate_share_link(link_id))
