"""
PlatformHandler 抽象基类

平台抽象层：封装 OS 级别的操作。
EditorAdapter 的各种操作最终通过 PlatformHandler 与操作系统交互。
"""

from abc import ABC, abstractmethod


class PlatformHandler(ABC):
    """平台操作抽象基类"""

    @abstractmethod
    def type_char(self, char: str) -> None:
        """输入单个字符"""
        ...

    @abstractmethod
    def send_key(self, key: str) -> None:
        """发送特殊按键（Enter, Tab, Backspace, Delete 等）"""
        ...

    @abstractmethod
    def send_hotkey(self, *keys: str) -> None:
        """发送组合快捷键（如 Cmd+S, Ctrl+Shift+P）"""
        ...

    @abstractmethod
    def activate_window(self, app_name: str) -> None:
        """激活指定应用窗口"""
        ...

    @abstractmethod
    def launch_app(self, app_name: str) -> None:
        """启动应用"""
        ...

    @abstractmethod
    def quit_app(self, app_name: str) -> None:
        """退出应用"""
        ...

    @abstractmethod
    def get_modifier_key(self) -> str:
        """返回当前平台的主修饰键名（如 command / ctrl），用于拼编辑器快捷键。"""
        ...

    @abstractmethod
    def open_app_with_folder(self, app_name: str, folder_path: str) -> None:
        """启动应用并打开指定目录（如 open -a App /path/to/folder）。"""
        ...
