"""
CursorAdapter：Cursor IDE 适配器

- restart(): 关闭文件夹 → 退出 Cursor → 启动 Cursor → 打开工作目录
- open_file(relative_path): 通过 Quick Open (Cmd+P) 打开文件，入参为相对路径
- goto(): 通过 Quick Open 输入 ":line:col" 定位
- type_char(): 透传 Platform 层输入单个字符
- delete_chars_forward(): 模拟 Delete 键（向后删除），每次间隔 0.03s
- save_file(): Cmd+S
- validate_settings(): 暂未实现
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

    def open_file(self, relative_path: str) -> None:
        """通过 Quick Open (Cmd+P) 打开文件，relative_path 为相对路径。"""
        p = self._platform
        p.activate_window("Cursor")
        time.sleep(0.2)
        p.send_hotkey(p.get_modifier_key(), "p")
        time.sleep(0.3)
        for c in relative_path:
            p.type_char(c)
            time.sleep(0.02)
        p.send_key("enter")

    def goto(self, line: int, col: int) -> None:
        """通过 Quick Open 输入 ":line:col" 定位到指定行列。"""
        p = self._platform
        p.send_hotkey(p.get_modifier_key(), "p")
        time.sleep(0.2)
        for c in f":{line}:{col}":
            p.type_char(c)
            time.sleep(0.02)
        p.send_key("enter")

    def type_char(self, char: str) -> None:
        """透传 Platform 层输入单个字符。"""
        self._platform.type_char(char)

    def delete_chars_forward(self, count: int) -> None:
        """在光标位置向后删除 count 个字符，每次删除间隔 0.03s。"""
        p = self._platform
        for _ in range(count):
            p.send_key("forward_delete")
            time.sleep(0.03)

    def save_file(self) -> None:
        """发送 Cmd+S 保存当前文件。"""
        mod = self._platform.get_modifier_key()
        self._platform.send_hotkey(mod, "s")

    def validate_settings(self) -> bool:
        """校验 Cursor 配置（暂未实现）。"""
        raise NotImplementedError("CursorAdapter.validate_settings 尚未实现")
