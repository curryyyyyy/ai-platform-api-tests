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
platforms/                         业务平台适配器
  hawk_admin/                      机器标注平台客户端
contracts/                         各平台 OpenAPI 快照和接口清单
tests/
  smoke/                           跨平台主链路冒烟
  hawk_admin/                      机器标注平台业务测试
  contracts/                       契约一致性测试
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
def test_project_create(hawk_data_factory):
    project_id, payload = hawk_data_factory.create_project(description="自动化测试")
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
| `HAWK_ADMIN_BASE_URL` | 机器标注平台地址 |
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

产物位置：

- `reports/allure/`：Allure 原始结果，可使用 `allure serve reports/allure` 查看
- `reports/junit/results.xml`：CI 平台通用的 JUnit 测试结果

`reports/` 已加入 `.gitignore`，报告不提交到代码仓库。

账号密码默认读取 `config/test.local.yaml`，该文件已被忽略；也可以使用 `API_USER`、`API_PASSWORD` 覆盖。Token 已存在时可直接设置 `API_TOKEN` 跳过登录。

## 扩展其他平台

新增平台时按以下顺序扩展：

1. 在 `config/test.yaml` 增加平台地址。
2. 新增 `platforms/<platform>/client.py`，只封装该平台的业务接口。
3. 将平台 OpenAPI 快照放入 `contracts/<platform>`。
4. 在 `tests/<platform>` 增加该平台测试，并使用 `central_token` 或对应平台 Client。
5. 为平台测试增加专属 marker，支持单平台执行。

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
