from __future__ import annotations

from typing import Any, Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases, dataset_defaults
from platforms.source_admin.client import SourceAdminClient
from platforms.source_admin.factories import SourceAdminDataFactory


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
NODE_DEFAULTS = dataset_defaults("source_admin", "node")
INVALID_CREATE_CASES = dataset_cases("source_admin", "node", "invalid_create")
INVALID_BATCH_CASES = dataset_cases("source_admin", "node", "invalid_batch")
PROJECT_CASES = dataset_case_map("source_admin", "node", "project")


def _data(body: Mapping[str, Any]) -> Any:
    value = body.get("data")
    if isinstance(value, dict) and set(value) == {"data"}:
        return value["data"]
    return value


def _case_id(case: Mapping[str, Any]) -> str:
    return str(case["id"])


@pytest.mark.core
def test_source_03_01_folder_crud_move_and_search(
    platform_client: SourceAdminClient,
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """文件夹节点支持创建、重命名、移动、搜索和删除，且每条数据由本用例清理。"""
    root_id = NODE_DEFAULTS["root_id"]
    # 先创建目标目录，使 DataScope 清理时先删 source，再删 target。
    target_id, _ = platform_data_factory.create_folder(parent_id=root_id)
    source_id, payload = platform_data_factory.create_folder(parent_id=root_id)
    listed = _data(assert_envelope(platform_client.list_nodes(root_id, type="folder"), required_keys=("data",)))
    assert any(item["id"] in {int(source_id), int(target_id)} for item in listed["nodes"])

    created = _data(assert_envelope(platform_client.get_node(source_id), required_keys=("data",)))["node"]
    assert created["name"] == payload["name"]
    renamed = f"{payload['name']}-updated"
    updated = _data(assert_envelope(
        platform_client.update_node(source_id, name=renamed), required_keys=("data",)
    ))["node"]
    assert updated["name"] == renamed

    assert_envelope(platform_client.move_node(source_id, target_parent_id=int(target_id)))
    moved = _data(assert_envelope(platform_client.get_node(source_id), required_keys=("data",)))["node"]
    assert moved["parent_id"] == int(target_id)

    results = _data(assert_envelope(
        platform_client.search_nodes(q=renamed, scope="folder"), required_keys=("data",)
    ))
    assert any(item["id"] == int(source_id) for item in results["node"])

    nodes = _data(assert_envelope(
        platform_client.batch_list_nodes(f"{source_id},{target_id}"), required_keys=("data",)
    ))
    assert len(nodes["nodes"]) >= 2


@pytest.mark.parametrize("case", INVALID_CREATE_CASES, ids=_case_id)
def test_source_03_02_invalid_node_create_is_rejected(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    """节点类型和父节点非法时，创建请求必须返回业务失败。"""
    assert_rejected(platform_client.create_node(**case_payload(case)))


def test_source_03_03_missing_node_operations_are_rejected(
    platform_client: SourceAdminClient,
) -> None:
    """不存在节点的目录列表返回空集，详情、更新、删除和移动应拒绝。"""
    node_id = NODE_DEFAULTS["missing_node_id"]
    listing = _data(assert_envelope(platform_client.list_nodes(node_id), required_keys=("data",)))
    assert listing["nodes"] == []
    assert_rejected(platform_client.get_node(node_id))
    assert_rejected(platform_client.update_node(node_id, name="missing-node-updated"))
    assert_rejected(platform_client.delete_node(node_id))
    assert_rejected(platform_client.move_node(node_id, target_parent_id=NODE_DEFAULTS["root_id"]))


@pytest.mark.parametrize("case", INVALID_BATCH_CASES, ids=_case_id)
def test_source_03_04_invalid_node_batch_query_is_rejected(
    case: Mapping[str, Any], platform_client: SourceAdminClient
) -> None:
    """批量节点查询拒绝非数字 ID，空 ID 按合法空查询处理。"""
    payload = case_payload(case)
    body = assert_envelope(
        platform_client.batch_list_nodes(payload["ids"]),
        required_keys=("data",),
        expected_code=payload["expected_code"],
    )
    if payload["expected_code"] == 0:
        assert _data(body)["nodes"] == []


@pytest.mark.core
def test_source_03_05_project_node_is_idempotent_and_queryable(
    platform_client: SourceAdminClient,
    platform_data_factory: SourceAdminDataFactory,
) -> None:
    """项目节点重复创建返回同一节点，并可通过项目节点查询接口回查。"""
    payload = case_payload(PROJECT_CASES["standard"])
    node_id, created_payload = platform_data_factory.create_project_node(**payload)

    repeated = _data(assert_envelope(
        platform_client.create_project_node(**created_payload), required_keys=("data",)
    ))
    assert repeated["node_id"] == int(node_id)
    assert repeated["exists"] is True

    info = _data(assert_envelope(
        platform_client.get_project_node_info(f"{node_id},{NODE_DEFAULTS['missing_node_id']}"),
        required_keys=("data",),
    ))
    assert any(item["id"] == int(node_id) for item in info["nodes"])
