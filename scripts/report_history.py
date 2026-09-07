"""Archive the current test reports and retain only the newest report runs."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_KEEP = 3


def make_run_id(history_dir: Path, now: datetime | None = None) -> str:
    current = now or datetime.now().astimezone()
    prefix = current.strftime("%Y%m%d_%H%M%S")
    candidate = prefix
    suffix = 1
    while (history_dir / candidate).exists():
        suffix += 1
        candidate = f"{prefix}_{suffix:02d}"
    return candidate


def archive_current_reports(
    reports_root: Path,
    run_id: str,
    *,
    include_html: bool = False,
    keep: int = DEFAULT_KEEP,
) -> Path:
    """Copy current report outputs into a run directory and prune old runs."""
    if keep < 1:
        raise ValueError("keep must be at least 1")

    reports_root = reports_root.resolve()
    history_dir = reports_root / "history"
    destination = history_dir / run_id
    if destination.exists():
        raise FileExistsError(f"report run already exists: {destination}")
    destination.mkdir(parents=True, exist_ok=False)

    _copy_directory_if_present(reports_root / "allure", destination / "allure")
    _copy_file_if_present(reports_root / "junit" / "results.xml", destination / "junit" / "results.xml")
    if include_html:
        _copy_directory_if_present(reports_root / "allure-report", destination / "allure-report")

    prune_history(history_dir, keep=keep)
    return destination


def prune_history(history_dir: Path, *, keep: int = DEFAULT_KEEP) -> list[Path]:
    """Remove report-run directories older than the newest ``keep`` directories."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    if not history_dir.exists():
        return []

    runs = [path for path in history_dir.iterdir() if path.is_dir()]
    runs.sort(key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
    removed: list[Path] = []
    for path in runs[keep:]:
        shutil.rmtree(path)
        removed.append(path)
    return removed


def _copy_directory_if_present(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)


def _copy_file_if_present(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="归档本轮测试报告并清理旧报告")
    parser.add_argument("--reports-root", type=Path, required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    parser.add_argument("--include-html", action="store_true")
    args = parser.parse_args()

    history_dir = args.reports_root / "history"
    run_id = args.run_id or make_run_id(history_dir)
    destination = archive_current_reports(
        args.reports_root,
        run_id,
        include_html=args.include_html,
        keep=args.keep,
    )
    print(f"历史报告: {destination}")
    print(f"保留轮次: {args.keep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
