"""测试配置加载及环境变量覆盖。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(root: Path, environment: str = "test") -> dict[str, Any]:
    config_dir = root / "config"
    settings: dict[str, Any] = {}
    for path in (config_dir / f"{environment}.yaml", config_dir / f"{environment}.local.yaml"):
        if path.exists():
            with path.open(encoding="utf-8") as stream:
                value = yaml.safe_load(stream) or {}
            if isinstance(value, dict):
                settings = _merge(settings, value)

    auth = settings.setdefault("auth", {})
    platforms = settings.setdefault("platforms", {})
    credentials = settings.setdefault("credentials", {})
    auth["base_url"] = os.getenv("AUTH_BASE_URL", auth.get("base_url", ""))
    auth["rsa_path"] = os.getenv("AUTH_RSA_PATH", auth.get("rsa_path", "/api/auth/rsa"))
    auth["login_path"] = os.getenv("AUTH_LOGIN_PATH", auth.get("login_path", "/api/auth/login"))
    credentials["username"] = os.getenv("API_USER", credentials.get("username", ""))
    credentials["password"] = os.getenv("API_PASSWORD", credentials.get("password", ""))
    # 平台地址按配置键通用覆盖，避免每接入一个平台就修改框架代码。
    # 保留旧的 HAWK_ADMIN_BASE_URL 作为兼容别名。
    for name, platform in platforms.items():
        if not isinstance(platform, dict):
            continue
        env_name = "PLATFORM_" + "_".join(part.upper() for part in name.replace("-", "_").split("_")) + "_BASE_URL"
        legacy_env = "HAWK_ADMIN_BASE_URL" if name == "hawk_admin" else ""
        platform["base_url"] = os.getenv(env_name, os.getenv(legacy_env, platform.get("base_url", "")))
    return settings
