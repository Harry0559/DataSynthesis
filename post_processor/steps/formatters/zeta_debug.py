"""Zeta Debug 格式化器：Standard → Zeta Debug"""

from __future__ import annotations

from typing import Optional

from ...models.sample import STANDARD, ZETA_DEBUG, StandardSample, ZetaDebugSample
from .base import FormatterBase
from .zeta_impl import build_zeta_io, to_posix_path


class ZetaDebugFormatter(FormatterBase):
    """Standard → Zeta Debug 格式。输出 17 字段用于调试。"""

    input_output_map = {STANDARD: ZETA_DEBUG}

    def __init__(
        self,
        region_radius_range: tuple[int, int] = (15, 15),
        context_radius_range: tuple[int, int] = (100, 100),
    ) -> None:
        self._region_radius_range = region_radius_range
        self._context_radius_range = context_radius_range
        self._id_counter = 0

    def process(
        self, sample: StandardSample, format_name: str
    ) -> Optional[ZetaDebugSample]:
        norm_file = to_posix_path(sample.get("file", ""))
        source_metadata = (sample.get("metadata") or {}).get("source_metadata") or {}

        io_result = build_zeta_io(
            standard_sample=sample,
            source_metadata=source_metadata,
            norm_file=norm_file,
            region_radius_min=self._region_radius_range[0],
            region_radius_max=self._region_radius_range[1],
            context_radius_min=self._context_radius_range[0],
            context_radius_max=self._context_radius_range[1],
        )
        if io_result is None:
            return None

        input_text, ground_truth, ground_truth_content = io_result
        self._id_counter += 1

        return {
            "id": self._id_counter,
            "file": norm_file,
            "input": input_text,
            "ground_truth": ground_truth,
            "ground_truth_content": ground_truth_content,
            "cursor": sample.get("cursor") or {},
            "init_content": sample.get("init_content", ""),
            "prev_content": sample.get("prev_content", ""),
            "content": sample.get("content", ""),
            "final_content": sample.get("final_content", ""),
            "model_output": sample.get("model_output", "") or "",
            "edit_history_from_init": sample.get("edit_history_from_init", []),
            "edit_history_from_prev": sample.get("edit_history_from_prev", []),
            "timestamp": sample.get("timestamp", ""),
            "collector": sample.get("collector", ""),
            "format": ZETA_DEBUG,
            "metadata": sample.get("metadata") or {},
        }
