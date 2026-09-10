from __future__ import annotations

import pytest

from framework.assertions import assert_envelope
from framework.data.dataset import dataset_defaults
from platforms.source_admin.factories import SourceAdminDataFactory


pytestmark = [pytest.mark.live, pytest.mark.source_admin]
NODE_DEFAULTS = dataset_defaults("source_admin", "node")


def _data(body: dict):
    value = body.get("data")
    if isinstance(value, dict) and set(value) == {"data"}:
        return value["data"]
    return value


@pytest.mark.core
def test_source_03_01_folder_crud_move_and_search(platform_client, platform_data_factory: SourceAdminDataFactory):
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
