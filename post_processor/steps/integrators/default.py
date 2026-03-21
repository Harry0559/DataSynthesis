"""默认整合器：collected + type_plan + session_meta → StandardSample"""

from __future__ import annotations

from typing import Optional

from ...models.input import ProcessingUnit
from ...models.sample import StandardSample
from .base import IntegratorBase


class DefaultIntegrator(IntegratorBase):
    """默认整合实现（骨架，待完善）"""

    def __init__(self, **params: object) -> None:
        self._params = params

    def process(self, unit: ProcessingUnit) -> Optional[StandardSample]:
        # TODO: 实现整合逻辑，参考 tools/synthetic_data
        record = unit.record
        type_plan = unit.type_plan
        session_meta = unit.session_meta
        # 骨架：简单拼接
        return {
            "file": record.get("file", ""),
            "cursor": record.get("cursor", {}),
            "prev_content": record.get("prev_content", ""),
            "content": record.get("content", ""),
            "model_output": record.get("model_output", ""),
            "action_index": record.get("action_index"),
            "timestamp": record.get("timestamp", ""),
            "metadata": {
                "source_metadata": type_plan.get("metadata", {}).get("source_metadata"),
                "session_metadata": session_meta,
            },
        }
