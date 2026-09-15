from __future__ import annotations

from typing import Any, Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_cases, dataset_defaults
from platforms.source_admin.client import SourceAdminClient
from tests.source_admin.helpers import data


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
CONTRACT_DEFAULTS = dataset_defaults("source_admin", "contract")
CONTRACT_LIST_CASES = dataset_cases("source_admin", "contract", "list")
MISSING_ASSOCIATE_CASES = dataset_cases("source_admin", "contract", "missing_associate")
MISSING_ARCHIVE_CASES = dataset_cases("source_admin", "contract", "missing_archive")


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case["id"])


def _contract_list(body: Mapping[str, Any]) -> dict[str, Any]:
    payload = data(body)
    assert isinstance(payload, dict), f"合同列表 data 应为对象: {body}"
    assert isinstance(payload.get("list"), list)
    assert isinstance(payload.get("total"), int)
    return payload


@pytest.mark.core
@pytest.mark.parametrize("case", CONTRACT_LIST_CASES, ids=_case_id)
def test_source_06_01_contract_list_filters(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    """合同列表支持默认分页和归档状态筛选，并返回稳定分页结构。"""
    body = assert_envelope(
        platform_client.list_contracts(**case_payload(case)),
        required_keys=("data",),
    )
    _contract_list(body)


def test_source_06_02_missing_contract_read_and_update_are_rejected(
    platform_client: SourceAdminClient,
) -> None:
    """不存在合同的详情、供应商关联和归档请求必须被拒绝。"""
    contract_id = CONTRACT_DEFAULTS["missing_contract_id"]
    assert_rejected(platform_client.get_contract(contract_id))
    assert_rejected(platform_client.associate_contract(contract_id, counterparty_id1=999999999))
    assert_rejected(platform_client.archive_contract(contract_id, archive_no="api-test-missing-contract"))


@pytest.mark.parametrize("case", MISSING_ASSOCIATE_CASES, ids=_case_id)
def test_source_06_03_missing_contract_associate_cases_are_rejected(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    payload = case_payload(case)
    payload["counterparty_id1"] = CONTRACT_DEFAULTS["missing_supplier_id"]
    assert_rejected(
        platform_client.associate_contract(
            CONTRACT_DEFAULTS["missing_contract_id"], **payload
        )
    )


@pytest.mark.parametrize("case", MISSING_ARCHIVE_CASES, ids=_case_id)
def test_source_06_04_missing_contract_archive_cases_are_rejected(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    assert_rejected(
        platform_client.archive_contract(
            CONTRACT_DEFAULTS["missing_contract_id"], **case_payload(case)
        )
    )


@pytest.mark.skip(reason="会触发全量飞书同步，需维护者确认外部依赖和限流窗口")
def test_source_06_05_contract_sync_is_deferred(platform_client: SourceAdminClient) -> None:
    """手动同步接口保留用例入口，但不在共享环境触发副作用。"""
    assert_envelope(platform_client.trigger_contract_sync())
