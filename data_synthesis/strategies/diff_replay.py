"""
DiffReplayStrategy：逐步重放 diff

TODO: 实现以下功能：
- 计算 before_content → after_content 的行级 diff
- 将 diff 转为 TypeAction / DeleteAction 序列
- 每 observe_every 个字符插入一个 ObserveAction
- 确定各文件的 initial_content（可能做部分预应用）
"""

from ..core.models import ChangeSet, ObserveConfig, TypePlan
from .base import PlanStrategy


class DiffReplayStrategy(PlanStrategy):
    """逐步重放 diff 的加工策略"""

    def __init__(self, observe_every: int = 5):
        self.observe_every = observe_every

    @property
    def name(self) -> str:
        return "diff_replay"

    def generate(self, change_set: ChangeSet, observe_config: ObserveConfig) -> TypePlan:
        """
        从变更集生成逐步重放计划。

        TODO:
        1. 对每个 FileChange 计算行级 diff
        2. 将 diff hunks 转为有序的 TypeAction / DeleteAction
        3. 每 self.observe_every 个字符插入 ObserveAction
        4. 生成 file_init_states（before_content 或预应用后的内容）
        5. 返回 TypePlan
        """
        raise NotImplementedError("DiffReplayStrategy.generate 尚未实现")
