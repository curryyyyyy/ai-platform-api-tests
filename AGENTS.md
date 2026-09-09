# Repository Working Guide

本文件是 Codex（Codex.ai/code）在本仓库工作的仓库级约束。子平台目录可以增加更具体的 `AGENTS.md`，其规则只对对应目录生效。

## 架构边界

- `framework/` 只放跨平台能力，不得导入或分支依赖具体平台。
- `platforms/<platform>/` 放客户端、数据工厂、状态预置器和平台注册声明。
- `data/<platform>/`、`contracts/<platform>/`、`test-cases/<platform>/`、`tests/<platform>/` 是平台隔离边界。
- 根目录 `README.md` 只描述通用框架；平台 URL、接口路径、环境变量、状态前置和业务用例必须写入对应子平台 README。
- 新增平台应新增自己的 README，不把平台细节追加到根文档或公共 fixture。

## 测试与契约

- 修改接口测试、Schema、OpenAPI、数据集或断言时，使用 `api-testing` skill 的接口测试规范。
- 写入型用例通过平台数据工厂和 `DataScope` 造数并清理，不依赖共享批次、固定资源或执行顺序。
- 参数边界和同类异常优先使用 `pytest.mark.parametrize` 与平台 YAML 数据集。
- Schema case 必须在对应平台的覆盖矩阵中登记；新增 case 同步更新矩阵和覆盖契约测试。
- 契约来源优先由子平台 CI 配置线上拉取；凭证只使用 CI Secret/环境变量，不写入仓库。
- 远程契约下载必须先校验格式和接口清单，再原子替换本地快照；本地快照用于离线回归兜底。

## 文档归属

- 根 README：架构、安装、通用命令、通用配置和新增平台流程。
- `tests/<platform>/README.md`：平台板块、数据、契约来源、环境前置、CI 和已知限制。
- 不重复维护同一平台的运行说明；修改平台配置时同步更新平台 README。

## 修改流程

1. 先阅读相关目录、平台 README、Schema、数据集和现有测试，确认当前 dirty worktree，不撤销用户已有改动。
2. 让改动保持在对应平台或公共层边界内；避免为单个平台增加公共层特判。
3. 手工编辑使用 `apply_patch`，默认 ASCII，避免无关格式化和元数据变更。
4. 至少运行受影响测试、`pytest -m contract -q` 和 `git diff --check`；若环境不可用，区分环境阻塞与代码失败并说明。
5. 完成后报告改动文件、验证结果和未执行的线上检查；不提交真实凭证。

## 常用验证

```bash
pytest -m contract -q
pytest -m 'not live' -q
pytest --collect-only -q
git diff --check
```

## 安全与破坏性操作

- 不读取、输出或提交真实 Token、密码和私有仓库凭证。
- 不使用 `git reset --hard`、`git checkout --` 或宽范围删除命令覆盖用户改动。
- 远程契约、测试环境和 CI Secret 变更要在对应平台范围内完成，并明确记录所需外部配置。
