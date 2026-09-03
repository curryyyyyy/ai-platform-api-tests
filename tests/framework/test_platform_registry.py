from __future__ import annotations

import pytest

from framework.settings import load_settings
from platforms.registry import discover_platforms, get_platform


@pytest.mark.contract
def test_platform_registry_discovers_hawk_definition() -> None:
    """平台定义由适配包自注册，公共入口不维护 Hawk 客户端映射。"""
    definitions = discover_platforms()
    assert "hawk_admin" in definitions
    assert get_platform("hawk_admin").short_name == "hawk"


@pytest.mark.contract
@pytest.mark.hawk_admin
def test_marker_bound_anonymous_platform_client_has_no_token(anonymous_platform_client) -> None:
    """平台 marker 应绑定无鉴权客户端，无需通过 Hawk 专属 fixture。"""
    assert anonymous_platform_client.base_url
    assert "Authorization" not in anonymous_platform_client.session.headers


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
