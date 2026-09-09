#!/usr/bin/env python3
"""Validate the runtime result of a merge-gate test suite."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def check_report(path: Path, *, no_skips: bool = False, expected_tests: int | None = None) -> int:
    if not path.is_file():
        print(f"门禁报告不存在: {path}", file=sys.stderr)
        return 2
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        print(f"门禁报告不是合法 JUnit XML: {path}: {exc}", file=sys.stderr)
        return 2

    testcases = list(root.iter("testcase"))
    failures = sum(1 for case in testcases if case.find("failure") is not None)
    errors = sum(1 for case in testcases if case.find("error") is not None)
    skipped = sum(1 for case in testcases if case.find("skipped") is not None)

    print(f"门禁结果: tests={len(testcases)} failures={failures} errors={errors} skipped={skipped}")
    problems: list[str] = []
    if not testcases:
        problems.append("没有收集到任何测试用例")
    if failures or errors:
        problems.append("存在失败或错误测试")
    if no_skips and skipped:
        problems.append("core 门禁不允许 skipped 测试")
    if expected_tests is not None and len(testcases) != expected_tests:
        problems.append(f"测试数量为 {len(testcases)}，期望 {expected_tests}")

    if problems:
        for problem in problems:
            print(f"门禁失败: {problem}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 JUnit 测试结果是否满足合并门禁")
    parser.add_argument("junit", type=Path)
    parser.add_argument("--no-skips", action="store_true", help="禁止任何测试被跳过")
    parser.add_argument("--expected-tests", type=int, default=None)
    args = parser.parse_args()
    return check_report(args.junit, no_skips=args.no_skips, expected_tests=args.expected_tests)


if __name__ == "__main__":
    raise SystemExit(main())
