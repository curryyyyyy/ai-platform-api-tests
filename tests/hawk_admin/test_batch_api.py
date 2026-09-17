from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_case_map, dataset_cases, dataset_defaults
from platforms.hawk_admin.presets import existing_flow_name


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
BATCH_CREATE_CASES = {case["id"]: case for case in dataset_cases("hawk_admin", "batch", "create")}
BATCH_CASES = dataset_case_map("hawk_admin", "batch", "create")
BATCH_DEFAULTS = dataset_defaults("hawk_admin", "batch")
INVALID_BATCH_CASES = {case["id"]: case for case in dataset_cases("hawk_admin", "batch", "invalid_create")}
INVALID_STATUS_CASES = dataset_cases("hawk_admin", "batch", "invalid_status")
BATCH_AUXILIARY_INVALID_WRITES = dataset_cases("hawk_admin", "batch", "auxiliary_invalid_write")


def test_hawk_05_07_running_batch_rejects_input_update(platform_client, platform_state):
    """处理中批次禁止修改输入文件：仅未启动批次允许修改，应拒绝且提示未启动。"""
    batch_id = platform_state("running", "HAWK_INPUT_UPDATE_RUNNING_BATCH_ID")
    body = assert_rejected(
        platform_client.update_batch_input(
            int(batch_id), inputFilePath=BATCH_CASES["update_input"]["updatedInputFilePath"],
            materialType=BATCH_DEFAULTS["materialType"]
        )
    )
    assert "未启动" in body["message"]


def _existing_flow_name(platform_client, *, required: bool = False):
    try:
        return existing_flow_name(platform_client)
    except Exception as exc:
        message = f"环境内没有可复用流程: {exc}"
        if required:
            raise AssertionError(message) from exc
        pytest.skip(message)


def _batch_prerequisites(platform_data_factory, platform_client, *, required: bool = False):
    project_id, _ = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
    return project_id, _existing_flow_name(platform_client, required=required)


@pytest.mark.core
def test_hawk_05_01_create_batch_defaults_to_init(platform_data_factory, platform_client):
    """创建批次并默认为未启动：回查 status 应为 0，projectId 与名称与创建值一致。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client, required=True)
    batch_id, payload = platform_data_factory.create_batch(
        project_id=project_id,
        flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["default_init"]["inputFilePath"],
    )
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert data["status"] == 0
    # Hawk 当前接口将 projectId 序列化为字符串，断言其数值语义而非 JSON 类型。
    assert str(data["projectId"]) == str(project_id)
    assert data["name"] == payload["name"]


# TC-05-08：CID 输入数据一致性
def test_hawk_05_08_create_batch_preserves_cid_input(platform_data_factory, platform_client):
    """使用 CID 创建批次：创建和详情均应保留 CID 输入路径。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    input_path = BATCH_CREATE_CASES["cid_input"]["inputFilePath"]
    batch_id, payload = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name, input_file_path=input_path,
    )
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert payload["inputFilePath"] == input_path
    assert data.get("inputFilePath") == input_path


@pytest.mark.parametrize(
    "case",
    tuple(INVALID_BATCH_CASES.values()),
    ids=lambda case: case["id"],
)
def test_hawk_05_02_create_batch_invalid_reference(case, platform_client, platform_data_factory):
    """TC-05-02/03：创建批次引用非法项目或流程。"""
    payload = case_payload(case)
    payload.setdefault("config", BATCH_DEFAULTS["config"])
    if "flowName" not in payload:
        payload["flowName"] = _existing_flow_name(platform_client)
    if payload.get("projectId") is None:
        project_id, _ = platform_data_factory.create_project(materialType="图片", notificationLevel=0)
        payload["projectId"] = int(project_id)
    assert_rejected(platform_client.create_batch(**payload))


def test_hawk_05_04_batch_name_check(platform_client, platform_data_factory):
    """批次名称重复检查：刚创建的批次名再次提交检查应返回 exists=True。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, payload = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["name_check"]["inputFilePath"],
    )
    assert batch_id
    body = assert_envelope(platform_client.check_batch_name(project_id, payload["name"]), required_keys=("data",))
    assert body["data"]["exists"] is True


def test_hawk_05_05_list_batches(platform_client, platform_data_factory):
    """按项目、状态和关键词查询批次：过滤条件应命中刚创建的批次。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    _, payload = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["list_filter"]["inputFilePath"],
    )
    body = assert_envelope(
        platform_client.list_batches(page=1, pageSize=10, projectId=project_id, status=0, keyword=payload["name"]),
        required_keys=("data",),
    )
    items = body["data"]["list"]
    assert items, "按唯一批次名称筛选不应返回空列表"
    assert all(str(item["projectId"]) == str(project_id) for item in items)
    assert all(int(item["status"]) == 0 for item in items)
    assert all(payload["name"] in item["name"] for item in items)
    assert any(item["name"] == payload["name"] for item in items)


@pytest.mark.core
def test_hawk_05_06_update_init_batch_input(platform_client, platform_data_factory):
    """未启动批次修改输入文件成功：修改后响应应包含新的输入路径。"""
    project_id, flow_name = _batch_prerequisites(
        platform_data_factory, platform_client, required=True
    )
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["update_input"]["inputFilePath"],
    )
    updated_input = BATCH_CREATE_CASES["update_input"]["updatedInputFilePath"]
    body = assert_envelope(
        platform_client.update_batch_input(
            batch_id,
            inputFilePath=updated_input,
            materialType=BATCH_DEFAULTS["materialType"],
        )
    )
    assert body["inputFilePath"] == updated_input
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert data["inputFilePath"] == updated_input


def test_hawk_05_12_update_init_batch_metadata(platform_client, platform_data_factory):
    """未启动批次通用更新：业务字段写入后可回读，系统补充字段不影响配置语义。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client, required=True)
    batch_id, payload = platform_data_factory.create_batch(
        project_id=project_id,
        flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["update_input"]["inputFilePath"],
    )
    before = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    updated_name = f"{payload['name']}-updated"
    assert_envelope(
        platform_client.update_batch(
            batch_id,
            name=updated_name,
            config=payload["config"],
            materialType=payload["materialType"],
        )
    )
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert data["name"] == updated_name
    assert data["materialType"] == payload["materialType"]
    assert data["inputFilePath"] == before["inputFilePath"] == payload["inputFilePath"]
    assert int(data["status"]) == int(before["status"]) == 0

    # 服务端会向 config 注入通知级别、素材类型和默认输出字段，比较业务语义而非原始字符串。
    requested_config = json.loads(payload["config"])
    returned_config = json.loads(data["config"])
    assert isinstance(requested_config, dict)
    assert isinstance(returned_config, dict)
    for key, value in requested_config.items():
        assert returned_config.get(key) == value


def test_hawk_05_09_update_batch_status(platform_client, platform_data_factory):
    """更新批次状态字段：置为处理中后回查 status 应为 1。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["status_update"]["inputFilePath"],
    )
    assert_envelope(platform_client.update_batch_status(batch_id, 1))
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert data["status"] == 1


@pytest.mark.parametrize("case", INVALID_STATUS_CASES, ids=lambda case: case["id"])
def test_hawk_05_10_invalid_batch_status(case, platform_client, platform_data_factory):
    """提交非法批次状态：每个不支持的状态值均应被拒绝。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["invalid_status"]["inputFilePath"],
    )
    assert_rejected(platform_client.update_batch_status(batch_id, case["status"]))
    data = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    assert int(data["status"]) == 0


def test_hawk_05_11_delete_batch_then_get(platform_client, platform_data_factory):
    """删除批次后查询失败：删除后再查询应返回非 0 业务码。"""
    project_id, flow_name = _batch_prerequisites(platform_data_factory, platform_client)
    batch_id, _ = platform_data_factory.create_batch(
        project_id=project_id, flow_name=flow_name,
        input_file_path=BATCH_CREATE_CASES["delete"]["inputFilePath"],
    )
    assert_envelope(platform_client.delete_batch(batch_id))
    assert_rejected(platform_client.get_batch(batch_id))


def _missing_batch_id() -> int:
    return int(BATCH_DEFAULTS["missingId"])


def _invoke_auxiliary_invalid_write(case, platform_client):
    method = getattr(platform_client, case["endpoint"])
    payload = case["payload"]
    if isinstance(payload, Mapping):
        return method(**payload)
    return method(payload=payload)


def test_hawk_07_07_get_batch_flowgraph_for_missing_batch(platform_client):
    assert_rejected(platform_client.flowgraph(_missing_batch_id()))


def test_hawk_07_08_copy_missing_batch_is_rejected(platform_client):
    assert_rejected(platform_client.copy_batch(_missing_batch_id()))


def test_hawk_07_09_get_statistics_csv_for_missing_batch(platform_client):
    assert_rejected(platform_client.statistics_batch_csv(_missing_batch_id()))


def test_hawk_07_10_list_statistics_batches(platform_client):
    body = assert_envelope(
        platform_client.list_statistics_batches(
            collectionId=BATCH_DEFAULTS["statisticsCollectionId"]
        ),
        required_keys=("data",),
    )
    assert isinstance(body["data"], dict)
    assert isinstance(body["data"].get("list"), list)
    assert isinstance(body["data"].get("total"), int)


@pytest.mark.parametrize("case", BATCH_AUXILIARY_INVALID_WRITES, ids=lambda case: case["id"])
def test_hawk_07_11_invalid_batch_auxiliary_write_is_rejected(case, platform_client):
    assert_rejected(_invoke_auxiliary_invalid_write(case, platform_client))
