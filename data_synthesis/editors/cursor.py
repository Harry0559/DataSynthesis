"""
CursorAdapter：Cursor IDE 适配器

所有 time.sleep 均由 Editor 层控制，PlatformHandler 只负责发送命令。

- restart(): 关闭文件夹 → 退出 Cursor → 启动 Cursor → 打开工作目录
- open_file(relative_path): 通过 Quick Open (Cmd+P) 打开文件，入参为相对路径
- goto(): 通过 Quick Open 输入 ":line:col" 定位
- type_char(): 透传 Platform 层输入单个字符
- type_chars(): 批量逐字输入，每字符间隔可配
- delete_chars_forward(): 模拟 Delete 键（向后删除），每次间隔可配
- save_file(): Cmd+S
- capture_tab_log(current_file_abs_path): 打开 Output → 保存 → 清空 → 读日志并解析后删除，返回模型输出
- validate_settings(): 暂未实现
"""

import os
import time

from .base import EditorAdapter
from ..platform.base import PlatformHandler

# Cursor Output 面板保存的 Tab 日志默认文件名（含空格）
CURSOR_TAB_LOG_FILENAME = "Cursor Tab.log"


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

        p.activate_window("Cursor")
        time.sleep(0.5)

        mod = p.get_modifier_key()
        p.send_hotkey(mod, "1")
        time.sleep(0.2)

        p.send_hotkey(mod, "r")
        time.sleep(0.2)
        p.type_char("f")
        time.sleep(1.0)

        p.quit_app("Cursor")
        time.sleep(3.0)

        p.open_app_with_folder("Cursor", work_dir_abs)
        time.sleep(3.0)

        p.activate_window("Cursor")
        time.sleep(0.5)

    def open_file(self, relative_path: str) -> None:
        """通过 Quick Open (Cmd+P) 打开文件，relative_path 为相对路径。"""
        p = self._platform
        p.activate_window("Cursor")
        time.sleep(0.5)
        p.send_hotkey(p.get_modifier_key(), "p")
        time.sleep(0.5)
        for c in relative_path:
            p.type_char(c)
            time.sleep(0.02)
        p.send_key("enter")
        time.sleep(0.3)

    def goto(self, line: int, col: int) -> None:
        """通过 Quick Open 输入 ":line:col" 定位到指定行列。"""
        p = self._platform
        p.activate_window("Cursor")
        time.sleep(0.3)
        p.send_hotkey(p.get_modifier_key(), "p")
        time.sleep(0.3)
        for c in f":{line}:{col}":
            p.type_char(c)
            time.sleep(0.02)
        p.send_key("enter")
        time.sleep(0.3)

    def type_char(self, char: str) -> None:
        """透传 Platform 层输入单个字符。"""
        self._platform.type_char(char)

    def type_chars(self, content: str, interval: float = 0.02) -> None:
        """批量逐字输入，每字符间隔 interval 秒。"""
        for c in content:
            self._platform.type_char(c)
            time.sleep(interval)

    def delete_chars_forward(self, count: int, interval: float = 0.02) -> None:
        """在光标位置向后删除 count 个字符，每次删除间隔 interval 秒。"""
        p = self._platform
        for _ in range(count):
            p.send_key("forward_delete")
            time.sleep(interval)

    def save_file(self) -> None:
        """发送 Cmd+S 保存当前文件。"""
        mod = self._platform.get_modifier_key()
        self._platform.send_hotkey(mod, "s")

    def capture_tab_log(self, current_file_abs_path: str) -> str:
        """
        执行完整的 Tab 日志捕获流程并返回解析出的模型输出。

        步骤：删旧日志 → 激活窗口 → 打开 Output(mod+shift+7) → 保存(mod+shift+8)
        → 清空 Output(mod+shift+9) → 等待并读取日志 → 解析 → 删除日志文件。
        """
        p = self._platform
        mod = p.get_modifier_key()
        log_path = self._get_tab_log_path(current_file_abs_path)
        self._ensure_log_deleted(log_path)
        p.activate_window("Cursor")
        time.sleep(0.5)
        self._open_output_panel()
        time.sleep(0.5)
        self._open_save_dialog_and_confirm()
        time.sleep(0.5)
        self._clear_output_panel()
        time.sleep(0.3)
        raw = self._wait_and_read_log(log_path, timeout=5.0)
        result = self._parse_tab_log(raw)
        self._delete_log(log_path)
        return result

    def _get_tab_log_path(self, current_file_abs_path: str) -> str:
        """根据当前打开文件绝对路径推导日志文件路径（与当前文件同目录，文件名 Cursor Tab.log）。"""
        dir_path = os.path.dirname(os.path.abspath(current_file_abs_path))
        return os.path.join(dir_path, CURSOR_TAB_LOG_FILENAME)

    def _ensure_log_deleted(self, log_path: str) -> None:
        """若日志文件已存在则删除。"""
        if os.path.isfile(log_path):
            os.remove(log_path)

    def _open_output_panel(self) -> None:
        """用主修饰+Option+Shift+O 打开 Output 工具栏。"""
        mod = self._platform.get_modifier_key()
        self._platform.send_hotkey(mod, "option", "shift", "o")

    def _open_save_dialog_and_confirm(self) -> None:
        """用主修饰+Option+Shift+S 打开保存弹框，再发送回车在默认路径保存默认文件名。"""
        mod = self._platform.get_modifier_key()
        self._platform.send_hotkey(mod, "option", "shift", "s")
        time.sleep(1.0)
        self._platform.send_key("enter")
        time.sleep(0.5)

    def _clear_output_panel(self) -> None:
        """用主修饰+Option+Shift+C 清空 Output 缓存区。"""
        mod = self._platform.get_modifier_key()
        self._platform.send_hotkey(mod, "option", "shift", "c")

    def _wait_and_read_log(self, log_path: str, timeout: float) -> str:
        """等待日志文件出现并读取其内容，超时返回空字符串。"""
        interval = 0.2
        elapsed = 0.0
        while elapsed < timeout:
            if os.path.isfile(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8-sig") as f:
                        return f.read()
                except OSError:
                    pass
            time.sleep(interval)
            elapsed += interval
        return ""

    def _parse_tab_log(self, raw: str) -> str:
        """
        从原始日志中解析模型输出：取最后一个「=======>Model output」到「=======>Debug stream time」之间的内容。
        """
        if not raw or not raw.strip():
            return ""
        lines = raw.splitlines()
        start_marker = "=======>Model output"
        end_marker = "=======>Debug stream time"
        last_start = -1
        last_end = -1
        i = 0
        while i < len(lines):
            if start_marker in lines[i]:
                last_start = i
                i += 1
                while i < len(lines) and end_marker not in lines[i]:
                    i += 1
                if i < len(lines):
                    last_end = i
                i += 1
            else:
                i += 1
        if last_start < 0 or last_end < 0:
            return ""
        block_lines = lines[last_start + 1 : last_end]
        return "\n".join(block_lines).strip()

    def _delete_log(self, log_path: str) -> None:
        """删除指定日志文件。"""
        if os.path.isfile(log_path):
            try:
                os.remove(log_path)
            except OSError:
                pass

    def validate_settings(self) -> bool:
        """校验 Cursor 配置（暂未实现）。"""
        raise NotImplementedError("CursorAdapter.validate_settings 尚未实现")
