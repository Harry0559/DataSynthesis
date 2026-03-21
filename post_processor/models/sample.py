"""标准格式与格式化样本结构"""

from __future__ import annotations

from typing import Any, Dict


# === 数据类型（扁平，用于 input_output_map、类型链校验）===
RAW = "raw"
STANDARD = "standard"
ZETA = "zeta"

# === 格式集合 ===
FORMAT_NAMES = (STANDARD, ZETA)  # 具体格式，用于 formatter 注册、CLI、input_format


# 标准格式样本（整合器输出）：dict 结构，字段待完善
StandardSample = Dict[str, Any]

# 格式化样本（格式化器输出）：dict + 隐含 format_name
FormattedSample = Dict[str, Any]


def get_format(sample: Dict[str, Any]) -> str:
    """从样本的 format 字段获取格式，无效则返回 unknown"""
    fmt = sample.get("format")
    if fmt in FORMAT_NAMES:
        return fmt
    return "unknown"
