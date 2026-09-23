#!/usr/bin/env python3
"""Send a compact JUnit summary to a Feishu bot webhook.

The webhook is deliberately supplied at runtime.  This keeps the bot secret
out of the repository and out of generated test artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ReportSummary:
    name: str
    tests: int
    failures: int
    errors: int
    skipped: int

    @property
    def status(self) -> str:
        return "failed" if self.failures or self.errors else "passed"


def summarize_report(path: Path) -> ReportSummary:
    """Read a JUnit file, supporting both ``testsuite`` and ``testsuites`` roots."""

    root = ET.parse(path).getroot()
    testcases = list(root.iter("testcase"))
    return ReportSummary(
        name=path.stem,
        tests=len(testcases),
        failures=sum(case.find("failure") is not None for case in testcases),
        errors=sum(case.find("error") is not None for case in testcases),
        skipped=sum(case.find("skipped") is not None for case in testcases),
    )


def collect_summaries(reports_dir: Path) -> list[ReportSummary]:
    summaries: list[ReportSummary] = []
    for path in sorted(reports_dir.glob("*.xml")):
        try:
            summaries.append(summarize_report(path))
        except (ET.ParseError, OSError) as exc:
            print(f"忽略无效 JUnit 报告 {path}: {exc}", file=sys.stderr)
    return summaries


def build_message(summaries: Iterable[ReportSummary], *, pipeline_url: str = "") -> str:
    items = list(summaries)
    tests = sum(item.tests for item in items)
    failures = sum(item.failures for item in items)
    errors = sum(item.errors for item in items)
    skipped = sum(item.skipped for item in items)
    status = "失败，存在失败用例" if failures or errors else "通过"
    lines = [
        f"AI 基建平台接口自动化扫描结果：{status}",
        f"测试总数：{tests}，失败：{failures}，错误：{errors}，跳过：{skipped}",
    ]
    for item in items:
        lines.append(
            f"{item.name}: {item.status} "
            f"(tests={item.tests}, failures={item.failures}, "
            f"errors={item.errors}, skipped={item.skipped})"
        )
    if not items:
        lines.append("未找到可解析的 JUnit 报告，请检查上游 job artifacts。")
    if pipeline_url:
        lines.append(f"流水线地址：{pipeline_url}")
    return "\n".join(lines)


def send(webhook: str, message: str, *, timeout: float = 15.0) -> None:
    payload = {
        "msg_type": "text",
        "content": {"text": message},
    }
    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"飞书通知请求失败: {exc}") from exc
    if body.get("code", 0) != 0:
        raise RuntimeError(f"飞书机器人返回失败: code={body.get('code')} msg={body.get('msg')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="发送 GitLab JUnit 汇总到飞书机器人")
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--webhook", default=os.getenv("FEISHU_WEBHOOK_URL", ""))
    parser.add_argument("--pipeline-url", default=os.getenv("CI_PIPELINE_URL", ""))
    args = parser.parse_args()
    if not args.webhook:
        print("未配置 FEISHU_WEBHOOK_URL，跳过飞书通知。", file=sys.stderr)
        return 0
    message = build_message(collect_summaries(args.reports_dir), pipeline_url=args.pipeline_url)
    send(args.webhook, message)
    print("飞书每日流水线报告已发送。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
