"""
macOS 平台实现

TODO: 实现以下功能（可参考 CursorSynthesis 项目的 platform/darwin.py）：
- type_char(): 使用 pyautogui 输入字符
- send_key(): 使用 pyautogui 发送特殊按键
- send_hotkey(): 使用 pyautogui 发送组合键
- activate_window(): 使用 Quartz/AppKit 激活窗口
- launch_app(): 使用 subprocess 启动应用
- quit_app(): 使用 AppleScript 或 Quartz 退出应用
"""

from .base import PlatformHandler


class DarwinPlatformHandler(PlatformHandler):
    """macOS 平台实现"""

    def type_char(self, char: str) -> None:
        """TODO: pyautogui.press / pyautogui.write"""
        raise NotImplementedError

    def send_key(self, key: str) -> None:
        """TODO: pyautogui.press"""
        raise NotImplementedError

    def send_hotkey(self, *keys: str) -> None:
        """TODO: pyautogui.hotkey"""
        raise NotImplementedError

    def activate_window(self, app_name: str) -> None:
        """TODO: Quartz / AppKit"""
        raise NotImplementedError

    def launch_app(self, app_name: str) -> None:
        """TODO: subprocess.Popen(['open', '-a', app_name])"""
        raise NotImplementedError

    def quit_app(self, app_name: str) -> None:
        """TODO: AppleScript osascript"""
        raise NotImplementedError
