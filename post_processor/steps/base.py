"""步骤 IO 基类：统一 input_output_map 约定"""

from __future__ import annotations

from abc import ABC
from typing import Dict


class StepIOBase(ABC):
    """
    步骤 IO 基类：子类必须定义 input_output_map。
    格式：{input_type: output_type}。
    """

    input_output_map: Dict[str, str] = {}
