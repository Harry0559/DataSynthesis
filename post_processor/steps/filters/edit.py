"""编辑数据过滤器：规则判断，保留编辑数据（续写取反）"""

from __future__ import annotations

from typing import Any, Optional, Union

from .base import FilterBase
from .cont import _is_cont


class EditFilter(FilterBase):
    """规则判断：保留编辑数据（续写取反）"""

    def __init__(self, **params: object) -> None:
        self._params = params

    def process(
        self, sample: Union[dict, Any]
    ) -> Optional[Union[dict, Any]]:
        if not isinstance(sample, dict):
            return None
        return sample if not _is_cont(sample) else None
