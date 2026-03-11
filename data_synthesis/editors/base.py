"""
EditorAdapter 抽象基类

编辑器适配器：抽象 IDE 特定的操作，实现跨 IDE 支持。
不同 IDE 的快捷键、命令面板、文件打开方式各不相同，
通过此接口统一为 Executor 可调用的标准操作。
"""

from abc import ABC, abstractmethod


class EditorAdapter(ABC):
    """编辑器适配器抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """编辑器名称"""
        ...

    @abstractmethod
    def restart(self, work_dir: str) -> None:
        """重启编辑器并打开工作目录"""
        ...

    @abstractmethod
    def open_file(self, relative_path: str) -> None:
        """打开指定文件。relative_path 为相对于工作目录的相对路径。"""
        ...

    @abstractmethod
    def goto(self, line: int, col: int) -> None:
        """定位到指定行列"""
        ...

    @abstractmethod
    def type_char(self, char: str) -> None:
        """输入单个字符。"""
        ...

    @abstractmethod
    def type_chars(self, content: str, interval: float = 0.02) -> None:
        """批量逐字输入，每字符间隔 interval 秒。"""
        ...

    @abstractmethod
    def delete_chars_forward(self, count: int, interval: float = 0.02) -> None:
        """在光标位置向后删除指定数量的字符，每次间隔 interval 秒。"""
        ...

    @abstractmethod
    def save_file(self) -> None:
        """保存当前文件"""
        ...

    @abstractmethod
    def validate_settings(self) -> bool:
        """
        校验编辑器配置是否满足运行要求。

        Returns:
            配置正确返回 True，否则返回 False
        """
        ...

    def capture_tab_log(self, current_file_abs_path: str) -> str:
        """
        捕获当前 Tab/补全日志并解析出模型输出。

        依赖 IDE 的 Output 面板与保存行为，非所有编辑器均支持。
        子类若支持则重写此方法；否则调用时抛出 NotImplementedError。

        Args:
            current_file_abs_path: 当前打开文件的绝对路径，用于推导日志保存路径等。

        Returns:
            解析得到的模型输出文本。

        Raises:
            NotImplementedError: 本编辑器不支持 Tab 日志捕获时。
        """
        raise NotImplementedError(f"{self.name} 不支持 Tab 日志捕获")
