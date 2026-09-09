"""从 GitLab 拉取平台 OpenAPI 契约到本地临时工作区。

支持两种来源：
1. 直接配置 ``*_OPENAPI_URL`` / ``*_INVENTORY_URL``；
2. 配置 GitLab API、项目、分支和仓库内文件路径，由脚本生成 raw 文件地址。

凭证只从环境变量读取，不写入 URL、日志或仓库。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

import yaml


DEFAULT_GITLAB_API = "https://gitlab.com/api/v4"
DEFAULT_REF = "main"
DEFAULT_OPENAPI_PATH = "openapi.yaml"
DEFAULT_INVENTORY_PATH = "api-tests/api_inventory.json"


def gitlab_file_url(api_url: str, project: str, path: str, ref: str) -> str:
    """生成 GitLab repository/files raw API 地址。"""
    project = _project_path(project)
    encoded_project = quote(project.strip("/"), safe="")
    encoded_path = quote(path.strip("/"), safe="")
    encoded_ref = quote(ref, safe="")
    return (
        f"{api_url.rstrip('/')}/projects/{encoded_project}/repository/files/"
        f"{encoded_path}/raw?ref={encoded_ref}"
    )


def _project_path(project: str) -> str:
    """接受 GitLab 项目 ID、namespace/path 或项目主页 URL。"""
    parsed = urlparse(project)
    if not parsed.scheme or not parsed.netloc:
        return project.strip("/")
    path = parsed.path.strip("/").split("/-/", 1)[0]
    if path.endswith(".git"):
        path = path[:-4]
    return unquote(path)


def _api_for_project(api_url: str, project: str) -> str:
    parsed = urlparse(project)
    if parsed.scheme and parsed.netloc and api_url == DEFAULT_GITLAB_API:
        return f"{parsed.scheme}://{parsed.netloc}/api/v4"
    return api_url


def _download(url: str, target: Path, token: str = "") -> None:
    headers = {"User-Agent": "ai-platform-api-tests-contract-fetcher"}
    if token:
        headers["PRIVATE-TOKEN"] = token
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read()
    except Exception as exc:  # pragma: no cover - depends on remote GitLab
        raise RuntimeError(f"契约下载失败: {url}: {exc}") from exc
    if not content:
        raise RuntimeError(f"契约下载为空: {url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.replace(target)


def _validate(target: Path, kind: str) -> None:
    try:
        if kind == "openapi":
            value = yaml.safe_load(target.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or not value.get("paths"):
                raise ValueError("OpenAPI 文档缺少非空 paths")
        else:
            value = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or not isinstance(value.get("operations"), list):
                raise ValueError("接口清单缺少 operations 数组")
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"下载的 {kind} 契约格式无效: {target}: {exc}") from exc


def fetch_contracts(
    *,
    platform: str,
    root: Path,
    openapi_url: str = "",
    inventory_url: str = "",
    gitlab_api: str = DEFAULT_GITLAB_API,
    gitlab_project: str = "",
    gitlab_ref: str = DEFAULT_REF,
    openapi_path: str = DEFAULT_OPENAPI_PATH,
    inventory_path: str = DEFAULT_INVENTORY_PATH,
    token: str = "",
    required: bool = False,
) -> bool:
    """拉取并校验契约；未配置来源且非 required 时返回 False。"""
    if not openapi_url and not inventory_url and gitlab_project:
        api_url = _api_for_project(gitlab_api, gitlab_project)
        openapi_url = gitlab_file_url(api_url, gitlab_project, openapi_path, gitlab_ref)
        inventory_url = gitlab_file_url(api_url, gitlab_project, inventory_path, gitlab_ref)
    if bool(openapi_url) != bool(inventory_url):
        raise ValueError("OpenAPI 和 api_inventory 必须同时配置")
    if not openapi_url:
        if required:
            raise ValueError("未配置远程契约来源，请设置 GitLab 项目或两个直接文件 URL")
        return False

    target = root / "contracts" / platform
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target) as staging_dir:
        staging = Path(staging_dir)
        openapi_staging = staging / "openapi.yaml"
        inventory_staging = staging / "api_inventory.json"
        _download(openapi_url, openapi_staging, token)
        _download(inventory_url, inventory_staging, token)
        _validate(openapi_staging, "openapi")
        _validate(inventory_staging, "inventory")
        openapi_staging.replace(target / "openapi.yaml")
        inventory_staging.replace(target / "api_inventory.json")
    print(f"已从远程拉取 {platform} 契约: {target}")
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 GitLab 拉取平台 OpenAPI 契约")
    parser.add_argument("--platform", default="hawk_admin")
    parser.add_argument("--required", action="store_true", help="未配置远程来源时失败")
    parser.add_argument("--openapi-url", default=os.getenv("HAWK_CONTRACT_OPENAPI_URL", ""))
    parser.add_argument("--inventory-url", default=os.getenv("HAWK_CONTRACT_INVENTORY_URL", ""))
    parser.add_argument("--gitlab-api", default=os.getenv("CONTRACT_GITLAB_API") or DEFAULT_GITLAB_API)
    parser.add_argument("--gitlab-project", default=os.getenv("CONTRACT_GITLAB_PROJECT", ""))
    parser.add_argument("--gitlab-ref", default=os.getenv("CONTRACT_GITLAB_REF") or DEFAULT_REF)
    parser.add_argument("--openapi-path", default=os.getenv("CONTRACT_OPENAPI_PATH") or DEFAULT_OPENAPI_PATH)
    parser.add_argument("--inventory-path", default=os.getenv("CONTRACT_INVENTORY_PATH") or DEFAULT_INVENTORY_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.getenv("CONTRACT_GITLAB_TOKEN", "")
    try:
        fetched = fetch_contracts(
            platform=args.platform,
            root=Path(__file__).resolve().parents[1],
            openapi_url=args.openapi_url,
            inventory_url=args.inventory_url,
            gitlab_api=args.gitlab_api,
            gitlab_project=args.gitlab_project,
            gitlab_ref=args.gitlab_ref,
            openapi_path=args.openapi_path,
            inventory_path=args.inventory_path,
            token=token,
            required=args.required,
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not fetched:
        print("未配置远程契约来源，保留仓库内契约快照")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
