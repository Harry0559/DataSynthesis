"""输入相关数据结构：Raw 状态（三文件）"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


# collected.jsonl 单行结构（TabLogCollector 输出）
CollectedRecord = Dict[str, Any]  # action_index, file, cursor, prev_content, content, model_output, timestamp, format, extra

# type_plan.json 结构
TypePlanData = Dict[str, Any]  # file_init_states, file_final_states, actions, observe_config, metadata

# session_meta.json 结构
SessionMeta = Dict[str, Any]  # timestamp 等


@dataclass
class ProcessingUnit:
    """最小处理单元：一条 collected 记录 + type_plan + session_meta"""

    record: CollectedRecord
    type_plan: TypePlanData
    session_meta: SessionMeta
