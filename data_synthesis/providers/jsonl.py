"""
JsonlProvider：从 JSONL 文件加载变更记录

TODO: 实现以下功能：
- 读取 JSONL 文件，每行是一个变更记录
- 选择一条记录（随机或指定索引）
- 解析记录中的文件变更信息
- 准备环境：创建临时目录，写入初始文件内容
- 恢复环境：删除临时目录

Session 路径约定（在 _manage_environment 中 yield WorkContext 时需设置）：
- source_type = "jsonl"
- source_path_segments = (jsonl_basename, entry_id)
  - jsonl_basename: 文件名，如 os.path.basename(jsonl_path)
  - entry_id: 该条记录的 "id" 字段值（每条记录需含 "id" 字段）

JSONL 记录格式待定义，初步设想需包含 "id" 及文件变更信息。
"""

from contextlib import contextmanager
from typing import Generator, Optional

from ..core.models import ChangeSet, ObserveConfig, TypePlan, WorkContext
from ..strategies.base import PlanStrategy
from .base import TaskProvider


class JsonlProvider(TaskProvider):
    """从 JSONL 文件加载变更记录的 Provider"""

    def __init__(
        self,
        jsonl_path: str,
        plan_strategy: PlanStrategy,
        observe_config: Optional[ObserveConfig] = None,
        sample_index: Optional[int] = None,
        random_seed: Optional[int] = None,
    ):
        super().__init__(plan_strategy=plan_strategy, observe_config=observe_config)
        self.jsonl_path = jsonl_path
        self.sample_index = sample_index
        self.random_seed = random_seed

    @property
    def name(self) -> str:
        return "jsonl"

    def _extract_changes(self) -> ChangeSet:
        """
        从 JSONL 文件提取文件变更。

        TODO:
        1. 读取 JSONL 文件
        2. 选择一条记录（根据 sample_index 或 random_seed 随机选）
        3. 解析记录中的 before_content / after_content
        4. 构建 FileChange 列表
        5. 返回 ChangeSet
        """
        raise NotImplementedError("JsonlProvider._extract_changes 尚未实现")

    @contextmanager
    def _manage_environment(
        self, type_plan: TypePlan
    ) -> Generator[WorkContext, None, None]:
        """
        创建临时工作目录。

        TODO:
        1. 创建临时目录
        2. 按 file_init_states 写入文件
        3. yield WorkContext
        4. 退出时删除临时目录
        """
        raise NotImplementedError("JsonlProvider._manage_environment 尚未实现")
