from __future__ import annotations

import re

import pytest

from framework.data.dataset import case_payload, dataset_case_map, dataset_cases, dataset_defaults


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


def test_hawk_flow_defaults_match_draft_create_contract() -> None:
    """草稿创建仅允许客户端提供 alias、desc，项目编号由数据工厂动态补充。"""
    defaults = dataset_defaults("hawk_admin", "flow")

    assert set(defaults) == {"alias", "desc"}
    assert all(isinstance(defaults[key], str) and defaults[key] for key in defaults)


def test_hawk_requirement_datasets_define_stable_template_and_favorite_inputs() -> None:
    """需求用例的无副作用参数统一放在平台数据集。"""
    favorite = dataset_cases("hawk_admin", "project", "favorite")
    template = dataset_cases("hawk_admin", "template_workflow", "batch_get")

    assert favorite == ({"id": "default", "onlyFavorite": True},)
    assert template == ({"id": "empty", "ids": []},)
    complete_cases = dataset_case_map("hawk_admin", "template_workflow", "invalid_complete")
    assert complete_cases["missing_workflow"]["workflow_id"] == 0
