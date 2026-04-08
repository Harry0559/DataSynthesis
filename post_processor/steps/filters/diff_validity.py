"""行级 diff 有效性过滤器：判断 ground_truth_content 的改动是否朝 final_content 靠近。

以 content 为基线，分别对 final_content 和 ground_truth_content 做行级 diff，
然后逐块验证 D_pred 的每个非 equal 操作是否落在 D_gold 期望变动的区域且方向一致。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Optional

from ...models.sample import ZETA_DEBUG, ZetaDebugSample
from .base import FilterBase


# ============================================================
# 工具函数
# ============================================================


def _line_ratio(a: str, b: str) -> float:
    """两行文本的相似度（去尾换行后比较）。"""
    return difflib.SequenceMatcher(
        None, a.rstrip("\n"), b.rstrip("\n")
    ).ratio()


def _get_opcodes(
    base: str, target: str
) -> tuple[list[tuple[str, int, int, int, int]], list[str], list[str]]:
    """行级 diff：返回 (opcodes, base_lines, target_lines)。"""
    base_lines = base.splitlines(True)
    target_lines = target.splitlines(True)
    sm = difflib.SequenceMatcher(None, base_lines, target_lines)
    return sm.get_opcodes(), base_lines, target_lines


def _match_lines(
    old_lines: list[str], new_lines: list[str], threshold: float
) -> list[tuple[int, int]]:
    """单调 DP 行匹配：相似度 >= threshold 才能配对，返回有序 [(old_idx, new_idx), ...]。"""
    m, n = len(old_lines), len(new_lines)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
            if _line_ratio(old_lines[i - 1], new_lines[j - 1]) >= threshold:
                dp[i][j] = max(dp[i][j], dp[i - 1][j - 1] + 1)

    matches: list[tuple[int, int]] = []
    i, j = m, n
    while i > 0 and j > 0:
        if (
            _line_ratio(old_lines[i - 1], new_lines[j - 1]) >= threshold
            and dp[i][j] == dp[i - 1][j - 1] + 1
        ):
            matches.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    matches.reverse()
    return matches


def _is_subsequence_match(
    pred_lines: list[str], gold_lines: list[str], threshold: float
) -> bool:
    """pred_lines 是否为 gold_lines 的有序子序列（按相似度匹配），至少一对。"""
    if not pred_lines:
        return True
    gi = 0
    matched = 0
    for pl in pred_lines:
        while gi < len(gold_lines):
            if _line_ratio(pl, gold_lines[gi]) >= threshold:
                matched += 1
                gi += 1
                break
            gi += 1
        else:
            return False
    return matched >= 1


# ============================================================
# ReplaceDetail：replace 块经行匹配后的内部结构
# ============================================================


@dataclass
class ReplaceDetail:
    content_start: int
    content_end: int
    old_lines: list[str]
    new_lines: list[str]
    matched_pairs: list[tuple[int, int]]
    unmatched_old: set[int] = field(default_factory=set)
    unmatched_new: list[int] = field(default_factory=list)


def _build_replace_detail(
    content_start: int,
    old_lines: list[str],
    new_lines: list[str],
    threshold: float,
) -> ReplaceDetail:
    pairs = _match_lines(old_lines, new_lines, threshold)
    matched_old = {p[0] for p in pairs}
    matched_new = {p[1] for p in pairs}
    unmatched_old = {i for i in range(len(old_lines)) if i not in matched_old}
    unmatched_new = [j for j in range(len(new_lines)) if j not in matched_new]
    return ReplaceDetail(
        content_start=content_start,
        content_end=content_start + len(old_lines),
        old_lines=old_lines,
        new_lines=new_lines,
        matched_pairs=pairs,
        unmatched_old=unmatched_old,
        unmatched_new=unmatched_new,
    )


# ============================================================
# GoldMap：D_gold 预处理
# ============================================================

_KEEP = "KEEP"
_DELETE = "DELETE"
_REPLACE = "REPLACE"


@dataclass
class GoldMap:
    line_status: dict[int, str] = field(default_factory=dict)
    replace_details: dict[int, ReplaceDetail] = field(default_factory=dict)
    inserts: dict[int, list[str]] = field(default_factory=dict)


def _build_gold_map(
    content: str, final_content: str, match_threshold: float
) -> GoldMap:
    opcodes, base_lines, target_lines = _get_opcodes(content, final_content)
    gm = GoldMap()
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for i in range(i1, i2):
                gm.line_status[i] = _KEEP
        elif tag == "delete":
            for i in range(i1, i2):
                gm.line_status[i] = _DELETE
        elif tag == "insert":
            gm.inserts[i1] = list(target_lines[j1:j2])
        elif tag == "replace":
            rd = _build_replace_detail(
                i1, list(base_lines[i1:i2]), list(target_lines[j1:j2]),
                match_threshold,
            )
            for i in range(i1, i2):
                gm.line_status[i] = _REPLACE
                gm.replace_details[i] = rd
    return gm


# ============================================================
# 验证 D_pred 每个非 equal 块
# ============================================================


def _verify_pred_delete(
    i1: int, i2: int, gold_map: GoldMap
) -> bool:
    """规则 1：D_pred 的 delete 块。"""
    for i in range(i1, i2):
        status = gold_map.line_status.get(i)
        if status == _DELETE:
            continue
        if status == _REPLACE:
            rd = gold_map.replace_details[i]
            offset = i - rd.content_start
            if offset not in rd.unmatched_old:
                return False
            continue
        return False
    return True


def _verify_pred_insert(
    anchor: int,
    pred_new_lines: list[str],
    gold_map: GoldMap,
    insert_threshold: float,
) -> bool:
    """规则 2：D_pred 的 insert 块。"""
    if anchor in gold_map.inserts:
        return _is_subsequence_match(
            pred_new_lines, gold_map.inserts[anchor], insert_threshold
        )

    status = gold_map.line_status.get(anchor)
    if status == _REPLACE:
        rd = gold_map.replace_details[anchor]
        unmatched_new_lines = [rd.new_lines[j] for j in rd.unmatched_new]
        return _is_subsequence_match(
            pred_new_lines, unmatched_new_lines, insert_threshold
        )

    return False


def _verify_pred_replace(
    i1: int,
    i2: int,
    pred_new_lines: list[str],
    base_lines: list[str],
    gold_map: GoldMap,
    match_threshold: float,
    insert_threshold: float,
    replace_threshold: float,
) -> bool:
    """规则 3：D_pred 的 replace 块。"""
    # 前置：所有行必须为 REPLACE 且属于同一个 gold replace 块
    gold_rd: ReplaceDetail | None = None
    for i in range(i1, i2):
        if gold_map.line_status.get(i) != _REPLACE:
            return False
        rd = gold_map.replace_details[i]
        if gold_rd is None:
            gold_rd = rd
        elif rd is not gold_rd:
            return False
    if gold_rd is None:
        return False

    # 构建 pred 自己的 ReplaceDetail
    pred_old = list(base_lines[i1:i2])
    pred_detail = _build_replace_detail(i1, pred_old, pred_new_lines, match_threshold)

    # gold 侧 matched_pairs 的 old 偏移集合（块内偏移）
    gold_matched_old_offsets = {p[0] for p in gold_rd.matched_pairs}
    # gold 侧的 (old_offset -> new_offset) 映射
    gold_old_to_new = {p[0]: p[1] for p in gold_rd.matched_pairs}

    # 3-i: matched_pairs 验证
    for pred_old_off, pred_new_off in pred_detail.matched_pairs:
        global_line = pred_detail.content_start + pred_old_off
        gold_off = global_line - gold_rd.content_start
        if gold_off not in gold_matched_old_offsets:
            return False
        gold_new_off = gold_old_to_new[gold_off]
        gold_final_line = gold_rd.new_lines[gold_new_off]
        pred_new_line = pred_new_lines[pred_new_off]
        if _line_ratio(pred_new_line, gold_final_line) < replace_threshold:
            return False

    # 3-ii: unmatched_old 验证
    for pred_old_off in pred_detail.unmatched_old:
        global_line = pred_detail.content_start + pred_old_off
        gold_off = global_line - gold_rd.content_start
        if gold_off not in gold_rd.unmatched_old:
            return False

    # 3-iii: unmatched_new 验证
    pred_unmatched_lines = [pred_new_lines[j] for j in pred_detail.unmatched_new]
    gold_unmatched_lines = [gold_rd.new_lines[j] for j in gold_rd.unmatched_new]
    if pred_unmatched_lines:
        if not _is_subsequence_match(
            pred_unmatched_lines, gold_unmatched_lines, insert_threshold
        ):
            return False

    return True


# ============================================================
# DiffValidityFilter
# ============================================================


class DiffValidityFilter(FilterBase):
    """行级 diff 有效性过滤器：判断 ground_truth_content 的改动是否朝 final_content 靠近。

    仅支持 zeta_debug 格式。以 content 为基线，分别对 final_content 和
    ground_truth_content 做行级 diff，逐块验证 D_pred 是否与 D_gold 方向一致。
    """

    input_output_map = {ZETA_DEBUG: ZETA_DEBUG}

    def __init__(
        self,
        match_threshold: float = 0.75,
        insert_threshold: float = 0.8,
        replace_threshold: float = 0.8,
    ) -> None:
        self._match_threshold = match_threshold
        self._insert_threshold = insert_threshold
        self._replace_threshold = replace_threshold

    def process(
        self, sample: ZetaDebugSample, format_name: str
    ) -> Optional[ZetaDebugSample]:
        if format_name != ZETA_DEBUG:
            return None

        content = sample.get("content", "")
        final_content = sample.get("final_content", "")
        gt_content = sample.get("ground_truth_content", "")

        # 特殊情况短路
        if gt_content == final_content:
            return sample
        if content == final_content:
            return sample if content == gt_content else None
        if content == gt_content:
            return None

        # 构建 GoldMap
        gold_map = _build_gold_map(content, final_content, self._match_threshold)

        # 遍历 D_pred 每个非 equal 块
        opcodes, base_lines, _ = _get_opcodes(content, gt_content)
        _, _, pred_target_lines = _get_opcodes(content, gt_content)

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                continue

            if tag == "delete":
                if not _verify_pred_delete(i1, i2, gold_map):
                    return None

            elif tag == "insert":
                pred_new = list(pred_target_lines[j1:j2])
                if not _verify_pred_insert(
                    i1, pred_new, gold_map, self._insert_threshold
                ):
                    return None

            elif tag == "replace":
                pred_new = list(pred_target_lines[j1:j2])
                if not _verify_pred_replace(
                    i1, i2, pred_new, base_lines, gold_map,
                    self._match_threshold,
                    self._insert_threshold,
                    self._replace_threshold,
                ):
                    return None

        return sample
