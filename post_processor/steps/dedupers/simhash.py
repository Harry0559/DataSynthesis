"""SimHash 去重器：流式处理"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional

from ...models.sample import ZETA, ZETA_DEBUG
from .base import DeduperBase


# === SimHash 指纹算法 ===

@dataclass
class SimHash:
    """SimHash 指纹，用于文本相似度计算。"""

    fingerprint: int
    hash_bits: int

    @staticmethod
    def _stable_hash(word: str, hash_bits: int = 64) -> int:
        """对单个 token 进行确定性哈希。"""
        h = hashlib.sha256(word.encode("utf-8")).digest()
        val = int.from_bytes(h[:8], "big")
        if hash_bits >= 64:
            return val
        mask = (1 << hash_bits) - 1
        return val & mask

    @classmethod
    def from_text(cls, text: str, hash_bits: int = 64) -> "SimHash":
        """从文本构造 SimHash 指纹。"""
        words = re.findall(r"\w+", text.lower())
        vector = [0] * hash_bits
        for word in words:
            h = cls._stable_hash(word, hash_bits=hash_bits)
            for i in range(hash_bits):
                bitmask = 1 << i
                if h & bitmask:
                    vector[i] += 1
                else:
                    vector[i] -= 1
        fingerprint = 0
        for i in range(hash_bits):
            if vector[i] > 0:
                fingerprint |= 1 << i
        return cls(fingerprint, hash_bits)

    def similarity(self, other: "SimHash") -> float:
        """相似度 = 1 - 归一化汉明距离。"""
        if self.hash_bits != other.hash_bits:
            raise RuntimeError("hash_bits 不一致")
        xor_result = self.fingerprint ^ other.fingerprint
        hamming_distance = xor_result.bit_count()
        return 1 - (hamming_distance / self.hash_bits)


# === SimHash 去重器 ===

def _text_from_sample(sample: dict, format_name: str) -> str:
    """从 ZETA/ZETA_DEBUG 样本中提取用于 SimHash 的文本。"""
    inp = sample.get("input", "")
    gt = sample.get("ground_truth", "")
    return (inp or "") + (gt or "")


class SimHashDeduplicator(DeduperBase):
    """基于 SimHash 的流式去重，仅支持 zeta、zeta_debug 格式。"""

    input_output_map = {ZETA: ZETA, ZETA_DEBUG: ZETA_DEBUG}

    def __init__(self, threshold: float = 0.9) -> None:
        self._threshold = threshold
        self._seen: List[SimHash] = []

    def process(self, sample: dict, format_name: str) -> Optional[dict]:
        if format_name not in self.input_output_map:
            return None
        text = _text_from_sample(sample, format_name)
        simhash = SimHash.from_text(text)
        for h in self._seen:
            if simhash.similarity(h) > self._threshold:
                return None
        self._seen.append(simhash)
        return sample
