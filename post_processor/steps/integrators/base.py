"""整合器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from ...models.sample import RAW, STANDARD
from ..base import StepIOBase

if TYPE_CHECKING:
    from ...models.input import ProcessingUnit
    from ...models.sample import StandardSample


class IntegratorBase(StepIOBase, ABC):
    """整合器：将 Raw (ProcessingUnit) 转为 StandardSample"""

    input_output_map = {RAW: STANDARD}

    @abstractmethod
    def process(self, unit: "ProcessingUnit") -> Optional["StandardSample"]:
        """处理一条，返回 StandardSample 或 None（丢弃）"""
        ...
