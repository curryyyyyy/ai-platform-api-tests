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
    hawk = platforms.setdefault("hawk_admin", {})
    hawk["base_url"] = os.getenv("HAWK_ADMIN_BASE_URL", hawk.get("base_url", ""))
    return settings
