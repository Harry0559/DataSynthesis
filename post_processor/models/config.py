"""配置与管线步骤定义"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .sample import STANDARD

# PipelineStep = (step_type, step_name, params)
PipelineStep = Tuple[str, str, Dict[str, Any]]

# StepKey = (step_type, step_name, occurrence)
StepKey = Tuple[str, str, int]


@dataclass
class PipelineConfig:
    """管线配置"""

    input_path: Path
    output_path: Optional[Path] = None
    input_format: str = STANDARD  # jsonl 输入时的格式
    steps: List[PipelineStep] = None
    step_params: Dict[StepKey, Dict[str, Any]] = None  # (type, name, occurrence) -> params

    def __post_init__(self) -> None:
        if self.steps is None:
            self.steps = []
        if self.step_params is None:
            self.step_params = {}


class ConfigError(Exception):
    """配置错误"""

    pass
