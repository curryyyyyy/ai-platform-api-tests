from __future__ import annotations

from pathlib import Path

import pytest

from framework.openapi import OpenApiContracts
from scripts.contract_coverage import validate_coverage
from scripts.contract_manifest import discover_manifests, load_manifest, relative_paths


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.contract
def test_all_platform_openapi_snapshots_are_valid_and_non_empty() -> None:
    """每个平台注册的 OpenAPI 快照都必须可解析且包含接口操作。"""
    for manifest_path in discover_manifests(ROOT):
        definition = load_manifest(manifest_path)
        contracts = OpenApiContracts.from_files(
            ROOT / relative
            for relative in relative_paths(definition["local"]["openapi"], field="local.openapi")
        )
        assert contracts.operation_count > 0, manifest_path


@pytest.mark.contract
def test_all_platform_inventories_match_their_snapshots() -> None:
    """接口清单和快照按 method + path 对齐，并且都有自动化覆盖。"""
    for manifest_path in discover_manifests(ROOT):
        definition = load_manifest(manifest_path)
        local = definition["local"]
        openapi = [ROOT / path for path in relative_paths(local["openapi"], field="local.openapi")]
        report = validate_coverage(
            openapi,
            ROOT / local["inventory"],
            ROOT / local["coverage"],
            repo_root=ROOT,
        )
        assert report["ok"], f"{manifest_path}: {report}"
