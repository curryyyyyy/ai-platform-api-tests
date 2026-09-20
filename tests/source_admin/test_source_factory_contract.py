from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from requests import Response

from framework.data.scope import DataScope
from platforms.source_admin.client import SourceAdminClient
from platforms.source_admin.factories import SourceAdminDataFactory


pytestmark = [pytest.mark.contract, pytest.mark.source_admin]


class FakeClient(SourceAdminClient):
    def __init__(self) -> None:
        super().__init__("http://source-admin.invalid", retries=0)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def _response(self, payload: dict[str, Any]) -> Response:
        response = SimpleNamespace(status_code=200)
        response.json = lambda: payload
        return cast(Response, response)

    def create_schema(self, **payload: Any) -> Response:
        self.calls.append(("POST", "/api/v1/schema", {"json": payload}))
        return self._response({"code": 0, "msg": "ok", "data": {"data": {"id": 11}}})

    def delete_schema(self, schema_id: Any) -> Response:
        self.calls.append(("DELETE", f"/api/v1/schema/{schema_id}", {}))
        return self._response({"code": 0, "msg": "ok", "data": {}})

    def create_collection_from_rowkeys(self, **payload: Any) -> Response:
        self.calls.append(("POST", "/api/v1/collections/create-from-rowkeys", {"json": payload}))
        return self._response({"code": 0, "msg": "ok", "data": {"collection_id": 42, "status": 2}})

    def get_collection_node_path(self, collection_id: Any) -> Response:
        self.calls.append(("GET", f"/api/v1/collections/{collection_id}/node-path", {}))
        return self._response({
            "code": 0,
            "msg": "ok",
            "data": {"path": [
                {"id": 1, "name": "/", "type": 1},
                {"id": 2187, "name": "TC-SOURCE-ROWKEY-001-rowkey-collection-abc123", "type": 2},
            ]},
        })

    def delete_node(self, node_id: Any) -> Response:
        self.calls.append(("DELETE", f"/api/v1/nodes/{node_id}", {}))
        return self._response({"code": 0, "msg": "ok", "data": {}})


def test_source_factory_registers_schema_cleanup() -> None:
    client = FakeClient()
    scope = DataScope("TC-SOURCE-SCHEMA-001")
    factory = SourceAdminDataFactory(client, scope)

    schema_id, payload = factory.create_schema()

    assert schema_id == "11"
    assert payload["name"].startswith("TC-SOURCE-SCHEMA-001-schema-")
    scope.cleanup()
    assert [(method, path) for method, path, _ in client.calls] == [
        ("POST", "/api/v1/schema"),
        ("DELETE", "/api/v1/schema/11"),
    ]


def test_source_factory_registers_rowkeys_collection_node_cleanup() -> None:
    client = FakeClient()
    scope = DataScope("TC-SOURCE-ROWKEY-001")
    factory = SourceAdminDataFactory(client, scope)

    collection_id, payload, created = factory.create_collection_from_rowkeys(
        parent_node_id=1,
        source_collection_id=7,
        rowkeys=["rk-001"],
        name="TC-SOURCE-ROWKEY-001-rowkey-collection-abc123",
    )

    assert collection_id == "42"
    assert payload["cid"] == 7
    assert created["status"] == 2
    scope.cleanup()
    assert [(method, path) for method, path, _ in client.calls] == [
        ("POST", "/api/v1/collections/create-from-rowkeys"),
        ("GET", "/api/v1/collections/42/node-path"),
        ("DELETE", "/api/v1/nodes/2187"),
    ]
