from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from framework.auth.central_sso import CentralSSO
from framework.data.scope import DataScope
from framework.http.client import ApiClient
from framework.settings import load_settings
from platforms.hawk_admin.factories import HawkDataFactory
from platforms.hawk_admin.client import HawkAdminClient

ROOT = Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def settings() -> dict[str, Any]:
    return load_settings(ROOT, os.getenv("TEST_ENV", "test"))


@pytest.fixture(scope="session")
def central_token(settings: dict[str, Any]) -> str:
    token = os.getenv("API_TOKEN", "")
    if token:
        return token
    auth = settings["auth"]
    credentials = settings["credentials"]
    if not credentials.get("username") or not credentials.get("password"):
        pytest.skip("未配置总平台账号密码，或设置 API_TOKEN")
    return CentralSSO(
        auth["base_url"],
        auth["rsa_path"],
        auth["login_path"],
        timeout=float(os.getenv("API_TIMEOUT", "10")),
    ).login(credentials["username"], credentials["password"])


@pytest.fixture(scope="session")
def anonymous_client(settings: dict[str, Any]) -> ApiClient:
    return ApiClient(settings["platforms"]["hawk_admin"]["base_url"], timeout=float(os.getenv("API_TIMEOUT", "10")))


@pytest.fixture(scope="session")
def hawk_client(settings: dict[str, Any], central_token: str) -> HawkAdminClient:
    return HawkAdminClient(settings["platforms"]["hawk_admin"]["base_url"], token=central_token)


@pytest.fixture
def data_scope(request: pytest.FixtureRequest) -> DataScope:
    scope = DataScope(request.node.nodeid)
    request.addfinalizer(scope.cleanup)
    return scope


@pytest.fixture
def hawk_data_factory(hawk_client: HawkAdminClient, data_scope: DataScope) -> HawkDataFactory:
    return HawkDataFactory(hawk_client, data_scope)
