"""续写数据过滤器：规则判断，保留续写数据"""

from __future__ import annotations

from typing import Optional

from ...models.sample import ZETA_DEBUG, ZetaDebugSample
from .base import FilterBase
from .cont_edit_impl import is_continuation


class ContFilter(FilterBase):
    """规则判断：保留续写数据。仅支持 zeta_debug 输入。"""

    input_output_map = {ZETA_DEBUG: ZETA_DEBUG}

    def __init__(self) -> None:
        pass

    def process(
        self, sample: ZetaDebugSample, format_name: str
    ) -> Optional[ZetaDebugSample]:
        return sample if is_continuation(sample) else None
