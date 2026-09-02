"""JSON Schema 响应断言。"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft7Validator


def assert_schema(instance: Any, schema: dict[str, Any], *, context: str = "响应") -> None:
    errors = sorted(Draft7Validator(schema).iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        details = "\n".join(f"- {error.message} (path: {'/'.join(map(str, error.path)) or '<root>'})" for error in errors)
        raise AssertionError(f"{context}不符合 JSON Schema:\n{details}")
