from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.contract_coverage import validate_coverage
from scripts.contract_manifest import discover_manifests, load_manifest, relative_paths


pytestmark = pytest.mark.contract


def test_current_platform_operation_coverage_is_complete() -> None:
    root = Path(__file__).resolve().parents[2]
    for manifest_path in discover_manifests(root):
        definition = load_manifest(manifest_path)
        local = definition["local"]
        openapi = [root / path for path in relative_paths(local["openapi"], field="local.openapi")]
        inventory = root / local["inventory"]
        coverage = root / local["coverage"]
        report = validate_coverage(openapi, inventory, coverage, repo_root=root)
        assert report["ok"], f"{manifest_path}: {report}"


def test_new_operation_is_blocked_until_inventory_and_case_mapping_are_added(tmp_path: Path) -> None:
    openapi = tmp_path / "openapi.yaml"
    inventory = tmp_path / "inventory.json"
    coverage = tmp_path / "coverage.yaml"
    openapi.write_text(
        yaml.safe_dump(
            {
                "openapi": "3.0.3",
                "paths": {
                    "/items": {"get": {"operationId": "listItems", "responses": {"200": {"description": "ok"}}}},
                    "/items/{id}": {"get": {"operationId": "getItem", "responses": {"200": {"description": "ok"}}}},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    inventory.write_text(
        json.dumps({"operations": [{"id": "LIST", "method": "GET", "path": "/items"}]}),
        encoding="utf-8",
    )
    coverage.write_text(
        "entries:\n  - id: TC-01\n    operations: [LIST]\n    tests: [tests/test_items.py::test_list]\n",
        encoding="utf-8",
    )

    report = validate_coverage([openapi], inventory, coverage)

    assert report["ok"] is False
    assert report["missing_inventory"] == ["GET /items/{id}"]


def test_stale_test_function_reference_is_blocked(tmp_path: Path) -> None:
    openapi = tmp_path / "openapi.yaml"
    inventory = tmp_path / "inventory.json"
    coverage = tmp_path / "coverage.yaml"
    test_file = tmp_path / "tests/test_items.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_current():\n    pass\n", encoding="utf-8")
    openapi.write_text(
        yaml.safe_dump(
            {"openapi": "3.0.3", "paths": {"/items": {"get": {"operationId": "listItems", "responses": {"200": {"description": "ok"}}}}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    inventory.write_text(
        json.dumps({"operations": [{"id": "LIST", "method": "GET", "path": "/items"}]}),
        encoding="utf-8",
    )
    coverage.write_text(
        "entries:\n  - id: TC-01\n    operations: [LIST]\n    tests: [tests/test_items.py::test_removed]\n",
        encoding="utf-8",
    )

    report = validate_coverage([openapi], inventory, coverage, repo_root=tmp_path)

    assert report["ok"] is False
    assert report["invalid_tests"] == ["tests/test_items.py::test_removed"]
