"""管线执行器：按配置串联步骤并执行"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.config import PipelineConfig, PipelineStep, StepKey
from ..models.sample import RAW, validate_sample
from ..steps import DEDUP, FILTER, FORMAT
from .loader import create_input_source
from .validator import validate_pipeline
from .writer import Writer

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    """运行统计"""

    input_count: int = 0
    output_count: int = 0
    dropped_by_integrate: int = 0
    dropped_by_filter: int = 0
    dropped_by_formatter: int = 0
    dropped_by_dedup: int = 0


def run_postprocessor(config: PipelineConfig) -> RunStats:
    """
    执行管线：加载输入 → 按步骤处理 → 写入输出。
    流式阶段：integrate → filters → formatter → buffer
    批量阶段：dedupers 对 buffer 去重 → writer
    """
    input_source = create_input_source(config.input_path, config.input_format)

    step_params = getattr(config, "step_params", {})
    step_instances = _build_step_instances(config.steps, step_params)
    output_format = validate_pipeline(step_instances, input_source.input_type)

    output_path = _resolve_output_path(config, output_format)
    stream_steps = [(t, s) for t, s in step_instances if t != DEDUP]
    dedup_steps = [s for t, s in step_instances if t == DEDUP]

    stats = RunStats()
    buffer: List[Dict[str, Any]] = []

    for item in input_source.iter_items():
        current_format = input_source.input_type
        step_idx = 0

        if input_source.input_type == RAW:
            integrate_step = stream_steps[0][1]
            sample = integrate_step.process(item)
            if sample is None:
                stats.dropped_by_integrate += 1
                continue
            current_format = integrate_step.output_format_for(RAW)
            step_idx = 1
        else:
            sample = item

        stats.input_count += 1
        dropped = False
        for i in range(step_idx, len(stream_steps)):
            step_type, step_instance = stream_steps[i]
            validated = validate_sample(sample, current_format)
            if validated is None:
                logger.error(
                    "第 %d 步 (%s) 入口格式校验失败（期望 %s），丢弃",
                    i + 1,
                    step_type,
                    current_format,
                )
                dropped = True
                break
            sample = validated

            if step_type == FILTER:
                sample = step_instance.process(sample, current_format)
                if sample is None:
                    stats.dropped_by_filter += 1
                    dropped = True
                    break
                current_format = step_instance.output_format_for(current_format)
            elif step_type == FORMAT:
                sample = step_instance.process(sample, current_format)
                if sample is None:
                    stats.dropped_by_formatter += 1
                    dropped = True
                    break
                current_format = step_instance.output_format_for(current_format)

        if not dropped and sample is not None:
            buffer.append(sample)

    before_dedup = len(buffer)
    for deduper in dedup_steps:
        buffer = deduper.deduplicate(buffer, output_format)
    stats.dropped_by_dedup = before_dedup - len(buffer)

    with Writer(output_path) as w:
        for item in buffer:
            w.write(item)
            stats.output_count += 1

    return stats


def _resolve_output_path(config: PipelineConfig, output_format: str) -> Path:
    """解析输出路径：未指定则 output/data/<format>_data_<timestamp>.jsonl"""
    if config.output_path is not None:
        return config.output_path.resolve()
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("output/data") / f"{output_format}_data_{ts}.jsonl"


def _build_step_instances(
    steps: List[PipelineStep],
    step_params: Dict[StepKey, Dict[str, Any]],
) -> List[tuple[str, Any]]:
    """为每个步骤构建实例：step_params 有则传覆盖，无则传空 dict"""
    from ..steps import get_step

    occurrence: Dict[tuple[str, str], int] = {}
    instances = []
    for step_type, step_name in steps:
        key = (step_type, step_name)
        occ = occurrence.get(key, 0)
        occurrence[key] = occ + 1
        params = step_params.get((step_type, step_name, occ)) or {}
        instances.append((step_type, get_step(step_type, step_name, params)))
    return instances
