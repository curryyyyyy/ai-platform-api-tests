from __future__ import annotations

import pytest

from framework.data.scope import DataScope
from platforms.hawk_admin.client import HawkAdminClient
from platforms.hawk_admin.presets import prepare_batch


pytestmark = [pytest.mark.contract, pytest.mark.hawk_admin]


def test_prepare_end_batch_requires_existing_running_task():
    """END 不能由仅处于 running 状态、但尚无任务的批次代替。"""
    with pytest.raises(RuntimeError, match="已有任务"):
        # running_end 在函数入口即被拒绝，不会发起请求；真实类型可避免测试桩违背客户端协议。
        prepare_batch(
            HawkAdminClient("http://hawk.invalid", retries=0),
            DataScope("test-end"),
            "running_end",
        )
