"""
Collector 抽象基类

采集器：在 ObserveAction 触发时执行具体的采集逻辑。
不同实现决定"观察"时具体做什么（保存日志、截图等）。
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..core.models import ObserveConfig, WorkContext


class Collector(ABC):
    """采集器抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """采集器名称"""
        ...

    @abstractmethod
    def init_session(
        self,
        session_dir: str,
        observe_config: ObserveConfig,
        work_context: Optional[WorkContext] = None,
    ) -> None:
        """
        会话开始时初始化。

        Args:
            session_dir: 当前会话的输出目录
            observe_config: Observe 全局默认配置
            work_context: 当前任务的工作上下文（含 work_dir 等），可选；采集器需要读工作区文件或推导路径时可使用
        """
        ...

    @abstractmethod
    def collect(
        self,
        relative_path: str,
        action_index: int,
        line: int,
        col: int,
    ) -> None:
        """
        执行一次采集。

        Args:
            relative_path: 当前文件的相对路径
            action_index: 本次 Observe 在 type_plan.actions 中的索引（0-based）
            line: 光标所在行（1-based），暂由调用方占位
            col: 光标所在列（1-based），暂由调用方占位
        """
        ...

    @abstractmethod
    def finalize(self) -> None:
        """会话结束时清理（flush 缓冲区等）"""
        ...
