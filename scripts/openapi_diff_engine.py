"""Adapters for mature OpenAPI diff engines.

The repository owns platform orchestration and test-asset traceability.  OpenAPI
compatibility semantics are delegated to the maintained ``oasdiff`` CLI.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


class OasDiffUnavailable(RuntimeError):
    """Raised when the configured external OpenAPI diff engine is unavailable."""


def _find_executable(executable: str) -> Optional[str]:
    """Resolve PATH binaries and the repository-local npm installation."""
    command = shutil.which(executable)
    if command and executable != "oasdiff":
        return command
    root = Path(__file__).resolve().parents[1]
    candidates = []
    if executable == "oasdiff":
        system = platform.system().lower()
        machine = platform.machine().lower()
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        candidates.append(
            root / "node_modules" / "@oasdiff-js" / f"oasdiff-{system}-{arch}" / "bin" / "oasdiff"
        )
    candidates.append(root / "node_modules" / ".bin" / executable)
    for local in candidates:
        if local.is_file():
            # The JS wrapper exists even when npm skipped its optional native
            # package; only return it after a real native binary was found.
            if executable == "oasdiff" and local.parent.name == ".bin":
                continue
            return str(local)
    if command and executable == "oasdiff" and "node_modules/.bin" not in command:
        return command
    return None


def _json_payload(output: str) -> Any:
    # Mature CLIs may prefix structured output with a status line.
    if not output.strip() or "No differences" in output or "No changes found" in output:
        return []
    starts = [index for index in (output.find("["), output.find("{")) if index >= 0]
    start = min(starts) if starts else -1
    if start < 0:
        raise ValueError("oasdiff 未输出 JSON 报告")
    try:
        value = json.loads(output[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"oasdiff 输出不是合法 JSON: {exc}") from exc
    return value


def _location(change: Dict[str, Any]) -> str:
    for key in ("destinationSpecEntityDetails", "sourceSpecEntityDetails"):
        details = change.get(key)
        if isinstance(details, list) and details and isinstance(details[0], dict):
            location = details[0].get("location")
            if isinstance(location, str) and location:
                return location
    return str(change.get("entity") or change.get("code") or "openapi")


def _normalise_change(change: Any, *, severity: str) -> Dict[str, str]:
    if not isinstance(change, dict):
        return {"severity": severity, "location": "openapi", "detail": str(change)}
    code = str(change.get("code") or change.get("entity") or "difference")
    action = str(change.get("action") or "change")
    path = change.get("path")
    location = str(path) if isinstance(path, str) and path else _location(change)
    return {
        "severity": severity,
        "location": location,
        "detail": f"{code}: {change.get('text') or action}",
    }


def _load_bundle(paths: Sequence[Path]) -> Dict[str, Any]:
    # Imported lazily to keep bundle loading independent from the CLI entry point.
    try:
        from scripts.contract_diff import _load, _load_openapi_bundle
    except ModuleNotFoundError:  # pragma: no cover - direct script entry point
        from contract_diff import _load, _load_openapi_bundle

    try:
        return _load_openapi_bundle(list(paths))
    except ValueError as exc:
        if "重复且不一致的组件" not in str(exc):
            raise
    return _load_tolerant_bundle([_load(path, kind="openapi") for path in paths])


def _rewrite_refs(value: Any, replacements: Dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                replacements.get(item, item)
                if key == "$ref" and isinstance(item, str)
                else _rewrite_refs(item, replacements)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rewrite_refs(item, replacements) for item in value]
    return value


def _load_tolerant_bundle(documents: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge bundles while isolating conflicting same-name components.

    Service teams sometimes publish one OpenAPI document per domain while
    reusing a component name such as ``BaseResponse`` with different fields.
    The project bundle validator rejects that ambiguity.  For the external engine we
    preserve each document's meaning by renaming only conflicting components
    and rewriting local references before comparison.
    """
    if not documents:
        raise ValueError("OpenAPI 契约至少需要一个文件")
    merged: Dict[str, Any] = {
        "openapi": documents[0].get("openapi", "3.0.3"),
        "paths": {},
    }
    for key in ("info", "servers", "tags", "security"):
        if key in documents[0]:
            merged[key] = deepcopy(documents[0][key])
    components: Dict[str, Dict[str, Any]] = {}
    for index, original in enumerate(documents):
        document = deepcopy(original)
        replacements: Dict[str, str] = {}
        raw_components = document.get("components")
        if isinstance(raw_components, dict):
            for component_type, values in raw_components.items():
                if not isinstance(values, dict):
                    continue
                target = components.setdefault(component_type, {})
                for name, value in list(values.items()):
                    if name in target and target[name] != value:
                        replacement = f"{name}__bundle_{index + 1}"
                        while replacement in target:
                            replacement += "_"
                        replacements[f"#/components/{component_type}/{name}"] = (
                            f"#/components/{component_type}/{replacement}"
                        )
                        values[replacement] = values.pop(name)
                    target.setdefault(name, values.get(name))
        document = _rewrite_refs(document, replacements)
        raw_components = document.get("components")
        if isinstance(raw_components, dict):
            for component_type, values in raw_components.items():
                if isinstance(values, dict):
                    components.setdefault(component_type, {}).update(values)
        paths = document.get("paths")
        if not isinstance(paths, dict):
            raise ValueError("OpenAPI bundle 中的文档缺少 paths 对象")
        merged_paths = merged["paths"]
        for path, path_item in paths.items():
            if path in merged_paths and merged_paths[path] != path_item:
                raise ValueError(f"OpenAPI bundle 存在重复且不一致的路径: {path}")
            merged_paths[path] = path_item
    if components:
        merged["components"] = components
    return merged


def _operations_map(spec: Dict[str, Any]) -> Dict[Any, Any]:
    try:
        from scripts.contract_diff import _operations
    except ModuleNotFoundError:  # pragma: no cover - direct script entry point
        from contract_diff import _operations

    return _operations(spec)


def _operations_count(spec: Dict[str, Any]) -> int:
    return len(_operations_map(spec))


def compare(
    baseline: Sequence[Path],
    current: Sequence[Path],
    *,
    executable: str = "oasdiff",
) -> Dict[str, Any]:
    """Run oasdiff against one or more platform contract documents."""
    command = _find_executable(executable)
    if command is None:
        raise OasDiffUnavailable(
            f"未找到 {executable}；请先执行 npm ci 和对应平台的 oasdiff 原生包"
        )

    baseline_spec = _load_bundle(baseline)
    current_spec = _load_bundle(current)
    with tempfile.TemporaryDirectory(prefix="oasdiff-") as temporary:
        root = Path(temporary)
        baseline_path = root / "baseline.json"
        current_path = root / "current.json"
        baseline_path.write_text(json.dumps(baseline_spec, ensure_ascii=False), encoding="utf-8")
        current_path.write_text(json.dumps(current_spec, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [command, "breaking", str(baseline_path), str(current_path), "--format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    if result.returncode not in (0, 1):
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"oasdiff 执行失败（退出码 {result.returncode}）: {detail}")
    payload = _json_payload(result.stdout or result.stderr)
    if isinstance(payload, list):
        breaking = [_normalise_change(item, severity="breaking") for item in payload]
        unclassified: list[Any] = []
        compatible = [
            {
                "severity": "compatible",
                "location": f"{method} {path}",
                "detail": "operation added",
            }
            for method, path in sorted(
                set(_operations_map(current_spec)) - set(_operations_map(baseline_spec))
            )
        ]
    elif isinstance(payload, dict):
        # Keep compatibility with mocked/older adapters that return a grouped object.
        breaking = [_normalise_change(item, severity="breaking") for item in payload.get("breakingDifferences", [])]
        compatible = [_normalise_change(item, severity="compatible") for item in payload.get("nonBreakingDifferences", [])]
        unclassified = payload.get("unclassifiedDifferences", [])
        if not isinstance(unclassified, list):
            unclassified = []
        breaking.extend(_normalise_change(item, severity="breaking") for item in unclassified)
    else:
        raise ValueError("oasdiff 输出顶层必须是数组或对象")
    breaking.sort(key=lambda item: (item["location"], item["detail"]))
    compatible.sort(key=lambda item: (item["location"], item["detail"]))
    return {
        "baseline": [str(path) for path in baseline],
        "current": [str(path) for path in current],
        "engine": "oasdiff",
        "breaking": breaking,
        "compatible": compatible,
        "unclassified": list(unclassified) if isinstance(unclassified, list) else [],
        "summary": {
            "breaking": len(breaking),
            "compatible": len(compatible),
            "baseline_operations": _operations_count(baseline_spec),
            "current_operations": _operations_count(current_spec),
        },
    }
