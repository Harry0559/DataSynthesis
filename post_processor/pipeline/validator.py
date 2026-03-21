"""管线校验：基于步骤实例与输入类型做类型链校验"""

from __future__ import annotations

from typing import Any, List

from ..models.sample import RAW
from ..steps import DEDUP, FORMAT, INTEGRATE


def _step_accepts(step: Any, current_type: str) -> bool:
    """步骤是否接受当前类型（基于 input_output_map 的 key）"""
    io_map = getattr(step, "input_output_map", {})
    return current_type in io_map


def _step_output(step: Any, current_type: str) -> str:
    """步骤输出类型（基于 input_output_map）"""
    io_map = getattr(step, "input_output_map", {})
    return io_map.get(current_type, current_type)


def _step_accepted_types(step: Any) -> list:
    """步骤接受的输入类型列表（用于错误提示）"""
    io_map = getattr(step, "input_output_map", {})
    return list(io_map.keys())


def validate_pipeline(
    step_instances: List[tuple[str, Any]],
    input_type: str,
) -> str:
    """
    校验管线（基于步骤实例），单循环完成所有检查，返回最终输出类型。
    - 整合器：raw 时必须有且仅有一个且为首步，非 raw 时不允许
    - 格式化器：最多 1 个
    - 去重器：若存在必须在末尾，可多个串联
    - 类型链：相邻步骤输入输出类型匹配
    """
    from ..models.config import ConfigError

    if not step_instances:
        raise ConfigError("管线不能为空")

    current_type = input_type
    integrate_count = 0
    format_count = 0
    seen_dedup = False

    for i, (step_type, step_instance) in enumerate(step_instances):
        if step_type == INTEGRATE:
            if input_type != RAW:
                raise ConfigError(
                    "输入为 jsonl（standard/zeta）时，管线中不允许包含整合器"
                )
            if i != 0:
                raise ConfigError(
                    f"输入为 raw 时，第一个步骤必须是整合器，当前第 {i + 1} 步为 {step_type}"
                )
            integrate_count += 1
            if integrate_count > 1:
                raise ConfigError("整合器最多只能有一个")

        if step_type == FORMAT:
            format_count += 1
            if format_count > 1:
                raise ConfigError("格式化器最多只能有一个")

        if step_type == DEDUP:
            seen_dedup = True
        else:
            if seen_dedup:
                raise ConfigError(
                    "去重器必须在管线末尾，不允许在去重器之后出现其他步骤"
                )

        if not _step_accepts(step_instance, current_type):
            accepted = _step_accepted_types(step_instance)
            raise ConfigError(
                f"管线步骤类型不匹配：步骤 {i + 1} ({step_type}) 期望输入 {accepted}，"
                f"但上一步输出 {current_type}"
            )
        current_type = _step_output(step_instance, current_type)

    if input_type == RAW and integrate_count == 0:
        raise ConfigError("输入为文件夹（Raw）时，必须包含整合器")

    return current_type
