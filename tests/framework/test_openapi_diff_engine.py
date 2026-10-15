from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.contract_diff import compare_with_engine
from scripts.openapi_diff_engine import OasDiffUnavailable, _json_payload, compare


pytestmark = pytest.mark.contract


def _write_openapi(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "demo", "version": "1"},
                "paths": {"/items": {"get": {"responses": {"200": {"description": "ok"}}}}},
            }
        ),
        encoding="utf-8",
    )


def test_json_payload_accepts_no_difference_output() -> None:
    assert _json_payload("") == []
    assert _json_payload("No changes found") == []


def test_compare_normalises_mature_engine_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_openapi(baseline)
    _write_openapi(current)
    payload = {
        "breakingDifferences": [
            {
                "code": "response.body.schema.type.changed",
                "action": "changed",
                "source": "response.body",
                "sourceSpecEntityDetails": [{"location": "paths./items.get.responses.200"}],
            }
        ],
        "nonBreakingDifferences": [{"code": "operation.added", "action": "added"}],
        "unclassifiedDifferences": [{"code": "unknown"}],
    }
    monkeypatch.setattr("scripts.openapi_diff_engine.shutil.which", lambda _name: "/tmp/openapi-diff")
    monkeypatch.setattr(
        "scripts.openapi_diff_engine.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, f"oasdiff\n{json.dumps(payload)}", ""),
    )

    result = compare([baseline], [current])

    assert result["engine"] == "oasdiff"
    assert result["summary"]["breaking"] == 2
    assert result["summary"]["compatible"] == 1
    assert {item["location"] for item in result["breaking"]} == {
        "paths./items.get.responses.200",
        "unknown",
    }


def test_compare_rejects_unexpected_cli_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_openapi(baseline)
    _write_openapi(current)
    monkeypatch.setattr("scripts.openapi_diff_engine.shutil.which", lambda _name: "/tmp/openapi-diff")
    monkeypatch.setattr(
        "scripts.openapi_diff_engine.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 2, "", "invalid OpenAPI"),
    )

    with pytest.raises(ValueError, match="退出码 2"):
        compare([baseline], [current])


def test_auto_engine_does_not_fall_back_to_duplicate_schema_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_openapi(baseline)
    _write_openapi(current)

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise OasDiffUnavailable("missing")

    monkeypatch.setattr("scripts.openapi_diff_engine.compare", unavailable)

    with pytest.raises(RuntimeError, match="oasdiff 未安装"):
        compare_with_engine(baseline, current, engine="auto")


def test_explicit_mature_engine_does_not_fall_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_openapi(baseline)
    _write_openapi(current)

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise OasDiffUnavailable("missing")

    monkeypatch.setattr("scripts.openapi_diff_engine.compare", unavailable)

    with pytest.raises(RuntimeError, match="oasdiff 未安装"):
        compare_with_engine(baseline, current, engine="oasdiff")
