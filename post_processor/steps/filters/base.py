"""过滤器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Union

from ..base import StepIOBase

from ...models.sample import STANDARD, ZETA, ZETA_DEBUG


class FilterBase(StepIOBase, ABC):
    """过滤器：输入 standard、zeta 或 zeta_debug，输出同类型或 None（丢弃）"""

    input_output_map = {
        STANDARD: STANDARD,
        ZETA: ZETA,
        ZETA_DEBUG: ZETA_DEBUG,
    }

    @abstractmethod
    def process(
        self, sample: Union[dict, Any], format_name: str
    ) -> Optional[Union[dict, Any]]:
        """处理一条，返回保留的样本或 None。format_name 用于多格式分支。"""
        ...
