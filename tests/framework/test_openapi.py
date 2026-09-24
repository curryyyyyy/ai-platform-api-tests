from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from framework.openapi import OpenApiContracts


ROOT = Path(__file__).resolve().parents[2]


def _write_spec(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "openapi": "3.0.3",
                "paths": {
                    "/items": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/Envelope"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "components": {
                    "schemas": {
                        "Envelope": {
                            "type": "object",
                            "required": ["data"],
                            "properties": {
                                "data": {
                                    "type": "array",
                                    "items": {"type": "string", "nullable": True},
                                }
                            },
                        }
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


@pytest.mark.contract
def test_openapi_contracts_resolves_refs_and_nullable_items(tmp_path: Path) -> None:
    spec = tmp_path / "openapi.yaml"
    _write_spec(spec)
    contracts = OpenApiContracts.from_files([spec])

    contracts.assert_response(
        {"data": ["value", None]}, method="GET", path="/items", status_code=200
    )
    assert contracts.operation_count == 1


@pytest.mark.contract
def test_openapi_contracts_reports_operation_and_field_errors(tmp_path: Path) -> None:
    spec = tmp_path / "openapi.yaml"
    _write_spec(spec)
    contracts = OpenApiContracts.from_files([spec])

    with pytest.raises(AssertionError, match="data"):
        contracts.assert_response({"data": {}}, method="GET", path="/items")
    with pytest.raises(AssertionError, match="未定义操作"):
        contracts.assert_response({}, method="POST", path="/items")


@pytest.mark.contract
def test_openapi_contracts_rejects_unsupported_or_empty_documents() -> None:
    with pytest.raises(ValueError, match="OpenAPI 3.x"):
        OpenApiContracts([("swagger.yaml", {"swagger": "2.0", "paths": {}})])
    with pytest.raises(ValueError, match="未定义任何接口操作"):
        OpenApiContracts([("openapi.yaml", {"openapi": "3.0.3", "paths": {}})])


@pytest.mark.contract
def test_openapi_contracts_validates_committed_hawk_response_schema() -> None:
    contracts = OpenApiContracts.from_files([ROOT / "contracts/hawk_admin/openapi.yaml"])
    response = {
        "code": 0,
        "message": "success",
        "timestamp": "2026-09-24T00:00:00Z",
        "data": {"list": [], "total": 0, "accessDenied": False},
    }

    contracts.assert_response(response, method="GET", path="/api/v1/project")
    response["data"]["total"] = "0"
    with pytest.raises(AssertionError, match="total"):
        contracts.assert_response(response, method="GET", path="/api/v1/project")
