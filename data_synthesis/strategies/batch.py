"""
BatchStrategy：按批次输入

TODO: 实现以下功能：
- 计算 diff
- 按 batch_size 合并连续变更为一个 TypeAction
- 每个 batch 结束后插入 ObserveAction
"""

from ..core.models import ChangeSet, ObserveConfig, TypePlan
from .base import PlanStrategy


class BatchStrategy(PlanStrategy):
    """按批次输入的输入重放策略"""

    def __init__(self, batch_size: int = 20):
        self.batch_size = batch_size

    @property
    def name(self) -> str:
        return "batch"

    def generate(self, change_set: ChangeSet, observe_config: ObserveConfig) -> TypePlan:
        """
        从变更集生成批次输入计划。

        TODO:
        1. 对每个 FileChange 计算 diff
        2. 按 batch_size 将连续操作合并为一个 TypeAction
        3. 每个 batch 后插入 ObserveAction
        4. 返回 TypePlan
        """
        raise NotImplementedError("BatchStrategy.generate 尚未实现")
