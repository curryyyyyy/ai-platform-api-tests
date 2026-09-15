"""测试配置加载及环境变量覆盖。"""

from __future__ import annotations

import json
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

    def merge_file(path: Path, label: str) -> None:
        if not path.is_file():
            return
        try:
            with path.open(encoding="utf-8") as stream:
                value = yaml.safe_load(stream) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"{label}读取失败: {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{label}必须是对象: {path}")
        settings.update(_merge(settings, value))

    for path in (config_dir / f"{environment}.yaml", config_dir / f"{environment}.local.yaml"):
        merge_file(path, "根目录配置")

    auth = settings.setdefault("auth", {})
    platforms = settings.setdefault("platforms", {})
    credentials = settings.setdefault("credentials", {})
    if not isinstance(auth, dict) or not isinstance(platforms, dict) or not isinstance(credentials, dict):
        raise ValueError("配置中的 auth、platforms、credentials 必须是对象")

    # Platform-owned configuration is discovered by directory convention.  The
    # shared loader does not import or enumerate platform packages, so adding a
    # platform only requires adding its own config file.
    platform_root = root / "platforms"
    if platform_root.is_dir():
        for config_dir in sorted(platform_root.glob("*/config")):
            platform_name = config_dir.parent.name
            for path in (config_dir / f"{environment}.yaml", config_dir / f"{environment}.local.yaml"):
                if not path.is_file():
                    continue
                try:
                    with path.open(encoding="utf-8") as stream:
                        value = yaml.safe_load(stream) or {}
                except (OSError, yaml.YAMLError) as exc:
                    raise ValueError(f"平台配置读取失败: {path}: {exc}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"平台配置必须是对象: {path}")
                # Accept an optional platform key for readability, but never
                # let it select a different package than the owning directory.
                declared = value.get("platform")
                if declared is not None and declared != platform_name:
                    raise ValueError(f"平台配置名称与目录不一致: {path}")
                value = {key: item for key, item in value.items() if key != "platform"}
                existing = platforms.get(platform_name)
                platforms[platform_name] = _merge(existing, value) if isinstance(existing, dict) else value

    # CI can inject all platform URLs as one JSON secret without putting a
    # platform list into a shared workflow.  Individual generic environment
    # variables remain supported below and take precedence over this map.
    raw_base_urls = os.getenv("PLATFORM_BASE_URLS_JSON", "").strip()
    if raw_base_urls:
        try:
            base_urls = json.loads(raw_base_urls)
        except json.JSONDecodeError as exc:
            raise ValueError("PLATFORM_BASE_URLS_JSON 必须是 JSON 对象") from exc
        if not isinstance(base_urls, dict) or not all(
            isinstance(name, str) and isinstance(url, str) for name, url in base_urls.items()
        ):
            raise ValueError("PLATFORM_BASE_URLS_JSON 必须是 {platform: base_url} 对象")
        for name, url in base_urls.items():
            config = platforms.setdefault(name, {})
            if isinstance(config, dict):
                config["base_url"] = url

    auth["base_url"] = os.getenv("AUTH_BASE_URL", auth.get("base_url", ""))
    auth["rsa_path"] = os.getenv("AUTH_RSA_PATH", auth.get("rsa_path", "/api/auth/rsa"))
    auth["login_path"] = os.getenv("AUTH_LOGIN_PATH", auth.get("login_path", "/api/auth/login"))
    credentials["username"] = os.getenv("API_USER", credentials.get("username", ""))
    credentials["password"] = os.getenv("API_PASSWORD", credentials.get("password", ""))
    # 平台地址按配置键通用覆盖，兼容别名由各平台配置声明，避免框架绑定具体平台。
    for name, platform in platforms.items():
        if not isinstance(platform, dict):
            continue
        env_name = "PLATFORM_" + "_".join(part.upper() for part in name.replace("-", "_").split("_")) + "_BASE_URL"
        legacy_env = str(platform.get("legacy_base_url_env", ""))
        platform["base_url"] = os.getenv(env_name, os.getenv(legacy_env, platform.get("base_url", "")))
    return settings
