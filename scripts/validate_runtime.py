#!/usr/bin/env python3
"""Validate runtime inputs before any live API test is started.

The validator discovers platform manifests and settings by convention.  It
does not contain a platform list, endpoint, credential, or state prerequisite.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

try:
    from framework.settings import load_settings
    from scripts.contract_manifest import discover_manifests, load_manifest
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from framework.settings import load_settings
    from scripts.contract_manifest import discover_manifests, load_manifest


def _valid_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_runtime(root: Path, *, environment: str = "test", platform: str = "") -> list[str]:
    settings = load_settings(root, environment)
    manifests = [load_manifest(path) for path in discover_manifests(root)]
    names = [str(item["platform"]) for item in manifests]
    if platform:
        if platform not in names:
            return [f"未找到平台契约清单: {platform}"]
        names = [platform]

    errors: list[str] = []
    auth = settings.get("auth") if isinstance(settings.get("auth"), dict) else {}
    token = os.getenv("API_TOKEN", "").strip()
    if not token:
        credentials = settings.get("credentials") if isinstance(settings.get("credentials"), dict) else {}
        if not _valid_url(auth.get("base_url")):
            errors.append("未配置有效的总平台 AUTH_BASE_URL")
        if not str(credentials.get("username") or "").strip():
            errors.append("未配置 API_USER")
        if not str(credentials.get("password") or "").strip():
            errors.append("未配置 API_PASSWORD")

    platforms = settings.get("platforms") if isinstance(settings.get("platforms"), dict) else {}
    for name in names:
        config = platforms.get(name)
        if not isinstance(config, dict) or not _valid_url(config.get("base_url")):
            errors.append(f"未配置平台 {name} 的有效 base_url")
    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验线上接口测试所需的通用地址和凭证")
    parser.add_argument("--environment", default=os.getenv("TEST_ENV", "test"))
    parser.add_argument("--platform", default="", help="只校验指定平台")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        errors = validate_runtime(root, environment=args.environment, platform=args.platform)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print("线上测试运行时配置校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
