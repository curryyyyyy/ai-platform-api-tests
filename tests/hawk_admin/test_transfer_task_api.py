from __future__ import annotations

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import dataset_cases, dataset_defaults


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
TRANSFER_DEFAULTS = dataset_defaults("hawk_admin", "transfer_task")
TRANSFER_INVALID_WRITES = dataset_cases("hawk_admin", "transfer_task", "invalid_write")
TRANSFER_ACTIONS = dataset_cases("hawk_admin", "transfer_task", "actions")


def test_hawk_07_01_list_common_templates(platform_client):
    body = assert_envelope(platform_client.common_templates(), required_keys=("data",))
    assert isinstance(body["data"], dict)
    assert isinstance(body["data"].get("list"), list)


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
        assert_rejected(platform_client.get_transfer_task(TRANSFER_DEFAULTS["transferTaskId"]))


@pytest.mark.parametrize("case", TRANSFER_INVALID_WRITES, ids=lambda case: case["id"])
def test_hawk_07_11_invalid_transfer_write_is_rejected(case, platform_client):
    assert_rejected(platform_client.create_transfer_task(**case["payload"]))


@pytest.mark.parametrize("case", TRANSFER_ACTIONS, ids=lambda case: case["id"])
def test_hawk_08_03_missing_transfer_action_is_rejected(case, platform_client):
    method = getattr(platform_client, case["client_method"])
    task_id = TRANSFER_DEFAULTS["missingId"]
    if "step_no" in case:
        response = method(task_id, int(case["step_no"]))
    else:
        response = method(task_id)
    assert_rejected(response)


def test_hawk_08_04_missing_transfer_config_is_rejected(platform_client):
    assert_rejected(platform_client.update_transfer_config(TRANSFER_DEFAULTS["missingId"]))
