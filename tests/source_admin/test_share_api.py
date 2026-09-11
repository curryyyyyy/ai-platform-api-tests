from __future__ import annotations

import os
from typing import Any, Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases, dataset_defaults
from platforms.source_admin.client import SourceAdminClient
from platforms.source_admin.factories import SourceAdminDataFactory


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
SHARE_CASES = dataset_case_map("source_admin", "share", "lifecycle")
INVALID_SHARE_CASES = dataset_cases("source_admin", "share", "invalid_create")
SHARE_DEFAULTS = dataset_defaults("source_admin", "share")


def _data(body: Mapping[str, Any]) -> Any:
    value = body.get("data")
    if isinstance(value, dict) and set(value) == {"data"}:
        return value["data"]
    return value


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case["id"])


def _collection_id(client: SourceAdminClient) -> int:
    value = os.getenv("SOURCE_ADMIN_COLLECTION_ID", "").strip()
    if value:
        return int(value)
    listing = _data(assert_envelope(client.list_collections(limit=1, offset=0), required_keys=("data",)))
    collections = listing.get("collections", []) if isinstance(listing, dict) else []
    if not collections:
        pytest.skip("当前环境没有可用于分享链接测试的圈选集，圈选异步依赖尚未准备")
    return int(collections[0]["id"])


@pytest.mark.core
def test_source_05_01_share_link_lifecycle(
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """分享链接创建、回查、列表和终止后状态应一致。"""
    link_id, payload = platform_data_factory.create_share_link(
        collection_id=_collection_id(platform_data_factory.client), **case_payload(SHARE_CASES["standard"])
    )
    detail = _data(assert_envelope(platform_data_factory.client.get_share_link(link_id), required_keys=("data",)))
    assert detail["id"] == int(link_id)
    assert detail["name"] == payload["name"]
    assert detail["collection_id"] == payload["collection_id"]

    listing = _data(assert_envelope(
        platform_data_factory.client.list_share_links(collection_id=payload["collection_id"], limit=20, offset=0),
        required_keys=("data",),
    ))
    assert any(item["id"] == int(link_id) for item in listing["data"])

    assert_envelope(platform_data_factory.client.terminate_share_link(link_id))
    terminated = _data(assert_envelope(platform_data_factory.client.get_share_link(link_id), required_keys=("data",)))
    assert terminated["status"] == 2


@pytest.mark.parametrize("case", INVALID_SHARE_CASES, ids=_case_id)
def test_source_05_02_invalid_share_create_is_rejected(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    """过期分享链接请求应在落库前被拒绝。"""
    payload = case_payload(case)
    payload.update({
        "name": "invalid-share-link",
        "collection_id": SHARE_DEFAULTS["missing_collection_id"],
    })
    assert_rejected(platform_client.create_share_link(**payload))


def test_source_05_03_missing_share_link_operations_are_rejected(
    platform_client: SourceAdminClient,
) -> None:
    """不存在的分享链接不能被查询或终止。"""
    link_id = SHARE_DEFAULTS["missing_link_id"]
    assert_rejected(platform_client.get_share_link(link_id))
    assert_rejected(platform_client.terminate_share_link(link_id))
