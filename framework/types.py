"""跨平台共享的静态数据边界。

这些类型只约束测试框架自己的稳定边界，不限制平台接口中故意变化的
``data`` 内容；负向用例仍可传递普通 dict。
"""

from __future__ import annotations

from typing import Any, Tuple, TypedDict, Union


Timeout = Union[float, Tuple[float, float]]


# 平台接口的信封字段和 data 内容会随接口而变化。字段存在性由
# assert_envelope(required_keys=...) 在实际断言点校验，不能用 total=False
# TypedDict 假装所有响应字段都可选，否则静态检查无法表达该动态约束。
ResponseEnvelope = dict[str, Any]


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
