"""步骤注册表与解析"""

from __future__ import annotations

import inspect
import re
from typing import Any, Dict, List, Optional, get_args, get_origin

from ..models.config import PipelineStep, StepKey
from ..models.sample import STANDARD, ZETA

from .base import StepIOBase

# 步骤类型
INTEGRATE = "integrate"
FILTER = "filter"
FORMAT = "format"
DEDUP = "dedup"

# 注册表
from .dedupers import DeduperBase, SimHashDeduplicator
from .filters import ContFilter, EditFilter, FilterBase, LlmFilter
from .formatters import FormatterBase, StandardFormatter, ZetaFormatter
from .integrators import DefaultIntegrator, IntegratorBase

INTEGRATORS: Dict[str, type] = {"default": DefaultIntegrator}
FILTERS: Dict[str, type] = {
    "llm": LlmFilter,
    "edit": EditFilter,
    "cont": ContFilter,
}
FORMATTERS: Dict[str, type] = {
    STANDARD: StandardFormatter,
    ZETA: ZetaFormatter,
}
DEDUPERS: Dict[str, type] = {"simhash": SimHashDeduplicator}

STEP_TYPES = (INTEGRATE, FILTER, FORMAT, DEDUP)
REGISTRIES: Dict[str, Dict[str, type]] = {
    INTEGRATE: INTEGRATORS,
    FILTER: FILTERS,
    FORMAT: FORMATTERS,
    DEDUP: DEDUPERS,
}

DEFAULT_NAMES: Dict[str, str] = {
    INTEGRATE: "default",
    FILTER: "llm",
    FORMAT: STANDARD,
    DEDUP: "simhash",
}

# --<type>-<name>.<occ?>.<param> 模式（匹配时传入 arg 或 arg[2:] 均可）
STEP_PARAM_PATTERN = re.compile(
    r"^(?:--)?([a-z]+)-([a-z0-9_]+)(?:\.(\d+))?\.(.+)$"
)


def _get_step_class(step_type: str, step_name: str) -> Optional[type]:
    """获取步骤类，不存在返回 None"""
    reg = REGISTRIES.get(step_type)
    return reg.get(step_name) if reg else None


def _get_step_defaults(step_type: str, step_name: str) -> Dict[str, Any]:
    """从 __init__ 签名提取默认参数"""
    cls = _get_step_class(step_type, step_name)
    if cls is None:
        return {}
    sig = inspect.signature(cls.__init__)
    defaults: Dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if param.default != inspect.Parameter.empty:
            defaults[name] = param.default
    return defaults


def _get_step_param_schema(step_type: str, step_name: str) -> Optional[Dict[str, Any]]:
    """
    获取步骤参数 schema：{param_name: annotation}。
    若 __init__ 仅有 **kwargs 无显式参数，返回 None 表示接受任意参数。
    """
    cls = _get_step_class(step_type, step_name)
    if cls is None:
        return None
    sig = inspect.signature(cls.__init__)
    schema: Dict[str, Any] = {}
    has_var_kwargs = False
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            has_var_kwargs = True
            continue
        ann = param.annotation if param.annotation != inspect.Parameter.empty else None
        schema[name] = ann
    if has_var_kwargs and not schema:
        return None
    return schema


def _guess_and_convert(value_str: str) -> Any:
    """无类型注解时的启发式转换"""
    v = value_str.lower()
    if v == "true":
        return True
    if v == "false":
        return False
    if value_str.lstrip("-").isdigit():
        return int(value_str)
    if _is_float(value_str):
        return float(value_str)
    if "," in value_str:
        return tuple(int(x.strip()) for x in value_str.split(",") if x.strip())
    return value_str


def _convert_param_value(
    value_str: str,
    param_name: str,
    expected_type: Any,
    step_type: str,
    step_name: str,
) -> Any:
    """根据期望类型转换并校验参数值"""
    if expected_type is None:
        return _guess_and_convert(value_str)

    origin = get_origin(expected_type)
    args = get_args(expected_type) if origin is not None else ()

    # Optional[X] / X | None -> 取 X
    if origin is not None and args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            expected_type = non_none[0]
            origin = get_origin(expected_type)
            args = get_args(expected_type) if origin is not None else ()

    try:
        if expected_type is int:
            if not value_str.lstrip("-").isdigit():
                raise ValueError(f"期望整数，得到: {value_str!r}")
            return int(value_str)
        if expected_type is float:
            return float(value_str)
        if expected_type is bool:
            v = value_str.lower()
            if v in ("true", "1"):
                return True
            if v in ("false", "0"):
                return False
            raise ValueError(f"期望 true/false，得到: {value_str!r}")
        if expected_type is str:
            return value_str
        if origin is tuple and args:
            parts = [x.strip() for x in value_str.split(",") if x.strip()]
            elem_type = args[0] if args else int
            return tuple(elem_type(p) for p in parts)
        return _guess_and_convert(value_str)
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"参数 {step_type}:{step_name}.{param_name} 类型错误: {e}"
        ) from e


def parse_pipeline(s: str) -> List[PipelineStep]:
    """
    解析管线字符串，强校验 type/name，合法步骤使用其默认参数。
    "integrate,filter:llm,format:zeta,dedup" -> [(type, name, default_params), ...]
    """
    steps = []
    for i, part in enumerate(s.split(",")):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            step_type, step_name = part.split(":", 1)
        else:
            step_type = part
            step_name = DEFAULT_NAMES.get(step_type, "default")

        if step_type not in STEP_TYPES:
            raise ValueError(
                f"管线步骤 {i + 1} 类型无效: '{step_type}'，"
                f"应为 {list(STEP_TYPES)} 之一"
            )

        cls = _get_step_class(step_type, step_name)
        if cls is None:
            valid_names = list(REGISTRIES[step_type].keys())
            raise ValueError(
                f"管线步骤 {i + 1} 名称无效: '{step_name}'，"
                f"{step_type} 可用: {valid_names}"
            )

        default_params = _get_step_defaults(step_type, step_name)
        steps.append((step_type, step_name, default_params))
    return steps


def parse_step_params_from_argv(argv: List[str]) -> Dict[StepKey, Dict[str, Any]]:
    """
    从命令行参数解析步骤参数，强校验 type/name/param/值类型。
    --filter-llm.strict true -> (("filter","llm",0), {"strict": True})
    """
    result: Dict[StepKey, Dict[str, Any]] = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if not arg.startswith("--"):
            i += 1
            continue
        m = STEP_PARAM_PATTERN.match(arg)
        if not m:
            i += 1
            continue
        step_type, step_name, occ_str, param = m.groups()
        occurrence = int(occ_str) if occ_str else 0
        param_name = param.replace("-", "_")

        if step_type not in STEP_TYPES:
            raise ValueError(
                f"未知步骤类型: '{step_type}'，应为 {list(STEP_TYPES)} 之一"
            )
        cls = _get_step_class(step_type, step_name)
        if cls is None:
            valid_names = list(REGISTRIES[step_type].keys())
            raise ValueError(
                f"未知步骤: {step_type}:{step_name}，{step_type} 可用: {valid_names}"
            )
        schema = _get_step_param_schema(step_type, step_name)
        if schema is not None and param_name not in schema:
            raise ValueError(
                f"未知参数 '{param_name}'，{step_type}:{step_name} 接受: {list(schema.keys())}"
            )

        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            value_str = argv[i + 1]
            i += 2
            expected_type = schema.get(param_name) if schema else None
            value = _convert_param_value(
                value_str, param_name, expected_type, step_type, step_name
            )
        else:
            value = True
            i += 1

        key = (step_type, step_name, occurrence)
        if key not in result:
            result[key] = {}
        result[key][param_name] = value
    return result


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def get_step(step_type: str, step_name: str, params: Dict[str, Any]) -> Any:
    """根据类型和名称获取步骤实例"""
    if step_type == INTEGRATE:
        cls = INTEGRATORS.get(step_name)
        if cls is None:
            raise ValueError(f"未知的整合器: {step_name}")
        return cls(**params)
    if step_type == FILTER:
        cls = FILTERS.get(step_name)
        if cls is None:
            raise ValueError(f"未知的过滤器: {step_name}")
        return cls(**params)
    if step_type == FORMAT:
        cls = FORMATTERS.get(step_name)
        if cls is None:
            raise ValueError(f"未知的格式化器: {step_name}")
        return cls(**params)
    if step_type == DEDUP:
        cls = DEDUPERS.get(step_name)
        if cls is None:
            raise ValueError(f"未知的去重器: {step_name}")
        return cls(**params)
    raise ValueError(f"未知的步骤类型: {step_type}")
