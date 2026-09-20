from __future__ import annotations

import json
from pathlib import Path

import pytest

from platforms.source_admin.client import OPERATION_METHODS, OPERATION_ROUTES, SourceAdminClient


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "contracts/source_admin/api_inventory.json"

pytestmark = [pytest.mark.contract, pytest.mark.source_admin]


def _inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def test_source_admin_inventory_has_62_unique_operations() -> None:
    inventory = _inventory()
    operations = inventory["operations"]
    assert len(operations) == 62
    assert len({item["id"] for item in operations}) == 62
    assert len({(item["method"], item["path"]) for item in operations}) == 62
    assert sum(item["documented_in_primary"] for item in operations) == 43
    assert len(inventory["documented_gaps"]) == 19


def test_source_admin_client_methods_cover_inventory() -> None:
    inventory_ids = {item["id"] for item in _inventory()["operations"]}
    assert set(OPERATION_ROUTES) == inventory_ids
    assert set(OPERATION_METHODS) == inventory_ids

    client = SourceAdminClient("http://source-admin.invalid", retries=0)
    for operation_id, method_name in OPERATION_METHODS.items():
        assert callable(getattr(client, method_name, None)), operation_id


def test_source_admin_client_routes_match_inventory() -> None:
    expected = {
        (item["id"], item["method"], item["path"])
        for item in _inventory()["operations"]
    }
    actual = {
        (operation_id, method, path)
        for operation_id, (method, path) in OPERATION_ROUTES.items()
    }
    assert actual == expected


def test_source_admin_client_uses_bearer_token_and_formats_path(monkeypatch) -> None:
    client = SourceAdminClient("http://source-admin.invalid", token="central-token", retries=0)
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method: str, path: str, **kwargs):
        calls.append((method, path, kwargs))
        return object()

    monkeypatch.setattr(client, "request", fake_request)
    client.get_collection_data("collection/42", fields=[{"name": "rowkey", "source": 2}], page=1)

    assert client.session.headers["Authorization"] == "Bearer central-token"
    assert calls == [
        (
            "POST",
            "/api/v1/collections/collection%2F42/data",
            {"json": {"fields": [{"name": "rowkey", "source": 2}], "page": 1}},
        )
    ]


def test_source_admin_client_uses_latest_collection_and_search_inputs(monkeypatch) -> None:
    client = SourceAdminClient("http://source-admin.invalid", retries=0)
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method: str, path: str, **kwargs):
        calls.append((method, path, kwargs))
        return object()

    monkeypatch.setattr(client, "request", fake_request)
    client.create_collection_from_rowkeys(
        parent_node_id=7,
        name="rowkey-collection",
        cid=42,
        rowkeys=["rowkey-1"],
    )
    client.search_nodes(q="folder", scope="path", parents_node_id=7)

    assert calls == [
        (
            "POST",
            "/api/v1/collections/create-from-rowkeys",
            {
                "json": {
                    "parent_node_id": 7,
                    "name": "rowkey-collection",
                    "cid": 42,
                    "rowkeys": ["rowkey-1"],
                }
            },
        ),
        (
            "GET",
            "/api/v1/nodes/search",
            {"params": {"q": "folder", "scope": "path", "parents_node_id": 7}},
        ),
    ]
