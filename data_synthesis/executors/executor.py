"""
Executor：按 TypePlan 操控编辑器

核心执行循环：遍历 actions 列表，根据 Action 类型分发：
- TypeAction → 定位 + 逐字输入
- ForwardDeleteAction → 定位 + 向后删除字符
- ObserveAction → 保存文件 + 通知采集器

支持 dry-run 模式（不操作编辑器，只打印日志）。

当启用光标位置采集插件（如 cursor-position-tracker-extension）时，
可在 Observe 阶段从约定的 JSON 文件中读取真实的光标行/列信息。
"""

import time
from typing import Optional

from ..collectors.base import Collector
from ..core.models import (
    ForwardDeleteAction,
    ObserveAction,
    ObserveConfig,
    TypeAction,
    TypePlan,
)
from ..editors.base import EditorAdapter


class Executor:
    """操作执行器"""

    def __init__(
        self,
        editor: Optional[EditorAdapter] = None,
        collector: Optional[Collector] = None,
        observe_config: Optional[ObserveConfig] = None,
        type_interval: float = 0.01,
        delete_interval: float = 0.01,
        dry_run: bool = False,
    ):
        self.editor = editor
        self.collector = collector
        self.observe_config = observe_config or ObserveConfig()
        self.type_interval = type_interval
        self.delete_interval = delete_interval
        self.dry_run = dry_run

    def execute(self, type_plan: TypePlan) -> None:
        """按 TypePlan 执行全部操作"""
        current_file: Optional[str] = None
        cursor_line: int = 0
        cursor_col: int = 0
        char_index = 0
        total = len(type_plan.actions)

        if self.dry_run:
            print("  [Executor] dry-run 模式")

        for i, action in enumerate(type_plan.actions):
            # Type / ForwardDelete：需要控制文件和光标
            if isinstance(action, (TypeAction, ForwardDeleteAction)):
                # 切换文件
                if action.file != current_file:
                    self._switch_file(action.file)
                    current_file = action.file
                    # 切到新文件后重置为非法坐标，确保首个动作一定会 goto
                    cursor_line = 0
                    cursor_col = 0

                # 判断是否需要 goto
                if (cursor_line, cursor_col) != (action.line, action.col):
                    self._goto(action.line, action.col)
                    cursor_line = action.line
                    cursor_col = action.col

                # 执行动作
                if isinstance(action, TypeAction):
                    self._type_chars(action.content)
                    char_index += len(action.content)
                else:
                    delete_count = len(action.content)
                    self._delete_chars_forward(delete_count)

                # 由动作自身计算执行后的光标位置
                end_line, end_col = action.get_end_cursor()
                cursor_line, cursor_col = end_line, end_col

                if self.dry_run:
                    if isinstance(action, TypeAction):
                        print(
                            f"  [{i + 1}/{total}] Type → {action.file}:{action.line}:{action.col} "
                            f"输入 {action.content!r} ({len(action.content)} 字符, "
                            f"结束于 {cursor_line}:{cursor_col})"
                        )
                    else:
                        print(
                            f"  [{i + 1}/{total}] ForwardDelete → {action.file}:{action.line}:{action.col} "
                            f"向后删除 {len(action.content)} 字符, 光标停在 {cursor_line}:{cursor_col}"
                        )

            # Observe：不改变光标，只使用当前状态
            elif isinstance(action, ObserveAction):
                self._observe(current_file, i, cursor_line, cursor_col)

                if self.dry_run:
                    collector_info = (
                        f"已采集 ({self.collector.name})"
                        if self.collector
                        else "跳过（无采集器）"
                    )
                    print(f"  [{i + 1}/{total}] Observe → {collector_info}")

        print(f"\n  执行完成: 共 {total} 个操作, 累计 {char_index} 个字符")

    # ================================================================
    # 内部方法
    # ================================================================

    def _switch_file(self, file: str) -> None:
        """切换到指定文件（file 为相对路径）。"""
        if self.dry_run:
            return
        self.editor.open_file(file)  # type: ignore[union-attr]

    def _goto(self, line: int, col: int) -> None:
        """定位到指定位置"""
        if self.dry_run:
            return
        self.editor.goto(line, col)  # type: ignore[union-attr]

    def _type_chars(self, content: str) -> None:
        """逐字输入，间隔由 editor 控制"""
        if self.dry_run:
            return
        self.editor.type_chars(content, interval=self.type_interval)  # type: ignore[union-attr]

    def _delete_chars_forward(self, count: int) -> None:
        """在光标位置向后删除 count 个字符，间隔由 editor 控制"""
        if self.dry_run:
            return
        self.editor.delete_chars_forward(count, interval=self.delete_interval)  # type: ignore[union-attr]

    def _observe(
        self,
        current_file: Optional[str],
        action_index: int,
        cursor_line: int,
        cursor_col: int,
    ) -> None:
        """执行观察采集；使用 Executor 内部维护的光标行列。"""
        if self.dry_run or not self.collector:
            return

        self.editor.save_file()  # type: ignore[union-attr]

        pre_wait = self.observe_config.pre_wait
        post_wait = self.observe_config.post_wait

        time.sleep(pre_wait)
        self.collector.collect(
            relative_path=current_file or "",
            action_index=action_index,
            line=cursor_line,
            col=cursor_col,
        )
        time.sleep(post_wait)
