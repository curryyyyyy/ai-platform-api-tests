# Hawk 机器标注平台测试

Hawk 子平台的接口测试、数据集、Schema 覆盖和 CI 前置均在本目录维护。根目录通用框架说明见 [`../../README.md`](../../README.md)。

## 测试板块

测试数据与 `data/hawk_admin/` 中的 YAML 同名对应；新增场景放入所属业务板块，不跨模块堆放。

| 板块 | 测试文件 | 数据集 | 覆盖范围 |
| --- | --- | --- | --- |
| 认证与权限 | `test_auth.py`、`test_project_api.py` | `auth.yaml`、`project.yaml` | Token、查看者写入/读取/更新越权 |
| 项目管理 | `test_project_api.py` | `project.yaml` | 创建、查询、列表、更新、OWNER、通知级别、删除 |
| 阶段管理 | `test_stage_api.py` | `stage.yaml` | 创建、列表筛选、更新、缺失查询、删除 |
| 流程管理 | `test_flow_api.py` | `flow.yaml` | 创建、非法 JSON、列表、更新、删除、缺失查询 |
| 批次管理 | `test_batch_api.py` | `batch.yaml` | 创建、CID、引用校验、名称、列表、输入/状态更新、删除 |
| 执行与统计 | `test_hawk_execution_api.py` | `execution.yaml` | 状态操作、任务流、统计、字段、错误日志、导出 |
| 适配器契约 | `test_*_contract.py` | - | 客户端、工厂、状态预置、注册和数据加载 |

## 覆盖矩阵

[`coverage.yaml`](coverage.yaml) 登记 Schema 中全部 46 条 case 的自动化入口、覆盖级别和环境依赖。
`test_coverage_contract.py` 在离线契约阶段校验 Schema 与矩阵的编号一致，新增或删除 case 时必须同步更新矩阵。

手工用例和 Schema 位于 [`../../test-cases/hawk_admin/`](../../test-cases/hawk_admin/)，OpenAPI 契约位于 [`../../contracts/hawk_admin/`](../../contracts/hawk_admin/)。

## 本地运行

```bash
# Hawk 离线契约与适配器
pytest tests/hawk_admin -m contract -v

# Hawk 全量线上用例
pytest tests/hawk_admin -m "live and hawk_admin" -v

# P0 主链路
pytest tests/hawk_admin -m "core and live" -v
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

状态相关用例使用独立批次，不能在多个测试间共享同一个会改变状态的批次。扩展 CI 配置位于 [`../../.github/workflows/api-tests.yml`](../../.github/workflows/api-tests.yml) 的 `hawk-stateful` job。

## 已知环境限制

- `failed`、`running_with_tasks`、`running_end` 依赖真实执行任务或失败产物，未配置前置时会跳过。
- 网关返回 `no healthy upstream` 表示 `tc-hawk` 下游没有健康实例，属于环境阻塞，不应归因于测试代码。
- 流程创建接口若返回“数据库操作失败”，说明服务端 flow schema 不可用；相关创建场景会明确跳过，批次场景继续复用已有流程。
