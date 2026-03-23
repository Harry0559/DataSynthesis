"""排序器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ...models.sample import FORMAT_NAMES
from ..base import StepIOBase


class SorterBase(StepIOBase, ABC):
    """排序器：对样本列表整体处理。默认支持 FORMAT_NAMES 中所有格式，输入输出格式相同。"""

    input_output_map = {fmt: fmt for fmt in FORMAT_NAMES}

    @abstractmethod
    def sort(self, samples: List[dict]) -> List[dict]:
        """对样本列表整体处理，返回（可能重排后的）列表。"""
        ...
