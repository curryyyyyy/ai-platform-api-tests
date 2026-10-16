from __future__ import annotations

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import dataset_cases, dataset_defaults
from framework.http.client import ApiClient


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
CREDENTIAL_DEFAULTS = dataset_defaults("hawk_admin", "credential")
CREDENTIAL_INVALID_WRITES = dataset_cases("hawk_admin", "credential", "invalid_write")


@pytest.fixture
def credential_access(platform_client):
    """验证账号具备 Hawk 凭证权限，再执行凭证业务断言。"""
    response = platform_client.list_credentials()
    body = ApiClient.json(response)
    if response.status_code == 403 and "Hawk凭证权限" in str(body.get("message", "")):
        pytest.skip("当前账号没有 Hawk 凭证权限；请为测试账号配置对应角色")
    return assert_envelope(response, required_keys=("data",))


def test_hawk_07_02_list_credentials(credential_access):
    body = credential_access
    data = body["data"]
    assert isinstance(data, dict)
    assert isinstance(data.get("list"), list)
    assert isinstance(data.get("total"), int)


@pytest.mark.parametrize("case", CREDENTIAL_INVALID_WRITES, ids=lambda case: case["id"])
def test_hawk_07_11_invalid_credential_write_is_rejected(case, platform_client, credential_access):
    assert_rejected(platform_client.create_credential(**case["payload"]))


def test_hawk_07_12_missing_credential_operations_are_rejected(platform_client, credential_access):
    credential_id = CREDENTIAL_DEFAULTS["missingId"]
    assert_rejected(platform_client.update_credential(credential_id))
    assert_rejected(platform_client.delete_credential(credential_id))
