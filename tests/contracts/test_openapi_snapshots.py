from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.contract_coverage import validate_coverage
from scripts.contract_manifest import discover_manifests, load_manifest, relative_paths


ROOT = Path(__file__).resolve().parents[2]
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


@pytest.mark.contract
def test_all_platform_openapi_snapshots_are_valid_and_non_empty() -> None:
    """每个平台注册的 OpenAPI 快照都必须可解析且包含接口操作。"""
    for manifest_path in discover_manifests(ROOT):
        definition = load_manifest(manifest_path)
        for relative in relative_paths(definition["local"]["openapi"], field="local.openapi"):
            spec = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            assert isinstance(spec, dict), manifest_path
            assert isinstance(spec.get("openapi"), str) and spec["openapi"].startswith("3."), manifest_path
            paths = spec.get("paths")
            assert isinstance(paths, dict) and paths, manifest_path
            assert any(
                isinstance(path_item, dict)
                and any(method in HTTP_METHODS for method in path_item)
                for path_item in paths.values()
            ), manifest_path


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
