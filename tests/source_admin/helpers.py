"""资源管理平台 live 测试的动态资源解析辅助函数。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import pytest

from framework.assertions import assert_envelope


def data(body: Mapping[str, Any]) -> Any:
    value = body.get("data")
    if isinstance(value, Mapping) and set(value) == {"data"}:
        return value["data"]
    return value


def required_collection_id(client, env_name: str = "SOURCE_ADMIN_COLLECTION_ID") -> int:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return int(configured)
    body = assert_envelope(client.list_collections(limit=1, offset=0), required_keys=("data",))
    listing = data(body)
    collections = listing.get("collections", []) if isinstance(listing, Mapping) else []
    if not collections:
        pytest.skip("当前环境没有可用圈选集，需先准备资源管理平台测试数据")
    return int(collections[0]["id"])


def required_schema(client) -> tuple[int, str]:
    body = assert_envelope(client.list_schemas(page=1, page_size=20), required_keys=("data",))
    schemas = data(body)
    if not isinstance(schemas, list) or not schemas:
        pytest.skip("当前环境没有可用 Schema")
    schema = schemas[0]
    return int(schema["id"]), str(schema["name"])


def required_root_node_id() -> int:
    return int(os.getenv("SOURCE_ADMIN_ROOT_NODE_ID", "1"))
