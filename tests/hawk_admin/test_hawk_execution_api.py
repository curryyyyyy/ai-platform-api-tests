from __future__ import annotations

import os

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import dataset_case_map, dataset_defaults
from platforms.hawk_admin.presets import wait_for_batch_status


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
EXECUTION_DEFAULTS = dataset_defaults("hawk_admin", "execution")
EXECUTION_OPERATIONS = dataset_case_map("hawk_admin", "execution", "operations")
TASK_STREAM_CASES = dataset_case_map("hawk_admin", "execution", "task_stream")


def _operation(name: str) -> int:
    return int(EXECUTION_OPERATIONS[name]["operation"])


def _assert_operation(
    platform_client, platform_state, state: str, env_name: str, operation: int,
    expected_status: int | tuple[int, ...], *, required: bool = False,
) -> int:
    batch_id = platform_state(state, env_name, required=required)
    body = assert_envelope(platform_client.operate_batch_with_retry(batch_id, operation))
    assert body["code"] == 0, body
    actual = wait_for_batch_status(platform_client, batch_id, expected_status)
    # 先确保 actual 是可转换的类型
    assert actual is not None, f"批次 {batch_id} 状态为空"
    assert isinstance(actual, (int, str)), f"批次状态类型异常: {type(actual)}, 值: {actual}"
    expected_values = (expected_status,) if isinstance(expected_status, int) else expected_status
    assert int(actual) in expected_values, f"批次 {batch_id} 状态未按操作流转: {actual}"
    return batch_id


@pytest.mark.core
def test_hawk_06_01_start_init_batch(platform_client, platform_state):
    """启动未启动批次：对未启动批次执行 START 应成功。"""
    _assert_operation(
        platform_client, platform_state, "init", "HAWK_INIT_BATCH_ID", _operation("start"), 1,
        required=True,
    )


def test_hawk_06_02_pause_running_batch(platform_client, platform_state):
    """暂停处理中批次：对处理中批次执行 PAUSE 应成功。"""
    _assert_operation(platform_client, platform_state, "running", "HAWK_RUNNING_BATCH_ID", _operation("pause"), 3)


def test_hawk_06_03_restart_stopped_batch(platform_client, platform_state):
    """从已暂停批次重启：对已暂停批次执行 RESTART 应成功。"""
    _assert_operation(platform_client, platform_state, "stopped", "HAWK_STOPPED_BATCH_ID", _operation("restart"), 1)


def test_hawk_06_04_retry_failed_batch(platform_client, platform_state):
    """对失败批次执行重试：对失败批次执行 RETRY 应成功。"""
    _assert_operation(platform_client, platform_state, "failed", "HAWK_FAILED_BATCH_ID", _operation("retry"), 1)


def test_hawk_06_05_end_running_batch(platform_client, platform_state):
    """结束批次并验证终态：对处理中批次执行 END 应成功。"""
    _assert_operation(platform_client, platform_state, "running_end", "HAWK_END_RUNNING_BATCH_ID", _operation("end"), (4, 5))


# TC-06-11：处理中批次导出
def test_hawk_06_11_export_running_batch_preserves_status(platform_client, platform_state):
    """导出批次输出不改变处理中状态：导出返回产物路径，且批次状态保持处理中。"""
    # 中途导出要求批次已有任务在执行，现场造数刚启动的批次会报“任务未开始，无法中途导出”
    batch_id = platform_state("running_with_tasks", "HAWK_EXPORT_RUNNING_BATCH_ID")
    before = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]["status"]
    body = assert_envelope(platform_client.export_output(batch_id), required_keys=("data",))
    data = body["data"]
    assert any(data.get(key) for key in ("deliveryTosPath", "errorTosPath", "zipTosPath"))
    after = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]["status"]
    assert before == after == 1


# TC-06-06/08：执行入口异常与任务流
def test_hawk_06_06_operate_missing_batch(platform_client):
    """对不存在批次执行操作：应返回非 0 业务码。"""
    assert_rejected(
        platform_client.operate_batch(EXECUTION_DEFAULTS["missingBatchId"], _operation("start"))
    )


def test_hawk_06_08_task_stream_status_validation(platform_client):
    """查询实时任务流并验证脱敏：非法 status 参数应被拒绝。"""
    assert_rejected(platform_client.task_stream(status="invalid", onlyMine=False))


def test_hawk_task_stream_accepts_valid_filters(platform_client):
    """查询实时任务流的合法筛选条件：返回结构应包含我的批次和其他批次列表。"""
    query = TASK_STREAM_CASES["all_tasks"]
    body = assert_envelope(
        platform_client.task_stream(
            status=query["status"], onlyMine=query["onlyMine"],
        ),
        required_keys=("data",),
    )
    data = body["data"]
    assert isinstance(data.get("myBatches"), list)
    assert isinstance(data.get("otherBatches"), list)


# TC-06-07/12：单批次与批量统计
def test_hawk_06_07_batch_stat_missing_batch(platform_client):
    """查询单批次统计：不存在的批次必须返回业务失败，不得用空统计伪装成功。"""
    assert_rejected(platform_client.batch_stat(EXECUTION_DEFAULTS["missingBatchId"]))


@pytest.mark.core
def test_hawk_batch_stat_matches_batch_detail(platform_client, platform_state):
    """查询已有批次统计：状态、计数和进度字段必须与批次详情对应。"""
    batch_id = platform_state("running", EXECUTION_DEFAULTS["statsBatchIdEnv"], required=True)
    detail = assert_envelope(platform_client.get_batch(batch_id), required_keys=("data",))["data"]
    body = assert_envelope(platform_client.batch_stat(batch_id), required_keys=("data",))
    data = body["data"]
    assert data.get("status") == int(detail["status"])
    assert all(key in data for key in ("totalCount", "successCount", "failedCount", "progress"))
    total_count = int(data["totalCount"])
    success_count = int(data["successCount"])
    failed_count = int(data["failedCount"])
    progress = float(data["progress"])
    assert total_count >= 0
    assert success_count >= 0 and failed_count >= 0
    assert success_count + failed_count <= total_count
    assert 0 <= progress <= 1


def test_hawk_06_12_batch_stats_preserves_valid_item(platform_client, platform_state):
    """批量统计包含不存在批次：整体报错或返回列表，不因单个缺失批次崩溃。"""
    batch_id = platform_state("running", EXECUTION_DEFAULTS["statsBatchIdEnv"])
    body = assert_envelope(
        platform_client.batch_stats([batch_id, EXECUTION_DEFAULTS["missingBatchId"]]), required_keys=("data",)
    )
    items = body["data"]
    assert isinstance(items, list)
    assert any(str(item.get("batchId")) == str(batch_id) for item in items)


def test_hawk_batch_stats_accepts_valid_batch(platform_client, platform_state):
    """批量统计包含有效批次：成功时应返回对应 batchId 的统计项。"""
    batch_id = platform_state("running", EXECUTION_DEFAULTS["statsBatchIdEnv"])
    body = assert_envelope(platform_client.batch_stats([batch_id]), required_keys=("data",))
    items = body["data"]
    assert isinstance(items, list)
    assert any(str(item.get("batchId")) == str(batch_id) for item in items)


# TC-06-09/10：字段和错误日志
def test_hawk_06_09_fields_for_missing_batch_are_not_fabricated(platform_client):
    """查询批次主键和输出字段：不存在的批次不应虚构 keyFields / outputFields。"""
    for response in (platform_client.key_fields(EXECUTION_DEFAULTS["missingBatchId"]), platform_client.output_fields(EXECUTION_DEFAULTS["missingBatchId"])):
        assert_rejected(response)


def test_hawk_fields_for_existing_batch_have_list_shape(platform_client, platform_state):
    """查询已有批次字段：成功时主键和输出字段必须是字符串列表。"""
    # 默认现场独立造 running 批次；CI 可用环境变量覆盖为稳定的长期批次。
    env_name = EXECUTION_DEFAULTS["fieldsBatchIdEnv"]
    batch_id = platform_state("running", env_name)
    key_body = assert_envelope(platform_client.key_fields(batch_id))
    output_body = assert_envelope(platform_client.output_fields(batch_id))
    assert isinstance(key_body.get("keyFields"), list)
    assert all(isinstance(value, str) for value in key_body["keyFields"])
    assert isinstance(output_body.get("outputFields"), list)
    assert all(isinstance(value, str) for value in output_body["outputFields"])


def test_hawk_06_10_error_log_for_missing_batch(platform_client):
    """查询错误日志：不存在的批次必须被拒绝，不得用空数据伪装成功。"""
    assert_rejected(platform_client.error_log(EXECUTION_DEFAULTS["missingBatchId"]))


def test_hawk_error_log_is_bounded_for_configured_batch(platform_client):
    """查询配置批次错误日志：返回行数不得超过 100，截断标识与总数一致。"""
    env_name = EXECUTION_DEFAULTS["errorLogBatchIdEnv"]
    batch_id = os.getenv(env_name, "")
    if not batch_id:
        pytest.skip(f"未配置 {env_name}，跳过错误日志截断校验")
    body = assert_envelope(platform_client.error_log(batch_id), required_keys=("data",))
    data = body["data"]
    assert "rows" in data, f"错误日志响应缺少 rows: {data}"
    rows = data["rows"]
    assert isinstance(rows, list)
    assert len(rows) <= 100
    if data.get("truncated"):
        assert data.get("total", 0) > len(rows)
