"""LLM 有效性过滤器：借助 LLM 判断样本有效性"""

from __future__ import annotations

from typing import Optional

from ...models.sample import STANDARD, ZETA_DEBUG
from .base import FilterBase


class LlmFilter(FilterBase):
    """借助 LLM 判断有效性（待实现）。支持 standard 或 zeta_debug 输入。"""

    input_output_map = {STANDARD: STANDARD, ZETA_DEBUG: ZETA_DEBUG}

    def __init__(self) -> None:
        pass

    def process(self, sample: dict, format_name: str) -> Optional[dict]:
        # TODO: 调用 LLM 判断有效性，可按 format_name 分支
        if not isinstance(sample, dict):
            return None
        return sample
