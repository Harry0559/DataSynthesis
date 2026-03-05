"""
CursorAdapter：Cursor IDE 适配器

TODO: 实现以下功能（可参考 CursorSynthesis 项目的 editor/cursor_control.py）：
- restart(): 关闭文件夹 → 退出 Cursor → 启动 Cursor → 打开工作目录
- open_file(): 通过 Quick Open (Cmd+P) 打开文件
- goto(): 通过 Go to Line (Ctrl+G) 定位
- type_text(): 通过 Platform 层模拟键盘输入
- delete_chars_forward(): 模拟 Delete 键（向后删除）
- save_file(): Cmd+S
- validate_settings(): 检查 Cursor settings.json 中的必要配置
"""

import os
import time

from .base import EditorAdapter
from ..platform.base import PlatformHandler


class CursorAdapter(EditorAdapter):
    """Cursor IDE 适配器"""

    def __init__(self, platform: PlatformHandler) -> None:
        """构造函数，注入 PlatformHandler 以便执行底层键盘/窗口操作。"""
        self._platform = platform

    @property
    def name(self) -> str:
        return "cursor"

    def restart(self, work_dir: str) -> None:
        """
        重启 Cursor 并打开指定工作目录。
        流程：激活窗口 → 聚焦编辑器(modifier+1) → 关闭当前文件夹(modifier+R+F) → 退出应用 → 用目录重新启动 → 再次激活窗口。
        """
        work_dir_abs = os.path.abspath(work_dir)
        p = self._platform

        # 1. 激活 Cursor，确保后续快捷键发到编辑器
        p.activate_window("Cursor")
        time.sleep(0.3)

        # 2. 聚焦到编辑器（modifier+1），否则 modifier+R+F 可能无效
        mod = p.get_modifier_key()
        p.send_hotkey(mod, "1")
        time.sleep(0.2)

        # 3. 关闭当前文件夹（Cursor 使用 Cmd+R 再按 F；依赖平台 modifier）
        p.send_hotkey(mod, "r")
        time.sleep(0.2)
        p.type_char("f")
        time.sleep(1.0)

        # 4. 退出 Cursor 进程
        p.quit_app("Cursor")
        time.sleep(1.0)

        # 5. 以指定目录启动新实例
        p.open_app_with_folder("Cursor", work_dir_abs)
        time.sleep(1.0)

        # 6. 再次激活窗口，确保新实例获得焦点
        p.activate_window("Cursor")

    def open_file(self, file_path: str) -> None:
        """TODO: 通过 Quick Open 打开文件"""
        raise NotImplementedError("CursorAdapter.open_file 尚未实现")

    def goto(self, line: int, col: int) -> None:
        """TODO: 通过 Go to Line 定位"""
        raise NotImplementedError("CursorAdapter.goto 尚未实现")

    def type_text(self, text: str) -> None:
        """TODO: 模拟键盘输入"""
        raise NotImplementedError("CursorAdapter.type_text 尚未实现")

    def delete_chars_forward(self, count: int) -> None:
        """TODO: 模拟向后删除（Delete 键）"""
        raise NotImplementedError("CursorAdapter.delete_chars_forward 尚未实现")

    def save_file(self) -> None:
        """TODO: Cmd+S 保存"""
        raise NotImplementedError("CursorAdapter.save_file 尚未实现")

    def validate_settings(self) -> bool:
        """TODO: 校验 Cursor 配置"""
        raise NotImplementedError("CursorAdapter.validate_settings 尚未实现")
