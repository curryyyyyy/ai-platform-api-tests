from __future__ import annotations

import re

import pytest

from framework.data.dataset import case_payload, dataset_cases, dataset_defaults


pytestmark = [pytest.mark.contract, pytest.mark.hawk_admin]


def test_hawk_dataset_loads_defaults_and_cases() -> None:
    defaults = dataset_defaults("hawk_admin", "project")
    cases = dataset_cases("hawk_admin", "project", "invalid_notification_levels")

    assert defaults["materialType"] == "图片"
    assert [case["id"] for case in cases] == ["negative", "unsupported", "too_large"]
    assert case_payload(cases[0]) == {"level": -1}


def test_hawk_dataset_keeps_nested_values_isolated() -> None:
    first = dataset_defaults("hawk_admin", "project")
    first["materialType"] = "changed"
    second = dataset_defaults("hawk_admin", "project")

    assert second["materialType"] == "图片"


def test_hawk_batch_cid_fixtures_use_numeric_collection_ids() -> None:
    """CID 输入必须符合服务端 `CID://<positive integer>` 协议。"""
    cid_pattern = re.compile(r"^CID://\d+$")
    dataset_groups = ("create", "invalid_create")

    for group in dataset_groups:
        for case in dataset_cases("hawk_admin", "batch", group):
            for field in ("inputFilePath", "updatedInputFilePath"):
                value = case.get(field)
                if value is not None:
                    assert cid_pattern.fullmatch(value) and int(value.removeprefix("CID://")) > 0, (
                        f"batch.yaml {group}/{case['id']} 的 {field} 必须为 "
                        "CID://<positive integer>"
                    )
