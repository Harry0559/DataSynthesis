"""
Git 操作管理模块

TODO: 实现以下功能（可参考 CursorSynthesis 项目的 git/manager.py）：
- get_commits(): 获取仓库 commit 列表
- get_diff(): 获取两个 commit 之间的 diff
- get_file_content_at_commit(): 读取指定 commit 时某文件的内容
- checkout(): 切换到指定 commit
- get_current_branch(): 获取当前分支名
- hide_git_dir(): 隐藏 .git 目录（移到临时位置）
- restore_git_dir(): 恢复 .git 目录
- select_random_repo(): 从目录中随机选择一个 repo
"""

from typing import Optional


def get_commits(repo_path: str, max_count: int = 100) -> list[str]:
    """TODO: git log --format=%H"""
    raise NotImplementedError


def get_diff(repo_path: str, commit_before: str, commit_after: str) -> str:
    """TODO: git diff commit_before..commit_after"""
    raise NotImplementedError


def get_file_content_at_commit(
    repo_path: str, commit: str, file_path: str
) -> Optional[str]:
    """TODO: git show commit:file_path"""
    raise NotImplementedError


def checkout(repo_path: str, ref: str) -> None:
    """TODO: git checkout ref"""
    raise NotImplementedError


def get_current_ref(repo_path: str) -> tuple[str, bool]:
    """
    TODO: 获取当前 ref（分支名或 commit hash）

    Returns:
        (ref, is_branch) 元组
    """
    raise NotImplementedError


def hide_git_dir(repo_path: str) -> str:
    """
    TODO: 将 .git 目录移到临时位置

    Returns:
        .git 的临时存放路径
    """
    raise NotImplementedError


def restore_git_dir(repo_path: str, hidden_path: str) -> None:
    """TODO: 将 .git 目录从临时位置恢复"""
    raise NotImplementedError
