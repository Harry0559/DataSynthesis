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

import json
import os
import time
from typing import Optional, Tuple

from ..collectors.base import Collector
from ..core.models import (
    ForwardDeleteAction,
    ObserveAction,
    ObserveConfig,
    TypeAction,
    TypePlan,
)
from ..editors.base import EditorAdapter

# 与光标位置插件约定的默认位置文件路径（可根据需要调整/抽象为配置）
CURSOR_POSITION_DEFAULT_PATH = os.path.expanduser("~/.cursor-position-tracker.json")


def _fetch_cursor_position_from_file(
    path: str = CURSOR_POSITION_DEFAULT_PATH,
) -> Tuple[int, int]:
    """
    从本地 JSON 文件读取最新光标位置（1-based line/col）。

    文件格式示例:
        {
            "filePath": "/path/to/file.py",
            "line": 42,
            "column": 15,
            "timestamp": "2026-03-10T10:30:00.000Z"
        }

    读取失败或字段缺失时返回 (0, 0) 作为占位。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return (0, 0)

    try:
        line = int(data.get("line", 0))
        col = int(data.get("column", 0))
    except (TypeError, ValueError):
        return (0, 0)

    if line < 0 or col < 0:
        return (0, 0)
    return (line, col)


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
                self._observe(action, current_file, i)

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
        action: ObserveAction,
        current_file: Optional[str],
        action_index: int,
    ) -> None:
        """执行观察采集；尝试从本地光标位置文件读取真实行/列。"""
        if self.dry_run or not self.collector:
            return

        self.editor.save_file()  # type: ignore[union-attr]

        pre_wait = self.observe_config.pre_wait
        post_wait = self.observe_config.post_wait

        time.sleep(pre_wait)
        line, col = _fetch_cursor_position_from_file()
        self.collector.collect(
            relative_path=current_file or "",
            action_index=action_index,
            line=line,
            col=col,
        )
        time.sleep(post_wait)
