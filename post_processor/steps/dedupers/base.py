"""去重器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..base import StepIOBase

from ...models.sample import STANDARD, ZETA


class DeduperBase(StepIOBase, ABC):
    """去重器：对样本集合整体去重"""

    input_output_map = {
        STANDARD: STANDARD,
        ZETA: ZETA,
    }

    @abstractmethod
    def deduplicate(self, samples: List[dict]) -> List[dict]:
        """对样本列表去重，返回保留的列表"""
        ...
