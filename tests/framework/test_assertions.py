from __future__ import annotations

from types import SimpleNamespace

import pytest

from framework.assertions import assert_envelope


@pytest.mark.contract
def test_assert_envelope_requires_business_code() -> None:
    response = SimpleNamespace(status_code=200, json=lambda: {"data": {}})

    with pytest.raises(AssertionError, match="业务码 code"):
        assert_envelope(response)


@pytest.mark.contract
def test_assert_envelope_allows_explicit_failure_code() -> None:
    response = SimpleNamespace(status_code=200, json=lambda: {"code": 1, "message": "rejected"})

    body = assert_envelope(response, expected_code=None)

    assert body["code"] == 1
