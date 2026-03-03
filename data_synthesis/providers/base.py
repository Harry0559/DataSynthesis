"""
TaskProvider 抽象基类

TaskProvider 是处理数据源的核心模块，负责：
1. 从数据源提取文件变更（_extract_changes）
2. 调用 PlanStrategy 生成 TypePlan
3. 准备工作环境（_manage_environment）
4. 退出时恢复原始状态

子类只需实现 _extract_changes() 和 _manage_environment()，
provide() 模板方法自动编排整个流程。
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Generator, Optional

from ..core.models import ChangeSet, ObserveConfig, Task, TypePlan, WorkContext
from ..strategies.base import PlanStrategy


class TaskProvider(ABC):
    """任务提供者抽象基类"""

    def __init__(
        self,
        plan_strategy: Optional[PlanStrategy] = None,
        observe_config: Optional[ObserveConfig] = None,
    ):
        self.plan_strategy = plan_strategy
        self.observe_config = observe_config or ObserveConfig()

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        ...

    @abstractmethod
    def _extract_changes(self) -> ChangeSet:
        """从数据源提取文件变更"""
        ...

    @abstractmethod
    @contextmanager
    def _manage_environment(
        self, type_plan: TypePlan
    ) -> Generator[WorkContext, None, None]:
        """
        准备和恢复工作环境（上下文管理器）。

        进入时：按 type_plan.file_init_states 准备文件系统。
        退出时：恢复到实验前状态。
        """
        ...

    @contextmanager
    def provide(self) -> Generator[Task, None, None]:
        """
        提供一个可执行任务（模板方法）。

        流程：提取变更 → PlanStrategy 生成计划 → 准备环境 → yield Task → 恢复环境。
        """
        change_set = self._extract_changes()

        if self.plan_strategy is None:
            raise ValueError(f"{self.name} 需要提供 PlanStrategy")
        type_plan = self.plan_strategy.generate(change_set, self.observe_config)

        with self._manage_environment(type_plan) as work_context:
            yield Task(type_plan=type_plan, context=work_context)
