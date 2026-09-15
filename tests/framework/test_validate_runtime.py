from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_runtime import validate_runtime


pytestmark = pytest.mark.contract


def _write_runtime_repo(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "config/test.yaml").write_text(
        "auth:\n  base_url: https://auth.example\n"
        "credentials:\n  username: user\n  password: pass\n",
        encoding="utf-8",
    )
    (root / "platforms/demo/config").mkdir(parents=True)
    (root / "platforms/demo/config/test.yaml").write_text(
        "platform: demo\nbase_url: https://demo.example/api\n", encoding="utf-8"
    )
    (root / "platforms/demo/contract.yaml").write_text(
        "platform: demo\nlocal:\n  openapi: [contracts/demo.yaml]\n",
        encoding="utf-8",
    )


def test_validate_runtime_discovers_platform_owned_configuration(tmp_path: Path) -> None:
    _write_runtime_repo(tmp_path)

    assert validate_runtime(tmp_path) == []


def test_validate_runtime_reports_missing_platform_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PLATFORM_BASE_URLS_JSON", raising=False)
    _write_runtime_repo(tmp_path)
    (tmp_path / "platforms/demo/config/test.yaml").write_text(
        "platform: demo\nbase_url: ''\n", encoding="utf-8"
    )

    errors = validate_runtime(tmp_path)

    assert errors == ["未配置平台 demo 的有效 base_url"]
