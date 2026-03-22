"""格式化器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..base import StepIOBase


class FormatterBase(StepIOBase, ABC):
    """格式化器：负责格式间转换。各子类必须定义 input_output_map 声明支持的输入→输出格式。"""

    @abstractmethod
    def process(self, sample: dict, format_name: str) -> Optional[dict]:
        """处理一条，返回格式化后的 dict 或 None（无法转换则丢弃）。format_name 为输入格式。"""
        ...
