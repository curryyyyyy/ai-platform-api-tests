"""Hawk 平台运行时数据上下文。

测试用例只依赖平台上下文，不直接维护共享环境中的项目、批次或阶段 ID。
新增需求如果需要只读业务数据，应扩展这里的平台能力，而不是新增 pytest
夹具或需求专属 conftest。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from platforms.hawk_admin.client import HawkAdminClient


@dataclass(frozen=True)
class HawkRuntimeContext:
    """为 Hawk 用例提供可复用的只读数据发现能力。"""

    client: HawkAdminClient
    timeout: float = 3.0
    budget: float = 15.0
    max_candidates: int = 12

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeout", max(float(os.getenv("RCB_DISCOVERY_TIMEOUT", self.timeout)), 0.5))
        object.__setattr__(self, "budget", max(float(os.getenv("RCB_DISCOVERY_BUDGET", self.budget)), 3.0))
        object.__setattr__(self, "max_candidates", max(int(os.getenv("RCB_DISCOVERY_MAX_CANDIDATES", self.max_candidates)), 1))
        object.__setattr__(self, "_cache", {})

    def _body(self, response: Any) -> dict[str, Any]:
        payload = self.client.json(response)
        return payload if isinstance(payload, dict) else {}

    def _configured_int(self, name: str) -> int | None:
        raw = os.getenv(name, "").strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            raise AssertionError(f"{name} 必须是整数，当前值: {raw!r}") from None
        if value <= 0:
            raise AssertionError(f"{name} 必须是正整数，当前值: {value}")
        return value

    def _probe_stage_index(self, batch_id: int, stage_count: int) -> int | None:
        configured = self._configured_int("RCB_STAGE_INDEX")
        indexes = (configured,) if configured is not None else range(0, max(stage_count, 1) + 1)
        for index in indexes:
            try:
                body = self._body(
                    self.client.get_stage_cost_detail(
                        batch_id, index, timeout=self.timeout, _retry=False
                    )
                )
            except Exception:
                continue
            data = body.get("data")
            if body.get("code") != 0 or not isinstance(data, dict):
                continue
            if not str(data.get("stageName", "")).strip():
                continue
            try:
                if int(data.get("stageIndex")) == index:
                    return index
            except (TypeError, ValueError):
                continue
        return None

    def _discover(self, *, require_stage: bool, require_cost: bool = False) -> dict[str, Any]:
        cache_key = "stage" if require_stage else ("cost" if require_cost else "stats")
        cache = self._cache
        if cache_key in cache:
            return cache[cache_key]
        deadline = time.monotonic() + self.budget
        configured_detail = self._configured_int("RCB_DETAIL_BATCH_ID")
        candidates: list[dict[str, Any]] = []
        if configured_detail is not None:
            candidates = [{"id": configured_detail}]
        else:
            for page in (1, 2):
                if time.monotonic() >= deadline or len(candidates) >= self.max_candidates:
                    break
                try:
                    body = self._body(
                        self.client.list_batches(
                            page=page, pageSize=50, timeout=self.timeout, _retry=False
                        )
                    )
                except Exception:
                    continue
                data = body.get("data") or {}
                items = data.get("list") if isinstance(data, dict) else None
                if isinstance(items, list):
                    candidates.extend(item for item in items if isinstance(item, dict))
                if len(candidates) >= self.max_candidates:
                    break
        candidates.sort(key=lambda item: str(item.get("status")) in {"4", "5", "6"}, reverse=True)
        candidates = candidates[: self.max_candidates]
        pairs: list[tuple[dict[str, Any], int]] = []
        for item in candidates:
            try:
                pairs.append((item, int(item.get("id", item.get("batchId")))))
            except (TypeError, ValueError):
                continue
        if not pairs:
            raise AssertionError("未发现可访问批次；请检查当前账号的批次列表权限")

        stat_items: dict[str, dict[str, Any]] = {}
        if configured_detail is None:
            try:
                bulk = self._body(
                    self.client.batch_stats(
                        [batch_id for _, batch_id in pairs],
                        timeout=self.timeout,
                        _retry=False,
                    )
                )
            except Exception:
                bulk = {}
            for raw in bulk.get("data", []) if isinstance(bulk.get("data"), list) else []:
                if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
                    stat_items[str(raw.get("batchId"))] = raw["data"]

        for item, batch_id in pairs:
            if configured_detail is None:
                data = stat_items.get(str(batch_id))
            else:
                try:
                    stat_body = self._body(
                        self.client.batch_stat(
                            batch_id, timeout=self.timeout, _retry=False
                        )
                    )
                except Exception:
                    continue
                data = stat_body.get("data")
            if not isinstance(data, dict) or data.get("rpcError"):
                continue
            stats = data.get("stats")
            if not isinstance(stats, list) or not stats:
                continue
            if any(data.get(field, -1) < 0 for field in ("totalCount", "successCount", "failedCount", "abortedCount")):
                continue
            stage_ids: list[int] = []
            for stat in stats:
                if not isinstance(stat, dict):
                    continue
                try:
                    stage_id = int(stat.get("stageId"))
                except (TypeError, ValueError):
                    continue
                if stage_id > 0 and stage_id not in stage_ids:
                    stage_ids.append(stage_id)
            if not stage_ids:
                continue
            if require_cost:
                try:
                    cost_body = self._body(
                        self.client.get_batch_cost_detail(
                            batch_id, timeout=self.timeout, _retry=False
                        )
                    )
                except Exception:
                    continue
                if cost_body.get("code") != 0 or not isinstance(cost_body.get("data"), dict):
                    continue
            stage_index = None
            if require_stage:
                if time.monotonic() >= deadline:
                    break
                stage_index = self._probe_stage_index(batch_id, len(stats))
                if stage_index is None:
                    continue
            result = {"id": batch_id, "item": item, "stat": data, "stage_ids": stage_ids, "stage_index": stage_index}
            cache[cache_key] = result
            return result
        if require_stage:
            message = "需要当前账号可访问、Hawk 统计正常且阶段成本详情可用的批次"
        elif require_cost:
            message = "需要当前账号可访问且批次成本详情接口可用的批次"
        else:
            message = "需要当前账号可访问且 Hawk 统计正常的批次"
        raise AssertionError(f"未发现可用成本看板批次：{message}")

    def project_id(self) -> int:
        cached = self._cache.get("project_id")
        if cached is not None:
            return int(cached)
        configured = self._configured_int("RCB_PROJECT_ID")
        if configured is not None:
            self._cache["project_id"] = configured
            return configured
        candidates: list[int] = []
        try:
            stats = self._discover(require_stage=False)
            project_id = stats["item"].get("projectId")
            if project_id not in (None, ""):
                candidates.append(int(project_id))
        except AssertionError:
            pass
        try:
            body = self._body(
                self.client.list_projects(
                    page=1, pageSize=50, timeout=self.timeout, _retry=False
                )
            )
            items = (body.get("data") or {}).get("list")
            if isinstance(items, list):
                candidates.extend(
                    int(item["id"])
                    for item in items
                    if isinstance(item, dict) and item.get("id") not in (None, "")
                )
        except Exception:
            pass
        for project_id in dict.fromkeys(candidates):
            try:
                body = self._body(
                    self.client.get_project_cost_detail(
                        project_id, timeout=self.timeout, _retry=False
                    )
                )
            except Exception:
                continue
            if body.get("code") == 0 and isinstance(body.get("data"), dict):
                self._cache["project_id"] = project_id
                return project_id
        raise AssertionError(
            "未发现当前账号可访问且成本接口可用的项目；请检查项目权限或配置 RCB_PROJECT_ID"
        )

    def batch_ids(self) -> list[int]:
        raw = os.getenv("RCB_BATCH_IDS", "").strip()
        if raw:
            try:
                values = [int(value.strip()) for value in raw.split(",") if value.strip()]
            except ValueError:
                raise AssertionError(f"RCB_BATCH_IDS 必须是逗号分隔的整数，当前值: {raw!r}") from None
            if not values or not all(value > 0 for value in values):
                raise AssertionError(f"RCB_BATCH_IDS 必须全部为正整数: {values}")
            return values
        return [self._discover(require_stage=False)["id"]]

    def detail_batch_id(self) -> int:
        return int(self._discover(require_stage=False)["id"])

    def cost_batch_id(self) -> int:
        """返回批次成本详情接口可访问的批次。"""
        return int(self._discover(require_stage=False, require_cost=True)["id"])

    def stage_batch_id(self) -> int:
        """返回具备有效阶段成本详情的批次，供阶段详情用例成对使用。"""
        return int(self._discover(require_stage=True)["id"])

    def expected_stage_ids(self) -> list[int]:
        raw = os.getenv("RCB_EXPECTED_STAGE_IDS", "").strip()
        if raw:
            try:
                values = [int(value.strip()) for value in raw.split(",") if value.strip()]
            except ValueError:
                raise AssertionError(f"RCB_EXPECTED_STAGE_IDS 必须是逗号分隔的整数，当前值: {raw!r}") from None
            if not values or not all(value > 0 for value in values):
                raise AssertionError(f"RCB_EXPECTED_STAGE_IDS 必须全部为正整数: {values}")
            return values
        return list(self._discover(require_stage=False)["stage_ids"])

    def stage_index(self) -> int:
        configured = self._configured_int("RCB_STAGE_INDEX")
        if configured is not None:
            return configured
        discovered = self._discover(require_stage=True).get("stage_index")
        if discovered is None:
            raise AssertionError("未发现有效 stageIndex；请确认阶段成本详情可用")
        return int(discovered)
