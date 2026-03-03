"""
GitRepoProvider：从 Git 仓库提取变更

TODO: 实现以下功能：
- 从 git repo 中选择 commit（随机或指定）
- 提取 commit 前后的文件变更（git diff）
- 准备环境：checkout commit、隐藏 .git 目录
- 恢复环境：恢复 .git、切回原始分支

Session 路径约定（在 _manage_environment 中 yield WorkContext 时需设置）：
- source_type = "git-repo"
- source_path_segments = (repo_name, commit_id)
  - repo_name: 仓库目录名，即 os.path.basename(os.path.normpath(repo_path))
  - commit_id: 短 hash，无前缀（如 7 位）
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from ..core.models import ChangeSet, ObserveConfig, TypePlan, WorkContext
from ..strategies.base import PlanStrategy
from .base import TaskProvider


class GitRepoProvider(TaskProvider):
    """从 Git 仓库提取文件变更的 Provider"""

    def __init__(
        self,
        repo_path: str,
        plan_strategy: PlanStrategy,
        observe_config: Optional[ObserveConfig] = None,
        commit: Optional[str] = None,
        random_seed: Optional[int] = None,
    ):
        super().__init__(plan_strategy=plan_strategy, observe_config=observe_config)
        self.repo_path = repo_path
        self.commit = commit
        self.random_seed = random_seed

    @property
    def name(self) -> str:
        return "git_repo"

    def _extract_changes(self) -> ChangeSet:
        """
        从 git 仓库提取文件变更。

        TODO:
        1. 如果未指定 commit，随机选择一个（使用 random_seed）
        2. 获取该 commit 的 parent commit
        3. 计算 parent → commit 的 diff
        4. 对每个变更文件构建 FileChange（before_content, after_content）
        5. 返回 ChangeSet
        """
        raise NotImplementedError("GitRepoProvider._extract_changes 尚未实现")

    @contextmanager
    def _manage_environment(
        self, type_plan: TypePlan
    ) -> Generator[WorkContext, None, None]:
        """
        准备 Git 仓库工作环境。

        TODO:
        进入时：
        1. 记录当前分支/commit（用于恢复）
        2. checkout 到目标 commit
        3. 隐藏 .git 目录（mv .git → 临时位置）
        4. 按 file_init_states 写入文件内容
        5. yield WorkContext

        退出时：
        1. 恢复 .git 目录
        2. checkout 回原始分支/commit
        """
        raise NotImplementedError("GitRepoProvider._manage_environment 尚未实现")
