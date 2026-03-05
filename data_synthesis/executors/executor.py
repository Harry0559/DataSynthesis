"""
Executor：按 TypePlan 操控编辑器

核心执行循环：遍历 actions 列表，根据 Action 类型分发：
- TypeAction → 定位 + 逐字输入
- ForwardDeleteAction → 定位 + 向后删除字符
- ObserveAction → 保存文件 + 通知采集器

支持 dry-run 模式（不操作编辑器，只打印日志）。
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
    WorkContext,
)
from ..editors.base import EditorAdapter


class Executor:
    """操作执行器"""

    def __init__(
        self,
        editor: Optional[EditorAdapter] = None,
        collector: Optional[Collector] = None,
        observe_config: Optional[ObserveConfig] = None,
        type_interval: float = 0.05,
        vi_mode: bool = False,
        dry_run: bool = False,
    ):
        self.editor = editor
        self.collector = collector
        self.observe_config = observe_config or ObserveConfig()
        self.type_interval = type_interval
        self.vi_mode = vi_mode
        self.dry_run = dry_run

    def execute(self, type_plan: TypePlan) -> None:
        """按 TypePlan 执行全部操作"""
        current_file: Optional[str] = None
        char_index = 0
        total = len(type_plan.actions)

        if self.dry_run:
            print("  [Executor] dry-run 模式")

        for i, action in enumerate(type_plan.actions):
            if isinstance(action, TypeAction):
                if action.file != current_file:
                    self._switch_file(action.file)
                    current_file = action.file

                self._goto(action.line, action.col)
                self._type_chars(action.content)
                char_index += len(action.content)

                if self.dry_run:
                    print(
                        f"  [{i + 1}/{total}] Type → {action.file}:{action.line}:{action.col} "
                        f"输入 {action.content!r} ({len(action.content)} 字符)"
                    )

            elif isinstance(action, ForwardDeleteAction):
                if action.file != current_file:
                    self._switch_file(action.file)
                    current_file = action.file

                self._goto(action.line, action.col)
                self._delete_chars_forward(action.count)

                if self.dry_run:
                    print(
                        f"  [{i + 1}/{total}] ForwardDelete → {action.file}:{action.line}:{action.col} "
                        f"向后删除 {action.count} 字符"
                    )

            elif isinstance(action, ObserveAction):
                self._observe(action, current_file, char_index)

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
        """逐字输入"""
        if self.dry_run:
            return
        for char in content:
            self.editor.type_char(char)  # type: ignore[union-attr]
            time.sleep(self.type_interval)

    def _delete_chars_forward(self, count: int) -> None:
        """在光标位置向后删除 count 个字符"""
        if self.dry_run:
            return
        self.editor.delete_chars_forward(count)  # type: ignore[union-attr]

    def _observe(
        self,
        action: ObserveAction,
        current_file: Optional[str],
        char_index: int,
    ) -> None:
        """执行观察采集"""
        if self.dry_run or not self.collector:
            return

        self.editor.save_file()  # type: ignore[union-attr]

        pre_wait = (
            action.pre_wait
            if action.pre_wait is not None
            else self.observe_config.pre_wait
        )
        post_wait = self.observe_config.post_wait

        time.sleep(pre_wait)
        self.collector.collect(file_path=current_file or "", char_index=char_index)
        time.sleep(post_wait)
