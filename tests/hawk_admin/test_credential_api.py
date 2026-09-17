from __future__ import annotations

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import dataset_cases, dataset_defaults


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
CREDENTIAL_DEFAULTS = dataset_defaults("hawk_admin", "credential")
CREDENTIAL_INVALID_WRITES = dataset_cases("hawk_admin", "credential", "invalid_write")


def test_hawk_07_02_list_credentials(platform_client):
    body = assert_envelope(platform_client.list_credentials(), required_keys=("data",))
    data = body["data"]
    assert isinstance(data, dict)
    assert isinstance(data.get("list"), list)
    assert isinstance(data.get("total"), int)


@pytest.mark.parametrize("case", CREDENTIAL_INVALID_WRITES, ids=lambda case: case["id"])
def test_hawk_07_11_invalid_credential_write_is_rejected(case, platform_client):
    assert_rejected(platform_client.create_credential(**case["payload"]))


def test_hawk_07_12_missing_credential_operations_are_rejected(platform_client):
    credential_id = CREDENTIAL_DEFAULTS["missingId"]
    assert_rejected(platform_client.update_credential(credential_id))
    assert_rejected(platform_client.delete_credential(credential_id))
