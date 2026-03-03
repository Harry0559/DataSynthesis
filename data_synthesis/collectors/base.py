"""
Collector 抽象基类

采集器：在 ObserveAction 触发时执行具体的采集逻辑。
不同实现决定"观察"时具体做什么（保存日志、截图等）。
"""

from abc import ABC, abstractmethod

from ..core.models import ObserveConfig


class Collector(ABC):
    """采集器抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """采集器名称"""
        ...

    @abstractmethod
    def init_session(self, session_dir: str, observe_config: ObserveConfig) -> None:
        """
        会话开始时初始化。

        Args:
            session_dir: 当前会话的输出目录
            observe_config: Observe 全局默认配置
        """
        ...

    @abstractmethod
    def collect(self, file_path: str, char_index: int) -> None:
        """
        执行一次采集。

        Args:
            file_path: 当前文件的相对路径
            char_index: 当前累计输入的字符数
        """
        ...

    @abstractmethod
    def finalize(self) -> None:
        """会话结束时清理（flush 缓冲区等）"""
        ...
