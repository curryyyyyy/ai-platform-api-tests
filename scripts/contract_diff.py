#!/usr/bin/env python3
"""Compare two OpenAPI contracts and report consumer-breaking changes.

This is intentionally a small, dependency-free (apart from the project's
PyYAML dependency) guard for CI.  It does not update tests or contracts: an
intentional API change still requires a reviewed update to the contract,
client, data, and case mapping.
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
Change = Dict[str, str]
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


def _operation_id(operation: JSONDict, method: str, path: str) -> str:
    value = operation.get("operationId")
    return value if isinstance(value, str) and value else f"{method} {path}"


def _schema(value: Any) -> Optional[JSONDict]:
    return cast(JSONDict, value) if isinstance(value, dict) else None


def _resolve_schema(ref: str, root: Optional[JSONDict]) -> Optional[JSONDict]:
    prefix = "#/components/schemas/"
    if root is None or not ref.startswith(prefix):
        return None
    components = root.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    value = schemas.get(ref[len(prefix):]) if isinstance(schemas, dict) else None
    return _schema(value)


def _schema_changes(
    baseline: Optional[JSONDict],
    current: Optional[JSONDict],
    *,
    baseline_root: Optional[JSONDict] = None,
    current_root: Optional[JSONDict] = None,
    location: str,
    changes: List[Change],
    seen: Set[Tuple[str, str, str]],
    visited_refs: Optional[Set[Tuple[str, str]]] = None,
) -> None:
    """Compare the contract parts that affect request/response consumers.

    The comparison is deliberately conservative.  A type change, a narrower
    enum, or a newly-required property can break an existing client and is
    therefore reported as breaking.  Added optional properties are compatible.
    ``$ref`` targets under ``#/components/schemas`` are dereferenced with a
    cycle guard so changes to a shared response/request model are reported.
    """
    if baseline is None and current is None:
        return
    if baseline is None:
        _change(changes, seen, "compatible", location, "schema was added")
        return
    if current is None:
        _change(changes, seen, "breaking", location, "schema was removed")
        return
    visited_refs = visited_refs or set()
    baseline_ref = baseline.get("$ref")
    current_ref = current.get("$ref")
    if baseline_ref != current_ref and (baseline_ref or current_ref):
        _change(changes, seen, "breaking", location, "schema reference changed")
    if baseline_ref or current_ref:
        if not isinstance(baseline_ref, str) or not isinstance(current_ref, str):
            return
        ref_pair = (baseline_ref, current_ref)
        if ref_pair in visited_refs:
            return
        visited_refs.add(ref_pair)
        baseline_resolved = _resolve_schema(baseline_ref, baseline_root)
        current_resolved = _resolve_schema(current_ref, current_root)
        if baseline_resolved is not None and current_resolved is not None:
            _schema_changes(
                baseline_resolved,
                current_resolved,
                baseline_root=baseline_root,
                current_root=current_root,
                location=location,
                changes=changes,
                seen=seen,
                visited_refs=visited_refs,
            )
        return
    baseline_type = baseline.get("type")
    current_type = current.get("type")
    if baseline_type != current_type and baseline_type is not None and current_type is not None:
        _change(
            changes,
            seen,
            "breaking",
            location,
            f"schema type changed: {baseline_type!r} -> {current_type!r}",
        )

    baseline_enum = baseline.get("enum")
    current_enum = current.get("enum")
    if isinstance(baseline_enum, list) and isinstance(current_enum, list):
        removed_enum = [item for item in baseline_enum if item not in current_enum]
        added_enum = [item for item in current_enum if item not in baseline_enum]
        if removed_enum:
            _change(changes, seen, "breaking", location, "enum values were removed")
        elif added_enum:
            _change(changes, seen, "compatible", location, "enum values were added")

    baseline_required = _string_values(baseline.get("required"))
    current_required = _string_values(current.get("required"))
    for name in sorted(current_required - baseline_required):
        _change(changes, seen, "breaking", f"{location}.{name}", "property became required")
    for name in sorted(baseline_required - current_required):
        _change(changes, seen, "compatible", f"{location}.{name}", "property is no longer required")

    baseline_properties = baseline.get("properties")
    current_properties = current.get("properties")
    if not isinstance(baseline_properties, dict) or not isinstance(current_properties, dict):
        return
    for name in sorted(set(baseline_properties) - set(current_properties)):
        _change(changes, seen, "breaking", f"{location}.{name}", "property was removed")
    for name in sorted(set(current_properties) - set(baseline_properties)):
        _change(changes, seen, "compatible", f"{location}.{name}", "optional property was added")
    for name in sorted(set(baseline_properties) & set(current_properties)):
        _schema_changes(
            _schema(baseline_properties[name]),
            _schema(current_properties[name]),
            baseline_root=baseline_root,
            current_root=current_root,
            location=f"{location}.{name}",
            changes=changes,
            seen=seen,
            visited_refs=visited_refs,
        )


def _change(
    changes: List[Change],
    seen: Set[Tuple[str, str, str]],
    severity: str,
    location: str,
    detail: str,
) -> None:
    key = (severity, location, detail)
    if key in seen:
        return
    seen.add(key)
    changes.append({"severity": severity, "location": location, "detail": detail})


def _parameters(operation: JSONDict, path_item: Optional[JSONDict] = None) -> Dict[Tuple[str, str], JSONDict]:
    values: List[Any] = []
    if isinstance(path_item, dict):
        values.extend(path_item.get("parameters") or [])
    values.extend(operation.get("parameters") or [])
    result: Dict[Tuple[str, str], JSONDict] = {}
    for value in values:
        if not isinstance(value, dict) or "$ref" in value:
            continue
        name, location = value.get("name"), value.get("in")
        if isinstance(name, str) and isinstance(location, str):
            result[(location, name)] = value
    return result


def _required(parameter: JSONDict, location: str) -> bool:
    return location == "path" or parameter.get("required") is True


def _content_schema(value: Any, media_type: str) -> Optional[JSONDict]:
    if not isinstance(value, dict):
        return None
    content = value.get("content")
    if not isinstance(content, dict) or not isinstance(content.get(media_type), dict):
        return None
    return _schema(content[media_type].get("schema"))


def _string_values(value: Any) -> Set[str]:
    """Return only valid string entries from an OpenAPI list-valued field."""
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _compare_operation(
    method: str,
    path: str,
    baseline: JSONDict,
    current: JSONDict,
    *,
    changes: List[Change],
    seen: Set[Tuple[str, str, str]],
    baseline_path_item: Optional[JSONDict] = None,
    current_path_item: Optional[JSONDict] = None,
    baseline_root: Optional[JSONDict] = None,
    current_root: Optional[JSONDict] = None,
) -> None:
    operation = _operation_id(baseline, method, path)
    current_operation = _operation_id(current, method, path)
    if operation != current_operation:
        _change(changes, seen, "breaking", f"{method} {path}", f"operationId changed: {operation!r} -> {current_operation!r}")

    baseline_parameters = _parameters(baseline, baseline_path_item)
    current_parameters = _parameters(current, current_path_item)
    for key in sorted(set(baseline_parameters) - set(current_parameters)):
        _change(changes, seen, "breaking", f"{method} {path} parameter {key[0]}:{key[1]}", "parameter was removed")
    for key in sorted(set(current_parameters) - set(baseline_parameters)):
        parameter = current_parameters[key]
        severity = "breaking" if _required(parameter, key[0]) else "compatible"
        _change(changes, seen, severity, f"{method} {path} parameter {key[0]}:{key[1]}", "parameter was added")
    for key in sorted(set(baseline_parameters) & set(current_parameters)):
        old, new = baseline_parameters[key], current_parameters[key]
        location = f"{method} {path} parameter {key[0]}:{key[1]}"
        if not _required(old, key[0]) and _required(new, key[0]):
            _change(changes, seen, "breaking", location, "parameter became required")
        _schema_changes(
            _schema(old.get("schema")),
            _schema(new.get("schema")),
            baseline_root=baseline_root,
            current_root=current_root,
            location=location,
            changes=changes,
            seen=seen,
        )

    old_body = baseline.get("requestBody")
    new_body = current.get("requestBody")
    if isinstance(old_body, dict) and isinstance(new_body, dict):
        if old_body.get("required") is not True and new_body.get("required") is True:
            _change(changes, seen, "breaking", f"{method} {path} requestBody", "request body became required")
        old_content = old_body.get("content") if isinstance(old_body.get("content"), dict) else {}
        new_content = new_body.get("content") if isinstance(new_body.get("content"), dict) else {}
        for media_type in sorted(set(old_content) - set(new_content)):
            _change(changes, seen, "breaking", f"{method} {path} requestBody {media_type}", "request media type was removed")
        for media_type in sorted(set(old_content) & set(new_content)):
            _schema_changes(
                _content_schema(old_body, media_type),
                _content_schema(new_body, media_type),
                baseline_root=baseline_root,
                current_root=current_root,
                location=f"{method} {path} requestBody {media_type}",
                changes=changes,
                seen=seen,
            )
    elif isinstance(new_body, dict) and new_body.get("required") is True:
        _change(changes, seen, "breaking", f"{method} {path} requestBody", "required request body was added")

    old_responses = baseline.get("responses") if isinstance(baseline.get("responses"), dict) else {}
    new_responses = current.get("responses") if isinstance(current.get("responses"), dict) else {}
    for status in sorted(set(old_responses) - set(new_responses)):
        _change(changes, seen, "breaking", f"{method} {path} response {status}", "response status was removed")
    for status in sorted(set(new_responses) - set(old_responses)):
        _change(changes, seen, "compatible", f"{method} {path} response {status}", "response status was added")
    for status in sorted(set(old_responses) & set(new_responses)):
        old_response, new_response = old_responses[status], new_responses[status]
        if not isinstance(old_response, dict) or not isinstance(new_response, dict):
            continue
        old_content = old_response.get("content") if isinstance(old_response.get("content"), dict) else {}
        new_content = new_response.get("content") if isinstance(new_response.get("content"), dict) else {}
        for media_type in sorted(set(old_content) - set(new_content)):
            _change(changes, seen, "breaking", f"{method} {path} response {status} {media_type}", "response media type was removed")
        for media_type in sorted(set(old_content) & set(new_content)):
            _schema_changes(
                _content_schema(old_response, media_type),
                _content_schema(new_response, media_type),
                baseline_root=baseline_root,
                current_root=current_root,
                location=f"{method} {path} response {status} {media_type}",
                changes=changes,
                seen=seen,
            )


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


def compare_contracts(
    baseline_openapi: PathInput,
    current_openapi: PathInput,
    *,
    baseline_inventory: Optional[Path] = None,
    current_inventory: Optional[Path] = None,
) -> JSONDict:
    baseline_paths = _paths(baseline_openapi)
    current_paths = _paths(current_openapi)
    if len(baseline_paths) > 1 or len(current_paths) > 1:
        if len(baseline_paths) != len(current_paths):
            raise ValueError("baseline/current OpenAPI bundle 文件数量不一致")
        reports = [compare_contracts(old, new) for old, new in zip(baseline_paths, current_paths)]
        result = _combine_reports(reports, baseline_paths, current_paths)
        if baseline_inventory is not None and current_inventory is not None:
            _add_inventory_changes(result, baseline_inventory, current_inventory)
        return result

    baseline_spec = _load_openapi_bundle(baseline_openapi)
    current_spec = _load_openapi_bundle(current_openapi)
    baseline_operations = _operations(baseline_spec)
    current_operations = _operations(current_spec)
    changes: List[Change] = []
    seen: Set[Tuple[str, str, str]] = set()

    for key in sorted(set(baseline_operations) - set(current_operations)):
        method, path = key
        operation = _operation_id(baseline_operations[key], method, path)
        _change(changes, seen, "breaking", f"{method} {path}", f"operation removed: {operation}")
    for key in sorted(set(current_operations) - set(baseline_operations)):
        method, path = key
        operation = _operation_id(current_operations[key], method, path)
        _change(changes, seen, "compatible", f"{method} {path}", f"operation added: {operation}")
    for key in sorted(set(baseline_operations) & set(current_operations)):
        baseline_path_item = baseline_spec["paths"].get(key[1])
        current_path_item = current_spec["paths"].get(key[1])
        _compare_operation(
            *key,
            baseline_operations[key],
            current_operations[key],
            changes=changes,
            seen=seen,
            baseline_path_item=baseline_path_item,
            current_path_item=current_path_item,
            baseline_root=baseline_spec,
            current_root=current_spec,
        )

    if baseline_inventory is not None and current_inventory is not None:
        old_inventory = _inventory(_load(baseline_inventory, kind="inventory"))
        new_inventory = _inventory(_load(current_inventory, kind="inventory"))
        for item in sorted(old_inventory - new_inventory):
            _change(changes, seen, "breaking", f"inventory {item[0]} {item[1]}", f"operation removed: {item[2]}")
        for item in sorted(new_inventory - old_inventory):
            _change(changes, seen, "compatible", f"inventory {item[0]} {item[1]}", f"operation added: {item[2]}")

    changes.sort(key=lambda item: (item["severity"], item["location"], item["detail"]))
    breaking = [item for item in changes if item["severity"] == "breaking"]
    return {
        "baseline": [str(path) for path in _paths(baseline_openapi)],
        "current": [str(path) for path in _paths(current_openapi)],
        "breaking": breaking,
        "compatible": [item for item in changes if item["severity"] == "compatible"],
        "summary": {
            "breaking": len(breaking),
            "compatible": len(changes) - len(breaking),
            "baseline_operations": len(baseline_operations),
            "current_operations": len(current_operations),
        },
    }


def _paths(value: PathInput) -> List[Path]:
    return [value] if isinstance(value, Path) else list(value)


def _combine_reports(
    reports: Sequence[JSONDict],
    baseline_paths: Sequence[Path],
    current_paths: Sequence[Path],
) -> JSONDict:
    breaking = [item for report in reports for item in report["breaking"]]
    compatible = [item for report in reports for item in report["compatible"]]
    return {
        "baseline": [str(path) for path in baseline_paths],
        "current": [str(path) for path in current_paths],
        "breaking": breaking,
        "compatible": compatible,
        "summary": {
            "breaking": len(breaking),
            "compatible": len(compatible),
            "baseline_operations": sum(report["summary"]["baseline_operations"] for report in reports),
            "current_operations": sum(report["summary"]["current_operations"] for report in reports),
        },
    }


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
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if bool(args.baseline_inventory) != bool(args.current_inventory):
        print("baseline/current inventory 必须同时提供", file=sys.stderr)
        return 2
    try:
        result = compare_contracts(
            args.baseline_openapi,
            args.current_openapi,
            baseline_inventory=args.baseline_inventory,
            current_inventory=args.current_inventory,
        )
    except ValueError as exc:
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
