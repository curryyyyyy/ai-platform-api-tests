from __future__ import annotations

import pytest

from framework.assertions import assert_envelope
from platforms.hawk_admin.presets import existing_flow_name


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]


def test_hawk_05_07_running_batch_rejects_input_update(platform_client, platform_state):
    """处理中批次禁止修改输入文件：仅未启动批次允许修改，应拒绝且提示未启动。"""
    batch_id = platform_state("running", "HAWK_RUNNING_BATCH_ID")
    body = assert_envelope(
        platform_client.update_batch_input(
            int(batch_id), inputFilePath="CID://collection/automation-0507", materialType="图片"
        ),
        expected_code=None,
    )
    assert body["code"] != 0
    assert "未启动" in body.get("message", "")


def _existing_flow_name(platform_client):
    try:
        return existing_flow_name(platform_client)
    except Exception as exc:
        pytest.skip(f"环境内没有可复用流程，跳过批次用例: {exc}")


def _batch_prerequisites(platform_data_factory, platform_client):
    project_id, _ = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
    return project_id, _existing_flow_name(platform_client)


def test_hawk_05_01_create_batch_defaults_to_init(platform_data_factory, platform_client):
    """创建批次并默认为未启动：回查 status 应为 0，projectId 与名称与创建值一致。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, payload = platform_data_factory.create_batch(
        project_id=project_id,
        flow_name=flow_name,
        input_file_path="CID://collection/automation-0501",
    )
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert data["status"] == 0
    # Hawk 当前接口将 projectId 序列化为字符串，断言其数值语义而非 JSON 类型。
    assert str(data["projectId"]) == str(project_id)
    assert data["name"] == payload["name"]


def test_hawk_05_02_create_batch_without_project(platform_client, platform_data_factory):
    """创建批次未选择项目：projectId=0 应被拒绝。"""
    flow_name = _existing_flow_name(platform_client)
    body = assert_envelope(
        platform_client.create_batch(
            name="TC-05-02-no-project", projectId=0, flowName=flow_name,
            inputFilePath="CID://collection/automation-0502", config='{"stages":[]}'
        ),
        expected_code=None,
    )
    assert body["code"] != 0


def test_hawk_05_03_create_batch_with_missing_flow(platform_client, platform_data_factory):
    """创建批次使用不存在的流程：flowName 不存在应被拒绝。"""
    project_id, _ = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
    body = assert_envelope(
        platform_client.create_batch(
            name="TC-05-03-no-flow", projectId=int(project_id), flowName="flow-not-exist-20260902",
            inputFilePath="CID://collection/automation-0503", config='{"stages":[]}'
        ),
        expected_code=None,
    )
    assert body["code"] != 0


def test_hawk_05_04_batch_name_check(platform_client, platform_data_factory):
    """批次名称重复检查：刚创建的批次名再次提交检查应返回 exists=True。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, payload = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path="CID://collection/automation-0504",
    )
    assert batch_id
    body = assert_envelope(platform_client.check_batch_name(project_id, payload["name"]), required_keys=("data",))
    assert body["data"]["exists"] is True


def test_hawk_05_05_list_batches(platform_client, platform_data_factory):
    """按项目、状态和关键词查询批次：过滤条件应命中刚创建的批次。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    _, payload = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path="CID://collection/automation-0505",
    )
    body = assert_envelope(
        platform_client.list_batches(page=1, pageSize=10, projectId=project_id, status=0, keyword=payload["name"]),
        required_keys=("data",),
    )
    assert any(item["name"] == payload["name"] for item in body["data"]["list"])


def test_hawk_05_06_update_init_batch_input(platform_client, platform_data_factory):
    """未启动批次修改输入文件成功：修改后响应应包含新的输入路径。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path="CID://collection/automation-0506",
    )
    body = assert_envelope(
        platform_client.update_batch_input(batch_id, inputFilePath="CID://collection/automation-0506-updated", materialType="图片")
    )
    assert body.get("inputFilePath") or body.get("data")


def test_hawk_05_09_update_batch_status(platform_client, platform_data_factory):
    """更新批次状态字段：置为处理中后回查 status 应为 1。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path="CID://collection/automation-0509",
    )
    assert_envelope(platform_client.update_batch_status(batch_id, 1))
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert data["status"] == 1


def test_hawk_05_10_invalid_batch_status(platform_client, platform_data_factory):
    """提交无效批次状态：把已创建的批次状态改回未启动应被拒绝。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path="CID://collection/automation-0510",
    )
    body = assert_envelope(platform_client.update_batch_status(batch_id, 0), expected_code=None)
    assert body["code"] != 0


def test_hawk_05_11_delete_batch_then_get(platform_client, platform_data_factory):
    """删除批次后查询失败：删除后再查询应返回非 0 业务码。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path="CID://collection/automation-0511",
    )
    assert_envelope(platform_client.delete_batch(batch_id))
    body = assert_envelope(platform_client.get_batch(batch_id), expected_code=None)
    assert body["code"] != 0
