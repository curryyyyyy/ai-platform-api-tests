"""跨平台共享的静态数据边界。

这些类型只约束测试框架自己的稳定边界，不限制平台接口中故意变化的
``data`` 内容；负向用例仍可传递普通 dict。
"""

from __future__ import annotations

from typing import Any, Tuple, TypedDict, Union


Timeout = Union[float, Tuple[float, float]]


class ResponseEnvelope(TypedDict, total=False):
    code: int
    message: str
    msg: str
    data: Any


class AuthSettings(TypedDict, total=False):
    base_url: str
    rsa_path: str
    login_path: str


class CredentialsSettings(TypedDict, total=False):
    username: str
    password: str


class PlatformSettings(TypedDict, total=False):
    base_url: str
    legacy_base_url_env: str
    viewer_credentials: CredentialsSettings


class Settings(TypedDict, total=False):
    auth: AuthSettings
    credentials: CredentialsSettings
    platforms: dict[str, PlatformSettings]
