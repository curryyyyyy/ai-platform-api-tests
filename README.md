# AI 平台接口自动化测试

这是独立于各业务服务仓库的多平台接口自动化测试框架。它不属于任何一个业务平台仓库，负责统一处理测试配置、HTTP 请求、总平台认证、断言、契约校验和测试报告；各业务平台只提供自己的接口适配器和测试用例。

## 框架定位

框架解决的是“一个总平台账号，访问多个业务子平台”的自动化测试问题：

- 总平台只登录一次，获取的 Token 可被多个子平台客户端复用。
- RSA 公钥获取、密码加密、登录响应解析等认证细节集中在 `framework/auth`。
- HTTP 重试、超时、请求日志和响应解析集中在 `framework/http`。
- 每个子平台通过 `platforms/<platform>` 提供独立客户端，不把平台 URL 和业务路径散落在测试中。
- 每个平台的 OpenAPI 契约和接口清单独立存放，测试执行不依赖业务仓库的相对路径。

框架与业务代码的边界如下：

```text
统一框架：认证、HTTP、配置、断言、契约、报告、执行入口
业务适配器：平台地址、业务路径、平台专属请求封装
测试用例：冒烟、回归、鉴权、参数、数据一致性和契约检查
业务仓库：只维护服务源码和服务自身的 OpenAPI 来源
```

## 当前主链路

```text
总平台 RSA -> 总平台登录 -> 获取 Token -> 对应子平台项目接口
```

当前已接入：

- 总平台 `https://ai-node-test.tucdev.com`
- 机器标注平台 `https://test-hawk-admin.tucdev.com/api/v1`

## 目录职责

```text
framework/                         通用框架能力
  auth/                            总平台 SSO、RSA 加密、Token
  http/                            统一 requests 客户端
  assertions.py                    通用响应断言
  settings.py                      YAML 配置和环境变量覆盖
  data/                            测试数据集加载与资源生命周期
    dataset.py                     按平台加载可执行 YAML 数据集
platforms/                         业务平台适配器
  registry.py                      自动发现和注册平台定义
  hawk_admin/                      机器标注平台客户端
    definition.py                  客户端、数据工厂、报告元数据声明
contracts/                         各平台 OpenAPI 快照和接口清单
data/                               按平台隔离的可执行测试数据
  hawk_admin/                       项目、阶段、流程、批次、认证、执行数据集
tests/
  smoke/                           跨平台主链路冒烟
  hawk_admin/                      机器标注平台业务测试
  contracts/                       契约一致性测试
test-cases/                        各子平台手工测试用例与 Schema
  hawk_admin/                      Hawk 核心接口用例（markmap + schema）
config/
  test.yaml                        非敏感测试环境配置
  test.local.yaml                  本地账号密码，已忽略不提交
scripts/                            契约同步和辅助执行脚本
```

目录之间的依赖方向必须保持为：

```text
tests -> platforms -> framework
tests -> contracts
```

`framework` 不允许反向依赖具体平台，避免新增平台时修改通用层。

## 测试数据工厂

写入型用例必须通过 `data_scope` 和平台数据工厂造数，不允许在测试函数中散写随机名称或依赖存量数据：

```python
def test_project_create(platform_data_factory):
    project_id, payload = platform_data_factory.create_project(description="自动化测试")
    # 用例断言写入和查询结果；测试结束后自动删除项目
```

`DataScope` 会按用例编号生成有界唯一名称，登记清理动作并在用例结束时逆序执行。清理失败只记录 warning，不会阻塞后续用例；后续可继续增加会话尾批量清理任务。

平台工厂位于 `platforms/<platform>/factories.py`，默认值和资源删除逻辑集中在工厂内，用例只传入当前测试点的差异参数。

## Schema 断言

`framework/schema.py` 提供 JSON Schema 字段级断言。平台用例可以从对应 OpenAPI 快照提取响应 Schema，结合状态码、业务码和关键字段完成三层校验：

```text
HTTP 状态码 -> 业务 code -> JSON Schema / 关键字段
```

Schema 断言只验证结构，业务语义和跨字段规则仍由具体用例负责。

## 认证链路

线上冒烟执行时，认证过程为：

```text
GET  总平台 /api/auth/rsa
  -> 使用 PEM 公钥以 RSA PKCS#1 v1.5 加密密码
POST 总平台 /api/auth/login
  -> 提取 data.token
  -> 创建各业务平台 Client
GET  Hawk /api/v1/project
```

总平台认证由 [framework/auth/central_sso.py](framework/auth/central_sso.py) 独立实现，业务平台测试不直接调用登录接口。

## 配置规则

配置按以下优先级生效：

```text
环境变量 > config/<environment>.local.yaml > config/<environment>.yaml
```

常用环境变量：

| 变量 | 用途 |
| --- | --- |
| `TEST_ENV` | 选择环境配置，默认 `test` |
| `API_USER` / `API_PASSWORD` | 覆盖总平台账号密码 |
| `API_TOKEN` | 已有 Token 时跳过登录 |
| `AUTH_BASE_URL` | 总平台地址 |
| `PLATFORM_<平台名>_BASE_URL` | 按平台名覆盖地址，例如 `PLATFORM_HAWK_ADMIN_BASE_URL` |
| `HAWK_ADMIN_BASE_URL` | `hawk_admin` 地址的旧兼容变量 |
| `API_TIMEOUT` | 请求超时时间 |

`config/test.local.yaml` 和其他 `*.local.yaml` 已加入 `.gitignore`。CI 中应使用密钥变量或密钥管理服务注入凭证，不应提交明文账号密码。

## 运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .

# 主链路冒烟：总平台登录 + Hawk 鉴权/项目列表
pytest -m "live and smoke" -v

# 离线契约检查
pytest -m contract -v
```

## Allure 和 CI 报告

安装项目依赖后，使用统一脚本同时生成 Allure 原始结果和 JUnit XML：

```bash
./scripts/run_tests.sh -m "live and smoke"
./scripts/run_tests.sh -m contract
```

只跑测试拿结果时不需要 `allure` 命令行；要生成 HTML 报告才需要：

```bash
brew install allure              # macOS
# 或 npm i -g allure-commandline # 其他平台
```

脚本的四种产出方式：

| 命令 | 用途 |
| --- | --- |
| `./scripts/run_tests.sh -m contract` | 只产出原始数据，适合 CI |
| `./scripts/run_tests.sh -m contract --report` | 额外生成静态 HTML，可归档 |
| `./scripts/run_tests.sh -m contract --open` | 生成 HTML 并在浏览器打开，日常排查用 |
| `./scripts/run_tests.sh -m contract --serve` | 用临时目录起服务并打开，不落盘 |

默认每轮清空 `reports/allure`，避免上一轮残留混入；需要在当前轮次合并结果时使用 `--no-clean`。每次脚本执行都会将当前 Allure/JUnit 结果归档到 `reports/history/<执行时间>/`，默认只保留最近 5 次；可用 `REPORT_KEEP=10` 或 `--keep 10` 临时调整保留轮次。

产物位置：

- `reports/allure/`：Allure 原始结果
- `reports/allure-report/`：静态 HTML 报告（`--report` / `--open` 生成）
- `reports/junit/results.xml`：CI 平台通用的 JUnit 测试结果
- `reports/history/<执行时间>/`：按执行轮次归档的报告，默认保留最近 5 次；包含本轮 Allure/JUnit，使用 `--report` 或 `--open` 时还包含 HTML

`reports/` 已加入 `.gitignore`，报告不提交到代码仓库。

### 可执行测试数据

运行时测试数据统一放在 `data/<platform>/`，按平台和资源拆分 YAML 文件。每个文件包含
`defaults`（工厂默认请求字段）和 `cases`（可参数化场景），场景记录必须有稳定的 `id`。
测试通过 `framework.data.dataset` 的 `dataset_defaults`、`dataset_cases` 或
`dataset_case_map` 加载，使用 `case_payload` 去除仅供报告追踪的 `id` 字段。

平台数据与平台适配器一一对应：新增平台只需新增 `data/<platform>/` 数据文件，并在该平台
测试中加载；动态名称、服务端 ID、清理动作和依赖线上状态仍由平台 `factories.py` /
`presets.py` 负责。这样静态场景、动态资源和环境状态各自有明确边界，不会把固定编号写入数据集。

### 报告中的用例信息

报告不是一长串函数名，而是按用例清单的维度组织，直接对应 `test-cases/<platform>/` 里的 Schema：

| Allure 字段 | 来源 | 示例 |
| --- | --- | --- |
| 标题 | 用例编号 + 动作 | `TC-04-02 invalid json config` |
| ID | `<子项目短名>/<用例编号>` | `hawk/TC-04-02` |
| Epic | 子平台 `definition.py` 的 reporting 元数据 | `机器标注平台 (hawk_admin)` |
| Feature | 用例编号的模块号映射，与 Schema 的 `modules` 一致 | `4. 流程管理接口` |
| Story | 用例编号 | `TC-04-02` |
| Tag | pytest marker，由 allure-pytest 自动转换 | `live`、`smoke`、`contract`、`hawk_admin` |

报告还包含两类辅助信息：

- `reports/allure/environment.properties`：环境名、Python / pytest 版本、总平台和子平台地址，展示在报告的 Environment 区域。
- `reports/allure/categories.json`：失败分类，把结果按「环境未配置已跳过 / 鉴权权限失败 / 响应不符合契约 / 造数或清理失败 / 服务不可用」聚合，源文件在 `config/allure/categories.json`（不要放在根目录的 `allure/`，会遮蔽 `allure` 包）。

报告元数据由 `platforms/<platform>/definition.py` 自注册，新增平台无需修改 `conftest.py` 的报告逻辑。

账号密码默认读取 `config/test.local.yaml`，该文件已被忽略；也可以使用 `API_USER`、`API_PASSWORD` 覆盖。Token 已存在时可直接设置 `API_TOKEN` 跳过登录。

## 用例编号与命名规范

用例编号只在单个子平台内唯一，跨子平台一律用平台标识区分，避免 Allure、CI 和回归清单出现重复编号：

| 位置 | 规范 | 示例 |
| --- | --- | --- |
| Schema `meta.platform` | 子平台标识，取值与 `platforms/<platform>` 目录名一致 | `platform: hawk_admin` |
| Schema 用例编号 `cases[].id` | 平台内唯一，模块号 + 序号 | `TC-04-01` |
| 自动化测试函数名 | `test_<子项目名>_<模块号>_<序号>_<动作>`，省略 `TC` 前缀 | `test_hawk_04_01_create_flow` |
| 无编号的辅助用例 | 同样带子项目名前缀 | `test_hawk_project_requires_token` |

函数名使用子项目短名，与目录 / `meta.platform` 的对应关系：

| 子项目短名 | 目录、`meta.platform`、marker | 测试函数名前缀 |
| --- | --- | --- |
| `hawk` | `hawk_admin` | `test_hawk_` |

短名在平台 `definition.py` 中声明，保证 `TC-04-01` 这类编号在跨子平台时仍能唯一定位。跨平台唯一键为 `<platform>/<用例编号>`，例如 `hawk_admin/TC-04-01`。

每个测试函数必须写一行中文 docstring 说明用例目的，与 Schema 中 `cases[].title` 对齐。`allure-pytest` 会自动把 docstring 渲染为报告里的 Description，普通注释做不到这一点，因此不要用 `#` 注释代替。

## 扩展其他平台

新增平台时按以下顺序扩展：

1. 在 `config/test.yaml` 增加平台地址。
2. 新增 `platforms/<platform>/client.py`，只封装该平台的业务接口。
3. 新增 `platforms/<platform>/definition.py`，注册客户端构造器、可选数据工厂、状态预置器和报告元数据。
4. 将平台 OpenAPI 快照放入 `contracts/<platform>`。
5. 在 `tests/<platform>` 增加该平台测试，使用 `client_for("<platform>")` 获取带总平台 Token 的客户端；匿名场景使用 `anonymous_for("<platform>")`。
6. 在 `definition.py` 的报告元数据中声明专属 marker，并新建 `test-cases/<platform>/` 用例 Schema；自动化函数名使用 `test_<子项目短名>_<模块号>_<序号>_<动作>` 格式。

平台注册采用包级自描述方式：`platforms/registry.py` 会自动发现各子包的 `definition.py`。因此新增平台的改动集中在自身目录和配置文件，不会让公共 fixture、报告逻辑和配置解析按平台数量线性增长。平台测试统一使用 `platform_client`、`platform_data_factory`、`platform_state` 等通用 fixture。

总平台认证保持复用，不在业务平台仓库中复制测试框架，也不在各平台测试中重复实现 RSA 登录。

机器标注平台契约同步：

```bash
python scripts/sync_hawk_contract.py
```

## 测试分类

| 分类 | 目的 | 是否访问线上环境 |
| --- | --- | --- |
| `smoke` | 验证总平台登录和关键业务入口 | 是 |
| `contract` | 校验 OpenAPI 结构和接口清单 | 否 |
| 平台回归 | 验证具体业务功能、鉴权和数据一致性 | 通常是 |

推荐在 CI 中分开执行契约检查和线上冒烟，避免环境不可用时混淆为代码或契约问题。

## Hawk 核心接口测试

Hawk 首批手工用例和接口自动化脚本分别位于：

```text
test-cases/hawk_admin/                  手工用例及 Schema
tests/hawk_admin/                       pytest + requests 接口测试
```

Hawk 适配层契约测试也位于 `tests/hawk_admin/`，包括客户端重试、数据工厂清理和状态预置。原 `tests/framework/test_hawk_*.py` 路径已移除，避免把平台实现混入公共框架测试。

```bash
pytest tests/hawk_admin/test_client_contract.py \
       tests/hawk_admin/test_factory_contract.py \
       tests/hawk_admin/test_presets_contract.py -m contract -v
```

执行 Hawk 接口测试（需要总平台账号或 `API_TOKEN`）：

```bash
pytest tests/hawk_admin -m "live and hawk_admin" -v
```

需要预置批次状态的状态机用例通过环境变量传入批次编号：

```text
HAWK_INIT_BATCH_ID       未启动批次，用于 START
HAWK_RUNNING_BATCH_ID    处理中批次，用于 PAUSE
HAWK_INPUT_UPDATE_RUNNING_BATCH_ID  处理中批次，用于修改运行中批次输入
HAWK_EXPORT_RUNNING_BATCH_ID  已有任务运行的批次，用于中途导出
HAWK_END_RUNNING_BATCH_ID 独立的处理中批次，用于 END（避免与 PAUSE 用例共享状态）
HAWK_STOPPED_BATCH_ID    已暂停批次，用于 RESTART
HAWK_FAILED_BATCH_ID     失败批次，用于 RETRY
HAWK_VIEWER_TOKEN        hawk-viewer 角色 Token，用于权限用例
HAWK_VIEWER_USER         查看者账号，用于现场登录换取 Token
HAWK_VIEWER_PASSWORD     查看者账号密码
```

这些变量**不再是必填**。状态机用例通过 `platform_state` fixture 取批次，优先级为：

```text
环境变量显式指定  >  为每个用例现场造数（init / running / stopped）  >  跳过
```

批次生命周期用例的普通前置数据也只复用环境内已有流程，不调用当前环境不可用的流程创建接口；环境没有可用流程时会明确跳过。

- 每条用例使用**独立批次**：状态机会改变批次状态，复用同一个批次会让用例互相干扰。PAUSE、输入修改和中途导出分别使用 `HAWK_RUNNING_BATCH_ID`、`HAWK_INPUT_UPDATE_RUNNING_BATCH_ID` 和 `HAWK_EXPORT_RUNNING_BATCH_ID`；END 用例单独使用 `HAWK_END_RUNNING_BATCH_ID`。END 未配置时会明确跳过（现场造数批次没有可结束任务），其他可造数批次的项目/批次在用例结束时由 `DataScope` 清理。
- 造数不创建流程（流程创建接口当前不可用），而是复用环境内已有的流程（只读）。默认使用 `flow.exif.get` 与素材集合 `CID://966`，并复用同流程存量批次的 `config`，保证批次启动后能持续运行一段时间；均可用 `HAWK_PRESET_FLOW_NAME`、`HAWK_PRESET_INPUT_PATH` 覆盖。
- 需要复现某个特定批次时，用环境变量覆盖即可，造数逻辑不会执行。
- `failed`（需要真实执行失败）、`running_with_tasks`（06_11 中途导出要求批次已有任务在执行）和 `running_end`（06_05 END 要求批次已有可结束任务）三种状态无法靠造数得到，仍须配置对应环境变量；中途导出使用独立的 `HAWK_EXPORT_RUNNING_BATCH_ID`，避免与 PAUSE 共享批次。
- 造数批次仍可能比真实批次执行得快，`running` 相关用例偶发竞态属于预期；需要 100% 稳定的回归时配置 `HAWK_RUNNING_BATCH_ID` 指向一个持续运行的批次。
- `PAUSE` / `RESTART` 后端节点释放存在短暂窗口，客户端对 `lock already taken` 做有限退避重试；超过重试窗口仍失败时才报告真实业务错误。
- 若状态预置返回 `no healthy upstream`，表示网关下游 `tc-hawk` 没有健康实例，测试会标记为跳过；恢复执行服务后重新运行即可。

查看者权限用例优先用 `HAWK_VIEWER_TOKEN`；Token 会过期，建议改配 `HAWK_VIEWER_USER` / `HAWK_VIEWER_PASSWORD`，由总平台 SSO 现场登录换取。

造数失败（例如被测接口不可用）时用例标记为跳过，并在跳过原因里带上真实错误，不会污染为用例失败。
