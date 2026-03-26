"""LLM 评估过滤器：调用 LLM 对 predicted_content 进行评估，将 score 写入样本并按 total_score 过滤"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from ...models.sample import ZETA_DEBUG, ZetaDebugSample
from .base import FilterBase

logger = logging.getLogger(__name__)

INVALID_TOTAL_SCORE = -1

# score_mode: always=总是调用并覆盖/新增；fill=仅无 score 时调用；skip=不调用
ScoreMode = Literal["always", "fill", "skip"]

PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompt.md"

_REQUIRED_SCORE_KEYS = (
    "direction",
    "functionality",
    "implementation",
    "incremental_value",
    "acceptability",
    "total_score",
    "reasoning",
    "key_observations",
)


def _load_prompt_template() -> str:
    """加载 prompt 模板。"""
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _build_prompt(sample: ZetaDebugSample) -> str:
    """从 zeta_debug 样本构建 prompt，替换四个占位符。"""
    template = _load_prompt_template()
    return (
        template.replace("{prev_content}", sample.get("prev_content", ""))
        .replace("{content}", sample.get("content", ""))
        .replace("{predicted_content}", sample.get("ground_truth_content", ""))
        .replace("{final_content}", sample.get("final_content", ""))
    )


def _parse_score_response(text: str) -> Dict[str, Any] | None:
    """从 LLM 返回中解析 JSON，支持 ```json ... ``` 包裹；校验必需字段。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    if start < 0:
        return None
    end = text.rfind("}") + 1
    if end <= start:
        return None
    try:
        obj = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None

    if not isinstance(obj, dict):
        return None
    missing = [k for k in _REQUIRED_SCORE_KEYS if k not in obj]
    if missing:
        logger.debug("LlmFilter 解析的 JSON 缺少字段 %s，视为解析失败", missing)
        return None

    return obj


def _extract_total_score(score_dict: Dict[str, Any]) -> int:
    """从 score 中提取 total_score，缺失或非法时返回 INVALID_TOTAL_SCORE。"""
    val = score_dict.get("total_score")
    if val is None:
        return INVALID_TOTAL_SCORE
    try:
        n = int(val) if isinstance(val, (int, float)) else INVALID_TOTAL_SCORE
        return n if n >= 0 else INVALID_TOTAL_SCORE
    except (ValueError, TypeError):
        return INVALID_TOTAL_SCORE


def _in_range(total_score: int, score_range: tuple[int, int]) -> bool:
    """判断 total_score 是否在 [lo, hi] 闭区间内。"""
    lo, hi = score_range
    return lo <= total_score <= hi


class LlmFilter(FilterBase):
    """LLM 评估过滤器：对 zeta_debug 样本调用 LLM 评估，将 score 写入样本并按 total_score 范围过滤。
    - score_mode: always=总是调用；fill=仅无 score 时调用；skip=不调用
    - score_range 为闭区间 [min, max]，默认 (0, 25)；获取总分失败或不在区间内则丢弃
    - score_mode 非 skip 时，LLM_API_KEY、LLM_API_URL、LLM_MODEL 须在 .env 中配置
    """

    input_output_map = {ZETA_DEBUG: ZETA_DEBUG}

    def __init__(
        self,
        score_mode: ScoreMode = "fill",
        score_range: tuple[int, int] = (0, 25),
        max_tokens: int = 2000,
        drop_on_invalid_score: bool = False,
    ) -> None:
        if score_mode not in ("always", "fill", "skip"):
            raise ValueError(
                f"score_mode 须为 always/fill/skip，得到: {score_mode!r}"
            )
        self._score_mode = score_mode
        self._score_range = score_range
        self._max_tokens = max_tokens
        self._drop_on_invalid_score = drop_on_invalid_score
        self._client = None

        if score_mode != "skip":
            self._api_key = os.environ.get("LLM_API_KEY") or ""
            self._api_url = (os.environ.get("LLM_API_URL") or "").rstrip("/")
            self._model = os.environ.get("LLM_MODEL") or ""
            if not self._api_key:
                raise ValueError("LlmFilter 需要 LLM_API_KEY，请在 .env 中配置")
            if not self._api_url:
                raise ValueError("LlmFilter 需要 LLM_API_URL，请在 .env 中配置")
            if not self._model:
                raise ValueError("LlmFilter 需要 LLM_MODEL，请在 .env 中配置")
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key, base_url=self._api_url)

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM，返回回复文本。"""
        t0 = time.perf_counter()
        r = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self._max_tokens,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        h, rest = divmod(int(elapsed_ms) // 1000, 3600)
        m, s = divmod(rest, 60)
        ms = int(elapsed_ms % 1000)
        print(f"LlmFilter 请求耗时: {h:02d}:{m:02d}:{s:02d}.{ms:03d}")

        u = getattr(r, "usage", None)
        if u is not None:
            p = getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", 0) or 0
            c = getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", 0) or 0
            t = getattr(u, "total_tokens", None) or (p + c)
            print(f"LlmFilter Token: 输入={p} 输出={c} 总计={t}")
        else:
            print("LlmFilter Token: 无 usage 数据")

        return (r.choices[0].message.content or "").strip()

    def process(
        self, sample: ZetaDebugSample, format_name: str
    ) -> Optional[ZetaDebugSample]:
        out = dict(sample)
        has_score_before = "score" in sample

        # 1. Score 生成
        if self._score_mode == "skip":
            pass
        elif self._score_mode == "fill" and has_score_before:
            pass
        else:
            prompt = _build_prompt(sample)
            try:
                answer = self._call_llm(prompt)
            except Exception as e:
                logger.warning("LlmFilter 调用失败: %s", e)
                if self._score_mode == "always" and has_score_before:
                    out.pop("score", None)
            else:
                score_dict = _parse_score_response(answer)
                if score_dict is not None:
                    out["score"] = score_dict
                else:
                    logger.warning("LlmFilter 无法解析 JSON")
                    if self._score_mode == "always" and has_score_before:
                        out.pop("score", None)

        # 2. 按 total_score 过滤
        score_dict = out.get("score")
        if score_dict is None:
            if self._drop_on_invalid_score:
                return None
            return out
        total_score = _extract_total_score(score_dict)
        if total_score == INVALID_TOTAL_SCORE:
            if self._drop_on_invalid_score:
                return None
            return out
        if not _in_range(total_score, self._score_range):
            return None

        return out
