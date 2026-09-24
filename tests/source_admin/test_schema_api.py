from __future__ import annotations

from typing import Any, Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases
from platforms.source_admin.client import SourceAdminClient
from platforms.source_admin.factories import SourceAdminDataFactory
from tests.source_admin.helpers import data


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
SCHEMA_UPDATE_CASES = dataset_case_map("source_admin", "schema", "update")
FIELD_UPDATE_CASES = dataset_case_map("source_admin", "schema_field", "update")
MISSING_RESOURCE_CASE = dataset_case_map("source_admin", "schema", "missing_resource")["schema"]
MISSING_UPDATE_CASES = dataset_cases("source_admin", "schema", "missing_update")


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case["id"])


@pytest.mark.core
@pytest.mark.skip(
    reason="线上数据库残留 node_type 非空列且无默认值，需先执行服务端 Schema 表迁移"
)
def test_source_04_01_schema_field_crud_and_readback(
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """Schema 与字段创建、回查、更新和字段列表应保持数据一致。"""
    schema_id, schema_payload = platform_data_factory.create_schema()
    field_id, field_payload = platform_data_factory.create_schema_field(schema_id=schema_id)

    schema = data(assert_envelope(platform_data_factory.client.get_schema(schema_id), required_keys=("data",)))
    assert schema["id"] == int(schema_id)
    assert schema["name"] == schema_payload["name"]

    field = data(assert_envelope(platform_data_factory.client.get_schema_field(field_id), required_keys=("data",)))
    assert field["id"] == int(field_id)
    assert field["qualifier"] == field_payload["qualifier"]

    update = case_payload(FIELD_UPDATE_CASES["standard"])
    updated = data(assert_envelope(
        platform_data_factory.client.update_schema_field(
            id=int(field_id), schema_id=int(schema_id), qualifier=field_payload["qualifier"],
            type=field_payload["type"], **update,
        ),
        required_keys=("data",),
    ))
    assert updated["name"] == update["name"]
    assert updated["sort_order"] == update["sort_order"]

    listed = data(assert_envelope(
        platform_data_factory.client.list_schema_fields(schema_id=schema_id, page=1, page_size=20),
        required_keys=("data",),
    ))
    assert any(item["id"] == int(field_id) for item in listed["list"])

    schema_update = case_payload(SCHEMA_UPDATE_CASES["standard"])
    assert_envelope(platform_data_factory.client.update_schema(id=int(schema_id), **schema_update))
    final_schema = data(assert_envelope(platform_data_factory.client.get_schema(schema_id), required_keys=("data",)))
    assert final_schema["comment"] == schema_update["comment"]


def test_source_04_02_missing_schema_and_empty_batch_semantics(
    platform_client: SourceAdminClient,
) -> None:
    """查询不存在的 Schema 应拒绝；空字段批量更新按合法空操作处理。"""
    missing_id = MISSING_RESOURCE_CASE["resource_id"]
    assert_rejected(platform_client.get_schema(missing_id))
    assert_envelope(platform_client.get_schema_by_name(name="source-admin-schema-not-found"), required_keys=("data",))
    assert_rejected(platform_client.delete_schema(missing_id))
    assert_rejected(platform_client.get_schema_field(missing_id))
    assert_rejected(platform_client.delete_schema_field(missing_id))
    assert_envelope(platform_client.list_schema_fields(schema_id=missing_id, page=1, page_size=20), required_keys=("data",))
    empty_update = assert_envelope(
        platform_client.batch_update_schema_fields(schema_id=missing_id, fields=[]),
        required_keys=("data",),
    )
    assert data(empty_update) == []
    assert_rejected(platform_client.sync_schema_fields_to_tos(schema_id=missing_id))
    assert_envelope(platform_client.list_schema_field_versions(schema_id=missing_id), required_keys=("data",))
    assert_rejected(platform_client.get_schema_field_version_snapshot(missing_id))
    assert_rejected(platform_client.rollback_schema_field(missing_id))


@pytest.mark.core
def test_source_04_04_schema_list_and_lookup(platform_client: SourceAdminClient) -> None:
    """Schema 只读查询覆盖分页和按名称查询，不依赖创建链路。"""
    listing = data(assert_envelope(platform_client.list_schemas(page=1, page_size=20), required_keys=("data",)))
    assert isinstance(listing, list)
    if not listing:
        pytest.skip("当前环境没有可查询的 Schema")
    schema = listing[0]
    assert schema.get("id") is not None and schema.get("name")
    lookup = assert_envelope(platform_client.get_schema_by_name(name=schema["name"]), required_keys=("data",))
    lookup_data = data(lookup)
    assert lookup_data is None or isinstance(lookup_data, (dict, list))


@pytest.mark.parametrize("case", MISSING_UPDATE_CASES, ids=_case_id)
def test_source_04_05_missing_schema_update_is_rejected(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    """更新不存在或零值 Schema 必须返回业务失败。"""
    payload = case_payload(case)
    payload["id"] = payload.pop("id_value")
    assert_rejected(platform_client.update_schema(**payload))


@pytest.mark.core
@pytest.mark.skip(
    reason="线上数据库残留 node_type 非空列且无默认值，需先执行服务端 Schema 表迁移"
)
def test_source_04_03_schema_field_version_snapshot_and_rollback(
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """字段变更后应产生版本，可读取快照并回滚到指定版本。"""
    schema_id, _ = platform_data_factory.create_schema()
    field_id, field_payload = platform_data_factory.create_schema_field(schema_id=schema_id)
    assert_envelope(
        platform_data_factory.client.update_schema_field(
            id=int(field_id), schema_id=int(schema_id), qualifier=field_payload["qualifier"],
            type=field_payload["type"], name="versioned", display_format="text", sort_order=20,
        )
    )

    versions = data(assert_envelope(
        platform_data_factory.client.list_schema_field_versions(schema_id=schema_id),
        required_keys=("data",),
    ))
    assert isinstance(versions, list) and versions
    version_id = versions[-1]["id"]
    snapshot = data(assert_envelope(
        platform_data_factory.client.get_schema_field_version_snapshot(version_id),
        required_keys=("data",),
    ))
    assert isinstance(snapshot, list) and snapshot
    assert_envelope(platform_data_factory.client.rollback_schema_field(version_id))
