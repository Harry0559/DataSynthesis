"""
PlanStrategy 抽象基类

加工策略：从 ChangeSet 生成 TypePlan。
这是关键扩展点——不同策略决定如何将文件变更转化为具体的操作序列。
"""

from abc import ABC, abstractmethod

from ..core.models import ChangeSet, ObserveConfig, TypePlan


class PlanStrategy(ABC):
    """加工策略抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...

    @abstractmethod
    def generate(self, change_set: ChangeSet, observe_config: ObserveConfig) -> TypePlan:
        """
        从变更集生成操作计划。

        Args:
            change_set: 文件变更描述
            observe_config: Observe 全局默认配置

        Returns:
            TypePlan 操作计划
        """
        ...
