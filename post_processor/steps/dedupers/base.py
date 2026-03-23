"""去重器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..base import StepIOBase


class DeduperBase(StepIOBase, ABC):
    """去重器：流式处理，逐条判断是否重复。各子类必须定义 input_output_map。"""

    @abstractmethod
    def process(self, sample: dict, format_name: str) -> Optional[dict]:
        """处理一条，返回保留的样本或 None（重复则丢弃）。"""
        ...
