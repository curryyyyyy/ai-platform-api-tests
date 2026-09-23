from __future__ import annotations

import os
import time

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_cases, dataset_defaults
from platforms.source_admin.factories import SourceAdminDataFactory
from tests.source_admin.helpers import data, required_collection_id, required_root_node_id, required_schema


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
DATA_DEFAULTS = dataset_defaults("source_admin", "data_manage")
INVALID_DOWNLOAD_CASES = dataset_cases("source_admin", "data_manage", "invalid_original_download")
INVALID_SET_CASES = dataset_cases("source_admin", "data_manage", "invalid_set_operation")
INVALID_IMPORT_CASES = dataset_cases("source_admin", "data_manage", "invalid_import")
INVALID_CSV_CASES = dataset_cases("source_admin", "data_manage", "invalid_csv")
INVALID_ROWKEY_COLLECTION_CASES = dataset_cases(
    "source_admin", "data_manage", "invalid_create_from_rowkeys"
)
INVALID_TEMPORARY_QUERY_CASES = dataset_cases(
    "source_admin", "data_manage", "invalid_temporary_query"
)


@pytest.mark.core
def test_source_02_01_collection_read_chain(platform_client):
    """圈选集列表、详情、列定义、节点路径和分页数据保持响应结构一致。"""
    collection_id = required_collection_id(platform_client)
    listing = data(assert_envelope(
        platform_client.list_collections(id=collection_id, limit=1, offset=0),
        required_keys=("data",),
    ))
    assert any(int(item["id"]) == collection_id for item in listing["collections"])

    detail = data(assert_envelope(platform_client.get_collection(collection_id), required_keys=("data",)))
    assert detail.get("collection", {}).get("id") == collection_id

    labels = data(assert_envelope(platform_client.get_collection_labels(collection_id), required_keys=("data",)))
    label_items = labels.get("labels", [])
    assert isinstance(label_items, list)
    fields = [{"name": item["name"], "source": item["source"]} for item in label_items]
    if not any(item.get("name") == "rowkey" and item.get("source") == 2 for item in fields):
        fields.insert(0, {"name": "rowkey", "source": 2})
    if fields:
        rows = data(assert_envelope(
            platform_client.get_collection_data(collection_id, fields=fields[:10], page=1, page_size=10),
            required_keys=("data",),
        ))
        assert isinstance(rows.get("data"), list)

    path = data(assert_envelope(platform_client.get_collection_node_path(collection_id), required_keys=("data",)))
    assert isinstance(path.get("path"), list)


@pytest.mark.core
def test_source_02_02_build_selection_query(platform_client):
    """使用现有 Schema 构建空条件圈选 SQL，不提交异步任务。"""
    _, table_name = required_schema(platform_client)
    body = data(assert_envelope(platform_client.build_selection_query(
        table_name=table_name,
        conditions={"logical_op": 1, "conditions": [], "groups": []},
        order_by=[],
    ), required_keys=("data",)))
    assert isinstance(body.get("sql"), str) and table_name in body["sql"]
    assert body.get("sql_id")


@pytest.mark.core
def test_source_02_03_collection_filters_and_pagination(platform_client):
    """集合筛选和边界分页应返回稳定的集合列表与总数结构。"""
    body = data(assert_envelope(platform_client.list_collections(
        status=2, data_type="image", limit=1, offset=0,
    ), required_keys=("data",)))
    assert isinstance(body.get("collections"), list)
    assert isinstance(body.get("total"), int)
    temporary_filtered = data(assert_envelope(platform_client.list_collections(
        is_temporary=False,
        parent_collection_id=DATA_DEFAULTS["missing_collection_id"],
        from_collection_id=DATA_DEFAULTS["missing_collection_id"],
        limit=1,
        offset=0,
    ), required_keys=("data",)))
    assert isinstance(temporary_filtered.get("collections"), list)
    assert temporary_filtered.get("total") == 0


@pytest.mark.parametrize("case", INVALID_DOWNLOAD_CASES, ids=lambda item: item["id"])
def test_source_02_04_invalid_original_download_is_rejected(case, platform_client):
    assert_rejected(platform_client.create_original_download(**case_payload(case)))


def test_source_02_05_missing_original_download_is_rejected(platform_client):
    assert_rejected(platform_client.get_original_download(DATA_DEFAULTS["missing_task_id"]))


def test_source_02_06_invalid_query_submit_is_rejected(platform_client):
    assert_rejected(platform_client.submit_query(
        sql="", name="", file_node_id=0, config_snapshot="{}", table_name="",
    ), allow_error_data=True)


@pytest.mark.parametrize("case", INVALID_SET_CASES, ids=lambda item: item["id"])
def test_source_02_07_invalid_set_operation_is_rejected(case, platform_client):
    payload = case_payload(case)
    payload.update({"name": "invalid-set-operation", "file_node_id": 0})
    assert_rejected(platform_client.submit_set_operation(**payload), allow_error_data=True)


def test_source_02_08_missing_collection_read_endpoints_are_rejected(platform_client):
    collection_id = DATA_DEFAULTS["missing_collection_id"]
    assert_rejected(platform_client.get_collection(collection_id))
    assert_rejected(platform_client.get_collection_labels(collection_id))
    assert_rejected(platform_client.get_collection_node_path(collection_id))
    assert_rejected(platform_client.get_collection_sql(collection_id))
    assert_rejected(platform_client.get_import_status(collection_id))
    assert_rejected(platform_client.get_import_errors(collection_id))


def test_source_02_09_missing_collection_data_is_rejected(platform_client):
    assert_rejected(platform_client.get_collection_data(
        DATA_DEFAULTS["missing_collection_id"], fields=[{"name": "rowkey", "source": 2}],
    ), allow_error_data=True)


def test_source_02_10_collection_download_missing_resource_is_rejected(platform_client):
    assert_rejected(platform_client.download_collection(DATA_DEFAULTS["missing_collection_id"]))


def test_source_02_11_csv_upload_url(platform_client):
    filename = f"api-test-{int(time.time() * 1000)}.csv"
    body = data(assert_envelope(platform_client.get_csv_upload_url(file_name=filename), required_keys=("data",)))
    assert body.get("presigned_url")
    assert body.get("tos_path")


@pytest.mark.parametrize("case", INVALID_IMPORT_CASES, ids=lambda item: item["id"])
def test_source_02_12_invalid_csv_import_is_rejected(case, platform_client):
    assert_rejected(platform_client.import_collection(**case_payload(case)["payload"] ))


@pytest.mark.parametrize("case", INVALID_CSV_CASES, ids=lambda item: item["id"])
def test_source_02_13_invalid_csv_check_is_rejected(case, platform_client):
    assert_rejected(platform_client.check_csv(tos_path=""))


def test_source_02_14_invalid_composite_preview_is_rejected(platform_client):
    assert_rejected(platform_client.preview_composite(node_type=0))


def test_source_02_15_audit_log_filters(platform_client):
    now = int(time.time() * 1000)
    body = data(assert_envelope(platform_client.list_audit_logs(
        operation_type=2, start_time=now - 30 * 24 * 60 * 60 * 1000, end_time=now,
        limit=10, offset=0,
    ), required_keys=("data",)))
    assert isinstance(body.get("logs"), list)
    assert isinstance(body.get("total"), int)


@pytest.mark.skipif(
    not os.getenv("SOURCE_ADMIN_WRITABLE_COLLECTION_ID"),
    reason="需要通过 SOURCE_ADMIN_WRITABLE_COLLECTION_ID 显式提供隔离圈选集",
)
def test_source_02_16_collection_metadata_write(platform_client):
    """在显式隔离集合上覆盖展示列和资源类型更新，避免修改共享集合。"""
    collection_id = int(os.environ["SOURCE_ADMIN_WRITABLE_COLLECTION_ID"])
    labels = data(assert_envelope(platform_client.get_collection_labels(collection_id), required_keys=("data",)))
    names = [item["name"] for item in labels.get("labels", []) if item.get("name") != "rowkey"]
    assert_envelope(platform_client.update_collection_columns(collection_id, show_col=names[:3]))
    assert_envelope(platform_client.update_collection_set_type(collection_id, set_type=2))


@pytest.mark.core
@pytest.mark.requirement(
    id="REQ-COLLECTION-ROWKEY-CREATION", name="collection_rowkey_creation"
)
@pytest.mark.case_id(
    "REQ-COLLECTION-ROWKEY-CREATION-API-01",
    title="按 rowkeys 创建圈选集在写入前拒绝非法参数",
)
@pytest.mark.parametrize("case", INVALID_ROWKEY_COLLECTION_CASES, ids=lambda item: item["id"])
def test_source_02_17_create_collection_from_rowkeys_rejects_invalid_input(
    case, platform_client
):
    """参数校验必须在读取源集或创建新集之前生效。"""
    payload = case_payload(case)
    rowkey_count = payload.pop("rowkey_count", None)
    if rowkey_count is not None:
        payload["rowkeys"] = ["api-test-rowkey"] * rowkey_count
    assert_rejected(platform_client.create_collection_from_rowkeys(**payload))


@pytest.mark.requirement(
    id="REQ-COLLECTION-ROWKEY-CREATION", name="collection_rowkey_creation"
)
@pytest.mark.case_id(
    "REQ-COLLECTION-ROWKEY-CREATION-API-02",
    title="按 rowkeys 创建圈选集拒绝不存在的源集合",
)
def test_source_02_18_create_collection_from_rowkeys_rejects_missing_source(platform_client):
    """源集不存在时不应创建新集，且要返回明确业务失败。"""
    assert_rejected(
        platform_client.create_collection_from_rowkeys(
            parent_node_id=1,
            name="api-test-missing-source-collection",
            cid=DATA_DEFAULTS["missing_source_collection_id"],
            rowkeys=["api-test-rowkey"],
        )
    )


@pytest.mark.core
@pytest.mark.requirement(
    id="REQ-COLLECTION-ROWKEY-CREATION", name="collection_rowkey_creation"
)
@pytest.mark.case_id(
    "REQ-COLLECTION-ROWKEY-CREATION-API-03",
    title="按 rowkeys 创建圈选集后可立即读取新集数据",
)
def test_source_02_19_create_collection_from_rowkeys_lifecycle(
    platform_data_factory: SourceAdminDataFactory,
    data_scope,
):
    """新圈选集同步写入 rowkey、可读回，并在用例结束后删除关联节点。"""
    client = platform_data_factory.client
    rowkey = data_scope.unique_name("rowkey", max_length=64)
    collection_id, payload, created = platform_data_factory.create_collection_from_rowkeys(
        parent_node_id=required_root_node_id(),
        source_collection_id=required_collection_id(client),
        rowkeys=[rowkey],
    )
    assert isinstance(created, dict)
    assert int(collection_id) > 0
    assert created["status"] == 2
    detail = data(assert_envelope(
        client.get_collection(collection_id), required_keys=("data",)
    ))
    assert detail.get("collection", {}).get("id") == int(collection_id)

    rows = data(assert_envelope(
        client.get_collection_data(
            collection_id,
            fields=[{"name": "rowkey", "source": 2}],
            page=1,
            page_size=10,
        ),
        required_keys=("data",),
    ))
    assert any(item.get("rowkey") == payload["rowkeys"][0] for item in rows["data"])


@pytest.mark.parametrize("case", INVALID_TEMPORARY_QUERY_CASES, ids=lambda item: item["id"])
def test_source_02_20_invalid_temporary_query_is_rejected(case, platform_client):
    """临时查询的必填字段和演进来源 ID 必须在进入 Spark 前拒绝。"""
    payload = case_payload(case)
    payload.update(payload.pop("payload", {}))
    assert_rejected(
        platform_client.submit_temporary_query(**payload), allow_error_data=True
    )


def test_source_02_21_invalid_temporary_collection_promotion_is_rejected(platform_client):
    """转正请求必须拒绝无效临时集合 ID 和父节点 ID。"""
    assert_rejected(platform_client.promote_temporary_collection(
        DATA_DEFAULTS["missing_collection_id"], parent_node_id=1,
    ))
    assert_rejected(platform_client.promote_temporary_collection(
        0, parent_node_id=0,
    ))


def test_source_02_22_temporary_collection_relation_semantics(platform_client):
    """子临时查询拒绝不存在集合，直接衍生查询对无结果返回合法空集。"""
    collection_id = DATA_DEFAULTS["missing_collection_id"]
    assert_rejected(platform_client.get_temporary_children(collection_id))
    derived = data(assert_envelope(
        platform_client.get_derived_collections(collection_id), required_keys=("data",)
    ))
    assert derived["collections"] == []
