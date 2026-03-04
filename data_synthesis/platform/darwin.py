"""
macOS 平台实现

注意事项:
    - 需要在系统设置中为运行本程序的终端/IDE 授予辅助功能 (Accessibility) 权限，
      否则 AppleScript 键盘事件可能被系统拦截。
"""

import subprocess
import time

from .base import PlatformHandler


class DarwinPlatformHandler(PlatformHandler):
    """macOS 平台实现，使用 AppleScript 发送键盘事件。"""

    # 修饰键名到 AppleScript using 子句的映射
    _MODIFIER_MAP = {
        "command": "command down",
        "cmd": "command down",
        "shift": "shift down",
        "option": "option down",
        "alt": "option down",
        "control": "control down",
        "ctrl": "control down",
    }

    def type_char(self, char: str) -> None:
        """使用 AppleScript 输入单个字符。"""
        if char == "\n":
            # 回车键
            script = """
            tell application "System Events"
                key code 36
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], check=True, capture_output=True
            )
        elif char == "\t":
            # Tab 键
            script = """
            tell application "System Events"
                key code 48
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], check=True, capture_output=True
            )
        elif ord(char) > 127:
            # 非 ASCII 字符（如中文）：通过剪贴板粘贴，避免键位映射问题
            subprocess.run(["pbcopy"], input=char.encode("utf-8"), check=True)
            self.send_hotkey("command", "v")
        elif char == '"':
            # 双引号需要转义
            script = """
            tell application "System Events"
                keystroke "\\\""
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], check=True, capture_output=True
            )
        elif char == "\\":
            # 反斜杠需要转义
            script = """
            tell application "System Events"
                keystroke "\\\\"
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], check=True, capture_output=True
            )
        else:
            # 普通 ASCII 字符，对特殊字符进行转义
            escaped_char = char.replace("\\", "\\\\").replace('"', '\\"')
            script = f"""
            tell application "System Events"
                keystroke "{escaped_char}"
            end tell
            """
            subprocess.run(
                ["osascript", "-e", script], check=True, capture_output=True
            )

    def send_key(self, key: str) -> None:
        """
        使用 AppleScript 发送单个控制键。

        约定:
            - "backspace": 向前删除（退格键，key code 51）
            - "delete" / "forward_delete": 向后删除（Forward Delete，fn+Delete，key code 117）
        """
        key_codes = {
            "escape": 53,
            "esc": 53,
            "enter": 36,
            "return": 36,
            "tab": 48,
            "up": 126,
            "down": 125,
            "left": 123,
            "right": 124,
            # 删除方向区分:
            "backspace": 51,  # 向前删除
            "delete": 117,  # 向后删除（Forward Delete）
            "forward_delete": 117,
            "space": 49,
            "home": 115,
            "end": 119,
            "pageup": 116,
            "pagedown": 121,
        }

        key_lower = key.lower()
        if key_lower not in key_codes:
            raise ValueError(f"不支持的按键: {key}")

        key_code = key_codes[key_lower]
        script = f"""
        tell application "System Events"
            key code {key_code}
        end tell
        """
        subprocess.run(
            ["osascript", "-e", script], check=True, capture_output=True
        )

    def send_hotkey(self, *keys: str) -> None:
        """使用 AppleScript 发送组合快捷键。"""
        modifiers: list[str] = []
        main_key: str | None = None

        for key in keys:
            key_lower = key.lower()
            if key_lower in self._MODIFIER_MAP:
                modifiers.append(self._MODIFIER_MAP[key_lower])
            else:
                main_key = key_lower

        if main_key is None:
            raise ValueError("send_hotkey 至少需要一个非修饰键")

        modifier_str = ", ".join(modifiers) if modifiers else ""

        if modifier_str:
            script = f"""
            tell application "System Events"
                keystroke "{main_key}" using {{{modifier_str}}}
            end tell
            """
        else:
            script = f"""
            tell application "System Events"
                keystroke "{main_key}"
            end tell
            """

        subprocess.run(["osascript", "-e", script], check=True)

    def activate_window(self, app_name: str) -> None:
        """使用 open -a 激活指定应用窗口。"""
        subprocess.run(["open", "-a", app_name], check=False)
        time.sleep(0.5)

    def launch_app(self, app_name: str) -> None:
        """使用 open -a 启动应用。"""
        subprocess.run(["open", "-a", app_name], check=False)
        time.sleep(1.0)

    def quit_app(self, app_name: str) -> None:
        """使用 AppleScript 关闭应用。"""
        script = f'tell application "{app_name}" to quit'
        subprocess.run(["osascript", "-e", script], check=False)
        time.sleep(0.5)
