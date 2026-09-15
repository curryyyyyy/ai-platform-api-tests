"""Load per-platform contract manifests.

The manifest is owned by the platform package.  This module deliberately
contains no platform names or endpoint knowledge; it only defines the common
configuration protocol consumed by the local contract tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


def load_manifest(path: Path) -> Dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"契约清单读取失败: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"契约清单必须是对象: {path}")
    if not isinstance(value.get("platform"), str) or not value["platform"].strip():
        raise ValueError(f"契约清单缺少 platform: {path}")
    if not isinstance(value.get("local"), dict):
        raise ValueError(f"契约清单缺少 local 配置: {path}")
    value["_manifest_path"] = str(path)
    return value


def discover_manifests(root: Path) -> List[Path]:
    """Discover platform-owned manifests without a central platform list."""
    manifests = sorted(root.glob("platforms/*/contract.yaml"))
    if not manifests:
        raise ValueError(f"未发现平台契约清单: {root / 'platforms'}/*/contract.yaml")
    return manifests


def relative_paths(values: Any, *, field: str) -> List[Path]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field} 必须是非空路径数组")
    if not all(isinstance(item, str) and item.strip() for item in values):
        raise ValueError(f"{field} 必须只包含非空字符串路径")
    paths = [Path(item) for item in values]
    if any(path.is_absolute() or ".." in path.parts for path in paths):
        raise ValueError(f"{field} 只能使用仓库内相对路径")
    return paths


def manifest_platform(path: Path, definition: Dict[str, Any]) -> str:
    value = definition.get("platform")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return path.parent.name


def select_manifests(
    root: Path,
    paths: Iterable[Path],
    platform: str = "",
) -> List[tuple[Path, Dict[str, Any]]]:
    selected: List[tuple[Path, Dict[str, Any]]] = []
    for path in paths:
        definition = load_manifest(path)
        name = manifest_platform(path, definition)
        if platform and name != platform:
            continue
        selected.append((path, definition))
    if not selected:
        detail = f"平台 {platform!r}" if platform else "平台"
        raise ValueError(f"未找到匹配的{detail}契约清单")
    return selected
