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
- 需求级接口包：测试函数归入已有业务模块，需求 ID、case 和接口映射统一登记到所属平台的覆盖矩阵，支持单需求筛选与独立 CI 门禁。

公共框架不得反向依赖具体平台。新增平台应集中修改自身目录，不通过不断增加平台分支来扩展 `framework/`。

## 目录

```text
framework/          通用认证、HTTP、配置、断言、数据和报告
platforms/          子平台适配器与注册定义
data/               子平台可执行测试数据
contracts/          子平台 OpenAPI 契约
test-cases/         子平台手工用例与 Schema
tests/              smoke、契约测试和各子平台业务测试
config/             总平台非敏感配置；*.local.yaml 不提交
scripts/            测试执行、契约 diff 和报告工具
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

线上测试需要总平台 `API_TOKEN`，或使用 `API_USER` / `API_PASSWORD` 现场登录。总平台地址和凭证只通过环境变量或 `config/<env>.local.yaml` 注入；子平台地址由各自 `platforms/<platform>/config/<env>.yaml` 管理，也可统一由 CI JSON Secret 注入：

| 变量 | 用途 |
| --- | --- |
| `TEST_ENV` | 环境配置名，默认 `test` |
| `AUTH_BASE_URL` | 总平台地址 |
| `PLATFORM_<平台名>_BASE_URL` | 子平台地址 |
| `PLATFORM_BASE_URLS_JSON` | CI 批量注入子平台地址的 JSON 对象 |
| `API_TOKEN` | 已有总平台 Token |
| `API_USER` / `API_PASSWORD` | 总平台登录凭证 |
| `API_TIMEOUT` | HTTP 超时时间 |
| `API_CONNECT_TIMEOUT` / `API_READ_TIMEOUT` | 可选：分别覆盖 HTTP 连接和读取超时；未设置时使用 `API_TIMEOUT` |
| `FEISHU_WEBHOOK_URL` | GitLab 定时流水线的飞书机器人 Webhook，仅配置在 CI/CD Secret |
| `CONTRACT_BASE_SHA` | 契约变更检测使用的 Git 基线；PR/MR 和主分支推送由 CI 自动注入 |
| `CONTRACT_DIFF_ALLOW_BREAKING` | 经维护者确认后临时放行契约破坏性变更，仅限受保护 CI 变量 |

配置优先级为：环境变量 > 平台/根目录 `*.local.yaml` > 平台/根目录 `*.yaml`。不得提交真实账号、密码或 Token。

HTTP 客户端按平台和 Token 在一次 pytest 会话内复用连接池，并在会话结束时关闭；探测类请求可通过客户端的 `_retry=False` 选项禁用重试但仍复用连接。普通请求默认只对 GET/HEAD 的网关瞬态错误重试，业务写入重试由平台客户端显式控制。

线上用例可使用通用 `openapi_contracts` fixture，按 HTTP method、契约路径和响应状态校验真实 JSON 响应。校验器固定读取平台 `contract.yaml` 声明的已提交快照，支持多文件契约、内部 `$ref` 和 OpenAPI 3 的 `nullable`，不替代业务码与业务字段断言。

## 测试分层

| 标记 | 目的 | 环境 |
| --- | --- | --- |
| `contract` | OpenAPI、接口清单、适配器和数据契约 | 离线 |
| `smoke` | 总平台登录及关键入口 | 线上 |
| `core` | P0 主链路回归 | 线上 |
| `live` | 访问实际测试环境 | 线上 |
| `<platform>` | 子平台隔离标记 | 取决于用例 |
| `requirement` | 需求接口包用例 | `-m requirement` 执行全部需求；`--requirement-id REQ-...` 精确筛选 |

推荐 CI 将 `contract` 与线上回归分开。仓库已提供 [`.github/workflows/api-tests.yml`](.github/workflows/api-tests.yml)：PR、合并队列和主分支推送先校验当前快照，再与事件对应的 Git 基线比较；受信任流水线在契约门禁通过后执行线上回归和需求接口包。定时和手动任务没有可靠事件基线时只校验已提交快照，不执行无意义的自比较。

GitLab 项目可使用 [`.gitlab-ci.yml`](.gitlab-ci.yml) 接入 Merge Request 门禁：contract 对所有 MR 执行，同项目受信任 MR 执行核心和需求回归。请在 GitLab 受保护分支中将对应 pipeline status 设为 Required，并将线上地址和凭证配置为受保护 CI/CD Variables。外部 fork 不应直接执行带线上凭证的测试代码。

每日定时流水线会在测试 job 完成后执行 `feishu_daily_report` 通知 job。启用通知时，在 GitLab 项目 `Settings -> CI/CD -> Variables` 新增受保护变量 `FEISHU_WEBHOOK_URL`，值填写飞书机器人的 Webhook 地址，并勾选 Masked/Protected；不要把地址写入仓库或普通日志。通知 job 校验 contract、requirements 和 core 三份预期 JUnit 报告，只在 `CI_PIPELINE_SOURCE=schedule` 时发送；报告缺失、为空、全部跳过或包含失败时会明确标记为异常或失败，不会显示为通过。通知失败不会覆盖测试 job 的结果。可通过 GitLab `Build -> Pipeline schedules` 设置每日执行时间，先手动运行一次 schedule 验证群消息和报告链接。

每个平台在 `platforms/<platform>/contract.yaml` 内声明自己的本地快照、接口清单和覆盖矩阵，在 `platforms/<platform>/config/` 管理运行地址。`contracts/<platform>/` 是日常测试使用的已提交快照；公共工具只读取这些协议，不包含具体平台的 URL、路径或业务分支。

### 契约变更检测

契约更新由维护者在对应服务代码仓库拉取目标分支到本地后完成，再运行 [`scripts/contract_diff.py`](scripts/contract_diff.py) 或 [`scripts/contract_pipeline.py`](scripts/contract_pipeline.py)。工具支持单文件和多文件 OpenAPI bundle，检测接口删除、`operationId` 变化、必填参数增加、请求/响应类型变化、枚举收窄、响应字段删除和共享 Schema 变化等破坏性变更。覆盖一致性由 contract 测试调用 [`scripts/contract_coverage.py`](scripts/contract_coverage.py)，检查每个最新接口是否有 inventory 和 testcase 映射。普通测试和 CI 不访问远程服务仓库；PR/MR 和推送的基线比较只读取当前 CI checkout 中的 Git 历史。

破坏性变更、新增接口没有覆盖映射、接口清单不一致或 testcase 引用失效，都会阻止门禁通过，并输出 diff/coverage 报告；维护者完成客户端和 case 回流后再提交新的快照。工具不会自动生成或修改业务 case，避免把未经审核的断言带入门禁。

每个平台的标准执行命令由平台目录提供；命令只校验当前提交中的契约快照，再启动测试：

```bash
./platforms/<platform>/test.sh -m "contract"
```

契约需要更新时，先在对应服务代码仓库拉取目标分支的最新提交（例如 `git fetch origin test`、`git pull --ff-only origin test`），阅读该分支的 OpenAPI 文档和代码变更，再从本地工作树复制文档到本仓库并审核更新 `contracts/<platform>/`、接口清单、覆盖矩阵、客户端和用例。快照、客户端和用例一起提交后，普通 `test.sh` 和 CI 即使用这组固定版本。

契约快照校验是测试执行的前置门禁，而不是静默刷新文件：每次平台测试命令只对仓库内快照执行格式、接口清单和 testcase 映射校验，再决定是否进入 pytest。新增、删除或破坏性变更应在快照提交前由维护者处理；兼容但可能影响断言的变更也要求人工复核。报告中的 `missing_inventory`、`missing_coverage`、`invalid_tests` 和 diff 明细就是回流清单。

框架不会在 CI 中自动拉取或改写契约和业务 case。接口变更后的固定回流顺序是：拉取服务方 `test` 分支 → 阅读 diff → 更新本仓库快照、client、数据、Schema、inventory 和覆盖映射 → 先执行受影响 case → 运行 `contract` 和平台回归全量 → 提交审核后的快照与测试变更。平台之间只共享同步、diff、覆盖校验和报告逻辑，不共享业务接口信息。

本地可直接比较两个契约：

```bash
python scripts/contract_diff.py \
  --baseline-openapi /path/to/old/openapi.yaml \
  --current-openapi contracts/<platform>/openapi.yaml \
  --baseline-inventory /path/to/old/api_inventory.json \
  --current-inventory contracts/<platform>/api_inventory.json \
  --report reports/contracts/<platform>-diff.json \
  --fail-on-breaking
```

比较当前快照与 Git 基线（不替换本地快照）可直接运行：

```bash
python scripts/contract_pipeline.py --base-ref "$BASE_SHA" --fail-on-breaking
```

`--base-ref` 指向的提交或其中任一契约文件不可读取时命令会失败，不会退回当前快照。未提供 `--base-ref` 和 `--source-root` 时同样拒绝执行，避免把当前快照与自身比较后产生无变化的假结果。

比较已拉取的某个服务工作树（仍不替换本地快照）：

```bash
python scripts/contract_pipeline.py --platform <platform> \
  --source-root /path/to/service-checkout --fail-on-breaking
```

平台目录下的 `test.sh` 只校验本地快照、运行时配置并启动 pytest；不会因为测试执行而访问远程契约。

接口变更后的同步顺序固定为：拉取服务方文档 → 阅读 diff 和 coverage report → 更新平台 client → 更新 `data/<platform>/`、测试 Schema 和覆盖矩阵 → 先跑目标 case，再跑 `contract` 和平台回归全量。已有 case ID 默认保持不变；新增行为新增 case，废弃行为需保留迁移依据，不能直接删除测试来消除失败。

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

本地需要验证飞书通知时，可显式开启通知选项；Webhook 只从当前 shell 环境读取，不会写入报告或仓库：

```bash
FEISHU_WEBHOOK_URL="$FEISHU_WEBHOOK_URL" ./scripts/run_tests.sh --notify-feishu -m contract
```

通知在测试执行和报告归档后发送，即使测试失败也会尝试推送；未配置 Webhook 时仅提示跳过。

产物位于 `reports/`，已加入 `.gitignore`。`reports/history/` 默认保留最近 5 轮，可通过 `REPORT_KEEP` 调整。

## 新增子平台

1. 在 `platforms/<platform>/definition.py` 注册客户端和平台能力。
2. 在 `platforms/<platform>/contract.yaml` 声明本地契约快照、inventory 和覆盖矩阵，并提供 `test.sh` 入口。
3. 在 `platforms/<platform>/` 实现客户端及可选的数据工厂、状态预置器。
4. 新增 `data/<platform>/`、`contracts/<platform>/` 和 `test-cases/<platform>/`。
5. 在 `tests/<platform>/` 按业务板块组织用例，并提供该目录的 README；使用通用 fixture，不复制认证和 HTTP 实现。

平台注册由 `platforms/registry.py` 自动发现。用例函数使用 `test_<子平台短名>_<模块号>_<序号>_<动作>` 命名，Schema 与自动化覆盖矩阵由子平台自行维护。

## 新增需求接口包

每个新需求在所属子平台下保留必要的 Schema 和数据资产；测试函数归入已有业务模块，需求 ID、case、接口和测试函数映射追加到平台现有 `coverage.yaml`，避免按需求新增 conftest、覆盖文件或独立测试文件。需求 ID 使用稳定的需求名或版本日期（例如 `REQ-<domain>-20260910`），不要复用其他需求的 `TC` 编号，也不要拼接执行时分秒。每条 case ID 必须以需求 ID 开头，框架会在 contract 测试和 Allure teardown 时校验。每条需求用例声明 `requirement` 和 `case_id` marker；Allure 会按需求 ID 覆盖标题、`testId`、`requirement` 标签和 story。执行全部需求使用 `-m "requirement and live"`；精确执行一个或多个需求使用 `--requirement-id REQ-...`（支持重复传入或逗号分隔），不依赖其所在测试文件。执行时间只由 `scripts/report_history.py` 生成报告 `run_id`，用于 `reports/history/<run_id>/` 归档，不参与用例身份。CI 的需求 job 统一按 `requirement` marker 执行，新增需求不需要修改公共 CI 文件。

## 子平台文档

各子平台的业务说明、契约来源和环境前置位于 `tests/<platform>/README.md`，新增平台时必须同步创建该文档。
