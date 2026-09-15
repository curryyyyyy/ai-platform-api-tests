"""Validate that the current contract has a case mapping for every operation."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import yaml

try:
    from scripts.contract_diff import _load_openapi_bundle, _operations
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from contract_diff import _load_openapi_bundle, _operations


OperationKey = Tuple[str, str]
Operation = Tuple[str, str, str]


def _load_inventory(path: Path) -> List[Dict[str, str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"接口清单读取失败: {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("operations"), list):
        raise ValueError(f"接口清单缺少 operations 数组: {path}")
    records: List[Dict[str, str]] = []
    for index, item in enumerate(value["operations"]):
        if not isinstance(item, dict):
            raise ValueError(f"接口清单 operations[{index}] 必须是对象: {path}")
        method, route = item.get("method"), item.get("path")
        identifier = item.get("id") or item.get("operationId")
        if not all(isinstance(part, str) and part.strip() for part in (method, route, identifier)):
            raise ValueError(f"接口清单 operations[{index}] 缺少有效 id/method/path: {path}")
        records.append({"id": identifier, "method": method.upper(), "path": route})
    return records


def _load_coverage(path: Path) -> List[Dict[str, Any]]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"接口覆盖清单读取失败: {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
        raise ValueError(f"接口覆盖清单缺少 entries 数组: {path}")
    entries = value["entries"]
    if not all(isinstance(item, dict) for item in entries):
        raise ValueError(f"接口覆盖清单 entries 必须只包含对象: {path}")
    return entries


def _operation_records(openapi_paths: Iterable[Path]) -> List[Operation]:
    combined: Dict[OperationKey, str] = {}
    for path in openapi_paths:
        operations = _operations(_load_openapi_bundle(path))
        for (method, route), operation in operations.items():
            operation_id = str(operation.get("operationId") or f"{method} {route}")
            previous = combined.get((method, route))
            if previous is not None and previous != operation_id:
                raise ValueError(f"OpenAPI bundle 存在重复且 operationId 不一致的接口: {method} {route}")
            combined[(method, route)] = operation_id
    return [(method, route, operation_id) for (method, route), operation_id in sorted(combined.items())]


def _test_reference_exists(repo_root: Path, reference: str) -> bool:
    """Check both the referenced Python file and its function/class target."""
    parts = reference.split("::")
    if len(parts) < 2 or not parts[0].strip() or not parts[-1].strip():
        return False
    path = repo_root / parts[0]
    if not path.is_file() or path.suffix != ".py":
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return False

    target = parts[1:]
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    # Pytest references may include a class before the method.  AST lookup of
    # the final function name is sufficient to reject stale mappings while
    # remaining compatible with parametrized tests.
    return target[-1] in functions


def validate_coverage(
    openapi_paths: Iterable[Path],
    inventory: Optional[Path],
    coverage: Optional[Path],
    *,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return a machine-readable coverage report; ``ok`` is strict by design.

    Inventory IDs are platform-owned business identifiers.  The comparison to
    OpenAPI uses method + path so documents without ``operationId`` are handled
    correctly as well.
    """
    records = _operation_records(openapi_paths)
    contract_keys: Set[OperationKey] = {(method, path) for method, path, _ in records}
    report: Dict[str, Any] = {
        "ok": True,
        "contract_operations": len(records),
        "inventory_operations": 0,
        "covered_operations": 0,
        "missing_inventory": [],
        "extra_inventory": [],
        "missing_coverage": [],
        "extra_coverage": [],
        "invalid_tests": [],
        "duplicate_inventory": [],
        "duplicate_coverage": [],
    }
    if inventory is None:
        report["ok"] = False
        report["missing_inventory"] = [f"{method} {path}" for method, path, _ in records]
        return report

    inventory_records = _load_inventory(inventory)
    inventory_by_key: Dict[OperationKey, str] = {}
    inventory_ids_seen: Dict[str, OperationKey] = {}
    for item in inventory_records:
        key = (item["method"], item["path"])
        previous_id = inventory_by_key.get(key)
        if previous_id is not None:
            duplicate = f"{item['method']} {item['path']} ({previous_id}, {item['id']})"
            if duplicate not in report["duplicate_inventory"]:
                report["duplicate_inventory"].append(duplicate)
        previous_key = inventory_ids_seen.get(item["id"])
        if previous_key is not None:
            duplicate = (
                f"{item['id']} ({previous_key[0]} {previous_key[1]}, "
                f"{item['method']} {item['path']})"
            )
            if duplicate not in report["duplicate_inventory"]:
                report["duplicate_inventory"].append(duplicate)
        inventory_by_key[key] = item["id"]
        inventory_ids_seen[item["id"]] = key
    inventory_keys = set(inventory_by_key)
    report["inventory_operations"] = len(inventory_records)
    report["missing_inventory"] = [
        f"{method} {path}" for method, path in sorted(contract_keys - inventory_keys)
    ]
    report["extra_inventory"] = [
        f"{method} {path}" for method, path in sorted(inventory_keys - contract_keys)
    ]

    inventory_ids = set(inventory_by_key.values())
    covered_ids: Set[str] = set()
    if coverage is not None:
        coverage_entries = _load_coverage(coverage)
        seen_case_ids: Set[str] = set()
        for entry in coverage_entries:
            operations = entry.get("operations")
            if isinstance(operations, list):
                for operation in operations:
                    if isinstance(operation, str):
                        covered_ids.add(operation)
            tests = entry.get("tests")
            if tests is None:
                tests = [entry.get("test")] if entry.get("test") else []
            if not isinstance(tests, list) or not tests:
                report["invalid_tests"].append(str(entry.get("id") or entry.get("operation") or "<entry>"))
            elif repo_root is not None:
                for test_ref in tests:
                    if not isinstance(test_ref, str) or "::" not in test_ref:
                        report["invalid_tests"].append(str(test_ref))
                        continue
                    if not _test_reference_exists(repo_root, test_ref):
                        report["invalid_tests"].append(str(test_ref))
            entry_id = entry.get("id") or entry.get("operation")
            if isinstance(entry_id, str):
                # Duplicate case IDs make report ownership ambiguous even if
                # the union of operation IDs happens to be complete.
                if entry_id in seen_case_ids:
                    report["duplicate_coverage"].append(entry_id)
                seen_case_ids.add(entry_id)
    report["covered_operations"] = len(inventory_ids & covered_ids)
    report["missing_coverage"] = sorted(inventory_ids - covered_ids)
    report["extra_coverage"] = sorted(covered_ids - inventory_ids)
    report["ok"] = not any(
        report[key]
        for key in ("missing_inventory", "extra_inventory", "missing_coverage", "extra_coverage", "invalid_tests")
        + ("duplicate_inventory", "duplicate_coverage")
    )
    return report


def format_coverage_issues(report: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for key, label in (
        ("missing_inventory", "OpenAPI 未登记到 inventory"),
        ("extra_inventory", "inventory 中不存在于 OpenAPI"),
        ("missing_coverage", "接口没有 testcase 覆盖映射"),
        ("extra_coverage", "覆盖映射引用了不存在的接口"),
        ("invalid_tests", "覆盖项缺少 tests"),
        ("duplicate_inventory", "inventory 存在重复接口或 ID"),
        ("duplicate_coverage", "覆盖表存在重复 case ID"),
    ):
        values = report.get(key) or []
        if values:
            issues.append(f"{label}: {', '.join(str(value) for value in values)}")
    return issues
