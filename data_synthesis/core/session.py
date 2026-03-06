"""
Session 编排模块

提供 run_session()，按四个阶段编排整个 Pipeline：
1. 获取任务（TaskProvider 内部完成提取+生成+准备）
2. 准备编辑器
3. 执行输入 + 采集
4. 恢复环境（TaskProvider 退出上下文管理器时自动完成）
"""

import json
import os
from datetime import datetime
from typing import Optional

from ..collectors.base import Collector
from ..editors.base import EditorAdapter
from ..executors.executor import Executor
from ..providers.base import TaskProvider
from .models import ObserveConfig, TypePlan, WorkContext


def run_session(
    task_provider: TaskProvider,
    editor: Optional[EditorAdapter] = None,
    collector: Optional[Collector] = None,
    observe_config: Optional[ObserveConfig] = None,
    type_interval: float = 0.05,
    vi_mode: bool = False,
    dry_run: bool = False,
    output_dir: str = "output/collected",
) -> bool:
    """
    执行一次完整的 Pipeline。

    Args:
        task_provider: 任务提供者（负责数据源处理 + 环境管理）
        editor: 编辑器适配器（dry-run 模式可为 None）
        collector: 采集器（可选，None 时不采集）
        observe_config: Observe 全局配置（None 时使用 TypePlan 中的配置）
        type_interval: 字符输入间隔（秒）
        vi_mode: 是否启用 Vi 模式
        dry_run: 是否为 dry-run 模式（不实际操作编辑器）
        output_dir: 输出根目录（全新采集时为默认 output/collected；复现时为 plan 所在目录/reproduce）

    Returns:
        是否成功
    """
    if not dry_run and editor is None:
        raise ValueError("非 dry-run 时需提供 EditorAdapter")

    print("\n" + "=" * 50)
    print("DataSynthesis Pipeline")
    print("=" * 50)

    # ====== 阶段一 + 阶段二：获取任务（含环境准备） ======
    with task_provider.provide() as task:
        type_plan = task.type_plan
        context = task.context

        effective_observe_config = observe_config or type_plan.observe_config

        print(f"\n[阶段一] 任务就绪")
        print(f"  工作目录: {context.work_dir}")
        print(f"  文件数量: {len(type_plan.file_init_states)}")
        print(f"  操作数量: {len(type_plan.actions)}")

        # ====== 阶段二：准备编辑器 ======
        print(f"\n[阶段二] 准备编辑器环境")
        if not dry_run:
            editor.restart(context.work_dir)  # type: ignore[union-attr]
        else:
            print("  (dry-run: 跳过编辑器操作)")

        # ====== 阶段三：执行 ======
        print(f"\n[阶段三] 开始执行")

        session_dir: Optional[str] = None
        if not dry_run:
            session_dir = _create_session_dir(output_dir, type_plan, context)
            _save_session_meta(session_dir, type_plan, context)
            type_plan.to_json(os.path.join(session_dir, "type_plan.json"))
            print(f"  输出目录: {session_dir}")

        if collector and session_dir:
            collector.init_session(
                session_dir, effective_observe_config, work_context=context
            )

        executor = Executor(
            editor=editor,
            collector=collector,
            observe_config=effective_observe_config,
            type_interval=type_interval,
            vi_mode=vi_mode,
            dry_run=dry_run,
        )
        executor.execute(type_plan)

        if collector:
            collector.finalize()

        if session_dir:
            print(f"\n  数据已保存: {session_dir}")

    # ====== 阶段四：自动清理（退出 with）======
    print(f"\n[阶段四] 环境已恢复")
    print("\n" + "=" * 50)
    print("Pipeline 完成")
    print("=" * 50)

    return True


def _sanitize_segment(segment: str) -> str:
    """将路径段中的非法字符替换为下划线，避免目录注入"""
    s = segment.replace("/", "_").replace("\\", "_").strip()
    return s or "unknown"


def _create_session_dir(
    output_dir: str, type_plan: TypePlan, context: WorkContext
) -> str:
    """
    创建会话输出目录。

    - 当 context 带 source_type / source_path_segments 时：
      output_dir / source_type / seg1 / seg2 / session_YYYYMMDD_HHMMSS
    - 否则（如复现）：output_dir / session_YYYYMMDD_HHMMSS
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if context.source_type and context.source_path_segments:
        segments = [
            _sanitize_segment(context.source_type),
            *(_sanitize_segment(s) for s in context.source_path_segments),
            f"session_{timestamp}",
        ]
        session_dir = os.path.join(output_dir, *segments)
    else:
        session_dir = os.path.join(output_dir, f"session_{timestamp}")
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def _save_session_meta(
    session_dir: str, type_plan: TypePlan, context: WorkContext
) -> None:
    """保存会话元数据"""
    meta = {
        "timestamp": datetime.now().isoformat(),
        "work_dir": context.work_dir,
        "file_count": len(type_plan.file_init_states),
        "action_count": len(type_plan.actions),
        "metadata": type_plan.metadata,
    }
    meta_path = os.path.join(session_dir, "session_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
