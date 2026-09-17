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
from framework.requirements import validate_requirement_identifiers
from platforms.registry import discover_platforms, get_platform

ROOT = Path(__file__).resolve().parent
# 注意：不要在项目根目录建 allure/ 目录，会遮蔽 allure 包
CATEGORIES_FILE = ROOT / "config" / "allure" / "categories.json"

# test_<子项目短名>_<模块号>_<序号>_<动作>
CASE_NAME_PATTERN = re.compile(
    r"^test_(?P<project>[a-z][a-z0-9]*)_(?P<module>\d{2})_(?P<seq>\d{2})_(?P<slug>.+)$"
)

# 由各平台 definition 提供报告元数据；平台标识也从注册定义动态带入，
# 这样公共 fixture 不需要维护任何平台名称或编号映射。
PLATFORM_REPORTING: dict[str, dict[str, Any]] = {
    definition.short_name: {
        **definition.reporting,
        "_platform": definition.short_name,
        "_name": definition.name,
    }
    for definition in discover_platforms().values()
}


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("requirement", "需求级用例筛选")
    group.addoption(
        "--requirement-id",
        action="append",
        default=[],
        metavar="REQ-ID",
        help="只收集指定需求 ID 的用例；可重复传入或使用逗号分隔多个 ID",
    )


def pytest_configure(config: pytest.Config) -> None:
    """将平台自描述的 marker 注入 pytest strict-markers。"""
    for definition in discover_platforms().values():
        marker = definition.reporting.get("marker")
        if marker:
            config.addinivalue_line("markers", f"{marker}: {definition.name} 平台测试")


def _marker_value(marker: pytest.Mark | None, name: str, position: int = 0) -> str:
    if marker is None:
        return ""
    value = marker.kwargs.get(name)
    if not value and len(marker.args) > position:
        value = marker.args[position]
    return str(value or "").strip()


def _selected_requirement_ids(config: pytest.Config) -> set[str]:
    values = config.getoption("requirement_id") or []
    return {
        requirement_id.strip()
        for value in values
        for requirement_id in str(value).split(",")
        if requirement_id.strip()
    }


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """按稳定 requirement marker 精确筛选，不依赖测试文件或函数命名。"""
    selected = _selected_requirement_ids(config)
    if not selected:
        return
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        requirement_id = _marker_value(item.get_closest_marker("requirement"), "id")
        (kept if requirement_id in selected else deselected).append(item)
    if not kept:
        raise pytest.UsageError(
            f"未找到需求用例: {', '.join(sorted(selected))}；请检查 requirement marker 或 coverage.yaml"
        )
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = kept



@pytest.fixture(scope="session")
def settings() -> dict[str, Any]:
    return load_settings(ROOT, os.getenv("TEST_ENV", "test"))


@pytest.fixture(scope="session")
def central_token(settings: dict[str, Any]) -> str:
    token = os.getenv("API_TOKEN", "").strip()
    if token:
        return token
    auth = settings["auth"]
    credentials = settings["credentials"]
    if not credentials.get("username") or not credentials.get("password"):
        pytest.fail("未配置总平台账号密码，或设置 API_TOKEN；线上用例不能以跳过计为通过")
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
            pytest.fail(f"未配置平台 {name} 的 base_url；线上用例不能以跳过计为通过")
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

    def resolve(platform_name: str, state: str, env_name: str, *, required: bool = False) -> int:
        definition = get_platform(platform_name)
        if definition.state_resolver is None:
            message = f"平台 {platform_name} 未提供状态预置器"
            if required:
                raise AssertionError(message)
            pytest.skip(message)
        value = os.getenv(env_name, "")
        if value:
            return int(value)
        try:
            return definition.state_resolver(client_for(platform_name), scope, state)
        except Exception as exc:
            if "no healthy upstream" in str(exc).lower():
                message = (
                    f"平台 {platform_name} 的下游执行服务不可用（no healthy upstream），"
                    f"无法准备 {state} 状态批次；请恢复对应服务实例后重试"
                )
            else:
                message = f"自动构造 {state} 状态批次失败: {exc}；也可通过 {env_name} 指定"
            if required:
                raise AssertionError(message) from exc
            pytest.skip(message)

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


@pytest.fixture(scope="session")
def platform_context_factory(client_for):
    """按平台提供可复用的运行时数据上下文。

    平台定义自行声明上下文工厂；公共测试入口不维护需求或平台专属
    fixture 名称。没有上下文能力的平台仍可使用其它通用 fixture。
    """
    contexts: dict[str, Any] = {}

    def create(name: str):
        if name not in contexts:
            definition = get_platform(name)
            if definition.runtime_context_factory is None:
                pytest.fail(f"平台 {name} 未提供运行时数据上下文")
            contexts[name] = definition.runtime_context_factory(client_for(name))
        return contexts[name]

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
    return lambda state, env_name, *, required=False: platform_batch_state(
        platform_name, state, env_name, required=required
    )


@pytest.fixture
def platform_data_factory(data_factory_for, request: pytest.FixtureRequest):
    return data_factory_for(_platform_name_for_node(request.node))


@pytest.fixture
def platform_context(platform_context_factory, request: pytest.FixtureRequest):
    """当前平台的共享运行时上下文，供只读数据发现类用例使用。"""
    return platform_context_factory(_platform_name_for_node(request.node))


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


def _reporting_platform_id(node: pytest.Item, reporting: dict[str, Any]) -> str:
    value = reporting.get("_platform")
    if isinstance(value, str) and value.strip():
        return value.strip()
    marker_names = {marker.name for marker in node.iter_markers()}
    for short_name, metadata in PLATFORM_REPORTING.items():
        if metadata.get("marker") in marker_names:
            return short_name
    return "platform"


def _resolve_requirement(node: pytest.Item) -> dict[str, str]:
    """读取需求级 marker，用稳定需求 ID 覆盖旧的 TC 编号报告身份。"""
    requirement = node.get_closest_marker("requirement")
    case = node.get_closest_marker("case_id")
    if requirement is None or case is None:
        return {}

    requirement_id = _marker_value(requirement, "id")
    requirement_name = _marker_value(requirement, "name", 1)
    case_id = _marker_value(case, "id")
    case_title = _marker_value(case, "title", 1)
    values = {
        "requirement_id": str(requirement_id or "").strip(),
        "requirement_name": str(requirement_name or "").strip(),
        "case_id": str(case_id or "").strip(),
        "case_title": str(case_title or "").strip(),
    }
    if not values["requirement_id"] or not values["case_id"]:
        raise ValueError("requirement marker 必须包含 id，case_id marker 必须包含 id")
    validate_requirement_identifiers(values["requirement_id"], values["case_id"])
    return values


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, Any, Any]:
    yield
    # 两处时机约束：
    # 1. allure-pytest 在 setup 结束时才写入用例名，标题必须在此之后覆盖；
    # 2. session 级 fixture 未配置时会在函数级 fixture 之前 skip，
    #    因此标签不能放在 autouse fixture 里，否则跳过用例会丢失分组信息。
    # Tag 不需要处理，allure-pytest 会自动把 pytest marker 转成 tag。
    reporting, match = _resolve_reporting(item)
    requirement = _resolve_requirement(item)
    if requirement:
        title = requirement["case_title"] or item.name
        allure.dynamic.title(f"{requirement['case_id']} {title}")
        allure.dynamic.label("requirement", requirement["requirement_id"])
        if requirement["requirement_name"]:
            allure.dynamic.label("requirementName", requirement["requirement_name"])
            allure.dynamic.feature(requirement["requirement_name"])
        allure.dynamic.label("caseId", requirement["case_id"])
        allure.dynamic.label(
            "testId",
            f"{_reporting_platform_id(item, reporting)}/{requirement['case_id']}",
        )
        allure.dynamic.story(requirement["case_id"])
    elif match:
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
