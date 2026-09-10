"""资源管理平台在通用平台注册表中的声明。"""

from __future__ import annotations

from platforms.registry import PlatformDefinition, register_platform
from platforms.source_admin.client import SourceAdminClient
from platforms.source_admin.factories import SourceAdminDataFactory


def _client(base_url: str, token: str, timeout: float) -> SourceAdminClient:
    return SourceAdminClient(base_url, token=token, timeout=timeout)


register_platform(
    PlatformDefinition(
        name="source_admin",
        short_name="source",
        client_factory=_client,
        data_factory_factory=SourceAdminDataFactory,
        reporting={
            "marker": "source_admin",
            "epic": "资源管理平台 (source_admin)",
            "modules": {
                "01": "1. 总平台 SSO 与只读冒烟",
                "02": "2. 数据管理接口",
                "03": "3. 文件系统接口",
                "04": "4. Schema 管理接口",
                "05": "5. 分享链接接口",
                "06": "6. 审计日志接口",
            },
        },
    )
)
