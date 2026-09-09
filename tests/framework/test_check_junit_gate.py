from __future__ import annotations

from pathlib import Path

from scripts.check_junit_gate import check_report


def _write_report(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_junit_gate_accepts_complete_suite(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path / "results.xml",
        '<testsuites><testsuite tests="2"><testcase name="a"/><testcase name="b"/></testsuite></testsuites>',
    )
    assert check_report(report, no_skips=True, expected_tests=2) == 0


def test_junit_gate_rejects_skipped_case(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path / "results.xml",
        '<testsuites><testsuite tests="1"><testcase name="a"><skipped/></testcase></testsuite></testsuites>',
    )
    assert check_report(report, no_skips=True) == 1


def test_junit_gate_rejects_unexpected_test_count(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path / "results.xml",
        '<testsuites><testsuite tests="1"><testcase name="a"/></testsuite></testsuites>',
    )
    assert check_report(report, expected_tests=2) == 1
