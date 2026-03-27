"""
Batch 编排模块

提供 run_batch()：在 BatchConfig 约束下循环调用 run_session，
依赖 BatchProvider 子类通过 iter_task_providers() 提供一串 TaskProvider。
"""

import time
from datetime import datetime
from typing import Iterator, Optional, Protocol

from ..collectors.base import Collector
from ..editors.base import EditorAdapter
from ..providers.base import TaskProvider

from .models import BatchConfig, SessionConfig
from .session import run_session


class BatchTaskProvider(Protocol):
    """批量任务提供者协议：可迭代产生多个 TaskProvider（每个对应一次 pipeline）。"""

    def iter_task_providers(self) -> Iterator[TaskProvider]:
        ...


def run_batch(
    batch_provider: BatchTaskProvider,
    config: SessionConfig,
    editor: Optional[EditorAdapter] = None,
    collector: Optional[Collector] = None,
    batch_config: Optional[BatchConfig] = None,
) -> None:
    """按 BatchConfig 配置批量执行多个 Pipeline，不打断单次 pipeline。"""
    if batch_config is None:
        batch_config = BatchConfig()

    start_ts = time.time()
    executed_total = 0
    success_count = 0
    failure_count = 0
    cooldown_count = 0
    cooldown_total_seconds = 0.0
    stop_reason = "normal"  # "timeout" / "max_items" / "normal"

    for task_provider in batch_provider.iter_task_providers():
        # 批量约束检查：在开始下一条之前判断，不打断正在执行的 pipeline
        if batch_config.max_duration_seconds is not None:
            elapsed = time.time() - start_ts
            if elapsed >= batch_config.max_duration_seconds:
                stop_reason = "timeout"
                break
        if batch_config.max_items_total is not None:
            if executed_total >= batch_config.max_items_total:
                stop_reason = "max_items"
                break

        ok = run_session(
            task_provider=task_provider,
            config=config,
            editor=editor,
            collector=collector,
        )
        executed_total += 1
        if ok:
            success_count += 1
        else:
            failure_count += 1

        # 周期性冷却：仅在两条 pipeline 之间执行，不打断单次 pipeline
        if (
            batch_config.cooldown_every_n is not None
            and batch_config.cooldown_every_n > 0
            and batch_config.cooldown_seconds > 0
            and executed_total % batch_config.cooldown_every_n == 0
        ):
            print(
                f"  [batch-cooldown] 已执行 {executed_total} 条，"
                f"休息 {batch_config.cooldown_seconds:.2f} 秒..."
            )
            time.sleep(batch_config.cooldown_seconds)
            cooldown_count += 1
            cooldown_total_seconds += batch_config.cooldown_seconds

    end_ts = time.time()
    total_duration = end_ts - start_ts

    # 总时长格式化为通用 HH:MM:SS 形式
    total_seconds = int(round(total_duration))
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # 使用当前系统时区的人类可读开始/结束时间
    start_dt = datetime.fromtimestamp(start_ts)
    end_dt = datetime.fromtimestamp(end_ts)
    start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    if stop_reason == "timeout":
        reason_msg = "达到批量执行时间上限"
    elif stop_reason == "max_items":
        reason_msg = "达到批量执行条目上限"
    else:
        reason_msg = "正常遍历完所有可用条目"

    print("\n========== 批量执行统计 ==========")
    print(f"  开始时间: {start_str}")
    print(f"  结束时间: {end_str}")
    print(f"  总耗时: {duration_str}")
    print(f"  执行总条数: {executed_total}")
    print(f"  成功条数: {success_count}")
    print(f"  失败条数: {failure_count}")
    print(f"  停止原因: {reason_msg}")

    if batch_config.max_duration_seconds is not None:
        print(f"  配置的时间上限: {batch_config.max_duration_seconds} 秒")
    if batch_config.max_items_total is not None:
        print(f"  配置的总条数上限: {batch_config.max_items_total}")
    if batch_config.cooldown_every_n is not None and batch_config.cooldown_seconds > 0:
        cooldown_seconds_int = int(round(cooldown_total_seconds))
        cd_h, cd_rem = divmod(cooldown_seconds_int, 3600)
        cd_m, cd_s = divmod(cd_rem, 60)
        cooldown_duration_str = f"{cd_h:02d}:{cd_m:02d}:{cd_s:02d}"
        print(
            "  周期性冷却: "
            f"每 {batch_config.cooldown_every_n} 条休息 "
            f"{batch_config.cooldown_seconds:.2f} 秒"
        )
        print(f"  冷却次数: {cooldown_count}")
        print(f"  冷却总时长: {cooldown_duration_str}")

    print("================================\n")
