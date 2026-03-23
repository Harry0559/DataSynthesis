"""随机打乱排序器"""

from __future__ import annotations

import random
from typing import List

from .base import SorterBase


class ShuffleSorter(SorterBase):
    """对样本列表随机打乱。"""

    def __init__(self, seed: int | None = None) -> None:
        if seed is not None:
            self._seed = seed
        else:
            self._seed = random.randint(0, 2**31 - 1)
        print(f"ShuffleSorter seed={self._seed}")

    def sort(self, samples: List[dict]) -> List[dict]:
        out = list(samples)
        random.seed(self._seed)
        random.shuffle(out)
        return out
