"""
Diff 计算工具

TODO: 提供 diff 相关的通用函数，供 PlanStrategy 使用：
- compute_line_diff(): 行级 diff
- compute_char_diff(): 字符级 diff
- diff_to_actions(): 将 diff 转为 Action 序列
"""

from typing import Any


def compute_line_diff(before: str, after: str) -> list[dict[str, Any]]:
    """
    TODO: 计算行级 diff

    Returns:
        diff 操作列表，每项包含 {type: "add"|"delete", line, content}
    """
    raise NotImplementedError


def compute_char_diff(before: str, after: str) -> list[dict[str, Any]]:
    """
    TODO: 计算字符级 diff

    Returns:
        diff 操作列表
    """
    raise NotImplementedError
