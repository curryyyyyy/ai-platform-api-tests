from __future__ import annotations

import pytest

from framework.settings import load_settings
from platforms.registry import discover_platforms


@pytest.mark.contract
def test_platform_registry_discovers_platform_definitions() -> None:
    """平台定义由适配包自注册，公共入口不维护具体平台映射。"""
    definitions = discover_platforms()
    assert definitions
    assert all(definition.name == name for name, definition in definitions.items())
    assert all(callable(definition.client_factory) for definition in definitions.values())


@pytest.mark.contract
def test_settings_uses_generic_platform_base_url_override(tmp_path, monkeypatch) -> None:
    """任意平台均可使用 PLATFORM_<NAME>_BASE_URL 覆盖地址。"""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "test.yaml").write_text(
        "platforms:\n  sample-platform:\n    base_url: http://config.invalid\n", encoding="utf-8"
    )
    monkeypatch.setenv("PLATFORM_SAMPLE_PLATFORM_BASE_URL", "http://env.invalid")
    settings = load_settings(tmp_path)
    assert settings["platforms"]["sample-platform"]["base_url"] == "http://env.invalid"


@pytest.mark.contract
def test_settings_uses_platform_declared_legacy_base_url_alias(tmp_path, monkeypatch) -> None:
    """兼容地址变量由平台配置声明，通用配置加载器不需要知道平台名称。"""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "test.yaml").write_text(
        "platforms:\n  sample-platform:\n"
        "    base_url: http://config.invalid\n"
        "    legacy_base_url_env: SAMPLE_LEGACY_BASE_URL\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SAMPLE_LEGACY_BASE_URL", "http://legacy.invalid")

    settings = load_settings(tmp_path)
    assert settings["platforms"]["sample-platform"]["base_url"] == "http://legacy.invalid"
