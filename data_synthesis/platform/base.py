"""
PlatformHandler 抽象基类

平台抽象层：封装 OS 级别的操作。
EditorAdapter 的各种操作最终通过 PlatformHandler 与操作系统交互。
"""

from abc import ABC, abstractmethod
import time


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

    @abstractmethod
    def is_app_running(self, app_name: str) -> bool:
        """判断指定应用是否仍在运行。具体实现由各平台子类提供。"""
        ...

    def wait_for_app_exit(
        self,
        app_name: str,
        timeout: float = 10.0,
    ) -> None:
        """轮询等待指定应用退出；轮询间隔统一为 0.1 秒。

        若在超时时间内应用仍在运行，则抛出 RuntimeError。
        """
        interval = 0.1
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.is_app_running(app_name):
                return
            time.sleep(interval)
        raise RuntimeError(
            f"wait_for_app_exit timeout: app '{app_name}' still running after {timeout} seconds"
        )
