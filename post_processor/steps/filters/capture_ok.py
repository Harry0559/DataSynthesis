"""按 extra.capture_ok（严格布尔 False）过滤标准格式样本"""

from __future__ import annotations

from typing import Any, Optional

from ...models.sample import STANDARD, StandardSample
from .base import FilterBase


def _is_capture_fail(extra: Any) -> bool:
    """extra 为 dict 且含布尔类型的 capture_ok，且值为 False。"""
    if not isinstance(extra, dict):
        return False
    if "capture_ok" not in extra:
        return False
    v = extra["capture_ok"]
    return isinstance(v, bool) and v is False


class CaptureOkFilter(FilterBase):
    """仅标准格式。默认丢弃 capture_ok 为 ``False`` 的样本；可配置为仅保留此类样本。"""

    input_output_map = {STANDARD: STANDARD}

    def __init__(self, keep_capture_fail_only: bool = False) -> None:
        """
        :param keep_capture_fail_only:
            False（默认）→ 命中「capture_ok 为布尔 False」则丢弃，否则保留。
            True → 仅保留命中该条件的样本，其余丢弃。
        """
        self._keep_capture_fail_only = keep_capture_fail_only

    def process(
        self, sample: StandardSample, format_name: str
    ) -> Optional[StandardSample]:
        if format_name != STANDARD:
            return None
        match = _is_capture_fail(sample.get("extra"))
        if self._keep_capture_fail_only:
            return sample if match else None
        return None if match else sample
