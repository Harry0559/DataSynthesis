"""
PlanFileProvider：从 JSON 文件加载 TypePlan

用于"先生成计划 → 手工调整 → 再执行"的工作流。
不需要 PlanStrategy，直接加载已有的 TypePlan。
"""

import os
import tempfile
from contextlib import contextmanager
from typing import Generator

from ..core.models import Task, TypePlan, WorkContext
from .base import TaskProvider


class PlanFileProvider(TaskProvider):
    """从 JSON 文件加载 TypePlan 的 Provider"""

    def __init__(self, plan_path: str):
        super().__init__(plan_strategy=None)
        self.plan_path = plan_path

    @property
    def name(self) -> str:
        return "plan_file"

    def _extract_changes(self):
        raise NotImplementedError("PlanFileProvider 直接加载 TypePlan，不使用此方法")

    @contextmanager
    def _manage_environment(
        self, type_plan: TypePlan
    ) -> Generator[WorkContext, None, None]:
        """创建临时工作目录，按 file_init_states 写入文件"""
        with tempfile.TemporaryDirectory(prefix="data_synthesis_") as tmp_dir:
            file_paths: dict[str, str] = {}

            for file_state in type_plan.file_init_states:
                abs_path = os.path.join(tmp_dir, file_state.relative_path)
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(file_state.content)
                file_paths[file_state.relative_path] = abs_path
                print(
                    f"  写入文件: {file_state.relative_path} "
                    f"({len(file_state.content)} 字符)"
                )

            yield WorkContext(work_dir=tmp_dir, file_paths=file_paths)
            print("  临时目录已清理")

    @contextmanager
    def provide(self) -> Generator[Task, None, None]:
        """直接从 JSON 加载 TypePlan（跳过 extract + plan 阶段）"""
        type_plan = TypePlan.from_json(self.plan_path)
        print(f"  从文件加载计划: {self.plan_path}")

        with self._manage_environment(type_plan) as work_context:
            yield Task(type_plan=type_plan, context=work_context)
