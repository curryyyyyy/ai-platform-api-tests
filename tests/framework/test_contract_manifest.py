from __future__ import annotations

from pathlib import Path

import pytest

from scripts.contract_manifest import discover_manifests, load_manifest, relative_paths


pytestmark = pytest.mark.contract


def test_platform_manifests_are_discovered_without_central_platform_list() -> None:
    root = Path(__file__).resolve().parents[2]
    manifests = discover_manifests(root)
    platforms = [path.parent.name for path in manifests]
    assert platforms
    assert len(platforms) == len(set(platforms))
    assert all(path.name == "contract.yaml" for path in manifests)


def test_platform_manifest_contains_only_local_snapshot_metadata() -> None:
    root = Path(__file__).resolve().parents[2]
    definition = load_manifest(root / "platforms/hawk_admin/contract.yaml")
    assert set(definition) >= {"platform", "local"}
    assert "remote" not in definition


@pytest.mark.parametrize("value", [["../outside.yaml"], ["/absolute.yaml"]])
def test_manifest_paths_cannot_escape_repository(value) -> None:
    from scripts.contract_manifest import relative_paths

    with pytest.raises(ValueError, match="仓库内相对路径"):
        relative_paths(value, field="local.openapi")
