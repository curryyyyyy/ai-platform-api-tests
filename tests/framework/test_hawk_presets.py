from __future__ import annotations

import pytest

from framework.data.scope import DataScope
from platforms.hawk_admin.presets import prepare_batch


class _UnusedClient:
    pass


def test_prepare_end_batch_requires_existing_running_task():
    """END 不能由仅处于 running 状态、但尚无任务的批次代替。"""
    with pytest.raises(RuntimeError, match="已有任务"):
        prepare_batch(_UnusedClient(), DataScope("test-end"), "running_end")
