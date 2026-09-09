"""从机器标注服务仓库同步 OpenAPI 契约快照。"""

from __future__ import annotations

import shutil
import os
from pathlib import Path

from fetch_contracts import fetch_contracts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    if (
        os.getenv("CONTRACT_GITLAB_PROJECT")
        or os.getenv("HAWK_CONTRACT_OPENAPI_URL")
        or os.getenv("HAWK_CONTRACT_INVENTORY_URL")
    ):
        fetch_contracts(
            platform="hawk_admin",
            root=root,
            openapi_url=os.getenv("HAWK_CONTRACT_OPENAPI_URL", ""),
            inventory_url=os.getenv("HAWK_CONTRACT_INVENTORY_URL", ""),
            gitlab_api=os.getenv("CONTRACT_GITLAB_API") or "https://gitlab.com/api/v4",
            gitlab_project=os.getenv("CONTRACT_GITLAB_PROJECT", ""),
            gitlab_ref=os.getenv("CONTRACT_GITLAB_REF") or "main",
            openapi_path=os.getenv("CONTRACT_OPENAPI_PATH") or "openapi.yaml",
            inventory_path=os.getenv("CONTRACT_INVENTORY_PATH") or "api-tests/api_inventory.json",
            token=os.getenv("CONTRACT_GITLAB_TOKEN", ""),
            required=True,
        )
        return
    source = root.parent / "biaozhu/tc-hawk-admin"
    target = root / "contracts/hawk_admin"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "openapi.yaml", target / "openapi.yaml")
    shutil.copy2(source / "api-tests/api_inventory.json", target / "api_inventory.json")
    print(f"已同步机器标注平台契约: {target}")


if __name__ == "__main__":
    main()
