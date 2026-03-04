import sys

from .base import PlatformHandler
from .darwin import DarwinPlatformHandler


def create_default_platform() -> PlatformHandler:
    """
    根据当前运行环境返回默认的 PlatformHandler 实例。

    当前仅支持:
        - macOS (sys.platform == "darwin") → DarwinPlatformHandler
    """
    if sys.platform == "darwin":
        return DarwinPlatformHandler()

    raise RuntimeError(f"暂不支持的平台: {sys.platform}")


__all__ = ["PlatformHandler", "DarwinPlatformHandler", "create_default_platform"]
