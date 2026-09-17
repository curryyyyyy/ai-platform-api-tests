# Hawk 机器标注平台测试

Hawk 子平台的接口测试、数据集、Schema 覆盖和 CI 前置均在本目录维护。根目录通用框架说明见 [`../../README.md`](../../README.md)。

## 测试板块

测试数据与 `data/hawk_admin/` 中的 YAML 同名对应；新增场景放入所属业务板块，不跨模块堆放。

| 板块 | 测试文件 | 数据集 | 覆盖范围 |
| --- | --- | --- | --- |
| 认证与权限 | `test_auth.py`、`test_project_api.py` | `auth.yaml`、`project.yaml` | Token、查看者写入/读取/更新越权 |
| 项目管理 | `test_project_api.py` | `project.yaml` | 创建、查询、列表、更新、OWNER、通知级别、删除 |
| 项目收藏需求 | `test_project_api.py` | `project.yaml` | 收藏/取消收藏幂等、详情 `isFavorite`、`onlyFavorite` 筛选 |
| 阶段管理 | `test_stage_api.py` | `stage.yaml` | 创建、列表筛选、更新、缺失查询、删除 |
| 流程生命周期（写入类） | `test_flow_api.py` | `flow.yaml` | 创建、非法 JSON、更新、删除 |
| 流程只读查询类 | `test_flow_read_api.py` | `flow.yaml` | 详情、缺失查询、Stage/状态筛选、调用次数排序、`canOffline` 条件 |
| 批次管理 | `test_batch_api.py` | `batch.yaml` | 创建、CID、引用校验、名称、列表、元数据/输入/状态更新、删除 |
| 执行与统计 | `test_hawk_execution_api.py` | `execution.yaml` | 状态操作、任务流、统计、字段、错误日志、导出 |
| 批次辅助能力 | `test_batch_api.py` | `batch.yaml` | 流程图、复制、统计批次、文件上传负向校验 |
| 执行辅助能力 | `test_hawk_execution_api.py` | `execution.yaml` | 系统负载、任务流刷新、结束告警、隐藏任务流批次 |
| 模板工作流 | `test_template_workflow_api.py` | `template_workflow.yaml` | 模板列表、批量查询、空工作流和补全校验 |
| 凭证管理 | `test_credential_api.py` | `credential.yaml` | 查询及非法创建、更新、删除 |
| 工具与文件 | `test_tools_file_api.py` | - | 临时文件、下载链接、CSV/HBase 运维工具 |
| 传输任务 | `test_transfer_task_api.py` | `transfer_task.yaml` | 公共模板、任务列表/详情、非法操作和配置更新 |
| 用户认证 | `test_auth.py` | `auth.yaml` | RSA、公钥认证、空凭证登录、无效 Token 退出 |
| 需求级用例 | 对应业务域模块 | `coverage.yaml` 的 `requirements` 节 | 通过稳定 `requirement`、`case_id` 标识跨模块筛选与追溯 |
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

契约快照和覆盖映射由 [`../../platforms/hawk_admin/contract.yaml`](../../platforms/hawk_admin/contract.yaml) 与 [`operation_coverage.yaml`](operation_coverage.yaml) 维护。日常测试固定使用已提交的 `../../contracts/hawk_admin/openapi.yaml` 和 inventory。更新契约时，维护者先在服务代码仓库拉取目标分支到本地，再将审核后的文档复制到快照目录。

日常执行仓库快照测试：

```bash
./platforms/hawk_admin/test.sh -m "live and hawk_admin"
```

需要更新契约时，先在服务代码仓库拉取 `test` 分支最新代码，再审核 `openapi.yaml` 与本仓库差异，并从本地工作树更新快照。随后同步更新 client、数据、testcase、inventory 和覆盖矩阵，先跑受影响用例，再跑本平台全量并提交。

契约 job 会将 MR 目标分支的 Hawk 契约保存为基线，并通过 [`../../scripts/contract_diff.py`](../../scripts/contract_diff.py) 检查删除接口、必填参数、请求/响应 Schema、枚举和共享组件等破坏性变化。报告保存于 `reports/contracts/hawk_admin-diff.json`；默认发现破坏性变化即阻断合并。确认是有意变更时，必须同步 `client.py`、数据 YAML、测试 Schema、断言和本文件，并由维护者通过受保护变量 `CONTRACT_DIFF_ALLOW_BREAKING=1` 临时放行。

## 本地运行

```bash
# Hawk 离线契约与适配器
pytest tests/hawk_admin -m contract -v

# Hawk 全量线上用例
pytest tests/hawk_admin -m "live and hawk_admin" -v

# 精确运行一个需求，即使其用例分布在多个业务模块中
pytest tests/hawk_admin -m "requirement and live" \
  --requirement-id REQ-TEMPLATE-WORKFLOW-LIFECYCLE -v

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
- `TC-07-15` 的 `POST /api/v1/tools/csv_info` 属于测试分支 OpenAPI 契约；若线上返回纯文本 `404 page not found`，说明部署实例未注册该路由或版本落后于契约，应先发布/核对服务版本，不能放宽负向断言。
- 流程创建接口若返回“数据库操作失败”，创建场景必须失败并要求排查服务端持久化层；批次场景继续复用已有流程。

## 需求级接入与持续集成

资源成本看板使用独立需求 ID `REQ-RCB-20260910`，来源 case `TC-04-01` 至 `TC-04-05` 映射见 [`coverage.yaml`](coverage.yaml) 的 `requirements` 节。需求 ID 和 case ID 在所有运行中保持不变；执行时间只作为 `reports/history/<run_id>/` 的报告目录名，不进入 Allure 用例身份。
用例函数保留平台命名约定（`test_hawk_10_01` 至 `test_hawk_10_05`），按接口所属业务模块放入既有测试文件；报告身份由每条用例的 `requirement` 和 `case_id` marker 覆盖，因此 Allure 标题、`testId`、`requirement` 标签都带有稳定需求 ID，不会与既有 Hawk 的 `TC-04-*` 混淆。
`source_id` 只表示原始人工用例的追溯关系，不是被测接口的响应断言；它由离线覆盖契约一次性校验 Schema 和平台覆盖矩阵，在线函数不重复断言。当前 5 条仅覆盖成功响应结构、关键标识和可解析非负金额，非法资源、权限、空数据以及金额跨接口一致性仍需后续补充。

成本看板不提交共享环境的固定项目、批次或阶段 ID。默认情况下，既有项目/执行模块中的用例通过通用 `platform_context` fixture 自动发现当前账号可访问的项目和批次：项目会先经过成本接口权限校验，批次统计会排除 Hawk RPC 降级数据，批次成本详情和阶段成本详情分别验证访问权限，`10_05` 再探测实际可用的 `stageIndex`。平台运行时上下文由 `platforms/hawk_admin/runtime.py` 注册提供，不再为单个需求增加 `tests/hawk_admin/conftest.py`。阶段成本明细不存在时只阻塞 `10_05`，不会连带影响批次统计用例；批次成本详情越权也不会被误报为接口断言失败。因此日常 CI 不需要人工逐项准备 `RCB_*` 变量。

如需复现指定环境资源，仍可通过 `RCB_PROJECT_ID`、`RCB_BATCH_IDS`（逗号分隔）、`RCB_DETAIL_BATCH_ID`、`RCB_STAGE_INDEX`、`RCB_EXPECTED_STAGE_IDS`（逗号分隔）覆盖自动发现结果。只有在环境没有任何可访问且统计链路正常的批次，或下游没有阶段成本数据时才会阻塞，并明确报告环境前置不足。
CI 的需求回归 job 统一筛选 `requirement and live`，在受信任 MR、Web 或定时流水线中执行，并将需求报告作为流水线产物。
