#!/usr/bin/env python3
"""Compare committed platform contract snapshots with a Git baseline.

The runner discovers ``platforms/*/contract.yaml`` manifests. The service
repository is maintained outside this project. Pull its desired
branch locally, copy reviewed documents into ``contracts/``, then compare the
resulting snapshot with Git history.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

try:  # Supports both ``python scripts/contract_pipeline.py`` and module imports.
    from scripts.contract_diff import compare_contracts
    from scripts.contract_manifest import (
        discover_manifests,
        load_manifest,
        relative_paths,
        select_manifests,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by the CLI entry point
    from contract_diff import compare_contracts
    from contract_manifest import (
        discover_manifests,
        load_manifest,
        relative_paths,
        select_manifests,
    )


def _load_manifest(path: Path) -> dict[str, Any]:
    """Backward-compatible wrapper used by callers that imported this helper."""
    return load_manifest(path)


def _relative_paths(values: Any) -> list[Path]:
    return relative_paths(values, field="平台 local.openapi")


def _copy_from_git(root: Path, relative: Path, destination: Path, base_ref: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if base_ref:
        result = subprocess.run(
            ["git", "show", f"{base_ref}:{relative.as_posix()}"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            destination.write_bytes(result.stdout)
            return
    source = root / relative
    if not source.is_file():
        raise ValueError(f"本地契约文件不存在: {source}")
    shutil.copy2(source, destination)


def _copy_local_snapshot(
    root: Path,
    definition: dict[str, Any],
    local_relative: list[Path],
    current_root: Path,
) -> tuple[list[Path], Optional[Path]]:
    current_openapi: list[Path] = []
    for relative in local_relative:
        destination = current_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = root / relative
        if not source.is_file():
            raise ValueError(f"本地契约文件不存在: {source}")
        shutil.copy2(source, destination)
        current_openapi.append(destination)

    local = definition.get("local")
    local_inventory_value = local.get("inventory") if isinstance(local, dict) else None
    current_inventory: Optional[Path] = None
    if isinstance(local_inventory_value, str) and local_inventory_value.strip():
        current_inventory = current_root / local_inventory_value
        current_inventory.parent.mkdir(parents=True, exist_ok=True)
        source = root / local_inventory_value
        if not source.is_file():
            raise ValueError(f"本地接口清单不存在: {source}")
        shutil.copy2(source, current_inventory)
    return current_openapi, current_inventory


def _copy_source_snapshot(
    root: Path,
    definition: dict[str, Any],
    local_relative: list[Path],
    current_root: Path,
    source_root: Path,
) -> tuple[list[Path], Optional[Path]]:
    """Copy reviewed documents from a locally checked-out service tree."""
    source = definition.get("source")
    source_openapi = source.get("openapi") if isinstance(source, dict) else None
    source_relative = _relative_paths(source_openapi)
    if len(source_relative) != len(local_relative):
        raise ValueError("source.openapi 与 local.openapi 数量不一致")
    current_openapi: list[Path] = []
    for relative, source_path in zip(local_relative, source_relative):
        source_file = source_root / source_path
        destination = current_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not source_file.is_file():
            raise ValueError(f"本地服务契约文件不存在: {source_file}")
        shutil.copy2(source_file, destination)
        current_openapi.append(destination)
    # Inventory remains platform-owned until the maintainer reviews and updates it.
    local = definition.get("local")
    inventory_value = local.get("inventory") if isinstance(local, dict) else None
    current_inventory: Optional[Path] = None
    if isinstance(inventory_value, str) and inventory_value.strip():
        current_inventory = current_root / inventory_value
        current_inventory.parent.mkdir(parents=True, exist_ok=True)
        inventory = root / inventory_value
        if not inventory.is_file():
            raise ValueError(f"本地接口清单不存在: {inventory}")
        shutil.copy2(inventory, current_inventory)
    return current_openapi, current_inventory


def run_platform(
    root: Path,
    platform: str,
    definition: dict[str, Any],
    *,
    base_ref: str,
    report_root: Path,
    source_root: Optional[Path] = None,
) -> dict[str, Any]:
    local = definition.get("local")
    if not isinstance(local, dict):
        raise ValueError(f"平台 {platform} 缺少 local 配置")
    local_relative = _relative_paths(local.get("openapi"))
    baseline_root = Path(tempfile.mkdtemp(prefix=f"contract-baseline-{platform}-"))
    current_root = Path(tempfile.mkdtemp(prefix=f"contract-current-{platform}-"))
    try:
        baseline_openapi: list[Path] = []
        for relative in local_relative:
            destination = baseline_root / relative
            _copy_from_git(root, relative, destination, base_ref)
            baseline_openapi.append(destination)
        if source_root is None:
            current_openapi, current_inventory = _copy_local_snapshot(
                root, definition, local_relative, current_root
            )
        else:
            current_openapi, current_inventory = _copy_source_snapshot(
                root, definition, local_relative, current_root, source_root
            )
        baseline_inventory: Optional[Path] = None
        inventory_value = local.get("inventory")
        if isinstance(inventory_value, str) and inventory_value.strip():
            baseline_inventory = baseline_root / inventory_value
            _copy_from_git(root, Path(inventory_value), baseline_inventory, base_ref)
        report = compare_contracts(
            baseline_openapi,
            current_openapi,
            baseline_inventory=baseline_inventory,
            current_inventory=current_inventory,
        )
        report["platform"] = platform
        report_root.mkdir(parents=True, exist_ok=True)
        report_path = report_root / f"{platform}-diff.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["report"] = str(report_path)
        return report
    finally:
        shutil.rmtree(baseline_root, ignore_errors=True)
        shutil.rmtree(current_root, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按平台契约清单执行 OpenAPI 变更检测")
    parser.add_argument("--manifest", type=Path, action="append", help="平台契约清单，可重复传入")
    parser.add_argument("--platform", help="只执行指定平台清单")
    parser.add_argument("--base-ref", default=os.getenv("CONTRACT_BASE_SHA", ""))
    parser.add_argument("--source-root", type=Path, help="已拉取的服务代码工作树，仅从本地读取契约")
    parser.add_argument("--report-root", type=Path, default=Path("reports/contracts"))
    parser.add_argument("--fail-on-breaking", action="store_true")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        manifest_paths = args.manifest
        if manifest_paths:
            manifest_paths = [path if path.is_absolute() else root / path for path in manifest_paths]
        else:
            manifest_paths = discover_manifests(root)
        selected = select_manifests(root, manifest_paths, args.platform or "")
        reports: List[Tuple[str, dict[str, Any]]] = []
        for _, definition in selected:
            platform = str(definition["platform"])
            reports.append(
                (
                    platform,
                    run_platform(
                        root,
                        platform,
                        definition,
                        base_ref=args.base_ref,
                        report_root=(args.report_root if args.report_root.is_absolute() else root / args.report_root),
                        source_root=(args.source_root if not args.source_root or args.source_root.is_absolute() else root / args.source_root),
                    ),
                )
            )
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    breaking = sum(report["summary"]["breaking"] for _, report in reports)
    compatible = sum(report["summary"]["compatible"] for _, report in reports)
    print(f"契约总 diff: platforms={len(reports)} breaking={breaking} compatible={compatible}")
    for platform, report in reports:
        print(
            f"{platform}: breaking={report['summary']['breaking']} "
            f"compatible={report['summary']['compatible']} report={report['report']}"
        )
    if args.fail_on_breaking and breaking and os.getenv("CONTRACT_DIFF_ALLOW_BREAKING") != "1":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
