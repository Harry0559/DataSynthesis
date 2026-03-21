"""Post-processor：整合/过滤/格式化/去重，输出 JSONL"""

from __future__ import annotations

from .models.config import PipelineConfig
from .pipeline.runner import run_postprocessor

__all__ = ["PipelineConfig", "run_postprocessor"]
