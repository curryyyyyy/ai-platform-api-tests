from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.notify_feishu import ReportSummary, build_message, collect_summaries, main, send


def test_collect_summaries_counts_junit_cases(tmp_path: Path) -> None:
    (tmp_path / "core.xml").write_text(
        "<testsuites><testsuite><testcase/><testcase><failure/></testcase>"
        "<testcase><skipped/></testcase></testsuite></testsuites>",
        encoding="utf-8",
    )

    assert collect_summaries(tmp_path) == [
        ReportSummary(name="core", tests=3, failures=1, errors=0, skipped=1)
    ]


def test_build_message_contains_totals_and_pipeline_url() -> None:
    message = build_message(
        [ReportSummary(name="contract", tests=2, failures=0, errors=1, skipped=0)],
        pipeline_url="https://gitlab.example/pipeline/1",
    )

    assert "失败" in message
    assert "测试总数：2" in message
    assert "流水线地址：https://gitlab.example/pipeline/1" in message


def test_build_message_marks_missing_reports_as_abnormal() -> None:
    message = build_message(
        [ReportSummary(name="contract", tests=2, failures=0, errors=0, skipped=0)],
        expected_reports=["contract.xml", "core_live.xml"],
    )

    assert "扫描结果：异常" in message
    assert "缺少报告：core_live" in message


def test_build_message_does_not_mark_skipped_suite_as_passed() -> None:
    summary = ReportSummary(name="core", tests=2, failures=0, errors=0, skipped=2)

    assert summary.status == "skipped"
    assert "全部用例被跳过" in build_message([summary])


def test_send_posts_feishu_text_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"code": 0}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("scripts.notify_feishu.urllib.request.urlopen", fake_urlopen)
    send("https://feishu.example/hook", "daily report")

    assert captured == {
        "url": "https://feishu.example/hook",
        "payload": {"msg_type": "text", "content": {"text": "daily report"}},
        "timeout": 15.0,
    }


def test_send_rejects_non_object_json_response(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"[]"

    monkeypatch.setattr("scripts.notify_feishu.urllib.request.urlopen", lambda *args, **kwargs: Response())

    with pytest.raises(RuntimeError, match="非对象 JSON"):
        send("https://feishu.example/hook", "daily report")


def test_main_sends_alert_and_fails_when_expected_report_is_missing(tmp_path: Path, monkeypatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr("scripts.notify_feishu.send", lambda webhook, message: sent.append(message))

    result = main(
        [
            "--reports-dir",
            str(tmp_path),
            "--webhook",
            "https://feishu.example/hook",
            "--expected-report",
            "contract.xml",
        ]
    )

    assert result == 1
    assert len(sent) == 1
    assert "缺少报告：contract" in sent[0]
