"""
CursorAdapter：Cursor IDE 适配器

TODO: 实现以下功能（可参考 CursorSynthesis 项目的 editor/cursor_control.py）：
- restart(): 关闭文件夹 → 退出 Cursor → 启动 Cursor → 打开工作目录
- open_file(): 通过 Quick Open (Cmd+P) 打开文件
- goto(): 通过 Go to Line (Ctrl+G) 定位
- type_text(): 通过 Platform 层模拟键盘输入
- delete_chars(): 模拟 Delete/Backspace 按键
- save_file(): Cmd+S
- send_hotkey(): 委托给 Platform 层
- validate_settings(): 检查 Cursor settings.json 中的必要配置
"""

from .base import EditorAdapter


class CursorAdapter(EditorAdapter):
    """Cursor IDE 适配器"""

    @property
    def name(self) -> str:
        return "cursor"

    def restart(self, work_dir: str) -> None:
        """
        TODO: 重启 Cursor 并打开工作目录
        参考: CursorSynthesis/cursor_synthesis/editor/cursor_control.py
        """
        raise NotImplementedError("CursorAdapter.restart 尚未实现")

    def open_file(self, file_path: str) -> None:
        """TODO: 通过 Quick Open 打开文件"""
        raise NotImplementedError("CursorAdapter.open_file 尚未实现")

    def goto(self, line: int, col: int) -> None:
        """TODO: 通过 Go to Line 定位"""
        raise NotImplementedError("CursorAdapter.goto 尚未实现")

    def type_text(self, text: str) -> None:
        """TODO: 模拟键盘输入"""
        raise NotImplementedError("CursorAdapter.type_text 尚未实现")

    def delete_chars(self, count: int) -> None:
        """TODO: 模拟删除"""
        raise NotImplementedError("CursorAdapter.delete_chars 尚未实现")

    def save_file(self) -> None:
        """TODO: Cmd+S 保存"""
        raise NotImplementedError("CursorAdapter.save_file 尚未实现")

    def send_hotkey(self, *keys: str) -> None:
        """TODO: 发送快捷键"""
        raise NotImplementedError("CursorAdapter.send_hotkey 尚未实现")

    def validate_settings(self) -> bool:
        """TODO: 校验 Cursor 配置"""
        raise NotImplementedError("CursorAdapter.validate_settings 尚未实现")
