from __future__ import annotations

from pathlib import Path

import pytest

from scripts.report_history import archive_current_reports, prune_history


def test_archive_current_reports_copies_outputs(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    (reports / "allure").mkdir(parents=True)
    (reports / "allure" / "result.json").write_text("{}", encoding="utf-8")
    (reports / "junit").mkdir(parents=True)
    (reports / "junit" / "results.xml").write_text("<testsuite/>", encoding="utf-8")
    (reports / "allure-report").mkdir()
    (reports / "allure-report" / "index.html").write_text("ok", encoding="utf-8")

    destination = archive_current_reports(reports, "20260903_120000", include_html=True)

    assert (destination / "allure" / "result.json").read_text(encoding="utf-8") == "{}"
    assert (destination / "junit" / "results.xml").read_text(encoding="utf-8") == "<testsuite/>"
    assert (destination / "allure-report" / "index.html").exists()


def test_prune_history_keeps_newest_runs(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    for index in range(1, 7):
        (history / f"20260903_12000{index}").mkdir()

    removed = prune_history(history, keep=5)

    assert len(removed) == 1
    assert len([path for path in history.iterdir() if path.is_dir()]) == 5


@pytest.mark.parametrize("keep", [0, -1])
def test_report_retention_rejects_non_positive_keep(tmp_path: Path, keep: int) -> None:
    with pytest.raises(ValueError):
        prune_history(tmp_path, keep=keep)
