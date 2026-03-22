"""SimHash 去重器"""

from __future__ import annotations

from typing import List

from ...models.sample import ZETA
from .base import DeduperBase


class SimHashDeduplicator(DeduperBase):
    """基于 SimHash 的去重（骨架，待完善）"""

    def __init__(
        self,
        format_name: str = ZETA,
        threshold: float = 0.9,
        shuffle: bool = False,
        seed: int | None = None,
        **params: object,
    ) -> None:
        self._format_name = format_name
        self._threshold = threshold
        self._shuffle = shuffle
        self._seed = seed
        self._params = params

    def deduplicate(self, samples: List[dict], format_name: str) -> List[dict]:
        # TODO: 实现 SimHash 去重，参考 tools/deduplication，可按 format_name 分支
        return samples  # 骨架：原样返回
