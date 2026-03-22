"""过滤器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..base import StepIOBase


class FilterBase(StepIOBase, ABC):
    """过滤器：负责样本过滤。各子类必须定义 input_output_map 声明支持的输入→输出格式。"""

    @abstractmethod
    def process(self, sample: dict, format_name: str) -> Optional[dict]:
        """处理一条，返回保留的样本或 None。format_name 用于多格式分支。"""
        ...
