# 资源管理平台测试接入

资源管理平台（`source_admin`）的接口基线已完成整理，当前尚未生成线上测试用例。

## 当前产物

- 接口清单：`../../test-cases/source_admin/资源管理平台_接口清单.md`
- 需求模型：`../../test-cases/source_admin/资源管理平台_需求模型.md`
- 机器可读接口库存：`../../contracts/source_admin/api_inventory.json`
- 上游仓库：`https://gitlab.ituchong.com/ai-dataset/ai-source-admin`
- 当前基线：`master@55040a84d1d711ed4198215bc61be43b93ab1d85`

## 接入范围

主文档 `docs/api.md` 包含 40 个操作；上游结构化 OpenAPI JSON 和代码路由确认共 49 个操作，另有 9 个接口未写入主文档，已在接口清单中标注。认证域还包括登录 Token、分享 Token 和 HBase 专用凭证，后续不能复用同一个认证 fixture。

## 后续接入前置

需要先确认测试 Base URL、Token 获取方式、写入权限、数据清理策略、异步任务轮询阈值，以及 HBase/TOS/Hive/LanceDB/RPC 的测试依赖。未裁决事项集中记录在需求模型中；确认前不创建客户端和写入型用例。

