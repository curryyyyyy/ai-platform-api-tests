from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Generator

import allure
import pytest

from framework.auth.central_sso import CentralSSO
from framework.data.scope import DataScope
from framework.settings import load_settings
from platforms.registry import discover_platforms, get_platform

ROOT = Path(__file__).resolve().parent
# 注意：不要在项目根目录建 allure/ 目录，会遮蔽 allure 包
CATEGORIES_FILE = ROOT / "config" / "allure" / "categories.json"

# test_<子项目短名>_<模块号>_<序号>_<动作>
CASE_NAME_PATTERN = re.compile(
    r"^test_(?P<project>[a-z][a-z0-9]*)_(?P<module>\d{2})_(?P<seq>\d{2})_(?P<slug>.+)$"
)

# 由各平台 definition 提供报告元数据；保留该名称供外部插件兼容读取。
PLATFORM_REPORTING: dict[str, dict[str, Any]] = {
    definition.short_name: definition.reporting for definition in discover_platforms().values()
}


def pytest_configure(config: pytest.Config) -> None:
    """将平台自描述的 marker 注入 pytest strict-markers。"""
    for definition in discover_platforms().values():
        marker = definition.reporting.get("marker")
        if marker:
            config.addinivalue_line("markers", f"{marker}: {definition.name} 平台测试")



@pytest.fixture(scope="session")
def settings() -> dict[str, Any]:
    return load_settings(ROOT, os.getenv("TEST_ENV", "test"))


@pytest.fixture(scope="session")
def central_token(settings: dict[str, Any]) -> str:
    token = os.getenv("API_TOKEN", "")
    if token:
        return token
    auth = settings["auth"]
    credentials = settings["credentials"]
    if not credentials.get("username") or not credentials.get("password"):
        pytest.skip("未配置总平台账号密码，或设置 API_TOKEN")
    return CentralSSO(
        auth["base_url"],
        auth["rsa_path"],
        auth["login_path"],
        timeout=float(os.getenv("API_TIMEOUT", "10")),
    ).login(credentials["username"], credentials["password"])


@pytest.fixture(scope="session")
def platform_client_factory(settings: dict[str, Any]):
    """返回按平台名称构造客户端的统一入口。"""
    timeout = float(os.getenv("API_TIMEOUT", "10"))

    def create(name: str, *, token: str = ""):
        definition = get_platform(name)
        config = settings.get("platforms", {}).get(name) or {}
        base_url = config.get("base_url", "")
        if not base_url:
            pytest.skip(f"未配置平台 {name} 的 base_url")
        return definition.client_factory(base_url, token, timeout)

    return create


@pytest.fixture(scope="session")
def client_for(platform_client_factory, central_token: str):
    def create(name: str):
        return platform_client_factory(name, token=central_token)

    return create


@pytest.fixture(scope="session")
def anonymous_for(platform_client_factory):
    return platform_client_factory


@pytest.fixture(scope="session")
def viewer_for(settings: dict[str, Any], platform_client_factory):
    def create(name: str):
        definition = get_platform(name)
        token = os.getenv(definition.viewer_token_env or "", "")
        if not token:
            config = settings.get("platforms", {}).get(name) or {}
            credentials = config.get("viewer_credentials") or settings.get("viewer_credentials") or {}
            username = os.getenv(definition.viewer_user_env or "", "") or credentials.get("username", "")
            password = os.getenv(definition.viewer_password_env or "", "") or credentials.get("password", "")
            if not username or not password:
                pytest.skip(f"未配置平台 {name} 的查看者 Token 或账号密码，跳过查看者权限用例")
            auth = settings["auth"]
            token = CentralSSO(
                auth["base_url"], auth["rsa_path"], auth["login_path"],
                timeout=float(os.getenv("API_TIMEOUT", "10")),
            ).login(username, password)
        return platform_client_factory(name, token=token)

    return create


@pytest.fixture
def platform_batch_state(
    client_for, request: pytest.FixtureRequest
) -> Callable[[str, str, str], int]:
    """解析状态机用例需要的批次编号。

    优先级：环境变量显式指定 > 为每个用例现场造数 > 跳过。
    每个用例使用独立批次：状态机会改变批次状态，复用同一个批次会让用例互相干扰
    （例如前一条用例 PAUSE 之后，后续用例拿到的已不是运行态）。
    """
    scope = DataScope(request.node.nodeid)
    request.addfinalizer(scope.cleanup)

    def resolve(platform_name: str, state: str, env_name: str) -> int:
        definition = get_platform(platform_name)
        if definition.state_resolver is None:
            pytest.skip(f"平台 {platform_name} 未提供状态预置器")
        value = os.getenv(env_name, "")
        if value:
            return int(value)
        try:
            return definition.state_resolver(client_for(platform_name), scope, state)
        except Exception as exc:  # 造数失败不应阻断其余用例
            if "no healthy upstream" in str(exc).lower():
                pytest.skip(
                    f"平台 {platform_name} 的下游执行服务不可用（no healthy upstream），"
                    f"无法准备 {state} 状态批次；请恢复 tc-hawk 健康实例后重试"
                )
            pytest.skip(f"自动构造 {state} 状态批次失败: {exc}；也可通过 {env_name} 指定")

    return resolve


@pytest.fixture
def data_scope(request: pytest.FixtureRequest) -> DataScope:
    scope = DataScope(request.node.nodeid)
    request.addfinalizer(scope.cleanup)
    return scope


@pytest.fixture
def data_factory_for(client_for, data_scope: DataScope):
    def create(name: str):
        definition = get_platform(name)
        if definition.data_factory_factory is None:
            pytest.skip(f"平台 {name} 未提供数据工厂")
        return definition.data_factory_factory(client_for(name), data_scope)

    return create


def _platform_name_for_node(node: pytest.Item) -> str:
    marker_names = {marker.name for marker in node.iter_markers()}
    for definition in discover_platforms().values():
        if definition.reporting.get("marker") in marker_names:
            return definition.name
    raise LookupError("测试未声明平台 marker，无法推断当前平台")


@pytest.fixture
def platform_client(client_for, request: pytest.FixtureRequest):
    return client_for(_platform_name_for_node(request.node))


@pytest.fixture
def anonymous_platform_client(platform_client_factory, request: pytest.FixtureRequest):
    return platform_client_factory(_platform_name_for_node(request.node), token="")


@pytest.fixture
def viewer_platform_client(viewer_for, request: pytest.FixtureRequest):
    return viewer_for(_platform_name_for_node(request.node))


@pytest.fixture
def platform_state(platform_batch_state, request: pytest.FixtureRequest) -> Callable[[str, str], int]:
    platform_name = _platform_name_for_node(request.node)
    return lambda state, env_name: platform_batch_state(platform_name, state, env_name)


@pytest.fixture
def platform_data_factory(data_factory_for, request: pytest.FixtureRequest):
    return data_factory_for(_platform_name_for_node(request.node))


def _allure_dir(config: pytest.Config) -> Path | None:
    try:
        value = config.getoption("--alluredir", default=None)
    except ValueError:  # 未安装 allure-pytest 时不生成报告元数据
        return None
    return Path(value) if value else None


def _resolve_reporting(node: pytest.Item) -> tuple[dict[str, Any], re.Match[str] | None]:
    """按函数名推断子项目，再回退到平台 marker。"""
    name = getattr(node, "originalname", None) or node.name
    match = CASE_NAME_PATTERN.match(name)
    if match:
        return PLATFORM_REPORTING.get(match.group("project"), {}), match
    marker_names = {marker.name for marker in node.iter_markers()}
    for reporting in PLATFORM_REPORTING.values():
        if reporting.get("marker") in marker_names:
            return reporting, None
    return {}, None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, Any, Any]:
    yield
    # 两处时机约束：
    # 1. allure-pytest 在 setup 结束时才写入用例名，标题必须在此之后覆盖；
    # 2. session 级 fixture 未配置时会在函数级 fixture 之前 skip，
    #    因此标签不能放在 autouse fixture 里，否则跳过用例会丢失分组信息。
    # Tag 不需要处理，allure-pytest 会自动把 pytest marker 转成 tag。
    reporting, match = _resolve_reporting(item)
    if match:
        case_id = f"TC-{match.group('module')}-{match.group('seq')}"
        allure.dynamic.title(f"{case_id} {match.group('slug').replace('_', ' ')}")
        allure.dynamic.label("testId", f"{match.group('project')}/{case_id}")
        allure.dynamic.story(case_id)
        modules = reporting.get("modules", {})
        allure.dynamic.feature(modules.get(match.group("module"), f"模块 {match.group('module')}"))
    if reporting.get("epic"):
        allure.dynamic.epic(reporting["epic"])


@pytest.fixture(scope="session", autouse=True)
def report_metadata(request: pytest.FixtureRequest) -> None:
    """写入环境信息和失败分类。

    使用会话级 fixture 而非 pytest_configure，确保发生在 --clean-alluredir 之后，
    否则这两个文件会被清空。
    """
    allure_dir = _allure_dir(request.config)
    if allure_dir is None:
        return
    allure_dir.mkdir(parents=True, exist_ok=True)
    _write_environment_properties(allure_dir)
    if CATEGORIES_FILE.is_file():
        (allure_dir / "categories.json").write_text(
            CATEGORIES_FILE.read_text(encoding="utf-8"), encoding="utf-8"
        )


def _write_environment_properties(allure_dir: Path) -> None:
    env = os.getenv("TEST_ENV", "test")
    lines = [
        f"环境={env}",
        f"Python={sys.version.split()[0]}",
        f"pytest={pytest.__version__}",
    ]
    try:  # 环境信息只用于展示，读取失败不影响执行
        settings = load_settings(ROOT, env)
        lines.append(f"总平台={settings['auth']['base_url']}")
        for name, platform in settings.get("platforms", {}).items():
            lines.append(f"平台.{name}={platform['base_url']}")
    except Exception:
        pass
    (allure_dir / "environment.properties").write_text("\n".join(lines) + "\n", encoding="utf-8")
