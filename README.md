# AI 平台接口自动化测试

多平台接口自动化测试框架。根目录只维护跨平台能力；每个子平台负责自己的客户端、数据集、Schema、测试和平台说明。

## 架构边界

```text
tests/<platform> -> platforms/<platform> -> framework
tests            -> contracts/<platform>
```

- `framework/`：认证、HTTP、配置、断言、数据生命周期、报告和通用 fixture。
- `platforms/<platform>/`：平台客户端、数据工厂、状态预置器和平台注册声明。
- `data/<platform>/`：按平台隔离的可执行 YAML 数据集。
- `contracts/<platform>/`：OpenAPI 快照和接口清单。
- `test-cases/<platform>/`：手工用例、Schema 和追溯依据。
- `tests/<platform>/`：按业务板块组织的 pytest 用例及平台 README。

公共框架不得反向依赖具体平台。新增平台应集中修改自身目录，不通过不断增加平台分支来扩展 `framework/`。

## 目录

```text
framework/          通用认证、HTTP、配置、断言、数据和报告
platforms/          子平台适配器与注册定义
data/               子平台可执行测试数据
contracts/          子平台 OpenAPI 契约
test-cases/         子平台手工用例与 Schema
tests/              smoke、契约测试和各子平台业务测试
config/             非敏感环境配置；*.local.yaml 不提交
scripts/            测试执行、契约同步和报告工具
```

## 安装与运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .

# 离线契约门禁
pytest -m contract -v

# 跨平台登录冒烟
pytest -m "live and smoke" -v

# P0 线上回归
pytest -m "core and live" -v
```

线上测试需要总平台 `API_TOKEN`，或使用 `API_USER` / `API_PASSWORD` 现场登录。地址和凭证只通过环境变量或 `config/<env>.local.yaml` 注入：

| 变量 | 用途 |
| --- | --- |
| `TEST_ENV` | 环境配置名，默认 `test` |
| `AUTH_BASE_URL` | 总平台地址 |
| `PLATFORM_<平台名>_BASE_URL` | 子平台地址 |
| `API_TOKEN` | 已有总平台 Token |
| `API_USER` / `API_PASSWORD` | 总平台登录凭证 |
| `API_TIMEOUT` | HTTP 超时时间 |

配置优先级为：环境变量 > `config/<environment>.local.yaml` > `config/<environment>.yaml`。不得提交真实账号、密码或 Token。

## 测试分层

| 标记 | 目的 | 环境 |
| --- | --- | --- |
| `contract` | OpenAPI、接口清单、适配器和数据契约 | 离线 |
| `smoke` | 总平台登录及关键入口 | 线上 |
| `core` | P0 主链路回归 | 线上 |
| `live` | 访问实际测试环境 | 线上 |
| `<platform>` | 子平台隔离标记 | 取决于用例 |

推荐 CI 将 `contract` 与线上回归分开。仓库已提供 [`.github/workflows/api-tests.yml`](.github/workflows/api-tests.yml)：PR/主分支推送执行契约门禁，定时或手动触发执行线上回归。

GitLab 项目可使用 [`.gitlab-ci.yml`](.gitlab-ci.yml) 接入 Merge Request 门禁：contract 对所有 MR 执行，同项目受信任 MR 执行 `core_live`。请在 GitLab 受保护分支中将 `core_live` 对应的 pipeline status 设为 Required，并将测试地址和凭证配置为受保护 CI/CD Variables；外部 fork 不应直接执行带线上凭证的测试代码。

契约门禁支持在 CI 中从 GitLab 拉取最新 OpenAPI 和接口清单。平台契约来源由各子平台文档和 CI 配置声明，通用拉取器支持项目地址、分支、文件路径或直接 raw URL。私有项目使用 `CONTRACT_GITLAB_TOKEN`；未配置远程来源时，门禁使用仓库内快照。GitHub Actions 仅在配置仓库 Variables `CONTRACT_GITLAB_PROJECT`（或 Secrets `HAWK_CONTRACT_OPENAPI_URL` 与 `HAWK_CONTRACT_INVENTORY_URL`）时启用远程拉取，避免 PR 因未配置内部契约源而失败。

## 数据与清理

写入型测试必须通过平台数据工厂和 `DataScope` 造数，测试结束自动逆序清理。静态参数放在 `data/<platform>/*.yaml`，动态名称、服务端 ID、状态转换和清理逻辑放在平台适配器中。

数据集使用 `framework.data.dataset` 的 `dataset_defaults`、`dataset_cases`、`dataset_case_map` 加载，并通过 `case_payload` 转为请求字段。新增数据集必须保持平台目录隔离并提供稳定 case id。

## 报告

统一入口会生成 Allure 原始结果和 JUnit XML：

```bash
./scripts/run_tests.sh -m contract
./scripts/run_tests.sh -m "live and smoke"
./scripts/run_tests.sh -m contract --report
```

产物位于 `reports/`，已加入 `.gitignore`。`reports/history/` 默认保留最近 5 轮，可通过 `REPORT_KEEP` 调整。

## 新增子平台

1. 新增 `config` 中的平台地址和 `platforms/<platform>/definition.py`。
2. 在 `platforms/<platform>/` 实现客户端及可选的数据工厂、状态预置器。
3. 新增 `data/<platform>/`、`contracts/<platform>/` 和 `test-cases/<platform>/`。
4. 在 `tests/<platform>/` 按业务板块组织用例，并提供该目录的 README。
5. 使用通用 fixture（如 `platform_client`、`platform_data_factory`、`platform_state`），不得复制认证和 HTTP 实现。

平台注册由 `platforms/registry.py` 自动发现。用例函数使用 `test_<子平台短名>_<模块号>_<序号>_<动作>` 命名，Schema 与自动化覆盖矩阵由子平台自行维护。

## 子平台文档

各子平台的业务说明、契约来源和环境前置位于 `tests/<platform>/README.md`，新增平台时必须同步创建该文档。
