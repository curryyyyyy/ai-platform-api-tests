from __future__ import annotations

import pytest


@pytest.mark.live
@pytest.mark.smoke
def test_central_login_returns_token(central_token: str) -> None:
    assert central_token
