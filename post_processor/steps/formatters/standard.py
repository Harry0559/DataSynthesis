"""标准格式恒等格式化器"""

from __future__ import annotations

from typing import Optional

from ...models.sample import STANDARD
from .base import FormatterBase


class StandardFormatter(FormatterBase):
    """恒等：StandardSample → 同结构 dict"""

    input_output_map = {STANDARD: STANDARD}

    def __init__(self) -> None:
        pass

    def process(self, sample: dict, format_name: str) -> Optional[dict]:
        return sample if isinstance(sample, dict) else None
