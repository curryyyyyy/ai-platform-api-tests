"""从机器标注服务仓库同步 OpenAPI 契约快照。"""

from __future__ import annotations

import shutil
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root.parent / "biaozhu/tc-hawk-admin"
    target = root / "contracts/hawk_admin"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "openapi.yaml", target / "openapi.yaml")
    shutil.copy2(source / "api-tests/api_inventory.json", target / "api_inventory.json")
    print(f"已同步机器标注平台契约: {target}")


if __name__ == "__main__":
    main()
