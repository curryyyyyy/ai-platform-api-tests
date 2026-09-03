"""Hawk 平台在通用平台注册表中的声明。"""

from __future__ import annotations

from platforms.hawk_admin.client import HawkAdminClient
from platforms.hawk_admin.factories import HawkDataFactory
from platforms.hawk_admin.presets import prepare_batch
from platforms.registry import PlatformDefinition, register_platform


def _client(base_url: str, token: str, timeout: float) -> HawkAdminClient:
    return HawkAdminClient(base_url, token=token, timeout=timeout)


register_platform(
    PlatformDefinition(
        name="hawk_admin",
        short_name="hawk",
        client_factory=_client,
        data_factory_factory=HawkDataFactory,
        state_resolver=prepare_batch,
        viewer_token_env="HAWK_VIEWER_TOKEN",
        viewer_user_env="HAWK_VIEWER_USER",
        viewer_password_env="HAWK_VIEWER_PASSWORD",
        reporting={
            "marker": "hawk_admin",
            "epic": "机器标注平台 (hawk_admin)",
            "modules": {
                "01": "1. 统一认证与请求鉴权",
                "02": "2. 项目管理接口",
                "03": "3. 阶段管理接口",
                "04": "4. 流程管理接口",
                "05": "5. 批次基础生命周期",
                "06": "6. Hawk 执行、统计与结果查询",
            },
        },
    )
)
