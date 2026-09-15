"""资源管理平台 HTTP 客户端。

认证由通用 fixture 通过总平台 SSO 获取，客户端只负责沿用 Bearer Token。
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote

from framework.http.client import ApiClient


OPERATION_ROUTES: dict[str, tuple[str, str]] = {
    "DM-01": ("POST", "/api/v1/original-downloads"),
    "DM-02": ("GET", "/api/v1/original-downloads/{task_id}"),
    "DM-03": ("POST", "/api/v1/query/build-selection"),
    "DM-04": ("POST", "/api/v1/query/submit"),
    "DM-05": ("POST", "/api/v1/set-operation/submit"),
    "DM-06": ("GET", "/api/v1/collections"),
    "DM-07": ("GET", "/api/v1/collections/{collection_id}"),
    "DM-08": ("GET", "/api/v1/collections/{collection_id}/labels"),
    "DM-09": ("POST", "/api/v1/collections/{collection_id}/data"),
    "DM-10": ("GET", "/api/v1/collections/{collection_id}/node-path"),
    "DM-11": ("PUT", "/api/v1/collections/{collection_id}/columns"),
    "DM-12": ("PUT", "/api/v1/collections/{collection_id}/set-type"),
    "DM-13": ("GET", "/api/v1/collections/{collection_id}/preview-sql"),
    "DM-14": ("POST", "/api/v1/collections/{collection_id}/download"),
    "DM-15": ("POST", "/api/v1/collections/csv-upload-url"),
    "DM-16": ("POST", "/api/v1/collections/import"),
    "DM-17": ("POST", "/api/v1/collections/check-csv"),
    "DM-18": ("GET", "/api/v1/collections/{collection_id}/import-status"),
    "DM-19": ("GET", "/api/v1/collections/{collection_id}/import-errors"),
    "DM-20": ("POST", "/api/v1/composite/preview"),
    "FS-01": ("GET", "/api/v1/nodes/{id}/list"),
    "FS-02": ("GET", "/api/v1/nodes/{id}"),
    "FS-03": ("POST", "/api/v1/nodes"),
    "FS-04": ("PUT", "/api/v1/nodes/{id}"),
    "FS-05": ("DELETE", "/api/v1/nodes/{id}"),
    "FS-06": ("POST", "/api/v1/nodes/{id}/move"),
    "FS-07": ("GET", "/api/v1/nodes/search"),
    "FS-08": ("GET", "/api/v1/nodes/batch"),
    "FS-09": ("POST", "/api/v1/nodes/project"),
    "FS-10": ("GET", "/api/v1/nodes/project/info"),
    "SC-01": ("POST", "/api/v1/schema"),
    "SC-02": ("PUT", "/api/v1/schema"),
    "SC-03": ("DELETE", "/api/v1/schema/{id}"),
    "SC-04": ("GET", "/api/v1/schema/{id}"),
    "SC-05": ("GET", "/api/v1/schema/by-name"),
    "SC-06": ("GET", "/api/v1/schema/list"),
    "SC-07": ("POST", "/api/v1/schema/field"),
    "SC-08": ("PUT", "/api/v1/schema/field"),
    "SC-09": ("DELETE", "/api/v1/schema/field/{id}"),
    "SC-10": ("GET", "/api/v1/schema/field/{id}"),
    "SC-11": ("GET", "/api/v1/schema/field/list"),
    "SC-12": ("PUT", "/api/v1/schema/field/batch"),
    "SC-13": ("POST", "/api/v1/schema/field/sync-tos"),
    "SC-14": ("GET", "/api/v1/schema/field/versions"),
    "SC-15": ("GET", "/api/v1/schema/field/versions/{version_id}/snapshot"),
    "SC-16": ("POST", "/api/v1/schema/field/versions/{version_id}/rollback"),
    "SH-01": ("POST", "/api/v1/share/link"),
    "SH-02": ("GET", "/api/v1/share/link/{id}"),
    "SH-03": ("GET", "/api/v1/share/link/list"),
    "SH-04": ("PUT", "/api/v1/share/link/{id}/terminate"),
    "AU-01": ("GET", "/api/v1/audit/logs"),
    "CT-01": ("GET", "/api/v1/contracts"),
    "CT-02": ("GET", "/api/v1/contracts/{id}"),
    "CT-03": ("PUT", "/api/v1/contracts/{id}/associate"),
    "CT-04": ("POST", "/api/v1/contracts/{id}/archive"),
    "CT-05": ("POST", "/api/v1/contracts/sync/trigger"),
    "SP-01": ("GET", "/api/v1/suppliers"),
    "SP-02": ("POST", "/api/v1/suppliers"),
    "SP-03": ("GET", "/api/v1/suppliers/{id}"),
    "SP-04": ("PUT", "/api/v1/suppliers/{id}"),
    "SP-05": ("GET", "/api/v1/public/suppliers"),
}

OPERATION_METHODS: dict[str, str] = {
    "DM-01": "create_original_download",
    "DM-02": "get_original_download",
    "DM-03": "build_selection_query",
    "DM-04": "submit_query",
    "DM-05": "submit_set_operation",
    "DM-06": "list_collections",
    "DM-07": "get_collection",
    "DM-08": "get_collection_labels",
    "DM-09": "get_collection_data",
    "DM-10": "get_collection_node_path",
    "DM-11": "update_collection_columns",
    "DM-12": "update_collection_set_type",
    "DM-13": "get_collection_sql",
    "DM-14": "download_collection",
    "DM-15": "get_csv_upload_url",
    "DM-16": "import_collection",
    "DM-17": "check_csv",
    "DM-18": "get_import_status",
    "DM-19": "get_import_errors",
    "DM-20": "preview_composite",
    "FS-01": "list_nodes",
    "FS-02": "get_node",
    "FS-03": "create_node",
    "FS-04": "update_node",
    "FS-05": "delete_node",
    "FS-06": "move_node",
    "FS-07": "search_nodes",
    "FS-08": "batch_list_nodes",
    "FS-09": "create_project_node",
    "FS-10": "get_project_node_info",
    "SC-01": "create_schema",
    "SC-02": "update_schema",
    "SC-03": "delete_schema",
    "SC-04": "get_schema",
    "SC-05": "get_schema_by_name",
    "SC-06": "list_schemas",
    "SC-07": "create_schema_field",
    "SC-08": "update_schema_field",
    "SC-09": "delete_schema_field",
    "SC-10": "get_schema_field",
    "SC-11": "list_schema_fields",
    "SC-12": "batch_update_schema_fields",
    "SC-13": "sync_schema_fields_to_tos",
    "SC-14": "list_schema_field_versions",
    "SC-15": "get_schema_field_version_snapshot",
    "SC-16": "rollback_schema_field",
    "SH-01": "create_share_link",
    "SH-02": "get_share_link",
    "SH-03": "list_share_links",
    "SH-04": "terminate_share_link",
    "AU-01": "list_audit_logs",
    "CT-01": "list_contracts",
    "CT-02": "get_contract",
    "CT-03": "associate_contract",
    "CT-04": "archive_contract",
    "CT-05": "trigger_contract_sync",
    "SP-01": "list_suppliers",
    "SP-02": "create_supplier",
    "SP-03": "get_supplier",
    "SP-04": "update_supplier",
    "SP-05": "list_external_suppliers",
}


def _compact(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class SourceAdminClient(ApiClient):
    """资源管理平台 61 个已确认操作的客户端封装。"""

    def _operation(
        self,
        operation_id: str,
        *,
        path_params: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        has_json: bool = False,
    ):
        method, path_template = OPERATION_ROUTES[operation_id]
        path = path_template
        for name, value in (path_params or {}).items():
            path = path.replace("{" + name + "}", quote(str(value), safe=""))
        kwargs: dict[str, Any] = {}
        if params:
            kwargs["params"] = dict(params)
        if headers:
            kwargs["headers"] = dict(headers)
        if has_json:
            kwargs["json"] = json
        return self.request(method, path, **kwargs)

    # 数据管理
    def create_original_download(self, *, type: int, rowkeys: list[str]):
        return self._operation("DM-01", json={"type": type, "rowkeys": rowkeys}, has_json=True)

    def get_original_download(self, task_id: Any):
        return self._operation("DM-02", path_params={"task_id": task_id})

    def build_selection_query(
        self,
        *,
        table_name: str,
        conditions: Mapping[str, Any],
        order_by: list[Mapping[str, Any]] | None = None,
    ):
        body = {"table_name": table_name, "conditions": conditions, "order_by": order_by}
        return self._operation("DM-03", json=_compact(body), has_json=True)

    def submit_query(self, **payload: Any):
        return self._operation("DM-04", json=payload, has_json=True)

    def submit_set_operation(self, **payload: Any):
        return self._operation("DM-05", json=payload, has_json=True)

    def list_collections(self, **params: Any):
        return self._operation("DM-06", params=_compact(params))

    def get_collection(self, collection_id: Any):
        return self._operation("DM-07", path_params={"collection_id": collection_id})

    def get_collection_labels(self, collection_id: Any):
        return self._operation("DM-08", path_params={"collection_id": collection_id})

    def get_collection_data(self, collection_id: Any, *, fields: list[Mapping[str, Any]], page: int | None = None, page_size: int | None = None):
        body = {"fields": fields, "page": page, "page_size": page_size}
        return self._operation("DM-09", path_params={"collection_id": collection_id}, json=_compact(body), has_json=True)

    def get_collection_node_path(self, collection_id: Any):
        return self._operation("DM-10", path_params={"collection_id": collection_id})

    def update_collection_columns(self, collection_id: Any, *, show_col: list[str]):
        return self._operation("DM-11", path_params={"collection_id": collection_id}, json={"show_col": show_col}, has_json=True)

    def update_collection_set_type(self, collection_id: Any, *, set_type: int):
        return self._operation("DM-12", path_params={"collection_id": collection_id}, json={"set_type": set_type}, has_json=True)

    def get_collection_sql(self, collection_id: Any):
        return self._operation("DM-13", path_params={"collection_id": collection_id})

    def download_collection(self, collection_id: Any, **payload: Any):
        return self._operation("DM-14", path_params={"collection_id": collection_id}, json=payload, has_json=bool(payload))

    def get_csv_upload_url(self, *, file_name: str):
        return self._operation("DM-15", json={"file_name": file_name}, has_json=True)

    def import_collection(self, **payload: Any):
        return self._operation("DM-16", json=payload, has_json=True)

    def check_csv(self, *, tos_path: str):
        return self._operation("DM-17", json={"tos_path": tos_path}, has_json=True)

    def get_import_status(self, collection_id: Any):
        return self._operation("DM-18", path_params={"collection_id": collection_id})

    def get_import_errors(self, collection_id: Any):
        return self._operation("DM-19", path_params={"collection_id": collection_id})

    def preview_composite(self, *, node_type: int, payload: Mapping[str, Any] | None = None):
        return self._operation("DM-20", params={"node_type": node_type}, json=payload, has_json=payload is not None)

    # 文件系统
    def list_nodes(self, node_id: Any, *, type: str | None = None):
        return self._operation("FS-01", path_params={"id": node_id}, params=_compact({"type": type}))

    def get_node(self, node_id: Any):
        return self._operation("FS-02", path_params={"id": node_id})

    def create_node(self, *, name: str, type: int, parent_id: int, resource_id: int | None = None, owner_id: str | None = None):
        headers = {"X-Owner-ID": owner_id} if owner_id is not None else None
        body = {"name": name, "type": type, "parent_id": parent_id, "resource_id": resource_id}
        return self._operation("FS-03", json=_compact(body), headers=headers, has_json=True)

    def update_node(self, node_id: Any, **payload: Any):
        return self._operation("FS-04", path_params={"id": node_id}, json=payload, has_json=True)

    def delete_node(self, node_id: Any):
        return self._operation("FS-05", path_params={"id": node_id})

    def move_node(self, node_id: Any, *, target_parent_id: int):
        return self._operation("FS-06", path_params={"id": node_id}, json={"target_parent_id": target_parent_id}, has_json=True)

    def search_nodes(self, *, q: str, scope: str | None = None, owner_id: str | None = None):
        headers = {"X-Owner-ID": owner_id} if owner_id is not None else None
        return self._operation("FS-07", params=_compact({"q": q, "scope": scope}), headers=headers)

    def batch_list_nodes(self, ids: Any):
        return self._operation("FS-08", params={"ids": ids})

    def create_project_node(self, *, node_name: str, force: bool | None = None):
        return self._operation(
            "FS-09",
            json=_compact({"node_name": node_name, "force": force}),
            has_json=True,
        )

    def get_project_node_info(self, ids: Any):
        return self._operation("FS-10", params={"ids": ids})

    # Schema
    def create_schema(self, **payload: Any):
        return self._operation("SC-01", json=payload, has_json=True)

    def update_schema(self, **payload: Any):
        return self._operation("SC-02", json=payload, has_json=True)

    def delete_schema(self, schema_id: Any):
        return self._operation("SC-03", path_params={"id": schema_id})

    def get_schema(self, schema_id: Any):
        return self._operation("SC-04", path_params={"id": schema_id})

    def get_schema_by_name(self, *, name: str):
        return self._operation("SC-05", params={"name": name})

    def list_schemas(self, *, page: int | None = None, page_size: int | None = None):
        return self._operation("SC-06", params=_compact({"page": page, "page_size": page_size}))

    def create_schema_field(self, **payload: Any):
        return self._operation("SC-07", json=payload, has_json=True)

    def update_schema_field(self, **payload: Any):
        return self._operation("SC-08", json=payload, has_json=True)

    def delete_schema_field(self, field_id: Any):
        return self._operation("SC-09", path_params={"id": field_id})

    def get_schema_field(self, field_id: Any):
        return self._operation("SC-10", path_params={"id": field_id})

    def list_schema_fields(self, *, schema_id: Any, page: int | None = None, page_size: int | None = None, scene: str | None = None):
        return self._operation("SC-11", params=_compact({"schema_id": schema_id, "page": page, "page_size": page_size, "scene": scene}))

    def batch_update_schema_fields(self, **payload: Any):
        return self._operation("SC-12", json=payload, has_json=True)

    def sync_schema_fields_to_tos(self, *, schema_id: Any):
        return self._operation("SC-13", json={"schema_id": schema_id}, has_json=True)

    def list_schema_field_versions(self, *, schema_id: Any):
        return self._operation("SC-14", params={"schema_id": schema_id})

    def get_schema_field_version_snapshot(self, version_id: Any):
        return self._operation("SC-15", path_params={"version_id": version_id})

    def rollback_schema_field(self, version_id: Any, payload: Mapping[str, Any] | None = None):
        return self._operation("SC-16", path_params={"version_id": version_id}, json=payload, has_json=payload is not None)

    # 分享链接
    def create_share_link(self, **payload: Any):
        return self._operation("SH-01", json=payload, has_json=True)

    def get_share_link(self, link_id: Any):
        return self._operation("SH-02", path_params={"id": link_id})

    def list_share_links(self, **params: Any):
        return self._operation("SH-03", params=_compact(params))

    def terminate_share_link(self, link_id: Any):
        return self._operation("SH-04", path_params={"id": link_id})

    # 审计
    def list_audit_logs(self, **params: Any):
        return self._operation("AU-01", params=_compact(params))

    # 合同管理
    def list_contracts(self, **params: Any):
        return self._operation("CT-01", params=_compact(params))

    def get_contract(self, contract_id: Any):
        return self._operation("CT-02", path_params={"id": contract_id})

    def associate_contract(self, contract_id: Any, **payload: Any):
        return self._operation(
            "CT-03",
            path_params={"id": contract_id},
            json=payload,
            has_json=True,
        )

    def archive_contract(self, contract_id: Any, **payload: Any):
        return self._operation(
            "CT-04",
            path_params={"id": contract_id},
            json=payload,
            has_json=True,
        )

    def trigger_contract_sync(self):
        return self._operation("CT-05")

    # 供应商管理
    def list_suppliers(self, **params: Any):
        return self._operation("SP-01", params=_compact(params))

    def create_supplier(self, **payload: Any):
        return self._operation("SP-02", json=payload, has_json=True)

    def get_supplier(self, supplier_id: Any):
        return self._operation("SP-03", path_params={"id": supplier_id})

    def update_supplier(self, supplier_id: Any, **payload: Any):
        return self._operation(
            "SP-04",
            path_params={"id": supplier_id},
            json=payload,
            has_json=True,
        )

    def list_external_suppliers(self, **params: Any):
        return self._operation("SP-05", params=_compact(params))
