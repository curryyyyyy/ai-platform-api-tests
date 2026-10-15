from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.contract_diff import _add_inventory_changes, _inventory, _load


pytestmark = pytest.mark.contract


def _write_inventory(path: Path, operations: list[dict[str, str]]) -> None:
    path.write_text(json.dumps({"operations": operations}), encoding="utf-8")


def test_inventory_diff_is_reported_as_project_specific_governance(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_inventory(baseline, [{"method": "GET", "path": "/items", "operationId": "LIST"}])
    _write_inventory(current, [])
    result = {"breaking": [], "compatible": [], "summary": {"breaking": 0, "compatible": 0}}

    _add_inventory_changes(result, baseline, current)

    assert result["summary"]["breaking"] == 1
    assert result["breaking"] == [
        {
            "severity": "breaking",
            "location": "inventory GET /items",
            "detail": "operation removed: LIST",
        }
    ]


def test_inventory_accepts_business_id_as_stable_identifier(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    _write_inventory(inventory, [{"method": "post", "path": "/items", "id": "ITEM-CREATE"}])

    assert _inventory(_load(inventory, kind="inventory")) == {("POST", "/items", "ITEM-CREATE")}
