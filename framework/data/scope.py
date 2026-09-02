"""单条测试用例的数据隔离和清理上下文。"""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Callable

LOG = logging.getLogger(__name__)


class DataScope:
    """登记测试资源的清理动作，并在用例结束时逆序执行。"""

    def __init__(self, case_id: str):
        normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", case_id).strip("-")
        self.case_id = normalized or "case"
        self._cleanups: list[tuple[str, Callable[[], object]]] = []

    def unique_name(self, resource: str, *, max_length: int = 64) -> str:
        suffix = secrets.token_hex(3)
        prefix = f"{self.case_id}-{resource}-"
        if max_length <= len(suffix):
            return suffix[:max_length]
        return prefix[: max_length - len(suffix)] + suffix

    def track(self, description: str, cleanup: Callable[[], object]) -> None:
        self._cleanups.append((description, cleanup))

    def cleanup(self) -> None:
        for description, cleanup in reversed(self._cleanups):
            try:
                cleanup()
            except Exception:  # pragma: no cover - cleanup failures are environment-dependent
                LOG.warning("测试数据清理失败: %s", description, exc_info=True)
        self._cleanups.clear()
