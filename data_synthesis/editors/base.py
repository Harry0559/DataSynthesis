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
    def open_file(self, file_path: str) -> None:
        """打开指定文件"""
        ...

    @abstractmethod
    def goto(self, line: int, col: int) -> None:
        """定位到指定行列"""
        ...

    @abstractmethod
    def type_text(self, text: str) -> None:
        """输入文本（单字符或短字符串）"""
        ...

    @abstractmethod
    def delete_chars(self, count: int) -> None:
        """删除指定数量的字符"""
        ...

    @abstractmethod
    def save_file(self) -> None:
        """保存当前文件"""
        ...

    @abstractmethod
    def send_hotkey(self, *keys: str) -> None:
        """发送快捷键组合"""
        ...

    @abstractmethod
    def validate_settings(self) -> bool:
        """
        校验编辑器配置是否满足运行要求。

        Returns:
            配置正确返回 True，否则返回 False
        """
        ...
