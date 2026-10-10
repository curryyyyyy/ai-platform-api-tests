from __future__ import annotations

import os
from typing import Any, Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases, dataset_defaults
from platforms.source_admin.client import SourceAdminClient
from platforms.source_admin.factories import SourceAdminDataFactory
from tests.source_admin.helpers import data, required_collection_id


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
SHARE_CASES = dataset_case_map("source_admin", "share", "lifecycle")
INVALID_SHARE_CASES = dataset_cases("source_admin", "share", "invalid_create")
PUBLIC_ACCESS_CASES = dataset_cases("source_admin", "share", "public_access")
SHARE_DEFAULTS = dataset_defaults("source_admin", "share")


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case["id"])


def _public_fields(labels: Mapping[str, Any]) -> list[dict[str, Any]]:
    fields = [
        {"name": item["name"], "source": item["source"]}
        for item in labels.get("labels", [])
        if isinstance(item, Mapping) and item.get("name") and item.get("source") is not None
    ]
    if not any(item["name"] == "rowkey" and item["source"] == 2 for item in fields):
        fields.insert(0, {"name": "rowkey", "source": 2})
    return fields[:10]


@pytest.mark.core
def test_source_05_01_share_link_lifecycle(
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """分享链接创建、回查、列表和终止后状态应一致。"""
    link_id, payload = platform_data_factory.create_share_link(
        collection_id=required_collection_id(platform_data_factory.client),
        **case_payload(SHARE_CASES["standard"]),
    )
    detail = data(assert_envelope(platform_data_factory.client.get_share_link(link_id), required_keys=("data",)))
    assert detail["id"] == int(link_id)
    assert detail["name"] == payload["name"]
    assert detail["collection_id"] == payload["collection_id"]

    listing = data(assert_envelope(
        platform_data_factory.client.list_share_links(collection_id=payload["collection_id"], limit=20, offset=0),
        required_keys=("data",),
    ))
    assert any(item["id"] == int(link_id) for item in listing["data"])

    assert_envelope(platform_data_factory.client.terminate_share_link(link_id))
    terminated = data(assert_envelope(platform_data_factory.client.get_share_link(link_id), required_keys=("data",)))
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


@pytest.mark.core
@pytest.mark.requirement(id="REQ-PUBLIC-SHARE-DATA-GUARD", name="public_share_data_guard")
@pytest.mark.case_id(
    "REQ-PUBLIC-SHARE-DATA-GUARD-API-01",
    title="公开集合接口拒绝缺失和无效分享 token",
)
@pytest.mark.parametrize("case", PUBLIC_ACCESS_CASES, ids=_case_id)
def test_source_05_04_public_collection_requires_valid_share_token(
    case: Mapping[str, Any], anonymous_platform_client: SourceAdminClient, platform_client: SourceAdminClient
) -> None:
    """公开集合元数据、标签和数据接口不能只凭集合 ID 访问。"""
    collection_id = required_collection_id(platform_client)
    token = case.get("share_token")
    assert_rejected(
        anonymous_platform_client.get_public_collection(collection_id, share_token=token),
        expected_http=401,
    )
    assert_rejected(
        anonymous_platform_client.get_public_collection_labels(collection_id, share_token=token),
        expected_http=401,
    )
    assert_rejected(
        anonymous_platform_client.get_public_collection_data(
            collection_id,
            fields=[{"name": "rowkey", "source": 2}],
            share_token=token,
            page=1,
            page_size=1,
        ),
        expected_http=401,
    )


@pytest.mark.core
@pytest.mark.requirement(id="REQ-PUBLIC-SHARE-DATA-GUARD", name="public_share_data_guard")
@pytest.mark.case_id(
    "REQ-PUBLIC-SHARE-DATA-GUARD-API-02",
    title="有效分享 token 只能无登录读取所属集合",
)
def test_source_05_05_public_share_collection_read_lifecycle(
    anonymous_platform_client: SourceAdminClient,
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """公开分享不需要总平台登录，但 token 必须绑定创建时指定的集合。"""
    collection_id = required_collection_id(platform_data_factory.client)
    _, token, _ = platform_data_factory.create_share_link_with_token(collection_id=collection_id)
    assert "Authorization" not in anonymous_platform_client.session.headers

    share = data(assert_envelope(
        anonymous_platform_client.get_public_share(token), required_keys=("data",)
    ))
    assert share["collection_id"] == collection_id

    collection = data(assert_envelope(
        anonymous_platform_client.get_public_collection(collection_id, share_token=token),
        required_keys=("data",),
    ))
    assert collection.get("collection", {}).get("id") == collection_id

    labels = data(assert_envelope(
        anonymous_platform_client.get_public_collection_labels(collection_id, share_token=token),
        required_keys=("data",),
    ))
    assert isinstance(labels.get("labels"), list)
    fields = _public_fields(labels)
    rows = data(assert_envelope(
        anonymous_platform_client.get_public_collection_data(
            collection_id,
            fields=fields,
            share_token=token,
            page=1,
            page_size=10,
        ),
        required_keys=("data",),
    ))
    assert isinstance(rows.get("data"), list)

    assert_rejected(
        anonymous_platform_client.get_public_collection(collection_id + 1, share_token=token),
        expected_http=401,
    )


@pytest.mark.requirement(id="REQ-PUBLIC-SHARE-DATA-GUARD", name="public_share_data_guard")
@pytest.mark.case_id(
    "REQ-PUBLIC-SHARE-DATA-GUARD-API-03",
    title="图片和视频公开分享不返回原始 TOS 路径",
)
def test_source_05_06_public_share_hides_sensitive_paths_for_media_collection(
    anonymous_platform_client: SourceAdminClient,
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """媒体集合的公开数据响应必须移除 tos_path 和 tos_path_url。"""
    raw_collection_id = os.getenv("SOURCE_ADMIN_PUBLIC_SHARE_MEDIA_COLLECTION_ID", "").strip()
    if not raw_collection_id:
        pytest.skip("需配置 SOURCE_ADMIN_PUBLIC_SHARE_MEDIA_COLLECTION_ID 并提供含媒体行的集合")
    collection_id = int(raw_collection_id)
    _, token, _ = platform_data_factory.create_share_link_with_token(collection_id=collection_id)
    rows = data(assert_envelope(
        anonymous_platform_client.get_public_collection_data(
            collection_id,
            fields=[
                {"name": "rowkey", "source": 2},
                {"name": "tos_path", "source": 2},
                {"name": "tos_path_url", "source": 2},
            ],
            share_token=token,
            page=1,
            page_size=10,
        ),
        required_keys=("data",),
    ))
    items = rows.get("data")
    if not isinstance(items, list) or not items:
        pytest.skip("指定媒体集合没有可用于脱敏验证的数据行")
    assert all("tos_path" not in item and "tos_path_url" not in item for item in items)
