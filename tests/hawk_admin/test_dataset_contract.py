from __future__ import annotations

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
