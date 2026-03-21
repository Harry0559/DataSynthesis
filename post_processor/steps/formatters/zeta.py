"""Zeta 格式化器"""

from __future__ import annotations

from typing import Optional

from ...models.sample import STANDARD, ZETA
from .base import FormatterBase


class ZetaFormatter(FormatterBase):
    """Standard → Zeta 格式（骨架，待完善）"""

    input_output_map = {STANDARD: ZETA}

    def __init__(
        self,
        region_radius: tuple[int, int] = (15, 15),
        context_radius: tuple[int, int] = (100, 100),
        with_debug_fields: bool = False,
        **params: object,
    ) -> None:
        self._region_radius = region_radius
        self._context_radius = context_radius
        self._with_debug_fields = with_debug_fields
        self._params = params

    def process(self, sample: dict) -> Optional[dict]:
        # TODO: 实现 zeta 转换，参考 tools/synthetic_data
        # 骨架：最小 zeta 结构以便管线可运行
        return {
            "format": ZETA,
            "input": sample.get("content", ""),
            "ground_truth": sample.get("model_output", ""),
        }
