#!/usr/bin/env python3
"""
Orchestrate mature OpenAPI diff output and project inventory governance.

OpenAPI compatibility semantics belong to ``oasdiff``. This module only owns
document loading, inventory identity checks, report aggregation and the CLI.
It does not update tests or contracts: an intentional API change still
requires a reviewed update to the contract, client, data, and case mapping.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union, cast

import yaml


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
JSONDict = Dict[str, Any]
PathInput = Union[Path, Sequence[Path]]


def _load(path: Path, *, kind: str) -> JSONDict:
    try:
        if kind == "openapi":
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"无法读取 {kind} 契约 {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{kind} 契约必须是对象: {path}")
    return cast(JSONDict, value)


def _load_openapi_bundle(paths: PathInput) -> JSONDict:
    """Load one OpenAPI document or merge a bundle of non-overlapping docs."""
    values = [paths] if isinstance(paths, Path) else list(paths)
    if not values:
        raise ValueError("OpenAPI 契约至少需要一个文件")
    documents = [_load(path, kind="openapi") for path in values]
    if len(documents) == 1:
        return documents[0]

    merged: JSONDict = {"openapi": documents[0].get("openapi", "3.0.3"), "paths": {}}
    for key in ("info", "servers", "tags", "security"):
        if key in documents[0]:
            merged[key] = documents[0][key]
    components: JSONDict = {}
    for document in documents:
        paths_value = document.get("paths")
        if not isinstance(paths_value, dict):
            raise ValueError("OpenAPI bundle 中的文档缺少 paths 对象")
        merged_paths = cast(Dict[str, Any], merged["paths"])
        for path, path_item in paths_value.items():
            if not isinstance(path, str):
                continue
            if path in merged_paths:
                existing = merged_paths[path]
                if existing != path_item:
                    raise ValueError(f"OpenAPI bundle 存在重复且不一致的路径: {path}")
            else:
                merged_paths[path] = path_item
        document_components = document.get("components")
        if not isinstance(document_components, dict):
            continue
        for component_type, values in document_components.items():
            if not isinstance(values, dict):
                merged.setdefault("components", {})[component_type] = values
                continue
            target = cast(Dict[str, Any], components.setdefault(component_type, {}))
            for name, value in values.items():
                if name in target and target[name] != value:
                    raise ValueError(
                        f"OpenAPI bundle 存在重复且不一致的组件: {component_type}/{name}"
                    )
                target[name] = value
    if components:
        merged["components"] = components
    return merged


def _operations(spec: JSONDict) -> Dict[Tuple[str, str], JSONDict]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI 缺少 paths 对象")
    result: Dict[Tuple[str, str], JSONDict] = {}
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if not isinstance(method, str) or method.lower() not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            result[(method.upper(), path)] = cast(JSONDict, operation)
    if not result:
        raise ValueError("OpenAPI 没有可比较的接口操作")
    return result


def _inventory(value: JSONDict) -> Set[Tuple[str, str, str]]:
    operations = value.get("operations")
    if not isinstance(operations, list):
        raise ValueError("接口清单缺少 operations 数组")
    result: Set[Tuple[str, str, str]] = set()
    for item in operations:
        if not isinstance(item, dict):
            continue
        method, path = item.get("method"), item.get("path")
        # Platform-owned inventories may use a stable business id instead of
        # OpenAPI's optional operationId. Both forms identify the same
        # inventory record for diff purposes.
        operation_id = item.get("operationId") or item.get("id")
        if all(isinstance(part, str) and part.strip() for part in (method, path, operation_id)):
            result.add((method.upper(), path, operation_id))
    return result


def compare_with_engine(
    baseline_openapi: PathInput,
    current_openapi: PathInput,
    *,
    baseline_inventory: Optional[Path] = None,
    current_inventory: Optional[Path] = None,
    engine: str = "auto",
) -> JSONDict:
    """Compare OpenAPI with a mature engine, retaining project-specific checks.

    ``oasdiff`` is the sole OpenAPI semantic comparison engine. ``auto`` is
    retained as a local convenience alias, but never falls back to duplicate
    in-repository Schema rules.
    """
    if engine not in {"auto", "oasdiff"}:
        raise ValueError(f"不支持的契约 diff 引擎: {engine}")

    try:
        from scripts.openapi_diff_engine import OasDiffUnavailable, compare
    except ModuleNotFoundError:  # pragma: no cover - direct script entry point
        from openapi_diff_engine import OasDiffUnavailable, compare

    try:
        result = compare(
            _paths(baseline_openapi),
            _paths(current_openapi),
        )
    except OasDiffUnavailable:
        raise RuntimeError(
            "oasdiff 未安装；请先安装项目锁定的 Node 依赖和当前平台原生包"
        ) from None

    if baseline_inventory is not None and current_inventory is not None:
        _add_inventory_changes(result, baseline_inventory, current_inventory)
    result["engine"] = "oasdiff"
    return result


def _paths(value: PathInput) -> List[Path]:
    return [value] if isinstance(value, Path) else list(value)


def _add_inventory_changes(result: JSONDict, baseline: Path, current: Path) -> None:
    old_inventory = _inventory(_load(baseline, kind="inventory"))
    new_inventory = _inventory(_load(current, kind="inventory"))
    for item in sorted(old_inventory - new_inventory):
        result["breaking"].append(
            {"severity": "breaking", "location": f"inventory {item[0]} {item[1]}", "detail": f"operation removed: {item[2]}"}
        )
    for item in sorted(new_inventory - old_inventory):
        result["compatible"].append(
            {"severity": "compatible", "location": f"inventory {item[0]} {item[1]}", "detail": f"operation added: {item[2]}"}
        )
    result["breaking"].sort(key=lambda item: (item["location"], item["detail"]))
    result["compatible"].sort(key=lambda item: (item["location"], item["detail"]))
    result["summary"]["breaking"] = len(result["breaking"])
    result["summary"]["compatible"] = len(result["compatible"])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="比较 OpenAPI 契约并检测破坏性变更")
    parser.add_argument("--baseline-openapi", type=Path, action="append", required=True)
    parser.add_argument("--current-openapi", type=Path, action="append", required=True)
    parser.add_argument("--baseline-inventory", type=Path)
    parser.add_argument("--current-inventory", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--fail-on-breaking", action="store_true")
    parser.add_argument(
        "--engine",
        choices=("auto", "oasdiff"),
        default="auto",
        help="OpenAPI 比较引擎；auto 是 oasdiff 的本地别名",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if bool(args.baseline_inventory) != bool(args.current_inventory):
        print("baseline/current inventory 必须同时提供", file=sys.stderr)
        return 2
    try:
        result = compare_with_engine(
            args.baseline_openapi,
            args.current_openapi,
            baseline_inventory=args.baseline_inventory,
            current_inventory=args.current_inventory,
            engine=args.engine,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    print(
        "契约 diff: "
        f"breaking={result['summary']['breaking']} "
        f"compatible={result['summary']['compatible']} "
        f"operations={result['summary']['baseline_operations']}->{result['summary']['current_operations']}"
    )
    for change in result["breaking"]:
        print(f"BREAKING {change['location']}: {change['detail']}", file=sys.stderr)
    if args.fail_on_breaking and result["breaking"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
