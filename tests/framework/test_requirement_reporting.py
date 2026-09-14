from __future__ import annotations

import pytest

from framework.requirements import validate_requirement_identifiers


@pytest.mark.contract
@pytest.mark.parametrize(
    ("requirement_id", "case_id"),
    [
        ("REQ-PIPELINE-20260910", "REQ-PIPELINE-20260910-API-01"),
        ("REQ-DATA-QUALITY", "REQ-DATA-QUALITY-API-01"),
    ],
)
def test_requirement_identifiers_are_stable(requirement_id: str, case_id: str) -> None:
    validate_requirement_identifiers(requirement_id, case_id)


@pytest.mark.contract
@pytest.mark.parametrize(
    ("requirement_id", "case_id"),
    [
        ("REQ-PIPELINE-20260911_153000", "REQ-PIPELINE-20260911_153000-API-01"),
        ("REQ-PIPELINE", "REQ-OTHER-API-01"),
        ("PIPELINE-20260910", "PIPELINE-20260910-API-01"),
        ("REQ-PIPELINE-20260910", "REQ-PIPELINE-20260910-20260911153000"),
    ],
)
def test_requirement_identifiers_reject_runtime_or_unrelated_ids(
    requirement_id: str, case_id: str
) -> None:
    with pytest.raises(ValueError):
        validate_requirement_identifiers(requirement_id, case_id)
