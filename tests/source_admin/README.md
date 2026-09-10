# 资源管理平台测试接入

资源管理平台（`source_admin`）的接口基线和第一批测试代码已接入；当前包含客户端契约、认证/只读冒烟，以及基于 `DataScope` 的 Schema、文件夹节点和分享链接写入生命周期测试。

## 当前产物

- 接口清单：`../../test-cases/source_admin/资源管理平台_接口清单.md`
- 需求模型：`../../test-cases/source_admin/资源管理平台_需求模型.md`
- 机器可读接口库存：`../../contracts/source_admin/api_inventory.json`
- 客户端：`../../platforms/source_admin/client.py`
- 数据工厂：`../../platforms/source_admin/factories.py`
- 测试数据：`../../data/source_admin/`
- 契约测试：`test_inventory_contract.py`
- 只读冒烟：`test_read_api.py`
- 认证冒烟：`test_source_auth.py`
- 数据管理测试：`test_data_manage_api.py`
- Schema 测试：`test_schema_api.py`
- 文件系统测试：`test_filesystem_api.py`
- 分享链接测试：`test_share_api.py`
- 覆盖矩阵：`coverage.yaml`；覆盖契约：`test_source_coverage_contract.py`
- 上游仓库：`https://gitlab.ituchong.com/ai-dataset/ai-source-admin`
- 当前基线：`master@55040a84d1d711ed4198215bc61be43b93ab1d85`

## 接入范围

主文档 `docs/api.md` 包含 40 个操作；上游结构化 OpenAPI JSON 和代码路由确认共 49 个操作，另有 9 个接口未写入主文档，已在接口清单中标注。认证域还包括登录 Token、分享 Token 和 HBase 专用凭证，后续不能复用同一个认证 fixture。

## 运行前置

认证复用机器标注平台的总平台 SSO，客户端自动发送 `Authorization: Bearer <central_token>`。测试 Base URL 已配置为 `https://src-admin.tucdev.com/api/v1`，也可通过 `PLATFORM_SOURCE_ADMIN_BASE_URL` 或 `SOURCE_ADMIN_BASE_URL` 覆盖。

分享链接测试优先使用 `SOURCE_ADMIN_COLLECTION_ID`，未设置时从圈选集列表动态发现；不得把共享环境资源 ID 写入仓库。文件夹测试默认使用根节点 `1`，如环境根节点不同，修改 `data/source_admin/node.yaml` 的 `root_id`。

```bash
.venv/bin/pytest -m 'contract and source_admin' -q
.venv/bin/pytest -m 'not live' -q
.venv/bin/pytest -m 'live and source_admin' -q
.venv/bin/pytest -m 'live and source_admin and core' -q
```

覆盖矩阵中的 49 个业务操作均已登记并至少映射到一条自动化调用，但 `full` 表示该测试条目的目标面已覆盖，不代表每个接口都完成了正向业务闭环；仅有负向、条件环境或外部依赖的条目已标记为 `partial`。标记为 `P0` 的自动化用例均添加了 `@pytest.mark.core`，可用最后一条命令执行核心门禁。Schema 创建及其字段版本链路暂以 `skip` 保留用例和覆盖映射，原因是当前服务端返回 `node_type` 数据库默认值错误；只读 Schema 列表、名称查询、缺失资源和批量更新的 `fields=[]` 空操作语义仍纳入回归。

## 暂未执行的链路

圈选 SQL、集合运算、原始下载、CSV/TOS 导入和集合数据查询依赖 Hive/LanceDB/HBase/RPC/TOS 及异步任务状态；待测试环境确认轮询阈值和样例资源后，再补现场造数、轮询和下载校验，不使用虚构资源或固定任务 ID。

当前 live 验证发现 Schema 创建接口返回 `Error 1364: Field 'node_type' doesn't have a default value`。请求模型和接口文档均未暴露 `node_type`，因此测试不会偷偷补充未被接口接受的字段；需先修复服务端数据库迁移/默认值或同步更新 API 契约后再恢复 Schema 写入回归。

Schema 批量更新的 `fields=[]` 被按合法空操作处理，不再作为“缺失 Schema 必须拒绝”的断言依据。需要确认的剩余语义是：服务端实现仍会尝试保存版本快照和写审计日志，是否应将空操作限制为完全无副作用，需产品/后端契约进一步明确。部分数据管理错误响应会携带占位 `data`，对应测试通过显式 `allow_error_data` 只校验非零业务码和错误消息。
