"""LLM 有效性过滤器：借助 LLM 判断标准格式样本是否有效"""

from __future__ import annotations

from typing import Any, Optional, Union

from .base import FilterBase


class LlmFilter(FilterBase):
    """借助 LLM 判断标准格式有效性（待实现）"""

    def __init__(self) -> None:
        pass

    def process(
        self, sample: Union[dict, Any], format_name: str
    ) -> Optional[Union[dict, Any]]:
        # TODO: 调用 LLM 判断有效性，可按 format_name 分支
        if not isinstance(sample, dict):
            return None
        return sample
