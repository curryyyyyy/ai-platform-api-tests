from __future__ import annotations

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import case_payload, dataset_cases, dataset_defaults


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
EXTENDED_DEFAULTS = dataset_defaults("hawk_admin", "extended")
INVALID_WRITES = dataset_cases("hawk_admin", "extended", "invalid_write")
TRANSFER_ACTIONS = dataset_cases("hawk_admin", "extended", "transfer_actions")


def _missing_id() -> int:
    return int(EXTENDED_DEFAULTS["missing_id"])


_SUCCESS_MESSAGES = (
    "success",
    "操作成功",
    "批次已删除，后续不再发送结束异常告警",
    "批次已回退到已完成",
)


def _assert_rejected(response) -> None:
    assert_rejected(response, forbidden_messages=_SUCCESS_MESSAGES)


def test_hawk_07_01_list_common_templates(platform_client):
    body = assert_envelope(platform_client.common_templates(), required_keys=("data",))
    assert isinstance(body["data"], dict)
    assert isinstance(body["data"].get("list"), list)


def test_hawk_07_02_list_credentials(platform_client):
    body = assert_envelope(platform_client.list_credentials(), required_keys=("data",))
    data = body["data"]
    assert isinstance(data, dict)
    assert isinstance(data.get("list"), list)
    assert isinstance(data.get("total"), int)


def test_hawk_07_03_get_system_load(platform_client):
    body = assert_envelope(platform_client.system_load(), required_keys=("data",))
    assert isinstance(body["data"], dict)


def test_hawk_07_04_list_task_stream_stats(platform_client):
    body = assert_envelope(platform_client.refresh_task_stream(), required_keys=("data",))
    assert isinstance(body["data"], list)


def test_hawk_07_05_get_feishu_project_info_rejects_invalid_link(platform_client):
    _assert_rejected(platform_client.feishu_project_info(link="not-a-feishu-link"))


def test_hawk_07_06_list_temp_files(platform_client):
    body = assert_envelope(platform_client.list_temp_files(prefix="automation-test"), required_keys=("data",))
    assert isinstance(body["data"], dict)
    assert isinstance(body["data"].get("files"), list)


def test_hawk_07_07_get_batch_flowgraph_for_missing_batch(platform_client):
    _assert_rejected(platform_client.flowgraph(_missing_id()))


def test_hawk_07_08_copy_missing_batch_is_rejected(platform_client):
    _assert_rejected(platform_client.copy_batch(_missing_id()))


def test_hawk_07_09_get_statistics_csv_for_missing_batch(platform_client):
    _assert_rejected(platform_client.statistics_batch_csv(_missing_id()))


def test_hawk_07_10_list_statistics_batches(platform_client):
    body = assert_envelope(
        platform_client.list_statistics_batches(
            collectionId=EXTENDED_DEFAULTS["statistics_collection_id"]
        ),
        required_keys=("data",),
    )
    assert isinstance(body["data"], dict)
    assert isinstance(body["data"].get("list"), list)
    assert isinstance(body["data"].get("total"), int)


def test_hawk_07_17_list_template_workflows(platform_client):
    """模板工作流列表接口返回稳定的响应信封。"""
    body = assert_envelope(platform_client.list_templates(page=1, pageSize=10), required_keys=("data",))
    data = body["data"]
    assert isinstance(data, dict)
    assert isinstance(data.get("data"), list)


@pytest.mark.parametrize("case", INVALID_WRITES, ids=lambda case: case["id"])
def test_hawk_07_11_invalid_extended_write_is_rejected(case, platform_client):
    method = getattr(platform_client, case["endpoint"])
    _assert_rejected(method(**case_payload(case)))


def test_hawk_07_12_missing_credential_operations_are_rejected(platform_client):
    credential_id = EXTENDED_DEFAULTS["credential_id"]
    _assert_rejected(platform_client.update_credential(credential_id))
    _assert_rejected(platform_client.delete_credential(credential_id))


def test_hawk_07_13_missing_template_operations_are_rejected(platform_client):
    template_id = EXTENDED_DEFAULTS["template_id"]
    _assert_rejected(platform_client.get_template(template_id))
    _assert_rejected(platform_client.update_template(template_id))
    _assert_rejected(platform_client.download_template(template_id))
    _assert_rejected(platform_client.template_metric([str(template_id)]))


def test_hawk_07_14_missing_file_operations_are_rejected(platform_client):
    _assert_rejected(platform_client.download_url())


def test_hawk_07_15_tools_validate_inputs_and_trigger_commands(platform_client):
    _assert_rejected(platform_client.csv_first_row(tos_path=""))
    _assert_rejected(platform_client.hbase_ddl(datatype=""))
    _assert_rejected(platform_client.tos_file_ext(tosPath="", tosPrefix=""))
    assert_envelope(platform_client.trigger_daily_metrics())
    assert_envelope(platform_client.refresh_stage_ref_counts())


def test_hawk_07_16_done_end_alert_actions_reject_missing_batch(platform_client):
    _assert_rejected(platform_client.done_end_delete(_missing_id()))
    _assert_rejected(platform_client.done_end_rollback(_missing_id()))


def test_hawk_08_01_list_transfer_tasks(platform_client):
    body = assert_envelope(platform_client.list_transfer_tasks(page=1, pageSize=10), required_keys=("data",))
    data = body["data"]
    assert isinstance(data, dict)
    assert isinstance(data.get("list"), list)
    assert isinstance(data.get("total"), int)


def test_hawk_08_02_get_transfer_task(platform_client):
    listing = assert_envelope(
        platform_client.list_transfer_tasks(page=1, pageSize=10), required_keys=("data",)
    )["data"]
    tasks = listing["list"]
    if tasks:
        task_id = tasks[0].get("id")
        assert task_id is not None
        body = assert_envelope(platform_client.get_transfer_task(task_id), required_keys=("data",))
        assert isinstance(body["data"], dict)
    else:
        _assert_rejected(platform_client.get_transfer_task(EXTENDED_DEFAULTS["transfer_task_id"]))


@pytest.mark.parametrize("case", TRANSFER_ACTIONS, ids=lambda case: case["id"])
def test_hawk_08_03_missing_transfer_action_is_rejected(case, platform_client):
    task_id = EXTENDED_DEFAULTS["missing_id"]
    method_name = case.get("client_method")
    if not isinstance(method_name, str) or not method_name.strip():
        raise AssertionError(f"数据集配置缺少有效的传输任务客户端方法: {method_name!r}")
    method = getattr(platform_client, method_name, None)
    if not callable(method):
        raise AssertionError(f"数据集配置的传输任务客户端方法不存在: {method_name}")
    if "step_no" in case:
        response = method(task_id, int(case["step_no"]))
    else:
        response = method(task_id)
    _assert_rejected(response)


def test_hawk_08_04_missing_transfer_config_is_rejected(platform_client):
    _assert_rejected(platform_client.update_transfer_config(EXTENDED_DEFAULTS["missing_id"]))


def test_hawk_08_05_hide_missing_task_stream_batch_is_rejected(platform_client):
    _assert_rejected(platform_client.hide_task_stream_batch(batchId=_missing_id()))


def test_hawk_09_01_user_auth_accepts_central_token(platform_client, central_token):
    """Hawk User/Auth 接口应能识别总平台登录产生的统一 Token。"""
    body = assert_envelope(platform_client.user_auth(token=central_token), required_keys=("data",))
    assert isinstance(body["data"], dict)


def test_hawk_09_02_user_rsa_returns_public_key(anonymous_platform_client):
    """Hawk User/RSA 接口必须返回非空公钥。"""
    body = assert_envelope(
        anonymous_platform_client.get("/api/v1/user/rsa"), required_keys=("data",)
    )
    rsa = body["data"].get("rsa")
    assert isinstance(rsa, str) and rsa.strip()


def test_hawk_09_03_user_login_rejects_empty_credentials(platform_client):
    """Hawk User/Login 不得接受空账号密码。"""
    _assert_rejected(platform_client.user_login())


def test_hawk_09_04_user_logout_invalid_token_is_idempotent(platform_client, central_token):
    """Hawk User/Logout 对伪造 Token 按幂等注销处理，且不得影响有效会话。"""
    body = assert_envelope(
        platform_client.user_logout(token=EXTENDED_DEFAULTS["invalid_user_token"])
    )
    assert body["code"] == 0
    assert body.get("data") in (None, {}, [], "")

    auth_body = assert_envelope(
        platform_client.user_auth(token=central_token), required_keys=("data",)
    )
    assert isinstance(auth_body["data"], dict)
