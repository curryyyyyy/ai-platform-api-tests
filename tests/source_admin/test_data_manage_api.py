from __future__ import annotations

import time
import csv
import io
from collections.abc import Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_cases, dataset_defaults
from platforms.source_admin.factories import SourceAdminDataFactory
from tests.source_admin.helpers import (
    assert_html_page,
    data,
    required_composite_schema,
    required_collection_id,
    required_collection_with_sql,
    required_media_collection_id,
    required_media_tos_path,
    required_numeric_selection_field,
    required_root_node_id,
    statistics_numeric_candidates,
    statistics_query_data,
    wait_for_statistics_completion,
)


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
NULL_AS_ZERO_CASES = dataset_cases("source_admin", "data_manage", "null_as_zero")
INVALID_TOS_SIGN_URL_CASES = dataset_cases(
    "source_admin", "data_manage", "invalid_tos_sign_urls"
)
STATISTICS_AUTH_CASES = dataset_cases("source_admin", "data_manage", "statistics_auth")
INVALID_STATISTICS_CASES = dataset_cases("source_admin", "data_manage", "invalid_statistics")


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
    """普通 Schema 使用其物理 source_table 构建空条件圈选 SQL。"""
    schemas = data(assert_envelope(
        platform_client.list_schemas(page=1, page_size=100), required_keys=("data",)
    ))
    if not isinstance(schemas, list):
        raise AssertionError(f"Schema 列表 data 应为数组: {schemas}")
    schema = next(
        (
            item
            for item in schemas
            if isinstance(item, dict)
            and item.get("name")
            and item.get("source_table") not in {"composite", "aigc_dataset_composite"}
        ),
        None,
    )
    if schema is None:
        pytest.skip("当前环境没有非复合类型 Schema，无法验证 source_table 物理表映射")
    table_name = str(schema["name"])
    source_table = str(schema.get("source_table") or table_name)
    physical_table = source_table.removeprefix("aigc_dataset_")
    body = data(assert_envelope(platform_client.build_selection_query(
        table_name=table_name,
        conditions={"logical_op": 1, "conditions": [], "groups": []},
        order_by=[],
    ), required_keys=("data",)))
    assert isinstance(body.get("sql"), str) and physical_table in body["sql"]
    assert body.get("sql_id")


@pytest.mark.core
@pytest.mark.requirement(id="REQ-COMPOSITE-SQL-ISOLATION", name="composite_sql_isolation")
@pytest.mark.case_id(
    "REQ-COMPOSITE-SQL-ISOLATION-API-01",
    title="复合类型查询固定物理表并附加 node_type 隔离条件",
)
def test_source_02_23_composite_selection_query_uses_node_type_guard(platform_client):
    """复合类型共享 composite 表时，SQL 必须按 node_type 隔离不同数据形态。"""
    table_env = DATA_DEFAULTS["composite_table_env"]
    node_type_env = DATA_DEFAULTS["composite_node_type_env"]
    table_name, node_type = required_composite_schema(
        platform_client, table_env=table_env, node_type_env=node_type_env
    )

    body = data(assert_envelope(platform_client.build_selection_query(
        table_name=table_name,
        conditions={"logical_op": 1, "conditions": [], "groups": []},
        order_by=[],
    ), required_keys=("data",)))
    sql = body.get("sql")
    assert isinstance(sql, str) and "composite" in sql
    assert "node_type" in sql and str(node_type) in sql


@pytest.mark.requirement(id="REQ-COLLECTION-NULL-AS-ZERO", name="collection_null_as_zero")
@pytest.mark.case_id(
    "REQ-COLLECTION-NULL-AS-ZERO-API-01",
    title="数字条件的 null_as_zero 默认值和显式开关生成正确 SQL",
)
@pytest.mark.parametrize("case", NULL_AS_ZERO_CASES, ids=lambda item: item["id"])
def test_source_02_30_numeric_condition_null_as_zero_is_data_driven(case, platform_client):
    """数字字段默认把 NULL 按 0 比较，显式 false 保留原始 NULL 语义。"""
    table_name, field_id, qualifier = required_numeric_selection_field(
        platform_client,
        table_env=DATA_DEFAULTS["null_as_zero_table_env"],
        field_id_env=DATA_DEFAULTS["null_as_zero_field_id_env"],
    )
    condition = {"field": field_id, "operator": 1, "value": "0"}
    if case.get("null_as_zero") is not None:
        condition["null_as_zero"] = case["null_as_zero"]
    body = data(assert_envelope(platform_client.build_selection_query(
        table_name=table_name,
        conditions={"logical_op": 1, "conditions": [condition], "groups": []},
        order_by=[],
    ), required_keys=("data",)))
    sql = body.get("sql")
    assert isinstance(sql, str) and sql
    if case["expected_coalesce"]:
        assert f"COALESCE({qualifier}, 0) = 0" in sql
    else:
        assert f"{qualifier} = 0" in sql
        assert f"COALESCE({qualifier}, 0)" not in sql


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


@pytest.mark.requirement(
    id="REQ-COLLECTION-READ-AUXILIARY", name="collection_read_auxiliary"
)
@pytest.mark.case_id(
    "REQ-COLLECTION-READ-AUXILIARY-API-01",
    title="有效圈选集可读取 SQL 和导入状态，并正确表达无失败明细",
)
def test_source_02_28_collection_sql_import_status_and_errors(platform_client):
    """只读查询不创建任务，并覆盖导入错误接口的合法无错误结果。"""
    collection_id, discovered_sql = required_collection_with_sql(
        platform_client, env_name=DATA_DEFAULTS["sql_collection_env"]
    )

    sql_body = data(assert_envelope(
        platform_client.get_collection_sql(collection_id), required_keys=("data",)
    ))
    sql = sql_body.get("sql")
    assert isinstance(sql, str) and sql.strip() == discovered_sql.strip()
    assert sql.upper().startswith("SELECT")
    assert "rowkey" in sql.lower()

    status_body = data(assert_envelope(
        platform_client.get_import_status(collection_id), required_keys=("data",)
    ))
    assert isinstance(status_body.get("status"), int)

    errors_response = platform_client.get_import_errors(collection_id)
    errors_envelope = assert_envelope(
        errors_response, expected_code=None, required_keys=("data",)
    )
    errors_body = data(errors_envelope)
    if errors_envelope["code"] == 0:
        assert isinstance(errors_body, Mapping)
        assert errors_body.get("tos_path") or errors_body.get("presigned_url")
    else:
        assert "暂无失败明细" in str(errors_envelope.get("msg", ""))


@pytest.mark.requirement(id="REQ-TOS-SIGN-URL", name="tos_sign_url")
@pytest.mark.case_id(
    "REQ-TOS-SIGN-URL-API-01",
    title="TOS 签名 URL 批量请求拒绝非法参数",
)
@pytest.mark.parametrize("case", INVALID_TOS_SIGN_URL_CASES, ids=lambda item: item["id"])
def test_source_02_31_tos_sign_urls_reject_invalid_batch(case, platform_client):
    """批量签名参数错误应在访问 TOS 对象前返回 HTTP 400 和业务错误。"""
    assert_rejected(
        platform_client.sign_tos_urls(**case_payload(case)),
        expected_http=400,
    )


@pytest.mark.requirement(id="REQ-TOS-SIGN-URL", name="tos_sign_url")
@pytest.mark.case_id(
    "REQ-TOS-SIGN-URL-API-02",
    title="TOS 签名 URL 对单项非法路径返回逐项失败结果",
)
def test_source_02_32_tos_sign_urls_reports_item_validation_errors(platform_client):
    """单项路径错误不应把整批请求变成 HTTP 错误，也不应触发外部签名。"""
    envelope = assert_envelope(
        platform_client.sign_tos_urls(
            tos_paths=["not-a-tos-path", "tos://bucket/"],
            include_cdn=False,
            include_preview=True,
        ),
        required_keys=("data",),
    )
    body = data(envelope)
    assert body["total"] == 2
    assert body["success"] == 0
    assert body["partial"] == 0
    assert body["failed"] == 2
    assert [item["index"] for item in body["items"]] == [0, 1]
    assert all(item["status"] == "failed" for item in body["items"])
    assert all(item["errors"][0]["field"] == "tos_path" for item in body["items"])


@pytest.mark.requirement(id="REQ-TOS-SIGN-URL", name="tos_sign_url")
@pytest.mark.case_id(
    "REQ-TOS-SIGN-URL-API-03",
    title="TOS 签名 URL 路由要求总平台登录",
)
def test_source_02_33_tos_sign_urls_require_login(anonymous_platform_client):
    response = anonymous_platform_client.sign_tos_urls(tos_paths=[])
    assert response.status_code in {401, 403}, (
        f"TOS 签名接口未登录时应拒绝访问: status={response.status_code}, "
        f"body={response.text[:500]}"
    )


@pytest.mark.requirement(id="REQ-TOS-SIGN-URL", name="tos_sign_url")
@pytest.mark.case_id(
    "REQ-TOS-SIGN-URL-API-04",
    title="TOS 签名 URL 正向返回媒体路径关联的签名地址",
)
def test_source_02_34_tos_sign_urls_sign_media_path(platform_client):
    """从已完成媒体集合动态发现路径，验证至少一种签名地址可用。"""
    tos_path = required_media_tos_path(platform_client)
    envelope = assert_envelope(
        platform_client.sign_tos_urls(tos_paths=[tos_path], expires_in=60),
        required_keys=("data",),
    )
    body = data(envelope)
    assert body["total"] == 1
    assert body["failed"] == 0
    item = body["items"][0]
    assert item["index"] == 0
    assert item["tos_path"] == tos_path
    assert item["status"] in {"ok", "partial"}
    assert item["tos_cdn_url"] or item["tos_preview_url"]


def test_source_02_09_missing_collection_data_is_rejected(platform_client):
    assert_rejected(platform_client.get_collection_data(
        DATA_DEFAULTS["missing_collection_id"], fields=[{"name": "rowkey", "source": 2}],
    ), allow_error_data=True)


def test_source_02_10_collection_download_missing_resource_is_rejected(platform_client):
    assert_rejected(platform_client.download_collection(DATA_DEFAULTS["missing_collection_id"]))


@pytest.mark.requirement(id="REQ-COLLECTION-DOWNLOAD-TOS-PATH", name="collection_download_tos_path")
@pytest.mark.case_id(
    "REQ-COLLECTION-DOWNLOAD-TOS-PATH-API-01",
    title="圈选集下载同时返回完整 TOS 路径和对象 key",
)
def test_source_02_24_collection_download_returns_full_tos_path(platform_client):
    """下载文件的完整 TOS 路径应保留 bucket 信息，供外部工具复制和后续处理。"""
    env_name = DATA_DEFAULTS["download_collection_env"]
    collection_id = required_media_collection_id(platform_client, env_name=env_name)

    body = data(assert_envelope(
        platform_client.download_collection(collection_id), required_keys=("data",)
    ))
    tos_key = body.get("tos_key")
    tos_path = body.get("tos_path")
    assert isinstance(tos_key, str) and tos_key.startswith("download/")
    assert isinstance(tos_path, str) and tos_path.startswith("tos://")
    assert tos_path.removeprefix("tos://").partition("/")[2] == tos_key


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


def test_source_02_16_collection_metadata_write(
    platform_data_factory: SourceAdminDataFactory,
    data_scope,
):
    """在现场创建的隔离集合上覆盖展示列和资源类型更新。"""
    client = platform_data_factory.client
    collection_id, _, _ = platform_data_factory.create_collection_from_rowkeys(
        parent_node_id=required_root_node_id(),
        source_collection_id=required_collection_id(client),
        rowkeys=[data_scope.unique_name("rowkey", max_length=64)],
    )
    labels = data(assert_envelope(client.get_collection_labels(collection_id), required_keys=("data",)))
    names = [item["name"] for item in labels.get("labels", []) if item.get("name") != "rowkey"]
    assert_envelope(client.update_collection_columns(collection_id, show_col=names[:3]))
    assert_envelope(client.update_collection_set_type(collection_id, set_type=2))


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
    """新圈选集同步写入 rowkey、可读回；系统节点按设计由平台统一管理。"""
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


@pytest.mark.requirement(
    id="REQ-COLLECTION-STATISTICS-TOOL", name="collection_statistics_tool"
)
@pytest.mark.case_id(
    "REQ-COLLECTION-STATISTICS-TOOL-API-01",
    title="圈选集统计工具 API 受登录保护且页面壳允许匿名访问",
)
@pytest.mark.parametrize("case", STATISTICS_AUTH_CASES, ids=lambda item: item["id"])
def test_source_02_25_statistics_routes_auth_boundary(
    case, anonymous_platform_client
):
    """统计业务 API 需要总平台登录，独立 HTML 页面保持匿名可加载。"""
    api_calls = {
        "submit": lambda: anonymous_platform_client.submit_selection_statistics(
            collection_id=0, fields=[]
        ),
        "preview": lambda: anonymous_platform_client.preview_selection_statistics_sql(
            collection_id=0, fields=[]
        ),
        "query": lambda: anonymous_platform_client.get_selection_statistics(""),
        "export": lambda: anonymous_platform_client.export_selection_statistics(""),
    }
    endpoint = case["endpoint"]
    if endpoint == "page":
        assert_html_page(anonymous_platform_client.get_selection_statistics_page())
        return
    response = api_calls[endpoint]()
    assert response.status_code in {401, 403}, (
        f"统计 API 未登录时应拒绝访问: {case['id']}, "
        f"status={response.status_code}, body={response.text[:500]}"
    )


@pytest.mark.requirement(
    id="REQ-COLLECTION-STATISTICS-TOOL", name="collection_statistics_tool"
)
@pytest.mark.case_id(
    "REQ-COLLECTION-STATISTICS-TOOL-API-02",
    title="圈选集统计工具拒绝空字段和缺失查询 ID",
)
@pytest.mark.parametrize("case", INVALID_STATISTICS_CASES, ids=lambda item: item["id"])
def test_source_02_26_invalid_statistics_inputs_are_rejected(case, platform_client):
    """统计业务参数应在访问外部 Lance/Spark 依赖前被拒绝。"""
    payload = case_payload(case)
    endpoint = payload.pop("endpoint")
    api_calls = {
        "submit": lambda values: platform_client.submit_selection_statistics(**values),
        "preview": lambda values: platform_client.preview_selection_statistics_sql(**values),
        "query": lambda values: platform_client.get_selection_statistics(**values),
        "export": lambda values: platform_client.export_selection_statistics(**values),
    }
    try:
        response = api_calls[endpoint](payload)
    except KeyError:
        raise AssertionError(f"未知统计接口场景: {endpoint}") from None
    assert_rejected(response)


@pytest.mark.requirement(
    id="REQ-COLLECTION-STATISTICS-TOOL", name="collection_statistics_tool"
)
@pytest.mark.case_id(
    "REQ-COLLECTION-STATISTICS-TOOL-API-03",
    title="圈选集统计支持预览、提交、查询和 CSV 导出",
)
def test_source_02_27_selection_statistics_lifecycle(platform_client):
    """统计任务使用现场发现的可用集合，完成后返回分页结果并导出 CSV。"""
    preview: dict[str, object] | None = None
    selected: tuple[int, dict[str, str]] | None = None
    for collection_id, fields in statistics_numeric_candidates(
        platform_client,
        collection_id_env=DATA_DEFAULTS["statistics_collection_env"],
    ):
        response = platform_client.preview_selection_statistics_sql(
            collection_id=collection_id, fields=[fields]
        )
        body = platform_client.json(response)
        if response.status_code == 200 and body.get("code") == 0:
            payload = data(body)
            if isinstance(payload, dict):
                preview = payload
                selected = (collection_id, fields)
                break
    if preview is None or selected is None:
        pytest.skip("未发现可完成统计 SQL 预览的圈选集")

    assert isinstance(preview.get("sql"), str) and preview["sql"]
    assert isinstance(preview.get("data_version"), str)
    assert isinstance(preview.get("columns"), list) and preview["columns"]

    collection_id, fields = selected
    submitted = statistics_query_data(platform_client.submit_selection_statistics(
        collection_id=collection_id,
        data_version=preview["data_version"],
        fields=[fields],
    ))
    query_id = submitted.get("query_id")
    assert isinstance(query_id, str) and len(query_id) == 32

    completed = wait_for_statistics_completion(
        platform_client,
        query_id,
        timeout_env=DATA_DEFAULTS["statistics_timeout_env"],
        poll_interval_env=DATA_DEFAULTS["statistics_poll_interval_env"],
    )
    assert isinstance(completed.get("preview"), list)
    assert isinstance(completed.get("total"), int) and completed["total"] > 0
    assert completed.get("offset", 0) == 0
    assert completed.get("limit") == 1
    assert completed.get("has_more", False) is False
    assert isinstance(completed.get("columns"), list) and completed["columns"]

    export = platform_client.export_selection_statistics(query_id)
    assert export.status_code == 200, export.text[:500]
    assert "text/csv" in export.headers.get("Content-Type", "").lower()
    assert "attachment;" in export.headers.get("Content-Disposition", "").lower()
    rows = list(csv.reader(io.StringIO(export.content.decode("utf-8"))))
    assert rows and rows[0] == completed["columns"]
    assert len(rows) > 1
