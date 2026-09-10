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
