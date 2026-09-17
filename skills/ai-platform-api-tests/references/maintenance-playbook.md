# 维护手册

这是 `ai-platform-api-tests` 技能的详细路由指南，记录扩展框架时最容易出错的仓库级决策。

## 归属边界

```text
tests/<platform> -> platforms/<platform> -> framework
tests            -> contracts/<platform>
tests            -> test-cases/<platform>
tests            -> data/<platform>
```

`framework/` 负责认证原语、HTTP 行为、配置、公共断言、数据范围、数据集加载、报告和通用 pytest fixture。这里不能导入具体平台，也不能按平台名称增加分支。

`platforms/<platform>/` 负责客户端、数据工厂、状态预置器、运行时上下文、平台定义、契约 manifest、平台配置和平台 shell 入口。业务路由和请求字段必须归属这里。

`data/<platform>/`、`contracts/<platform>/`、`test-cases/<platform>/` 和 `tests/<platform>/` 是平台隔离边界。平台 README 放在 `tests/<platform>/README.md`；不要把平台 URL 或业务前置不断追加到根 README。

## 发现与追踪

在依赖服务文档之前，先以仓库内容为准：

```bash
git status --short
rg --files -g 'AGENTS.md' -g 'README.md' -g 'contract.yaml' -g 'coverage.yaml' -g '*.schema.yaml'
rg -n 'operationId|/api/|requirement|case_id|DataScope|dataset_' \
  platforms/<platform> contracts/<platform> test-cases/<platform> tests/<platform>
```

追踪已有用例时按以下顺序：

1. 阅读 testcase 或 Schema 条目及稳定 case ID。
2. 在 `tests/<platform>/coverage.yaml` 或 `operation_coverage.yaml` 中查找该 ID 或接口。
3. 阅读映射到的 pytest 函数，包括 fixture、数据、清理和 marker。
4. 阅读 `platforms/<platform>/client.py` 中所有被调用的方法，再检查公共 `framework/http/client.py` 的 URL 拼接、认证、超时、重试和 JSON 解析。
5. 在已提交的 OpenAPI 快照和接口清单中核对对应操作。

不要从测试文件名推断 URL，也不要假定一个 testcase 只对应一次 HTTP 请求。生命周期用例通常会创建、查询、更新和删除多个资源。

## 新增平台

只创建平台归属的资产，并复用公共 fixture：

1. 增加 `platforms/<platform>/definition.py` 并注册客户端工厂。只有平台确实需要时才增加数据工厂、运行时上下文或状态解析器。
2. 增加 `platforms/<platform>/contract.yaml`，声明本地快照、接口清单和覆盖矩阵，并提供 `test.sh` 入口。
3. 在 `platforms/<platform>/config/` 增加平台配置；凭证和本地覆盖配置不能提交到 Git。
4. 增加 `contracts/<platform>/`、`data/<platform>/`、`test-cases/<platform>/` 和 `tests/<platform>/README.md`。
5. 按服务真实的 method、path、payload 和响应形状实现客户端；不能复制认证或 HTTP 实现。
6. 在适用范围内增加注册、客户端路径和请求体、数据工厂清理、数据集加载以及接口清单/覆盖一致性的契约测试。
7. 先执行收集和契约测试，再执行线上测试。客户端能调用但接口清单、覆盖映射或 README 缺失时，平台仍未接入完成。

需要特别确认 Base URL 规则：配置可能已经以 `/api/v1` 结尾，而客户端方法可能使用 `/api/v1/...`。修改任一侧前先确认公共客户端会去除重复前缀。不能在 `framework/` 增加平台专用 URL 逻辑来掩盖重复路径。

## 新增接口或需求

先确认接口是否属于已有业务模块。通常应扩展已有客户端、数据 YAML、testcase/Schema、覆盖矩阵和测试文件，而不是新增 conftest、需求专用 fixture 或一次性覆盖文件。

需求级接入遵守以下规则：

- 使用稳定的需求 ID，例如 `REQ-<domain>-<date>`；稳定 case ID 必须以该需求 ID 开头。
- 每个映射到自动化的测试同时添加 `pytest.mark.requirement(...)` 和 `pytest.mark.case_id(...)`。
- 保留原始人工用例 ID 作为追溯信息，但它不能替代需求 case ID。
- 将映射写入平台已有的 `coverage.yaml` 的 `requirements` 节或当前平台既有的等价结构。
- `run_id` 和时间戳只用于报告存储，不能放进测试或 case ID。
- 校验 `pyproject.toml` 中的 marker 声明，并在线上测试前收集精确的需求子集。

参数和边界用例应放在 `data/<platform>/*.yaml` 的稳定记录中，使用 `dataset_cases` 或 `dataset_case_map` 加载，只通过 `case_payload` 去掉数据集元字段，并使用 `pytest.mark.parametrize(..., ids=...)`。动态 ID、时间戳和服务端生成字段由工厂负责。

## 契约变更

契约快照是日常测试输入，不是远程服务缓存。上游测试分支发生变化时：

1. 在服务代码仓库拉取或检查维护者批准的上游 `test` 分支；日常 CI 不能依赖该远程仓库。
2. 使用候选文件前校验所有 OpenAPI 文件和接口清单。多文件来源应保持文档分离，除非现有工具明确支持且组件互不冲突的 bundle。
3. 使用 `scripts/contract_diff.py` 或 `scripts/contract_pipeline.py` 比较基线和候选版本。重点检查接口删除、operation ID 变化、新增必填输入、类型变化、枚举收窄、响应字段删除和共享 Schema 变化。
4. 执行覆盖校验。解决 `missing_inventory`、`extra_inventory`、`missing_coverage`、`extra_coverage`、`invalid_tests` 以及重复 ID 后，才能替换快照。
5. 更新平台客户端和断言。请求或响应字段变化时同步更新数据默认值和边界记录；行为或追溯关系变化时同步更新 testcase Schema、接口清单、覆盖矩阵和平台 README。
6. 先跑受影响测试，再跑 `contract`、离线测试、收集检查和平台回归。除非行为确实是新用例，否则保持原有 case ID；废弃行为要保留迁移依据。
7. 只通过审核后的提交替换快照。破坏性变更需要维护者明确批准；会影响断言的兼容性变更也需要人工复核。

常用命令：

```bash
python scripts/contract_diff.py \
  --baseline-openapi /path/to/old/openapi.yaml \
  --current-openapi contracts/<platform>/openapi.yaml \
  --baseline-inventory /path/to/old/api_inventory.json \
  --current-inventory contracts/<platform>/api_inventory.json \
  --report reports/contracts/<platform>-diff.json \
  --fail-on-breaking

python scripts/contract_pipeline.py --platform <platform> --source-root /path/to/service-checkout --fail-on-breaking
```

不能用刷新快照来让失败测试变绿。字段变化必须被分类，并反映到面向消费者的测试资产中。

## 数据生命周期与异步状态

写入型测试必须独立且可安全清理：

- 通过平台工厂创建资源，不要把原始请求散落到测试函数中。
- 使用 `DataScope.unique_name` 生成有长度上限的唯一名称，并遵守服务端长度限制。
- 服务端返回资源 ID 后立即登记删除或终止动作。
- 先创建被依赖资源，再创建依赖资源，让 `DataScope` 按逆序清理。
- 避免固定共享 ID；只读场景可以动态发现资源，必须复现的前置则接受显式环境变量覆盖。
- 接口无法产生的状态不能被宣称为可构造。按测试契约选择显式前置、清晰跳过或产品失败。

异步操作应等待有界的、可观察的服务端状态。操作后重新读取资源；不能把操作接口的即时响应当成持久化已经完成。如果造数失败，要把 fixture/前置失败与业务断言分开。

如果某状态天然依赖外部资源，应记录所需变量及无法现场构造的原因。不能为了增加覆盖率伪造失败任务、运行中任务或下游产物。

## 响应与断言

不要把一种响应包裹结构强加给所有平台。有的接口返回 `data`，有的返回 `base`，有的返回扁平字段，错误响应也可能合法地带占位 `data`。使用 `framework.assertions` 的公共 code、message 和 status 检查，再用窄范围的平台 helper 处理业务 payload。

JSON Schema 校验应来自已提交契约或审核过的 testcase 源，并在正确的响应层级校验实例。字段是可选的或接口之间存在差异时，应写入接口级 Schema，而不是放宽全局断言。

服务端拒绝未记录的字段时，不能静默把该字段加入测试 payload。先核对上游实现和契约，否则应记录为服务或契约问题。

## 运行时与故障分类

线上执行前使用平台入口和运行时校验器，检查：

- 总平台 URL，以及 Token 或登录凭证；
- 目标平台 base URL；
- 平台特有的外部前置和状态变量；
- marker 表达式是否确实包含 `live`。

按最先可观察到的边界分类：

| 现象 | 首要检查 | 分类 |
| --- | --- | --- |
| 缺少 URL、Token 或凭证 | 运行时校验器和最终生效配置 | 环境配置问题，不应报告为接口断言失败 |
| `no healthy upstream`、连接失败、超时 | 服务部署和下游依赖健康度 | 环境或下游阻塞，除非测试契约另有规定 |
| 文档有路由但返回 404 | 部署版本和路由注册 | 服务/契约漂移，保留负向证据 |
| 创建接口返回数据库或默认值错误 | 服务端迁移和请求契约 | 产品或部署缺陷，不要臆造请求字段 |
| 操作成功但立即 GET 仍是旧数据 | 异步持久化和有界轮询 | 同步问题，修正等待逻辑或记录最终一致性 |
| 测试结束后清理失败 | 清理顺序、资源依赖和服务可用性 | 清理缺陷或环境问题，不能用共享资源掩盖 |

只有在测试明确依赖的外部前置不可用且 README 已说明时才使用 `skip`。正常的产品拒绝或意外响应必须失败。

## 完成门禁

受影响的改动应留下可追溯的文件集合：

- 接口或平台变化时，更新客户端和平台适配器；
- 前置或边界变化时，更新数据 YAML 和工厂/状态预置器；
- 契约面或覆盖变化时，更新 testcase/Schema、接口清单和覆盖映射；
- 命令、前置、契约来源或已知限制变化时，更新平台 README；
- 为变更行为增加针对性测试和契约测试。

至少执行：

```bash
.venv/bin/pytest -m contract -q
.venv/bin/pytest -m 'not live' -q
.venv/bin/pytest --collect-only -q
git diff --check
```

线上改动要在运行时校验后执行目标平台命令。最终报告说明变更文件、通过的命令、跳过及其前置，以及未执行的线上或远程检查。

## 反模式

- 在 `framework/` 中增加平台专用 `if` 分支、URL 或业务字段名。
- 为每个平台复制 `conftest.py`、认证实现或 HTTP 客户端。
- 使用固定 ID、共享可变批次、执行顺序假设，或不清理测试数据。
- 已有业务模块可以承载时，新增需求专用测试文件或覆盖矩阵。
- 未审核 diff 和覆盖就更新快照，或在普通 CI 中拉取远程契约。
- 只有“HTTP 状态码成功”这类宽断言，遗漏业务 code、响应层级或资源标识。
- 为弥补服务端或数据库缺陷而添加未记录的请求字段。
- 只为消除失败而删除或重编号旧用例。
