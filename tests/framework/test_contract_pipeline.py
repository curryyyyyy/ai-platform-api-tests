from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.contract_pipeline import run_platform


pytestmark = pytest.mark.contract


def test_run_platform_uses_manifest_paths_and_writes_report(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    openapi = root / "contracts/demo/openapi.yaml"
    inventory = root / "contracts/demo/api_inventory.json"
    openapi.parent.mkdir(parents=True)
    openapi.write_text(
        yaml.safe_dump(
            {"openapi": "3.0.3", "paths": {"/items": {"get": {"operationId": "listItems", "responses": {"200": {"description": "ok"}}}}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    inventory.write_text(
        json.dumps({"operations": [{"method": "GET", "path": "/items", "operationId": "listItems"}]}),
        encoding="utf-8",
    )

    report = run_platform(
        root,
        "demo",
        {
            "local": {
                "openapi": ["contracts/demo/openapi.yaml"],
                "inventory": "contracts/demo/api_inventory.json",
            },
        },
        base_ref="",
        report_root=tmp_path / "reports",
    )

    assert report["summary"] == {
        "breaking": 0,
        "compatible": 0,
        "baseline_operations": 1,
        "current_operations": 1,
    }
    assert (tmp_path / "reports/demo-diff.json").is_file()


def test_run_platform_reads_latest_contract_from_local_source_tree(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    openapi = root / "contracts/demo/openapi.yaml"
    inventory = root / "contracts/demo/api_inventory.json"
    source = tmp_path / "service"
    openapi.parent.mkdir(parents=True)
    source.mkdir()
    openapi.write_text(
        yaml.safe_dump(
            {"openapi": "3.0.3", "paths": {"/items": {"get": {"responses": {"200": {"description": "ok"}}}}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    inventory.write_text(json.dumps({"operations": [{"method": "GET", "path": "/items", "id": "LIST"}]}), encoding="utf-8")
    (source / "openapi.yaml").write_text(
        yaml.safe_dump(
            {
                "openapi": "3.0.3",
                "paths": {
                    "/items": {"get": {"responses": {"200": {"description": "ok"}}}},
                    "/new": {"get": {"responses": {"200": {"description": "ok"}}}},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    definition = {
        "local": {"openapi": ["contracts/demo/openapi.yaml"], "inventory": "contracts/demo/api_inventory.json"},
        "source": {"openapi": ["openapi.yaml"]},
    }

    report = run_platform(root, "demo", definition, base_ref="", report_root=tmp_path / "reports", source_root=source)

    assert report["summary"]["compatible"] >= 1
