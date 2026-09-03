"""按平台加载可执行测试数据集。

运行时数据与人工用例 Schema 分离：``data/<platform>`` 保存可直接供
pytest 参数化或数据工厂消费的 YAML，平台目录名是唯一的隔离边界。
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml


DATA_ROOT = Path(__file__).resolve().parents[2] / "data"


class DatasetError(ValueError):
    """测试数据集文件或结构无效。"""


@lru_cache(maxsize=None)
def _load(platform: str, resource: str) -> dict[str, Any]:
    if not platform or Path(platform).name != platform or not resource or Path(resource).name != resource:
        raise DatasetError(f"平台或资源名称无效: {platform}/{resource}")
    path = DATA_ROOT / platform / f"{resource}.yaml"
    if not path.is_file():
        raise DatasetError(f"测试数据集不存在: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DatasetError(f"测试数据集 YAML 无法解析: {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise DatasetError(f"测试数据集顶层必须是对象: {path}")
    return dict(value)


def load_dataset(platform: str, resource: str) -> dict[str, Any]:
    """加载一个平台资源数据集，并返回副本避免测试间互相修改。"""
    return deepcopy(_load(platform, resource))


def dataset_defaults(platform: str, resource: str) -> dict[str, Any]:
    """读取资源默认字段。"""
    dataset = load_dataset(platform, resource)
    defaults = dataset.get("defaults", {})
    if not isinstance(defaults, Mapping):
        raise DatasetError(f"数据集 defaults 必须是对象: {platform}/{resource}")
    return dict(defaults)


def dataset_cases(platform: str, resource: str, name: str) -> tuple[dict[str, Any], ...]:
    """读取一个可参数化场景集合，要求每条记录带稳定的 id。"""
    dataset = load_dataset(platform, resource)
    cases = dataset.get("cases", {})
    if not isinstance(cases, Mapping) or name not in cases:
        raise DatasetError(f"数据集场景不存在: {platform}/{resource}#{name}")
    records = cases[name]
    if not isinstance(records, list) or not records:
        raise DatasetError(f"数据集场景必须是非空数组: {platform}/{resource}#{name}")
    result: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise DatasetError(f"数据集场景第 {index + 1} 条必须是对象: {platform}/{resource}#{name}")
        if not record.get("id"):
            raise DatasetError(f"数据集场景第 {index + 1} 条缺少 id: {platform}/{resource}#{name}")
        result.append(dict(record))
    return tuple(result)


def case_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """去除数据集元字段，返回可直接传给接口/工厂的请求字段。"""
    return {key: deepcopy(value) for key, value in record.items() if key != "id"}


def dataset_case_map(platform: str, resource: str, name: str) -> dict[str, dict[str, Any]]:
    """按稳定 case id 建立索引，供同一资源的多个测试复用。"""
    return {record["id"]: record for record in dataset_cases(platform, resource, name)}
