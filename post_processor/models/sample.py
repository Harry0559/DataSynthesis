"""标准格式与格式化样本结构"""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

try:
    from typing import NotRequired, Required
except ImportError:
    from typing_extensions import NotRequired, Required

from pydantic import TypeAdapter, ValidationError


# === 数据类型（扁平，用于 input_output_map、类型链校验）===
RAW = "raw"
STANDARD = "standard"
ZETA = "zeta"

# === 格式集合 ===
FORMAT_NAMES = (STANDARD, ZETA)  # 具体格式，用于 formatter 注册、CLI、input_format


class StandardSample(TypedDict, total=True):
    """标准格式样本（整合器输出），所有字段必填"""

    id: int
    file: str
    cursor: Dict[str, Any]
    init_content: str
    prev_content: str
    content: str
    final_content: str
    model_output: str
    edit_history_from_init: List[Dict[str, Any]]
    edit_history_from_prev: List[Dict[str, Any]]
    timestamp: str
    collector: str
    format: str
    metadata: Dict[str, Any]


class ZetaSample(TypedDict, total=False):
    """Zeta 格式样本（格式化器输出），骨架字段，可按需扩展"""

    format: Required[str]
    id: int
    file: str
    input: str
    ground_truth: str
    metadata: Dict[str, Any]
    prev_content: str
    content: str
    ground_truth_content: str


# === 格式 Schema 与校验器 ===
FORMAT_SCHEMAS: Dict[str, type] = {
    STANDARD: StandardSample,
    ZETA: ZetaSample,
}

FORMAT_VALIDATORS: Dict[str, TypeAdapter] = {
    fmt: TypeAdapter(FORMAT_SCHEMAS[fmt]) for fmt in FORMAT_NAMES
}


def validate_sample(obj: Dict[str, Any], format_name: str) -> Dict[str, Any] | None:
    """
    校验 obj 是否符合 format_name 的 schema。
    通过则返回（可能规范化后的）dict，否则返回 None。
    """
    validator = FORMAT_VALIDATORS.get(format_name)
    if validator is None:
        return None
    try:
        return validator.validate_python(obj)
    except ValidationError:
        return None
