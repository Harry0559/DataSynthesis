"""
CursorTabLogCollector：通过快捷键触发 Cursor 保存 Tab 日志

TODO: 实现以下功能：
1. 发送快捷键通知 Cursor 保存当前 Tab 补全日志
2. 等待日志文件更新（带超时和重试）
3. 读取并解析日志内容
4. 将采集记录追加到 session 目录下的 JSONL 文件
"""

from ..core.models import ObserveConfig
from .base import Collector


class CursorTabLogCollector(Collector):
    """通过快捷键保存 Cursor Tab 日志的采集器"""

    def __init__(self, hotkey: str = "", log_path: str = ""):
        self.hotkey = hotkey
        self.log_path = log_path
        self._session_dir = ""
        self._observe_config = ObserveConfig()

    @property
    def name(self) -> str:
        return "cursor_tab_log"

    def init_session(self, session_dir: str, observe_config: ObserveConfig) -> None:
        """
        TODO:
        1. 保存 session_dir 和 observe_config
        2. 创建 JSONL 输出文件
        3. 验证 hotkey 和 log_path 配置
        """
        self._session_dir = session_dir
        self._observe_config = observe_config
        raise NotImplementedError("CursorTabLogCollector.init_session 尚未实现")

    def collect(self, file_path: str, char_index: int) -> None:
        """
        TODO:
        1. 发送 self.hotkey（通过 EditorAdapter 或 Platform）
        2. 等待 self.log_path 文件更新（超时 = observe_config.timeout）
        3. 读取日志内容
        4. 构建 record: {file_path, char_index, log_content, timestamp}
        5. 追加到 JSONL 文件
        """
        raise NotImplementedError("CursorTabLogCollector.collect 尚未实现")

    def finalize(self) -> None:
        """
        TODO:
        1. flush JSONL 文件
        2. 打印采集统计信息
        """
        raise NotImplementedError("CursorTabLogCollector.finalize 尚未实现")
