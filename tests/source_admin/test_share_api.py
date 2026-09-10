from __future__ import annotations

import os

import pytest

from framework.assertions import assert_envelope
from framework.data.dataset import case_payload, dataset_case_map
from platforms.source_admin.factories import SourceAdminDataFactory


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
SHARE_CASES = dataset_case_map("source_admin", "share", "lifecycle")


def _data(body: dict):
    value = body.get("data")
    if isinstance(value, dict) and set(value) == {"data"}:
        return value["data"]
    return value


def _collection_id(client) -> int:
    value = os.getenv("SOURCE_ADMIN_COLLECTION_ID", "").strip()
    if value:
        return int(value)
    listing = _data(assert_envelope(client.list_collections(limit=1, offset=0), required_keys=("data",)))
    collections = listing.get("collections", []) if isinstance(listing, dict) else []
    if not collections:
        pytest.skip("当前环境没有可用于分享链接测试的圈选集，圈选异步依赖尚未准备")
    return int(collections[0]["id"])


@pytest.mark.core
def test_source_05_01_share_link_lifecycle(platform_data_factory: SourceAdminDataFactory):
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
