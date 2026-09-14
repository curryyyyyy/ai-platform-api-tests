"""需求级测试标识规则。

需求 ID 和 case ID 是 Allure 历史趋势的稳定主键；执行时间属于报告 run_id，
不能混入这两个标识。
"""

from __future__ import annotations

import re


_IDENTIFIER_PATTERN = re.compile(r"^REQ-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
_LONG_TIMESTAMP_PATTERN = re.compile(r"(?<![A-Z0-9])\d{12,14}(?![A-Z0-9])")


def validate_requirement_identifiers(requirement_id: str, case_id: str) -> None:
    """校验需求/用例标识可用于跨运行趋势追踪。"""
    requirement = str(requirement_id or "").strip()
    case = str(case_id or "").strip()
    if not _IDENTIFIER_PATTERN.fullmatch(requirement):
        raise ValueError(
            f"需求 ID 格式无效: {requirement!r}；应使用 REQ-需求名[-版本]，不要使用运行时间"
        )
    if not _IDENTIFIER_PATTERN.fullmatch(case):
        raise ValueError(f"case ID 格式无效: {case!r}；应由稳定需求 ID 加 case 后缀组成")
    if not case.startswith(f"{requirement}-"):
        raise ValueError(f"case ID 必须以需求 ID 开头: requirement={requirement}, case={case}")
    if _LONG_TIMESTAMP_PATTERN.search(requirement) or _LONG_TIMESTAMP_PATTERN.search(case):
        raise ValueError("需求 ID/case ID 不得包含 12-14 位运行时间；时间只能进入报告 run_id")
