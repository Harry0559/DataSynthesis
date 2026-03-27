"""
macOS 平台实现

注意事项:
    - 需要在系统设置中为运行本程序的终端/IDE 授予辅助功能 (Accessibility) 权限，
      否则 Quartz 键盘事件可能被系统拦截。
"""

import subprocess
from typing import Dict, Tuple

import Quartz

from .base import PlatformHandler


class DarwinPlatformHandler(PlatformHandler):
    """macOS 平台实现，使用 Quartz 发送键盘事件。"""

    # 修饰键映射到 Quartz flags
    _MODIFIER_FLAG_MAP = {
        "command": Quartz.kCGEventFlagMaskCommand,
        "cmd": Quartz.kCGEventFlagMaskCommand,
        "shift": Quartz.kCGEventFlagMaskShift,
        "option": Quartz.kCGEventFlagMaskAlternate,
        "alt": Quartz.kCGEventFlagMaskAlternate,
        "control": Quartz.kCGEventFlagMaskControl,
        "ctrl": Quartz.kCGEventFlagMaskControl,
    }

    # ANSI US 键盘布局 keycode
    _KEY_CODE_MAP = {
        "a": 0,
        "s": 1,
        "d": 2,
        "f": 3,
        "h": 4,
        "g": 5,
        "z": 6,
        "x": 7,
        "c": 8,
        "v": 9,
        "b": 11,
        "q": 12,
        "w": 13,
        "e": 14,
        "r": 15,
        "y": 16,
        "t": 17,
        "1": 18,
        "2": 19,
        "3": 20,
        "4": 21,
        "6": 22,
        "5": 23,
        "=": 24,
        "9": 25,
        "7": 26,
        "-": 27,
        "8": 28,
        "0": 29,
        "]": 30,
        "o": 31,
        "u": 32,
        "[": 33,
        "i": 34,
        "p": 35,
        "l": 37,
        "j": 38,
        "'": 39,
        "k": 40,
        ";": 41,
        "\\": 42,
        ",": 43,
        "/": 44,
        "n": 45,
        "m": 46,
        ".": 47,
        "`": 50,
    }

    def send_key(self, key: str) -> None:
        """
        使用 Quartz 发送单个控制键。

        约定:
            - "backspace": 向前删除（退格键）
            - "delete" / "forward_delete": 向后删除（Forward Delete）
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

        self._tap_key(key_codes[key_lower], flags=0)

    def send_hotkey(self, *keys: str) -> None:
        """使用 Quartz 发送组合快捷键。"""
        flags = 0
        main_key: str | None = None

        for key in keys:
            key_lower = key.lower()
            if key_lower in self._MODIFIER_FLAG_MAP:
                flags |= self._MODIFIER_FLAG_MAP[key_lower]
            else:
                main_key = key_lower

        if main_key is None:
            raise ValueError("send_hotkey 至少需要一个非修饰键")

        key_code = self._keycode_from_token(main_key)
        if key_code is None:
            raise ValueError(f"不支持的快捷键主键: {main_key}")
        self._tap_key(key_code, flags=flags)

    def paste_text(self, text: str) -> None:
        """通过剪贴板粘贴整段文本，减少逐字符输入的系统调用。"""
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        self.send_hotkey("command", "v")

    def type_char(self, char: str) -> None:
        """使用 Quartz 输入单个字符；复杂字符回退为剪贴板粘贴。"""
        if char == "\n":
            self.send_key("enter")
            return
        if char == "\t":
            self.send_key("tab")
            return
        if ord(char) > 127:
            self.paste_text(char)
            return

        mapped = self._char_to_keycode_and_flags(char)
        if mapped is None:
            self.paste_text(char)
            return
        key_code, flags = mapped
        self._tap_key(key_code, flags)

    def get_modifier_key(self) -> str:
        """macOS 使用 command 作为主修饰键。"""
        return "command"

    def activate_window(self, app_name: str) -> None:
        """使用 open -a 激活指定应用窗口。"""
        subprocess.run(["open", "-a", app_name], check=False)

    def open_app_with_folder(self, app_name: str, folder_path: str) -> None:
        """使用 open -a 启动应用并打开指定目录。"""
        subprocess.run(["open", "-a", app_name, folder_path], check=False)

    def launch_app(self, app_name: str) -> None:
        """使用 open -a 启动应用。"""
        subprocess.run(["open", "-a", app_name], check=False)

    def quit_app(self, app_name: str) -> None:
        """使用 AppleScript 关闭应用。"""
        script = f'tell application "{app_name}" to quit'
        subprocess.run(["osascript", "-e", script], check=False)

    def is_app_running(self, app_name: str) -> bool:
        """
        使用 AppleScript 判断应用是否仍在运行。

        返回:
            True 表示有同名进程在运行，False 表示未运行或查询失败。
        """
        script = f'tell application "System Events" to (name of processes) contains "{app_name}"'
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip().lower() == "true"

    def _post_key_event(self, key_code: int, is_down: bool, flags: int = 0) -> None:
        event = Quartz.CGEventCreateKeyboardEvent(None, key_code, is_down)
        Quartz.CGEventSetFlags(event, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _tap_key(self, key_code: int, flags: int = 0) -> None:
        self._post_key_event(key_code, True, flags)
        self._post_key_event(key_code, False, flags)

    def _keycode_from_token(self, token: str) -> int | None:
        if len(token) == 1:
            key = token.lower()
            return self._KEY_CODE_MAP.get(key)
        return None

    def _char_to_keycode_and_flags(self, char: str) -> Tuple[int, int] | None:
        shift = Quartz.kCGEventFlagMaskShift
        no_shift = 0

        shifted_symbols: Dict[str, str] = {
            "!": "1",
            "@": "2",
            "#": "3",
            "$": "4",
            "%": "5",
            "^": "6",
            "&": "7",
            "*": "8",
            "(": "9",
            ")": "0",
            "_": "-",
            "+": "=",
            "{": "[",
            "}": "]",
            "|": "\\",
            ":": ";",
            '"': "'",
            "<": ",",
            ">": ".",
            "?": "/",
            "~": "`",
        }

        if char == " ":
            return 49, no_shift
        if "a" <= char <= "z":
            code = self._KEY_CODE_MAP.get(char)
            return (code, no_shift) if code is not None else None
        if "A" <= char <= "Z":
            code = self._KEY_CODE_MAP.get(char.lower())
            return (code, shift) if code is not None else None
        if char in self._KEY_CODE_MAP:
            return self._KEY_CODE_MAP[char], no_shift
        if char in shifted_symbols:
            base = shifted_symbols[char]
            code = self._KEY_CODE_MAP.get(base)
            return (code, shift) if code is not None else None
        return None
