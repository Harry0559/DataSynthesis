"""续写数据过滤器：规则判断，保留续写数据"""

from __future__ import annotations

from typing import Any, Optional, Union

from .base import FilterBase


def _is_cont(sample: dict, format_name: str) -> bool:
    """规则判断：是否为续写数据（待实现）"""
    # TODO: 基于 format_name 分支，zeta 与 standard 判断逻辑不同
    return False


class ContFilter(FilterBase):
    """规则判断：保留续写数据"""

    def __init__(self) -> None:
        pass

    def process(
        self, sample: Union[dict, Any], format_name: str
    ) -> Optional[Union[dict, Any]]:
        if not isinstance(sample, dict):
            return None
        return sample if _is_cont(sample, format_name) else None
