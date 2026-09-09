# Hawk 机器标注平台测试

Hawk 子平台的接口测试、数据集、Schema 覆盖和 CI 前置均在本目录维护。根目录通用框架说明见 [`../../README.md`](../../README.md)。

## 测试板块

测试数据与 `data/hawk_admin/` 中的 YAML 同名对应；新增场景放入所属业务板块，不跨模块堆放。

| 板块 | 测试文件 | 数据集 | 覆盖范围 |
| --- | --- | --- | --- |
| 认证与权限 | `test_auth.py`、`test_project_api.py` | `auth.yaml`、`project.yaml` | Token、查看者写入/读取/更新越权 |
| 项目管理 | `test_project_api.py` | `project.yaml` | 创建、查询、列表、更新、OWNER、通知级别、删除 |
| 阶段管理 | `test_stage_api.py` | `stage.yaml` | 创建、列表筛选、更新、缺失查询、删除 |
| 流程生命周期（写入类） | `test_flow_api.py` | `flow.yaml` | 创建、非法 JSON、更新、删除 |
| 流程只读查询类 | `test_flow_read_api.py` | `flow.yaml` | 详情、缺失查询、Stage/状态筛选、调用次数排序、`canOffline` 条件 |
| 批次管理 | `test_batch_api.py` | `batch.yaml` | 创建、CID、引用校验、名称、列表、元数据/输入/状态更新、删除 |
| 执行与统计 | `test_hawk_execution_api.py` | `execution.yaml` | 状态操作、任务流、统计、字段、错误日志、导出 |
| Hawk 辅助接口 | `test_hawk_extended_api.py` | `extended.yaml` | 统计辅助、文件/工具、凭证、模板、系统负载、结束告警 |
| 传输任务 | `test_hawk_extended_api.py` | `extended.yaml` | 任务列表/详情、非法操作和配置更新 |
| 用户认证 | `test_auth.py`、`test_hawk_extended_api.py` | `auth.yaml`、`extended.yaml` | RSA、公钥认证、空凭证登录、无效 Token 退出 |
| 适配器契约 | `test_*_contract.py` | - | 客户端、工厂、状态预置、注册和数据加载 |

## 覆盖矩阵

[`coverage.yaml`](coverage.yaml) 登记 Schema 中全部 61 条 case 的自动化入口、覆盖级别和环境依赖。
`test_coverage_contract.py` 在离线契约阶段校验 Schema 与矩阵的编号一致，新增或删除 case 时必须同步更新矩阵。

手工用例和 Schema 位于 [`../../test-cases/hawk_admin/`](../../test-cases/hawk_admin/)，OpenAPI 契约位于 [`../../contracts/hawk_admin/`](../../contracts/hawk_admin/)。

## 逐层查看 Case URL

不要直接从测试文件名猜 URL。当前调用链是：

```text
Schema case
  -> coverage.yaml 自动化映射
  -> tests/hawk_admin 测试函数
  -> platforms/hawk_admin/client.py 客户端方法
  -> framework/http/client.py URL 拼接、Token、超时和重试
  -> contracts/hawk_admin/openapi.yaml 路径、参数和响应契约
```

以 `TC-05-01` 为例，按以下顺序阅读：

```bash
# 1. 看业务目标、前置条件和期望
rg -n -A14 -B2 'id: TC-05-01' test-cases/hawk_admin/机器标注平台_测试用例.schema.yaml

# 2. 看它对应哪些自动化函数（不要假设函数编号一定相同）
rg -n -A1 -B1 'id: TC-05-01' tests/hawk_admin/coverage.yaml

# 3. 看测试如何造数、调用哪些客户端方法
rg -n -A18 'def test_hawk_05_01' tests/hawk_admin/test_batch_api.py
rg -n 'create_project|list_flows|create_batch|get_batch' platforms/hawk_admin/client.py platforms/hawk_admin/factories.py

# 4. 看客户端方法对应的 HTTP method 和相对路径
rg -n -A3 -B1 'def (create_project|list_flows|create_batch|get_batch)' platforms/hawk_admin/client.py

# 5. 在 OpenAPI 中核对同一路径的参数、请求体和响应
rg -n -A24 -B2 '/api/v1/(project|flow|batch)' contracts/hawk_admin/openapi.yaml
```

`TC-05-01` 实际不是一个请求，而是：创建临时项目 `POST /api/v1/project`、查询或选择流程 `GET /api/v1/flow`、创建批次 `POST /api/v1/batch`、回查批次 `GET /api/v1/batch/{id}`。项目和批次由 `HawkDataFactory` 创建并由 `DataScope` 清理，流程目前只读复用环境已有数据。

完整 URL 的拼接规则在 [`framework/http/client.py`](../../framework/http/client.py) 第 37 行附近：

```text
config/test.yaml 的 base_url
  https://test-hawk-admin.tucdev.com/api/v1
+ client.py 的相对路径
  /api/v1/batch
= 实际请求
  https://test-hawk-admin.tucdev.com/api/v1/batch
```

`ApiClient` 会在 base URL 已经以 `/api/v1` 结尾时，自动去掉客户端路径中重复的 `/api/v1`，避免拼成 `/api/v1/api/v1/...`。运行时地址可由 `PLATFORM_HAWK_ADMIN_BASE_URL` 或兼容变量 `HAWK_ADMIN_BASE_URL` 覆盖。

常用 URL 对照：

| 业务域 | 客户端方法 | HTTP 路径 |
| --- | --- | --- |
| 项目 | `list_projects`、`create_project` | `/api/v1/project` |
| 项目详情 | `get_project`、`update_project`、`delete_project` | `/api/v1/project/{id}` |
| 阶段 | `list_stages`、`create_stage` | `/api/v1/stage` |
| 流程 | `list_flows`、`create_flow` | `/api/v1/flow` |
| 流程详情 | `get_flow`、`update_flow`、`delete_flow` | `/api/v1/flow/{id}` |
| 批次 | `list_batches`、`create_batch` | `/api/v1/batch` |
| 批次详情 | `get_batch`、`update_batch`、`delete_batch` | `/api/v1/batch/{id}` |
| 批次执行 | `operate_batch` | `/api/v1/hawk/operate` |
| 批次统计 | `batch_stat`、`batch_stats` | `/api/v1/hawk/stat/{batchId}`、`/api/v1/hawk/stats` |
| 任务流 | `task_stream` | `/api/v1/hawk/task-stream` |
| 输出与字段 | `export_output`、`key_fields`、`output_fields` | `/api/v1/hawk/output`、`/api/v1/hawk/key-fields/{batchId}`、`/api/v1/hawk/output-fields/{batchId}` |

其他辅助接口按相同方法查看：先在测试中找到客户端方法，再回到 `client.py` 查路径，最后在 OpenAPI 中查 `operationId`、参数和响应。状态操作还要额外阅读 `presets.py`，因为它会先调用列表、创建、操作和状态查询接口来准备前置批次。

契约门禁当前从 `https://gitlab.ituchong.com/ai-dataset/tc-hawk-admin` 的 `master` 分支线上拉取 `openapi.yaml` 和 `api-tests/api_inventory.json`。私有项目使用 CI Secret `CONTRACT_GITLAB_TOKEN`；其他平台或分支可覆盖 `CONTRACT_GITLAB_PROJECT`、`CONTRACT_GITLAB_REF`、`CONTRACT_OPENAPI_PATH`、`CONTRACT_INVENTORY_PATH`。如果更适合直接使用 raw 地址，则配置 `HAWK_CONTRACT_OPENAPI_URL` 和 `HAWK_CONTRACT_INVENTORY_URL`。实现脚本为 [`../../scripts/fetch_contracts.py`](../../scripts/fetch_contracts.py)。

## 本地运行

```bash
# Hawk 离线契约与适配器
pytest tests/hawk_admin -m contract -v

# Hawk 全量线上用例
pytest tests/hawk_admin -m "live and hawk_admin" -v

# P0 主链路
CORE_EXPECTED_TESTS=10 ./scripts/run_tests.sh --no-skips -m "core and live"
```

## 数据隔离与状态造数

写入型场景统一使用 `HawkDataFactory` 和 `DataScope`，每条用例生成唯一名称并在结束时逆序清理。`init`、`running`、`stopped` 状态默认按用例现场创建独立批次；状态预置会轮询确认异步状态落库，并对节点锁冲突做有限重试。

状态变量优先级为：环境变量指定批次 > 现场独立造数 > 明确跳过。可造数状态包括 `init`、`running`、`stopped`；流程创建接口不可用时，批次造数只读复用环境中的流程，可用 `HAWK_PRESET_FLOW_NAME` 和 `HAWK_PRESET_INPUT_PATH` 覆盖。

可通过 `HAWK_STATE_TIMEOUT`（默认 15 秒）和 `HAWK_STATE_POLL_INTERVAL`（默认 0.5 秒）调整状态等待。

## CI 环境前置

以下场景无法仅靠普通接口稳定构造，扩展 CI job 会在执行前强制检查对应变量：

| 变量 | 用途 | 关联场景 |
| --- | --- | --- |
| `HAWK_FAILED_BATCH_ID` | 可重试的失败批次 | `TC-06-04` |
| `HAWK_EXPORT_RUNNING_BATCH_ID` | 已有任务运行且可导出的批次 | `TC-06-11` |
| `HAWK_END_RUNNING_BATCH_ID` | 存在可结束任务的处理中批次 | `TC-06-05` |
| `HAWK_ERROR_LOG_BATCH_ID` | 错误 CSV 超过 100 行的批次 | `TC-06-10` |

权限场景可配置：

| 变量 | 用途 |
| --- | --- |
| `HAWK_VIEWER_TOKEN` | 查看者 Token |
| `HAWK_VIEWER_USER` / `HAWK_VIEWER_PASSWORD` | 查看者账号登录 |
| `HAWK_VIEWER_PROJECT_ID` | 查看者无权限项目 |
| `HAWK_FLOW_ID` | 只读 Flow 详情用例指定的已有流程编号；未配置时从列表读取首条已有流程 |

状态相关用例使用独立批次，不能在多个测试间共享同一个会改变状态的批次。Core 门禁额外要求不能出现 skipped，并固定校验当前 10 条收集结果；扩展 CI 配置位于 [`../../.github/workflows/api-tests.yml`](../../.github/workflows/api-tests.yml) 的 `core` job。

GitLab Merge Request 门禁位于根目录 [`.gitlab-ci.yml`](../../.gitlab-ci.yml)：所有 MR 执行 contract；同项目受信任 MR 额外执行 `core_live`，并将该 job 配置为受保护分支的 Required pipeline status。外部 fork MR 不注入线上凭证，需由维护者在受信任流水线中手动触发 core。

## 已知环境限制

- `failed`、`running_with_tasks`、`running_end` 依赖真实执行任务或失败产物，未配置前置时会跳过。
- 网关返回 `no healthy upstream` 表示 `tc-hawk` 下游没有健康实例，属于环境阻塞，不应归因于测试代码。
- `TC-07-15` 的 `GET /api/v1/tools/tos_file_ext` 属于当前 OpenAPI 契约；若线上返回纯文本 `404 page not found`，说明部署实例未注册该路由或版本落后于契约，应先发布/核对服务版本，不能放宽负向断言。
- 流程创建接口若返回“数据库操作失败”，创建场景必须失败并要求排查服务端持久化层；批次场景继续复用已有流程。
