"""步骤 IO 基类：统一 input_output_map 约定"""

from __future__ import annotations

from abc import ABC
from typing import Dict, Tuple


class StepIOBase(ABC):
    """
    步骤 IO 基类：子类必须定义 input_output_map。
    格式：{input_format: output_format}。
    """

    input_output_map: Dict[str, str] = {}

    @property
    def accepted_input_formats(self) -> Tuple[str, ...]:
        """步骤接受的输入格式列表"""
        return tuple(self.input_output_map.keys())

    def accepts(self, format_name: str) -> bool:
        """步骤是否接受指定格式的输入"""
        return format_name in self.input_output_map

    def output_format_for(self, format_name: str) -> str:
        """给定输入格式，返回对应的输出格式"""
        return self.input_output_map[format_name]
