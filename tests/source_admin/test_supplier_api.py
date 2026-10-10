from __future__ import annotations

import json
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
ENHANCED_FILTER_CASES = dataset_cases("source_admin", "supplier", "enhanced_filters")


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case["id"])


def _supplier_list(body: Mapping[str, Any]) -> dict[str, Any]:
    payload = data(body)
    assert isinstance(payload, dict), f"供应商列表 data 应为对象: {body}"
    assert isinstance(payload.get("list"), list)
    assert isinstance(payload.get("total"), int)
    return payload


def _listed_suppliers(client: SourceAdminClient) -> list[dict[str, Any]]:
    listing = _supplier_list(
        assert_envelope(client.list_suppliers(page=1, page_size=1000), required_keys=("data",))
    )
    return [item for item in listing["list"] if isinstance(item, dict)]


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
@pytest.mark.requirement(id="REQ-SUPPLIER-MULTI-OWNER", name="supplier_multi_owner")
@pytest.mark.case_id(
    "REQ-SUPPLIER-MULTI-OWNER-API-01",
    title="供应商负责人和多归属方筛选命中对应供应商",
)
@pytest.mark.parametrize("case", ENHANCED_FILTER_CASES, ids=_case_id)
def test_source_07_05_supplier_manager_and_multi_category_filters(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    """负责人、CSV 和 JSON 数组归属方筛选都应命中已存在的对应供应商。"""
    suppliers = _listed_suppliers(platform_client)
    filter_name = case["filter"]
    if filter_name == "manager":
        candidates = [
            supplier
            for supplier in suppliers
            if isinstance(supplier.get("manager"), str) and supplier["manager"].strip()
        ]
        if not candidates:
            pytest.skip("当前环境没有带负责人的供应商，无法验证 manager 筛选")
        candidate = candidates[0]
        query = candidate["manager"].strip()
        response = platform_client.list_suppliers(manager=query, page=1, page_size=1000)
    else:
        candidates = []
        for supplier in suppliers:
            category = supplier.get("category")
            if not isinstance(category, str):
                continue
            categories = [item.strip() for item in category.split(",") if item.strip()]
            if len(categories) > 1:
                candidates.append((supplier, categories[:2]))
        if not candidates:
            pytest.skip("当前环境没有多归属方供应商，无法验证 category 多选筛选")
        candidate, categories = candidates[0]
        category_query = (
            ",".join(categories)
            if filter_name == "category_csv"
            else json.dumps(categories, ensure_ascii=False)
        )
        response = platform_client.list_suppliers(
            category=category_query,
            page=1,
            page_size=1000,
        )

    result = _supplier_list(assert_envelope(response, required_keys=("data",)))
    assert any(item.get("id") == candidate.get("id") for item in result["list"]), (
        f"供应商筛选未命中候选 id={candidate.get('id')}, filter={filter_name}"
    )


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
