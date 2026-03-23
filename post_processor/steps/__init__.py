"""步骤注册表与解析"""

from __future__ import annotations

import inspect
import re
from typing import Any, Dict, List, Optional, get_args, get_origin, get_type_hints

from ..models.config import PipelineStep, StepKey
from ..models.sample import ZETA, ZETA_DEBUG

from .base import StepIOBase

# 步骤类型
INTEGRATE = "integrate"
FILTER = "filter"
FORMAT = "format"
DEDUP = "dedup"
SORT = "sort"

# 注册表
from .dedupers import DeduperBase, SimHashDeduplicator
from .filters import ContFilter, EditFilter, FilterBase, LlmFilter
from .formatters import FormatterBase, ZetaDebugFormatter, ZetaFormatter
from .integrators import DefaultIntegrator, IntegratorBase
from .sorters import ShuffleSorter, SorterBase

INTEGRATORS: Dict[str, type] = {"default": DefaultIntegrator}
FILTERS: Dict[str, type] = {
    "llm": LlmFilter,
    "edit": EditFilter,
    "cont": ContFilter,
}
FORMATTERS: Dict[str, type] = {
    ZETA: ZetaFormatter,
    ZETA_DEBUG: ZetaDebugFormatter,
}
DEDUPERS: Dict[str, type] = {"simhash": SimHashDeduplicator}
SORTERS: Dict[str, type] = {"shuffle": ShuffleSorter}

STEP_TYPES = (INTEGRATE, FILTER, FORMAT, DEDUP, SORT)
REGISTRIES: Dict[str, Dict[str, type]] = {
    INTEGRATE: INTEGRATORS,
    FILTER: FILTERS,
    FORMAT: FORMATTERS,
    DEDUP: DEDUPERS,
    SORT: SORTERS,
}

DEFAULT_NAMES: Dict[str, str] = {
    INTEGRATE: "default",
    FILTER: "llm",
    FORMAT: ZETA,
    DEDUP: "simhash",
    SORT: "shuffle",
}

# --<type>-<name>.<occ?>.<param> 模式（匹配时传入 arg 或 arg[2:] 均可）
STEP_PARAM_PATTERN = re.compile(
    r"^(?:--)?([a-z]+)-([a-z0-9_]+)(?:\.(\d+))?\.(.+)$"
)


def _resolve_step(
    step_type: str, step_name: str, *, step_index: Optional[int] = None
) -> type:
    """检查 (step_type, step_name) 合法并返回 cls，否则 raise。"""
    if step_type not in STEP_TYPES:
        if step_index is not None:
            raise ValueError(
                f"管线步骤 {step_index} 类型无效: '{step_type}'，"
                f"应为 {list(STEP_TYPES)} 之一"
            )
        raise ValueError(
            f"未知步骤类型: '{step_type}'，应为 {list(STEP_TYPES)} 之一"
        )
    cls = REGISTRIES.get(step_type, {}).get(step_name)
    if cls is None:
        valid = list(REGISTRIES.get(step_type, {}).keys())
        if step_index is not None:
            raise ValueError(
                f"管线步骤 {step_index} 名称无效: '{step_name}'，"
                f"{step_type} 可用: {valid}"
            )
        raise ValueError(
            f"未知步骤: {step_type}:{step_name}，{step_type} 可用: {valid}"
        )
    return cls


def _get_init_overridable_params(
    cls: type,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """从 cls.__init__ 提取可覆盖参数：schema（类型）和 defaults（默认值）。跳过 self 和 **kwargs。"""
    sig = inspect.signature(cls.__init__)
    schema: Dict[str, Any] = {}
    defaults: Dict[str, Any] = {}
    try:
        hints = get_type_hints(cls.__init__)
    except Exception:
        hints = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            continue
        schema[name] = hints.get(name)
        defaults[name] = (
            param.default if param.default != inspect.Parameter.empty else None
        )
    return schema, defaults


def _guess_and_convert(value_str: str) -> Any:
    """无类型注解时的启发式转换"""
    v = value_str.lower()
    if v == "true":
        return True
    if v == "false":
        return False
    if value_str.lstrip("-").isdigit():
        return int(value_str)
    try:
        return float(value_str)
    except ValueError:
        pass
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
        type_hint = f"（期望 {expected_type.__name__}）" if expected_type else ""
        raise ValueError(
            f"参数 {step_type}:{step_name}.{param_name} 类型错误{type_hint}: {e}"
        ) from e


def parse_pipeline(s: str) -> List[PipelineStep]:
    """
    解析管线字符串，强校验 type/name。
    返回 [(step_type, step_name), ...]，不保存默认值。
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

        _resolve_step(step_type, step_name, step_index=i + 1)
        steps.append((step_type, step_name))
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

        cls = _resolve_step(step_type, step_name)
        schema, defaults = _get_init_overridable_params(cls)
        if param_name not in schema:
            if not schema:
                raise ValueError(
                    f"步骤 {step_type}:{step_name} 无参数，不能传入 '{param_name}'"
                )
            raise ValueError(
                f"未知参数 '{param_name}'，{step_type}:{step_name} "
                f"接受的参数及默认值: {defaults}"
            )

        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            value_str = argv[i + 1]
            i += 2
            expected_type = schema.get(param_name) if schema else None
            value = _convert_param_value(
                value_str, param_name, expected_type, step_type, step_name
            )
        else:
            expected_type = schema.get(param_name) if schema else None
            if expected_type is not None:
                origin = get_origin(expected_type)
                args = get_args(expected_type) if origin is not None else ()
                if origin is not None and args:
                    non_none = [a for a in args if a is not type(None)]
                    if len(non_none) == 1:
                        expected_type = non_none[0]
            if expected_type is not bool:
                raise ValueError(
                    f"参数 {step_type}:{step_name}.{param_name} 省略值时仅支持 bool 类型，请显式提供值"
                )
            value = True
            i += 1

        key = (step_type, step_name, occurrence)
        if key not in result:
            result[key] = {}
        result[key][param_name] = value
    return result


def get_step(step_type: str, step_name: str, params: Dict[str, Any]) -> Any:
    """根据类型和名称获取步骤实例。params 为空则 cls()，否则 cls(**params)"""
    cls = _resolve_step(step_type, step_name)
    schema, _ = _get_init_overridable_params(cls)
    if not schema and params:
        raise ValueError(
            f"步骤 {step_type}:{step_name} 无参数，但传入了: {list(params.keys())}"
        )
    return cls() if not params else cls(**params)
