from __future__ import annotations

from pathlib import Path

import pytest

from scripts.fetch_contracts import fetch_contracts, gitlab_file_url


@pytest.mark.contract
def test_gitlab_file_url_encodes_project_path_and_ref() -> None:
    url = gitlab_file_url(
        "https://gitlab.example/api/v4",
        "team/api-tests",
        "api-tests/openapi.yaml",
        "release/2026-09",
    )
    assert url == (
        "https://gitlab.example/api/v4/projects/team%2Fapi-tests/repository/files/"
        "api-tests%2Fopenapi.yaml/raw?ref=release%2F2026-09"
    )


@pytest.mark.contract
def test_gitlab_file_url_accepts_project_homepage_url() -> None:
    url = gitlab_file_url(
        "https://gitlab.com/api/v4",
        "https://gitlab.example/team/api-tests/-/tree/main",
        "openapi.yaml",
        "main",
    )
    assert "/projects/team%2Fapi-tests/repository/files/openapi.yaml/raw" in url


@pytest.mark.contract
def test_fetch_contracts_requires_both_direct_urls(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="必须同时配置"):
        fetch_contracts(
            platform="hawk_admin",
            root=tmp_path,
            openapi_url="https://gitlab.example/openapi.yaml",
            required=True,
        )


@pytest.mark.contract
def test_fetch_contracts_optional_without_source_keeps_snapshot(tmp_path: Path) -> None:
    assert fetch_contracts(platform="hawk_admin", root=tmp_path) is False
