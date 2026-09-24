"""基于已提交 OpenAPI 快照校验接口响应结构。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft7Validator, FormatChecker, validators
from referencing import Registry
from referencing.jsonschema import DRAFT7


def _validate_type(validator, expected, instance, schema):
    if instance is None and schema.get("nullable") is True:
        return
    yield from Draft7Validator.VALIDATORS["type"](validator, expected, instance, schema)


OpenApiValidator = validators.extend(Draft7Validator, {"type": _validate_type})


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


class OpenApiContracts:
    """索引一组平台 OpenAPI 文件，并按具体操作校验响应。"""

    def __init__(self, documents: Iterable[tuple[str, dict[str, Any]]]):
        self._operations: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
        self._registry = Registry()
        for index, (source, document) in enumerate(documents):
            version = document.get("openapi")
            if not isinstance(version, str) or not version.startswith("3."):
                raise ValueError(f"只支持 OpenAPI 3.x: {source}")
            uri = f"urn:openapi-contract:{index}"
            self._registry = self._registry.with_resource(uri, DRAFT7.create_resource(document))
            paths = document.get("paths")
            if not isinstance(paths, dict):
                raise ValueError(f"OpenAPI paths 必须是对象: {source}")
            for path, path_item in paths.items():
                if not isinstance(path, str) or not isinstance(path_item, dict):
                    continue
                for method, operation in path_item.items():
                    key = (str(method).upper(), path)
                    if method.lower() not in {
                        "get", "post", "put", "patch", "delete", "head", "options", "trace"
                    } or not isinstance(operation, dict):
                        continue
                    if key in self._operations:
                        raise ValueError(f"OpenAPI 操作重复: {key[0]} {path}")
                    self._operations[key] = (uri, operation)
        if not self._operations:
            raise ValueError("OpenAPI 未定义任何接口操作")

    @classmethod
    def from_files(cls, paths: Iterable[Path]) -> "OpenApiContracts":
        documents: list[tuple[str, dict[str, Any]]] = []
        for path in paths:
            try:
                value = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                raise ValueError(f"OpenAPI 读取失败: {path}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"OpenAPI 顶层必须是对象: {path}")
            documents.append((str(path), value))
        if not documents:
            raise ValueError("至少需要一个 OpenAPI 文件")
        return cls(documents)

    @property
    def operation_count(self) -> int:
        return len(self._operations)

    def assert_response(
        self,
        instance: Any,
        *,
        method: str,
        path: str,
        status_code: int | str = 200,
        media_type: str = "application/json",
    ) -> None:
        key = (method.upper(), path)
        try:
            uri, operation = self._operations[key]
        except KeyError as exc:
            raise AssertionError(f"OpenAPI 未定义操作: {key[0]} {path}") from exc

        responses = operation.get("responses")
        status = str(status_code)
        response = responses.get(status) if isinstance(responses, dict) else None
        if response is None and isinstance(responses, dict):
            response = responses.get("default")
            status = "default"
        content = response.get("content") if isinstance(response, dict) else None
        media = content.get(media_type) if isinstance(content, dict) else None
        schema = media.get("schema") if isinstance(media, dict) else None
        if not isinstance(schema, dict):
            raise AssertionError(
                f"OpenAPI 未定义响应 Schema: {key[0]} {path} status={status_code} media={media_type}"
            )

        ref = (
            f"{uri}#/paths/{_pointer(path)}/{method.lower()}/responses/{_pointer(status)}"
            f"/content/{_pointer(media_type)}/schema"
        )
        validator = OpenApiValidator(
            {"$ref": ref},
            registry=self._registry,
            format_checker=FormatChecker(),
        )
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
        if errors:
            details = "\n".join(
                f"- {error.message} (path: {'/'.join(map(str, error.path)) or '<root>'})"
                for error in errors
            )
            raise AssertionError(
                f"响应不符合 OpenAPI: {key[0]} {path} status={status_code}\n{details}"
            )
