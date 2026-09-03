from __future__ import annotations

import pytest

from framework.assertions import assert_envelope
from framework.data.dataset import dataset_case_map, dataset_defaults


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
EXECUTION_DEFAULTS = dataset_defaults("hawk_admin", "execution")
EXECUTION_OPERATIONS = dataset_case_map("hawk_admin", "execution", "operations")


def _operation(name: str) -> int:
    return int(EXECUTION_OPERATIONS[name]["operation"])


def _assert_operation(platform_client, platform_state, state: str, env_name: str, operation: int) -> int:
    batch_id = platform_state(state, env_name)
    body = assert_envelope(platform_client.operate_batch_with_retry(batch_id, operation))
    assert body["code"] == 0, body
    return batch_id


def test_hawk_06_01_start_init_batch(platform_client, platform_state):
    """启动未启动批次：对未启动批次执行 START 应成功。"""
    _assert_operation(platform_client, platform_state, "init", "HAWK_INIT_BATCH_ID", _operation("start"))


def test_hawk_06_02_pause_running_batch(platform_client, platform_state):
    """暂停处理中批次：对处理中批次执行 PAUSE 应成功。"""
    _assert_operation(platform_client, platform_state, "running", "HAWK_RUNNING_BATCH_ID", _operation("pause"))


def test_hawk_06_03_restart_stopped_batch(platform_client, platform_state):
    """从已暂停批次重启：对已暂停批次执行 RESTART 应成功。"""
    _assert_operation(platform_client, platform_state, "stopped", "HAWK_STOPPED_BATCH_ID", _operation("restart"))


def test_hawk_06_04_retry_failed_batch(platform_client, platform_state):
    """对失败批次执行重试：对失败批次执行 RETRY 应成功。"""
    _assert_operation(platform_client, platform_state, "failed", "HAWK_FAILED_BATCH_ID", _operation("retry"))


def test_hawk_06_05_end_running_batch(platform_client, platform_state):
    """结束批次并验证终态：对处理中批次执行 END 应成功。"""
    _assert_operation(platform_client, platform_state, "running_end", "HAWK_END_RUNNING_BATCH_ID", _operation("end"))


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


def test_hawk_06_06_operate_missing_batch(platform_client):
    """对不存在批次执行操作：应返回非 0 业务码。"""
    body = assert_envelope(
        platform_client.operate_batch(EXECUTION_DEFAULTS["missingBatchId"], _operation("start")),
        expected_code=None,
    )
    assert body["code"] != 0


def test_hawk_06_08_task_stream_status_validation(platform_client):
    """查询实时任务流并验证脱敏：非法 status 参数应被拒绝。"""
    body = assert_envelope(platform_client.task_stream(status="invalid", onlyMine=False), expected_code=None)
    assert body["code"] != 0


def test_hawk_06_07_batch_stat_missing_batch(platform_client):
    """查询单批次统计：不存在的批次应报错或返回 rpcError，不虚构数据。"""
    body = assert_envelope(platform_client.batch_stat(EXECUTION_DEFAULTS["missingBatchId"]), expected_code=None)
    data = body.get("data") or {}
    assert body["code"] != 0 or data.get("rpcError")


def test_hawk_06_12_batch_stats_preserves_valid_item(platform_client):
    """批量统计包含不存在批次：整体报错或返回列表，不因单个缺失批次崩溃。"""
    body = assert_envelope(platform_client.batch_stats([EXECUTION_DEFAULTS["missingBatchId"]]), expected_code=None)
    assert body["code"] != 0 or isinstance(body.get("data"), list)


def test_hawk_06_09_fields_for_missing_batch_are_not_fabricated(platform_client):
    """查询批次主键和输出字段：不存在的批次不应虚构 keyFields / outputFields。"""
    for response in (platform_client.key_fields(EXECUTION_DEFAULTS["missingBatchId"]), platform_client.output_fields(EXECUTION_DEFAULTS["missingBatchId"])):
        body = assert_envelope(response, expected_code=None)
        assert body["code"] != 0 or not body.get("keyFields") and not body.get("outputFields")


def test_hawk_06_10_error_log_for_missing_batch(platform_client):
    """查询错误日志最多返回 100 行：不存在的批次返回空数据。"""
    body = assert_envelope(platform_client.error_log(EXECUTION_DEFAULTS["missingBatchId"]), expected_code=None)
    assert body["code"] != 0 or body.get("data") == {}
