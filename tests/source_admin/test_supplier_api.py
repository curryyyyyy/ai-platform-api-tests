from __future__ import annotations

from typing import Any, Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_cases, dataset_defaults
from platforms.source_admin.client import SourceAdminClient
from tests.source_admin.helpers import data


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
SUPPLIER_DEFAULTS = dataset_defaults("source_admin", "supplier")
SUPPLIER_LIST_CASES = dataset_cases("source_admin", "supplier", "list")
EXTERNAL_LIST_CASES = dataset_cases("source_admin", "supplier", "external_list")


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case["id"])


def _supplier_list(body: Mapping[str, Any]) -> dict[str, Any]:
    payload = data(body)
    assert isinstance(payload, dict), f"供应商列表 data 应为对象: {body}"
    assert isinstance(payload.get("list"), list)
    assert isinstance(payload.get("total"), int)
    return payload


@pytest.mark.core
@pytest.mark.parametrize("case", SUPPLIER_LIST_CASES, ids=_case_id)
def test_source_07_01_supplier_list_filters(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    body = assert_envelope(
        platform_client.list_suppliers(**case_payload(case)),
        required_keys=("data",),
    )
    _supplier_list(body)


@pytest.mark.core
@pytest.mark.parametrize("case", EXTERNAL_LIST_CASES, ids=_case_id)
def test_source_07_02_public_supplier_list_requires_no_token(
    case: Mapping[str, Any], anonymous_platform_client: SourceAdminClient
) -> None:
    body = assert_envelope(
        anonymous_platform_client.list_external_suppliers(**case_payload(case)),
        required_keys=("data",),
    )
    _supplier_list(body)


def test_source_07_03_missing_supplier_read_and_update_are_rejected(
    platform_client: SourceAdminClient,
) -> None:
    supplier_id = SUPPLIER_DEFAULTS["missing_supplier_id"]
    assert_rejected(platform_client.get_supplier(supplier_id))
    assert_rejected(platform_client.update_supplier(supplier_id, name="missing-supplier"))


def test_source_07_04_invalid_supplier_create_is_rejected(
    platform_client: SourceAdminClient,
) -> None:
    """供应商当前没有删除 API，先覆盖不会落库的创建参数校验链路。"""
    assert_rejected(platform_client.create_supplier(name="", alias="", type="机构供应商"))
