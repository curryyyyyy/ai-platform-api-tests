"""资源管理平台 live 测试的动态资源解析辅助函数。"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Mapping
from typing import Any

import pytest

from framework.assertions import assert_envelope


def data(body: Mapping[str, Any]) -> Any:
    value = body.get("data")
    if isinstance(value, Mapping) and set(value) == {"data"}:
        return value["data"]
    return value


def assert_html_page(
    response: Any,
    *,
    expected_content_type: str = "text/html",
    expected_cache_control: str | None = None,
) -> None:
    """校验资源管理平台 HTML 页面响应，不套用 JSON 信封断言。"""
    assert response.status_code == 200, response.text[:500]
    content_type = response.headers.get("Content-Type", "").lower()
    assert expected_content_type.lower() in content_type
    if expected_cache_control is not None:
        assert response.headers.get("Cache-Control") == expected_cache_control
    assert response.content.strip()
    assert b"<html" in response.content.lower()


def statistics_query_data(response: Any) -> dict[str, Any]:
    """提取统计接口 ``data.query``，避免把其嵌套响应误当作普通 data。"""
    payload = data(assert_envelope(response, required_keys=("data",)))
    query = payload.get("query") if isinstance(payload, Mapping) else None
    if not isinstance(query, Mapping):
        raise AssertionError(f"统计响应缺少 data.query: {payload!r}")
    return dict(query)


def statistics_numeric_candidates(
    client: Any,
    *,
    collection_id_env: str = "SOURCE_ADMIN_STATISTICS_COLLECTION_ID",
) -> list[tuple[int, dict[str, str]]]:
    """发现可做数值聚合的圈选集和字段，不把共享集合 ID 写入测试代码。"""
    configured = os.getenv(collection_id_env, "").strip()
    collection_ids: list[int] = []
    if configured:
        try:
            collection_ids.append(int(configured))
        except ValueError:
            raise AssertionError(f"{collection_id_env} 必须是整数，当前值: {configured!r}") from None
    else:
        listing = data(assert_envelope(
            client.list_collections(limit=100, offset=0), required_keys=("data",)
        ))
        collections = listing.get("collections", []) if isinstance(listing, Mapping) else []
        if isinstance(collections, list):
            for item in collections:
                collection_id = item.get("id") if isinstance(item, Mapping) else None
                if isinstance(collection_id, int):
                    collection_ids.append(collection_id)

    schemas = data(assert_envelope(
        client.list_schemas(page=1, page_size=100), required_keys=("data",)
    ))
    schema_by_name: dict[str, int] = {}
    if isinstance(schemas, list):
        for schema in schemas:
            if not isinstance(schema, Mapping):
                continue
            name = schema.get("name")
            schema_id = schema.get("id")
            if isinstance(name, str) and isinstance(schema_id, int):
                schema_by_name[name] = schema_id
    candidates: list[tuple[int, dict[str, str]]] = []
    numeric_types = ("int", "float", "double", "decimal", "number", "long", "short")
    for collection_id in collection_ids:
        detail = data(assert_envelope(
            client.get_collection(collection_id), required_keys=("data",)
        ))
        collection = detail.get("collection") if isinstance(detail, Mapping) else None
        table_name = collection.get("table_name") if isinstance(collection, Mapping) else None
        if not isinstance(table_name, str):
            continue
        schema_id = schema_by_name.get(table_name)
        if schema_id is None:
            continue
        field_data = data(assert_envelope(
            client.list_schema_fields(
                schema_id=schema_id, page=1, page_size=1000, scene="search"
            ),
            required_keys=("data",),
        ))
        fields = field_data.get("list", []) if isinstance(field_data, Mapping) else []
        selection: dict[str, str] | None = None
        if isinstance(fields, list):
            for field in fields:
                if not isinstance(field, Mapping):
                    continue
                qualifier = field.get("qualifier")
                if (
                    isinstance(qualifier, str)
                    and field.get("status") == 1
                    and field.get("need_sync") == 1
                    and any(
                        type_name in str(field.get("type", "")).lower()
                        for type_name in numeric_types
                    )
                ):
                    selection = {"qualifier": qualifier, "operation": "avg"}
                    break
        if selection is not None:
            candidates.append((collection_id, selection))

    if not candidates:
        pytest.skip(
            "当前环境没有带已启用、已同步数值字段的统计候选圈选集；"
            f"可配置 {collection_id_env} 指向隔离圈选集"
        )
    return candidates


def wait_for_statistics_completion(
    client: Any,
    query_id: str,
    *,
    timeout_env: str = "SOURCE_ADMIN_STATISTICS_TIMEOUT",
    poll_interval_env: str = "SOURCE_ADMIN_STATISTICS_POLL_INTERVAL",
) -> dict[str, Any]:
    """有界轮询异步统计任务，完成时返回含分页预览的 query。"""
    timeout = max(float(os.getenv(timeout_env, "120")), 1.0)
    interval = min(max(float(os.getenv(poll_interval_env, "3")), 0.5), 10.0)
    deadline = time.monotonic() + timeout
    last_status = ""
    while time.monotonic() < deadline:
        query = statistics_query_data(
            client.get_selection_statistics(query_id, offset=0, limit=1)
        )
        last_status = str(query.get("status", ""))
        if last_status == "Completed":
            return query
        if last_status == "Failed":
            raise AssertionError(f"统计任务执行失败: {query}")
        time.sleep(interval)
    raise AssertionError(f"统计任务未在 {timeout:g} 秒内完成，最后状态: {last_status}")


def required_composite_schema(
    client: Any,
    *,
    table_env: str = "SOURCE_ADMIN_COMPOSITE_TABLE_NAME",
    node_type_env: str = "SOURCE_ADMIN_COMPOSITE_NODE_TYPE",
) -> tuple[str, int]:
    """发现一个能生成 node_type 隔离 SQL 的复合 Schema。

    环境变量仍可固定现场资源；未配置时以 Schema 列表和真实 SQL 结果为准，
    不在测试代码中维护复合类型到 node_type 的静态映射。
    """
    configured_table = os.getenv(table_env, "").strip()
    configured_node_type = os.getenv(node_type_env, "").strip()
    if configured_table or configured_node_type:
        if not configured_table or not configured_node_type:
            raise AssertionError(f"{table_env} 和 {node_type_env} 必须同时配置")
        try:
            return configured_table, int(configured_node_type)
        except ValueError:
            raise AssertionError(f"{node_type_env} 必须是整数: {configured_node_type!r}") from None

    schemas = data(assert_envelope(client.list_schemas(page=1, page_size=100), required_keys=("data",)))
    if not isinstance(schemas, list):
        raise AssertionError(f"Schema 列表 data 应为数组: {schemas!r}")
    for schema in schemas:
        if not isinstance(schema, Mapping) or not schema.get("name"):
            continue
        if schema.get("source_table") not in {"composite", "aigc_dataset_composite"}:
            continue
        table_name = str(schema["name"])
        response = client.build_selection_query(
            table_name=table_name,
            conditions={"logical_op": 1, "conditions": [], "groups": []},
            order_by=[],
        )
        body = client.json(response)
        payload = body.get("data") if isinstance(body, Mapping) else None
        if isinstance(payload, Mapping) and set(payload) == {"data"}:
            payload = payload["data"]
        sql = payload.get("sql") if isinstance(payload, Mapping) else None
        match = re.search(r"\bnode_type\s*=\s*(\d+)\b", str(sql or ""), re.IGNORECASE)
        if match:
            return table_name, int(match.group(1))
    pytest.skip("当前环境没有可生成 node_type 隔离 SQL 的复合 Schema")


def media_collection_fields(client: Any, collection_id: int) -> list[dict[str, Any]] | None:
    """按集合标签解析 rowkey 和媒体路径各自的字段 source。"""
    labels = data(assert_envelope(
        client.get_collection_labels(collection_id), required_keys=("data",)
    ))
    raw_label_items = labels.get("labels", []) if isinstance(labels, Mapping) else []
    label_items = raw_label_items if isinstance(raw_label_items, list) else []
    rowkey_label = next(
        (label for label in label_items if isinstance(label, Mapping) and label.get("name") == "rowkey"),
        None,
    )
    path_label = next(
        (label for label in label_items if isinstance(label, Mapping) and label.get("name") == "tos_path"),
        None,
    )
    if (
        not isinstance(rowkey_label, Mapping)
        or rowkey_label.get("source") is None
        or not isinstance(path_label, Mapping)
        or path_label.get("source") is None
    ):
        return None
    # 请求字段的 source 是查询层枚举：rowkey 必须使用 ORG(2)。标签返回的
    # source 表示字段归属来源，不能直接回填到查询请求中。
    rowkey_source = 2
    path_source = 2
    return [
        {"name": "rowkey", "source": rowkey_source},
        {"name": "tos_path", "source": path_source},
        {"name": "tos_path_url", "source": path_source},
    ]


def required_media_collection_id(
    client: Any,
    *,
    env_name: str = "SOURCE_ADMIN_PUBLIC_SHARE_MEDIA_COLLECTION_ID",
) -> int:
    """发现含真实 TOS 媒体路径的已完成集合，支持 env 固定隔离资源。"""
    configured = os.getenv(env_name, "").strip()
    if configured:
        try:
            return int(configured)
        except ValueError:
            raise AssertionError(f"{env_name} 必须是整数: {configured!r}") from None

    listing = data(assert_envelope(
        client.list_collections(status=2, limit=100, offset=0), required_keys=("data",)
    ))
    collections = listing.get("collections", []) if isinstance(listing, Mapping) else []
    if not isinstance(collections, list):
        raise AssertionError(f"圈选集列表 data.collections 应为数组: {listing!r}")

    for item in collections:
        if not isinstance(item, Mapping) or item.get("id") is None:
            continue
        collection_id = int(item["id"])
        fields = media_collection_fields(client, collection_id)
        if fields is None:
            continue
        rows_body = assert_envelope(
            client.get_collection_data(
                collection_id,
                fields=fields,
                page=1,
                page_size=10,
            ),
            required_keys=("data",),
        )
        rows_data = data(rows_body)
        raw_rows = rows_data.get("data", []) if isinstance(rows_data, Mapping) else []
        rows = raw_rows if isinstance(raw_rows, list) else []
        if any(
            isinstance(row, Mapping)
            and any(isinstance(row.get(key), str) and row[key].strip() for key in ("tos_path", "tos_path_url"))
            for row in rows
        ):
            return collection_id
    pytest.skip("当前环境没有含有效 tos_path 的已完成媒体集合")


def required_collection_id(client, env_name: str = "SOURCE_ADMIN_COLLECTION_ID") -> int:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return int(configured)
    body = assert_envelope(client.list_collections(limit=1, offset=0), required_keys=("data",))
    listing = data(body)
    collections = listing.get("collections", []) if isinstance(listing, Mapping) else []
    if not isinstance(collections, list) or not collections:
        pytest.skip("当前环境没有可用圈选集，需先准备资源管理平台测试数据")
    first = collections[0]
    if not isinstance(first, Mapping) or "id" not in first:
        raise AssertionError(f"圈选集列表缺少 id: {first!r}")
    collection_id = first["id"]
    if not isinstance(collection_id, (int, str)):
        raise AssertionError(f"圈选集 id 类型异常: {collection_id!r}")
    return int(collection_id)


def required_schema(client) -> tuple[int, str]:
    body = assert_envelope(client.list_schemas(page=1, page_size=20), required_keys=("data",))
    schemas = data(body)
    if not isinstance(schemas, list) or not schemas:
        pytest.skip("当前环境没有可用 Schema")
    schema = schemas[0]
    return int(schema["id"]), str(schema["name"])


def required_root_node_id() -> int:
    return int(os.getenv("SOURCE_ADMIN_ROOT_NODE_ID", "1"))
