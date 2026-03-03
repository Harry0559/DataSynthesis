"""
DiffHunkStrategy：按 diff hunk 重放文件变更

基于行级 diff（difflib.SequenceMatcher）将 FileChange 拆分为若干连续变更块（opcode/hunk），
对每个 hunk 依次执行：
    - 删除 before 段中的旧行（delete/replace）
    - 插入 after 段中的新行（insert/replace）
    - 在该 hunk 结束时插入一次 ObserveAction

注意：
- 重放过程中维护 current_line（1-base），表示当前缓冲区中下一次操作所在的行号。
- delete 时，逐行在 current_line 做 DeleteAction，删除后下一行会顶上来，current_line 不变。
- insert 时，在 current_line 逐行 Type 新行，每插入一行 current_line += 1。
"""

from __future__ import annotations

import difflib
from typing import List

from ..core.models import (
    ChangeSet,
    DeleteAction,
    FileFinalState,
    FileInitState,
    ObserveAction,
    ObserveConfig,
    TypeAction,
    TypePlan,
)
from .base import PlanStrategy


class DiffHunkStrategy(PlanStrategy):
    """按 diff hunk 生成 TypePlan 的策略"""

    def __init__(self) -> None:
        # 目前不做更细的 batch 拆分，后续如需按字符/Token 再细分可在单个 hunk 内继续切分。
        ...

    @property
    def name(self) -> str:
        return "diff_hunk"

    def generate(self, change_set: ChangeSet, observe_config: ObserveConfig) -> TypePlan:
        """
        从 ChangeSet 生成按 diff hunk 重放的 TypePlan。

        对每个 FileChange：
        - file_init_states 使用 before_content 作为初始内容
        - file_final_states 使用 after_content / is_deleted 作为最终状态
        - 基于行级 diff 生成 Delete/Type/Observe 序列
        """
        file_init_states: List[FileInitState] = []
        file_final_states: List[FileFinalState] = []
        actions: List[object] = []

        for fc in change_set.file_changes:
            file_init_states.append(
                FileInitState(
                    relative_path=fc.relative_path,
                    content=fc.before_content,
                    is_new_file=fc.is_new_file,
                )
            )

            # 约定：最终状态使用 ChangeSet 中的 after_content / is_deleted
            final_content = "" if fc.is_deleted else fc.after_content
            file_final_states.append(
                FileFinalState(
                    relative_path=fc.relative_path,
                    content=final_content,
                    is_deleted=fc.is_deleted,
                )
            )

            file_actions = self._generate_actions_for_file(
                relative_path=fc.relative_path,
                before_content=fc.before_content,
                after_content=fc.after_content,
            )
            actions.extend(file_actions)

        metadata = {
            "strategy": self.name,
            "source_metadata": change_set.metadata,
        }

        return TypePlan(
            file_init_states=file_init_states,
            actions=actions,
            file_final_states=file_final_states,
            observe_config=observe_config,
            metadata=metadata,
        )

    def _generate_actions_for_file(
        self,
        relative_path: str,
        before_content: str,
        after_content: str,
    ) -> List[object]:
        """
        基于行级 diff hunk，为单个文件生成 Delete/Type/Observe 的 Action 序列。

        使用 difflib.SequenceMatcher 在按行拆分的 before/after 上计算 opcode：
        - equal: 行内容完全相同，current_line 前进相同的行数
        - delete: before[i1:i2] 被删除
        - insert: after[j1:j2] 为新增行
        - replace: before[i1:i2] 被 after[j1:j2] 替换（视为 delete + insert）

        每处理完一个非 equal 的 opcode（即一个 hunk）后，插入一次 ObserveAction。
        """
        actions: List[object] = []

        if not before_content and not after_content:
            return actions

        # 一份不带换行用于 diff，一份保留换行用于准确计算 Delete/Type 的字符数
        before_lines = before_content.splitlines()
        before_lines_nl = before_content.splitlines(keepends=True)

        after_lines = after_content.splitlines()
        after_lines_nl = after_content.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, before_lines, after_lines)

        current_line = 1  # 1-base，始终表示“当前缓冲区中下一次操作所在的行号”

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                # 这段完全相同，跳过即可：前进等长的行数
                current_line += (i2 - i1)
                continue

            # delete/replace：先删掉 before[i1:i2] 这段旧行
            if tag in ("delete", "replace"):
                for k in range(i1, i2):
                    old_line = before_lines_nl[k]
                    if not old_line:
                        continue
                    actions.append(
                        DeleteAction(
                            file=relative_path,
                            line=current_line,
                            col=1,
                            count=len(old_line),
                        )
                    )
                # 删除后，后续行会顶上来，因此 current_line 保持不变

            # insert/replace：再插入 after[j1:j2] 这段新行
            if tag in ("insert", "replace"):
                for k in range(j1, j2):
                    new_line = after_lines_nl[k]
                    if not new_line:
                        continue
                    actions.append(
                        TypeAction(
                            file=relative_path,
                            line=current_line,
                            col=1,
                            content=new_line,
                        )
                    )
                    # 插入一行后，后续内容整体下移一行
                    current_line += 1

            # 每处理完一个非 equal 的 opcode，视为一个 hunk，插入一次 Observe
            actions.append(ObserveAction())

        return actions

