from __future__ import annotations

import pytest

from framework.assertions import assert_envelope


@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.hawk_admin
def test_project_requires_token(anonymous_client) -> None:
    response = anonymous_client.get("/api/v1/project")
    assert response.status_code in {401, 403}, f"未携带 Token 时应拒绝访问: {response.status_code}"


@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.hawk_admin
def test_user_rsa_is_public(anonymous_client) -> None:
    payload = assert_envelope(anonymous_client.get("/api/v1/user/rsa"), required_keys=("data",))
    assert isinstance((payload.get("data") or {}).get("rsa"), str)


@pytest.mark.live
@pytest.mark.smoke
@pytest.mark.hawk_admin
def test_authenticated_project_list(hawk_client: object) -> None:
    response = hawk_client.list_projects()
    payload = assert_envelope(response, required_keys=("data",))
    assert isinstance((payload.get("data") or {}).get("list"), list)
    assert isinstance((payload.get("data") or {}).get("total"), int)
