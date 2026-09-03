"""Hawk 状态机用例所需的预置批次。

优先由环境变量显式指定批次编号（便于复现特定批次）；未指定时现场造数，
避免状态机用例长期依赖人工维护的线上批次。

造数的两个前提：
- 只复用环境内已存在的流程（只读），不自建流程：流程创建接口当前不可用，
  且状态机用例关注的是批次状态流转，与流程由谁创建无关。
- 输入路径必须是合法的 `CID://<int>` 格式，否则启动批次时会被校验拦截。
两者都可通过环境变量覆盖。
"""

from __future__ import annotations

import logging
import os

from framework.data.scope import DataScope
from platforms.hawk_admin.client import HawkAdminClient
from platforms.hawk_admin.factories import HawkDataFactory

LOG = logging.getLogger(__name__)

# 造数默认选用的流程与素材集合：需要“启动后能持续运行”的流程，
# 否则批次会立刻执行完毕，PAUSE / RESTART 这类操作抢不到窗口而报 invalid operation。
PRESET_FLOW_NAME = os.getenv("HAWK_PRESET_FLOW_NAME", "flow.exif.get")
PRESET_INPUT_PATH = os.getenv("HAWK_PRESET_INPUT_PATH", "CID://966")

# 可现场造出的目标状态：状态名 -> 批次状态码
PROVISIONABLE_STATES = {"init": 0, "running": 1, "stopped": 3}

# 无法造出、必须由环境变量指定的状态及原因
UNPROVISIONABLE_REASONS = {
    "failed": "失败批次需要真实执行失败，无法靠操作码构造",
    "running_with_tasks": "需要已有任务在执行的批次，造数批次刚启动尚无任务",
    "running_end": "END 需要已有任务在执行的批次，现场启动的造数批次没有可结束任务",
}

# 状态名 -> 从创建后到达该状态需要依次执行的操作码
_STATE_OPERATIONS: dict[str, tuple[int, ...]] = {
    "init": (),
    "running": (1,),
    "stopped": (1, 2),
}


def _preset_flow_name(client: HawkAdminClient) -> str:
    """优先用指定流程，不存在时回退到环境内的第一条流程。"""
    if PRESET_FLOW_NAME:
        matched = (client.json(client.list_flows(page=1, pageSize=1, flowName=PRESET_FLOW_NAME)).get("data") or {}).get("list") or []
        if matched:
            return PRESET_FLOW_NAME
    flows = (client.json(client.list_flows(page=1, pageSize=1)).get("data") or {}).get("list") or []
    if not flows:
        raise RuntimeError("环境内没有可用流程，无法通过造数准备批次")
    return flows[0]["flowName"]


def existing_flow_name(client: HawkAdminClient) -> str:
    """返回可用于批次造数的存量流程，不调用流程创建接口。"""
    return _preset_flow_name(client)


def _preset_batch_config(client: HawkAdminClient, flow_name: str) -> str | None:
    """取同流程存量批次的 config 作为造数模板（只读）。

    用空 config 建出的批次会瞬间执行完毕，PAUSE / RESTART 抢不到运行态窗口，
    因此复用同流程批次的真实 config，让批次的执行时长接近真实批次。
    """
    fallback: str | None = None
    for page in (1, 2, 3, 4, 5):
        batches = (client.json(client.list_batches(page=page, pageSize=20)).get("data") or {}).get("list") or []
        for item in batches:
            if item.get("flowName") != flow_name or not item.get("config"):
                continue
            if item.get("status") == PROVISIONABLE_STATES["running"]:
                return item["config"]
            fallback = fallback or item["config"]
    return fallback


def _batch_status(client: HawkAdminClient, batch_id: int) -> object:
    return (client.json(client.get_batch(batch_id)).get("data") or {}).get("status")


def prepare_batch(client: HawkAdminClient, scope: DataScope, state: str) -> int:
    """造出一个处于指定状态的批次，并登记清理动作。"""
    # START 只能把批次置为 running，不能保证下游已经创建任务；END
    # 在没有任务时会返回 invalid operation。因此 END 必须使用环境中
    # 已经有任务运行的批次（HAWK_END_RUNNING_BATCH_ID）。
    if state == "running_end":
        raise RuntimeError(UNPROVISIONABLE_REASONS[state])
    if state not in _STATE_OPERATIONS:
        raise ValueError(f"不支持自动构造的批次状态: {state}")
    factory = HawkDataFactory(client, scope)
    project_id, _ = factory.create_project(materialType="图片", notificationLevel=0)
    flow_name = _preset_flow_name(client)
    batch_kwargs = {}
    config = _preset_batch_config(client, flow_name)
    if config:
        batch_kwargs["config"] = config
    batch_id, _ = factory.create_batch(
        project_id=project_id,
        flow_name=flow_name,
        input_file_path=PRESET_INPUT_PATH,
        **batch_kwargs,
    )
    batch_id = int(batch_id)
    for operation in _STATE_OPERATIONS[state]:
        body = client.json(client.operate_batch_with_retry(batch_id, operation))
        if body.get("code") != 0:
            raise AssertionError(f"批次 {batch_id} 执行操作 {operation} 失败: {body}")
    expected = PROVISIONABLE_STATES[state]
    actual = _batch_status(client, batch_id)
    if actual != expected:
        raise AssertionError(
            f"批次 {batch_id} 状态为 {actual}，期望 {expected}；"
            f"批次可能已自动执行完毕，可通过对应的 HAWK_*_BATCH_ID 指定持续运行的批次"
        )
    LOG.info("已准备 %s 状态批次: %s", state, batch_id)
    return batch_id
