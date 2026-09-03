"""平台适配器注册表。

平台实现细节留在 ``platforms/<name>`` 包内，测试框架只依赖本文件定义的
最小构造协议。新增平台不需要修改 ``conftest.py`` 或 ``framework``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import pkgutil
from typing import Any, Callable


ClientFactory = Callable[[str, str, float], Any]
DataFactoryFactory = Callable[[Any, Any], Any]


@dataclass(frozen=True)
class PlatformDefinition:
    name: str
    short_name: str
    client_factory: ClientFactory
    data_factory_factory: DataFactoryFactory | None = None
    reporting: dict[str, Any] = field(default_factory=dict)
    state_resolver: Callable[[Any, Any, str], int] | None = None
    viewer_token_env: str | None = None
    viewer_user_env: str | None = None
    viewer_password_env: str | None = None

    @property
    def base_url_env(self) -> str:
        return "PLATFORM_" + "_".join(part.upper() for part in self.name.replace("-", "_").split("_")) + "_BASE_URL"


_REGISTRY: dict[str, PlatformDefinition] = {}
_DISCOVERED = False


def register_platform(definition: PlatformDefinition) -> PlatformDefinition:
    if definition.name in _REGISTRY and _REGISTRY[definition.name] != definition:
        raise ValueError(f"平台重复注册: {definition.name}")
    _REGISTRY[definition.name] = definition
    return definition


def discover_platforms() -> dict[str, PlatformDefinition]:
    """导入各平台的 definition 模块并返回注册结果。"""
    global _DISCOVERED
    if not _DISCOVERED:
        import platforms

        for module in pkgutil.iter_modules(platforms.__path__):
            if module.name.startswith("_") or module.name == "registry":
                continue
            try:
                importlib.import_module(f"platforms.{module.name}.definition")
            except ModuleNotFoundError as exc:
                # 允许仅包含客户端的实验包存在；若 definition 内部缺依赖则继续抛出。
                if exc.name != f"platforms.{module.name}.definition":
                    raise
        _DISCOVERED = True
    return dict(_REGISTRY)


def get_platform(name: str) -> PlatformDefinition:
    definitions = discover_platforms()
    try:
        return definitions[name]
    except KeyError as exc:
        known = ", ".join(sorted(definitions)) or "无"
        raise KeyError(f"未注册平台 {name!r}，已注册平台: {known}") from exc
