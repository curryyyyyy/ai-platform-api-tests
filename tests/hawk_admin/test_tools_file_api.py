from __future__ import annotations

from framework.assertions import assert_envelope, assert_rejected
from framework.http.client import ApiClient

import pytest


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]


def _skip_for_legacy_flow_schema(response):
    """共享环境存在历史 object-schema Flow 时，明确标记环境前置阻塞。"""
    body = ApiClient.json(response)
    message = str(body.get("message", ""))
    if body.get("code") != 0 and "解析 Flow" in message and "schema" in message:
        pytest.skip(f"环境存在不兼容的历史 Flow schema，无法刷新 Stage 引用计数: {message}")


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
    refresh_response = platform_client.refresh_stage_ref_counts()
    _skip_for_legacy_flow_schema(refresh_response)
    assert_envelope(refresh_response)
