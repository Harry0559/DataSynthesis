"""默认整合器：collected + type_plan + session_meta → StandardSample"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...models.input import ProcessingUnit
from ...models.sample import STANDARD, StandardSample
from .base import IntegratorBase


def _build_init_final_maps(type_plan_data: Dict[str, Any]) -> tuple[Dict[str, str], Dict[str, str]]:
    """从 type_plan 构建 init_map 与 final_map（relative_path -> content）"""
    init_map: Dict[str, str] = {}
    final_map: Dict[str, str] = {}

    for f in type_plan_data.get("file_init_states", []):
        rel = f.get("relative_path")
        if isinstance(rel, str):
            init_map[rel] = f.get("content", "")

    for f in type_plan_data.get("file_final_states", []):
        rel = f.get("relative_path")
        if isinstance(rel, str):
            final_map[rel] = f.get("content", "")

    return init_map, final_map


def _compute_edit_history_from_init(actions: List[Dict], action_index: int) -> List[Dict]:
    """取 actions[0:action_index] 中所有非 observe 动作"""
    prefix = actions[:action_index]
    return [a for a in prefix if a.get("type") != "observe"]


def _compute_edit_history_from_prev(actions: List[Dict], action_index: int) -> List[Dict]:
    """从 action_index-1 向前找最近 observe，取其后到 action_index 的非 observe 动作"""
    last_obs_idx: Optional[int] = None
    for i in range(action_index - 1, -1, -1):
        if actions[i].get("type") == "observe":
            last_obs_idx = i
            break

    start = 0 if last_obs_idx is None else last_obs_idx + 1
    segment = actions[start:action_index]
    return [a for a in segment if a.get("type") != "observe"]


def _build_metadata(
    type_plan: Dict[str, Any],
    session_meta: Dict[str, Any],
    collected_idx: Optional[int],
) -> Dict[str, Any]:
    """构造 metadata：溯源用，三个字段始终存在，缺失时为 None"""
    source_metadata = (type_plan.get("metadata") or {}).get("source_metadata")
    session_timestamp = session_meta.get("timestamp") if session_meta else None
    return {
        "source_metadata": source_metadata,
        "session_timestamp": session_timestamp,
        "collected_idx": collected_idx,
    }


class DefaultIntegrator(IntegratorBase):
    """默认整合实现：collected + type_plan + session_meta → 标准格式"""

    def __init__(self) -> None:
        self._id_counter = 0

    def process(self, unit: ProcessingUnit) -> Optional[StandardSample]:
        record = unit.record
        type_plan = unit.type_plan
        session_meta = unit.session_meta

        action_index = record.get("action_index")
        if not isinstance(action_index, int):
            return None

        file = record.get("file", "")
        cursor = record.get("cursor", {})
        prev_content = record.get("prev_content", "")
        content = record.get("content", "")
        model_output = record.get("model_output", "")
        timestamp = record.get("timestamp", "")
        collector = record.get("format", "")

        init_map, final_map = _build_init_final_maps(type_plan)
        init_content = init_map.get(file, "")
        final_content = final_map.get(file, "")

        actions: List[Dict] = type_plan.get("actions", [])
        edit_from_init = _compute_edit_history_from_init(actions, action_index)
        edit_from_prev = _compute_edit_history_from_prev(actions, action_index)

        metadata = _build_metadata(
            type_plan,
            session_meta,
            getattr(unit, "collected_idx", None),
        )

        self._id_counter += 1
        sample_id = self._id_counter

        return {
            "id": sample_id,
            "file": file,
            "cursor": cursor,
            "init_content": init_content,
            "prev_content": prev_content,
            "content": content,
            "final_content": final_content,
            "model_output": model_output,
            "edit_history_from_init": edit_from_init,
            "edit_history_from_prev": edit_from_prev,
            "timestamp": timestamp,
            "collector": collector,
            "format": STANDARD,
            "metadata": metadata,
        }
