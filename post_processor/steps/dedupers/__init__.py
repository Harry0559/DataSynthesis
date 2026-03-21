"""去重器：对格式数据集合整体清洗"""

from __future__ import annotations

from .base import DeduperBase
from .simhash import SimHashDeduplicator

__all__ = ["DeduperBase", "SimHashDeduplicator"]
