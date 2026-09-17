# 可执行测试数据

`data/<platform>/` 是运行时测试数据的唯一归属目录。每个平台独立维护资源数据集，
避免不同子平台共享业务字段或固定编号。

每个资源文件使用统一结构：

```yaml
defaults:
  # 工厂创建资源时使用的默认请求字段
cases:
  scenario_name:
    - id: stable_case_id
      # 可直接传给接口或工厂的字段
```

需求级数据集还应在 `meta` 中声明稳定的 `requirement_id`，例如
`REQ-domain-20260910`。这个 ID 和 `cases.*[].id` 会贯穿 Schema、覆盖映射和
Allure 历史；不要把执行时间写入 ID。执行时间由报告归档工具生成
`reports/history/<run_id>/` 目录名。

Python 用例通过 `framework.data.dataset` 读取：

```python
from framework.data.dataset import case_payload, dataset_cases

cases = dataset_cases("<platform>", "<resource>", "<scenario>")
pytest.mark.parametrize("case", cases, ids=lambda item: item["id"])
payload = case_payload(case)
```

`id` 仅用于参数名称和报告追踪，不会发送给被测接口。动态资源名称、服务端 ID、状态批次
仍由平台 `factories.py` 和状态预置器负责生成，不能写入静态数据集。

固定的异常令牌、缺失资源 ID、操作码等协议测试常量也应放入对应资源数据集的 `defaults`，
避免在多个测试文件重复维护。
