"""格式化器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..base import StepIOBase

from ...models.sample import STANDARD


class FormatterBase(StepIOBase, ABC):
    """格式化器：Standard → Standard | Formatted"""

    input_output_map = {STANDARD: STANDARD}

    @abstractmethod
    def process(self, sample: dict) -> Optional[dict]:
        """处理一条，返回格式化后的 dict 或 None（无法转换则丢弃）"""
        ...
