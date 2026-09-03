from __future__ import annotations

import pytest

from framework.data import dataset as dataset_module
from framework.data.dataset import DatasetError, dataset_cases, dataset_defaults


@pytest.mark.contract
def test_dataset_loads_defaults_and_cases(tmp_path, monkeypatch) -> None:
    (tmp_path / "sample").mkdir()
    (tmp_path / "sample" / "resource.yaml").write_text(
        "defaults:\n  limit: 10\ncases:\n  invalid:\n    - id: negative\n      value: -1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dataset_module, "DATA_ROOT", tmp_path)

    defaults = dataset_defaults("sample", "resource")
    cases = dataset_cases("sample", "resource", "invalid")

    assert defaults == {"limit": 10}
    assert cases == ({"id": "negative", "value": -1},)


def test_dataset_rejects_missing_resource() -> None:
    # 使用不存在的资源名验证错误，不依赖某个具体平台目录。
    with pytest.raises(DatasetError, match="测试数据集不存在"):
        dataset_defaults("sample", "missing")


def test_dataset_returns_independent_copies(tmp_path, monkeypatch) -> None:
    (tmp_path / "sample").mkdir()
    (tmp_path / "sample" / "nested.yaml").write_text(
        "defaults:\n  nested:\n    value: original\n", encoding="utf-8"
    )
    monkeypatch.setattr(dataset_module, "DATA_ROOT", tmp_path)

    first = dataset_defaults("sample", "nested")
    first["nested"]["value"] = "changed"
    second = dataset_defaults("sample", "nested")

    assert second["nested"]["value"] == "original"
