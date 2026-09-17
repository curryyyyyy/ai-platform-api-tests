from __future__ import annotations

from framework.assertions import assert_envelope, assert_rejected

import pytest


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]


def test_hawk_07_06_list_temp_files(platform_client):
    body = assert_envelope(platform_client.list_temp_files(prefix="automation-test"), required_keys=("data",))
    assert isinstance(body["data"], dict)
    assert isinstance(body["data"].get("files"), list)


def test_hawk_07_14_missing_file_operations_are_rejected(platform_client):
    assert_rejected(platform_client.download_url())


def test_hawk_07_15_tools_validate_inputs_and_trigger_commands(platform_client):
    assert_rejected(platform_client.csv_first_row(tos_path=""))
    assert_rejected(platform_client.hbase_ddl(datatype=""))
    assert_rejected(platform_client.csv_info(tosPath="", tosPrefix=""))
    assert_envelope(platform_client.trigger_daily_metrics())
    assert_envelope(platform_client.refresh_stage_ref_counts())
