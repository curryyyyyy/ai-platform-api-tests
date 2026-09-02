from __future__ import annotations

from types import SimpleNamespace

import pytest

from framework.data.scope import DataScope
from platforms.hawk_admin.factories import HawkDataFactory


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def post(self, path: str, **kwargs):
        self.calls.append(("POST", path, kwargs))
        return SimpleNamespace(status_code=200)

    def delete(self, path: str, **kwargs):
        self.calls.append(("DELETE", path, kwargs))
        return SimpleNamespace(status_code=200)

    @staticmethod
    def json(response) -> dict:
        return {"code": 0, "id": "project-1"} if response.status_code == 200 else {}


@pytest.mark.contract
def test_hawk_factory_registers_project_cleanup() -> None:
    client = FakeClient()
    scope = DataScope("TC-HAWK-PROJECT-001")
    factory = HawkDataFactory(client, scope)

    project_id, payload = factory.create_project(description="factory test")
    assert project_id == "project-1"
    assert payload["description"] == "factory test"

    scope.cleanup()
    assert [call[0:2] for call in client.calls] == [
        ("POST", "/api/v1/project"),
        ("DELETE", "/api/v1/project/project-1"),
    ]
