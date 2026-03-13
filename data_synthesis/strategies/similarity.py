"""
SimilarityStrategy：基于相似度的细粒度重放策略

在行级 diff 的基础上，对 replace 块进行行内细粒度拆分：

1. 行级 diff → equal / delete / insert / replace 四种块
2. equal → 跳过
3. delete → 整行 ForwardDeleteAction
4. insert → 整行 TypeAction（可选切分）
5. replace → 通过相似度做单调行匹配：
   - 匹配成功的行对 → 行内字符级 diff，生成细粒度 Type/Delete
   - 匹配失败的旧行 → 整行删除
   - 匹配失败的新行 → 整行新增

行匹配采用 SequenceMatcher.ratio() + 阈值：ratio >= similarity_threshold 即认为两行值得做行内修改。

匹配必须保持顺序（单调），使用类似 LCS 的 DP 求解最优匹配。

可配置参数（通过 CLI 传入）：
- observe_mode:          观察模式 (all / random / hunk_end / every_n)
- observe_param:         观察参数（random 为概率，every_n 为间隔）
- similarity_threshold:  SequenceMatcher.ratio 阈值（默认 0.75）
- split_mode:            动作拆分模式 (none / random / every_n)
- split_random_prob:     随机拆分概率，概率越大每个片段越长
- split_every_n:         every_n 模式下，每 N 个字符拆分一次
- merge_mode:            动作合并模式 (none / random / full / batch_n)
- merge_random_prob:     随机合并概率，概率越大越容易合并
- merge_batch_size:      batch_n 模式下单组最多合并的动作数
- observe_after_delete:  删除动作后是否允许紧接着插入 ObserveAction
- split_merge_order:     拆分/合并整体顺序 (none / split_only / merge_only / split_then_merge / merge_then_split)
"""

from __future__ import annotations

import difflib
import random
from typing import List, Tuple

from ..core.models import (
    ChangeSet,
    FileFinalState,
    FileInitState,
    ForwardDeleteAction,
    ObserveAction,
    ObserveConfig,
    TypeAction,
    TypePlan,
)
from .base import PlanStrategy


# ============================================================
# 相似度计算（纯 Python，无外部依赖，当前未使用）
# ============================================================


def _levenshtein_distance(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def _levenshtein_ratio(a: str, b: str) -> float:
    """1 - distance / max(len(a), len(b))，值域 [0, 1]。"""
    if not a and not b:
        return 1.0
    dist = _levenshtein_distance(a, b)
    return 1.0 - dist / max(len(a), len(b))


def _jaro_similarity(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0

    for i in range(len1):
        lo = max(0, i - match_distance)
        hi = min(i + match_distance + 1, len2)
        for j in range(lo, hi):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    transpositions = 0
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (
        matches / len1 + matches / len2 + (matches - transpositions / 2) / matches
    ) / 3


def _jaro_winkler_similarity(s1: str, s2: str) -> float:
    """前缀加权 p=0.1，前缀长度上限 4。"""
    jaro = _jaro_similarity(s1, s2)
    prefix_len = 0
    for i in range(min(4, len(s1), len(s2))):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    return jaro + prefix_len * 0.1 * (1 - jaro)


# ============================================================
# 观察采样器
# ============================================================


class _ObserveSampler:
    """根据 observe_mode 决定是否在当前动作后插入 ObserveAction。

    hunk_end 模式下 after_action 始终返回 False，由外部在块末尾显式插入。
    """

    def __init__(self, mode: str, param: float) -> None:
        self.mode = mode
        self.param = param
        self._action_count = 0

    def after_action(self) -> bool:
        self._action_count += 1
        if self.mode == "all":
            return True
        if self.mode == "random":
            return random.random() < self.param
        if self.mode == "every_n":
            n = max(1, int(self.param))
            return self._action_count % n == 0
        return False


# ============================================================
# 策略实现
# ============================================================


class SimilarityStrategy(PlanStrategy):
    """基于相似度的细粒度重放策略"""

    def __init__(
        self,
        observe_mode: str = "all",
        observe_param: float = 0.3,
        similarity_threshold: float = 0.75,
        split_mode: str = "none",
        split_random_prob: float = 0.5,
        split_every_n: int = 0,
        merge_mode: str = "none",
        merge_random_prob: float = 0.5,
        merge_batch_size: int = 0,
        observe_after_delete: bool = True,
        split_merge_order: str = "none",
    ) -> None:
        self._observe_mode = observe_mode
        self._observe_param = observe_param
        self._similarity_threshold = similarity_threshold
        self._split_mode = split_mode
        self._split_random_prob = split_random_prob
        self._split_every_n = split_every_n
        self._merge_mode = merge_mode
        self._merge_random_prob = merge_random_prob
        self._merge_batch_size = merge_batch_size
        self._observe_after_delete = observe_after_delete
        # 拆分/合并整体顺序：none / split_only / merge_only / split_then_merge / merge_then_split
        self._split_merge_order = split_merge_order

    @property
    def name(self) -> str:
        return "similarity"

    # ----------------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------------

    def generate(self, change_set: ChangeSet, observe_config: ObserveConfig) -> TypePlan:
        file_init_states: List[FileInitState] = []
        file_final_states: List[FileFinalState] = []
        actions: List[object] = []

        for fc in change_set.file_changes:
            file_init_states.append(
                FileInitState(
                    relative_path=fc.relative_path,
                    content=fc.before_content,
                    is_new_file=fc.is_new_file,
                )
            )
            final_content = "" if fc.is_deleted else fc.after_content
            file_final_states.append(
                FileFinalState(
                    relative_path=fc.relative_path,
                    content=final_content,
                    is_deleted=fc.is_deleted,
                )
            )
            file_actions = self._generate_actions_for_file(
                relative_path=fc.relative_path,
                before_content=fc.before_content,
                after_content=fc.after_content,
            )
            actions.extend(file_actions)

        metadata = {
            "strategy": self.name,
            "observe_mode": self._observe_mode,
            "observe_param": self._observe_param,
            "similarity_threshold": self._similarity_threshold,
            "split_mode": self._split_mode,
            "split_random_prob": self._split_random_prob,
            "split_every_n": self._split_every_n,
            "merge_mode": self._merge_mode,
            "merge_random_prob": self._merge_random_prob,
            "merge_batch_size": self._merge_batch_size,
            "observe_after_delete": self._observe_after_delete,
            "split_merge_order": self._split_merge_order,
            "source_metadata": change_set.metadata,
        }

        return TypePlan(
            file_init_states=file_init_states,
            actions=actions,
            file_final_states=file_final_states,
            observe_config=observe_config,
            metadata=metadata,
        )

    # ----------------------------------------------------------------
    # 文件级 action 生成
    # ----------------------------------------------------------------

    def _generate_actions_for_file(
        self,
        relative_path: str,
        before_content: str,
        after_content: str,
    ) -> List[object]:
        actions: List[object] = []
        if not before_content and not after_content:
            return actions

        before_lines = before_content.splitlines()
        before_lines_nl = before_content.splitlines(keepends=True)
        after_lines = after_content.splitlines()
        after_lines_nl = after_content.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
        current_line = 1

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                current_line += i2 - i1
                continue

            # 为当前 opcode/hunk 构建基础动作列表（不含 Observe，未做拆分/合并）
            hunk_actions: List[object] = []

            if tag == "delete":
                for k in range(i1, i2):
                    old_line = before_lines_nl[k]
                    if not old_line:
                        continue
                    hunk_actions.append(
                        ForwardDeleteAction(
                            file=relative_path,
                            line=current_line,
                            col=1,
                            content=old_line,
                        )
                    )

            elif tag == "insert":
                for k in range(j1, j2):
                    new_line = after_lines_nl[k]
                    if not new_line:
                        continue
                    hunk_actions.append(
                        TypeAction(
                            file=relative_path,
                            line=current_line,
                            col=1,
                            content=new_line,
                        )
                    )
                    current_line += 1

            elif tag == "replace":
                current_line, replace_actions = self._handle_replace(
                    relative_path,
                    before_lines_nl[i1:i2],
                    after_lines_nl[j1:j2],
                    current_line,
                )
                hunk_actions.extend(replace_actions)

            # 对当前 hunk 的基础动作应用拆分/合并（整体顺序由 split_merge_order 控制），然后插入 Observe
            order = self._split_merge_order
            if order == "none":
                # 不拆分也不合并
                pass
            elif order == "split_only":
                hunk_actions = self._apply_split(hunk_actions)
            elif order == "merge_only":
                hunk_actions = self._apply_merge(hunk_actions)
            elif order == "split_then_merge":
                hunk_actions = self._apply_split(hunk_actions)
                hunk_actions = self._apply_merge(hunk_actions)
            elif order == "merge_then_split":
                hunk_actions = self._apply_merge(hunk_actions)
                hunk_actions = self._apply_split(hunk_actions)

            hunk_actions = self._apply_observe(hunk_actions)

            actions.extend(hunk_actions)

            if self._observe_mode == "hunk_end":
                actions.append(ObserveAction())

        return actions

    # ----------------------------------------------------------------
    # replace 块处理：行匹配 + 行内 diff
    # ----------------------------------------------------------------

    def _handle_replace(
        self,
        file: str,
        old_lines_nl: List[str],
        new_lines_nl: List[str],
        current_line: int,
    ) -> Tuple[int, List[object]]:
        """处理 replace 块，返回 (更新后的 current_line, 基础动作列表)。"""
        old_stripped = [l.rstrip("\n") for l in old_lines_nl]
        new_stripped = [l.rstrip("\n") for l in new_lines_nl]

        matches = self._match_lines(old_stripped, new_stripped)

        old_idx = 0
        new_idx = 0
        actions: List[object] = []

        for oi, ni in matches:
            # 删除匹配前的未匹配旧行
            while old_idx < oi:
                if old_lines_nl[old_idx]:
                    actions.append(
                        ForwardDeleteAction(
                            file=file,
                            line=current_line,
                            col=1,
                            content=old_lines_nl[old_idx],
                        )
                    )
                old_idx += 1

            # 插入匹配前的未匹配新行
            while new_idx < ni:
                if new_lines_nl[new_idx]:
                    actions.append(
                        TypeAction(
                            file=file,
                            line=current_line,
                            col=1,
                            content=new_lines_nl[new_idx],
                        )
                    )
                    current_line += 1
                new_idx += 1

            # 行内修改：字符级 diff
            inline_actions = self._inline_diff(
                file, old_lines_nl[oi], new_lines_nl[ni], current_line
            )
            for ia in inline_actions:
                actions.append(ia)
            current_line += 1
            old_idx = oi + 1
            new_idx = ni + 1

        # 处理剩余未匹配旧行
        while old_idx < len(old_lines_nl):
            if old_lines_nl[old_idx]:
                actions.append(
                    ForwardDeleteAction(
                        file=file,
                        line=current_line,
                        col=1,
                        content=old_lines_nl[old_idx],
                    )
                )
            old_idx += 1

        # 处理剩余未匹配新行
        while new_idx < len(new_lines_nl):
            if new_lines_nl[new_idx]:
                actions.append(
                    TypeAction(
                        file=file,
                        line=current_line,
                        col=1,
                        content=new_lines_nl[new_idx],
                    )
                )
                current_line += 1
            new_idx += 1

        return current_line, actions

    # ----------------------------------------------------------------
    # 行匹配（单调 DP + 相似度阈值）
    # ----------------------------------------------------------------

    def _match_lines(
        self, old_lines: List[str], new_lines: List[str]
    ) -> List[Tuple[int, int]]:
        """
        在保持顺序的前提下，找出旧行与新行之间的最优匹配。
        使用类似 LCS 的 DP，只有相似度满足阈值的行对才能配对。
        返回 [(old_idx, new_idx), ...] 列表。
        """
        m, n = len(old_lines), len(new_lines)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
                if self._is_similar(old_lines[i - 1], new_lines[j - 1]):
                    dp[i][j] = max(dp[i][j], dp[i - 1][j - 1] + 1)

        matches: List[Tuple[int, int]] = []
        i, j = m, n
        while i > 0 and j > 0:
            if (
                self._is_similar(old_lines[i - 1], new_lines[j - 1])
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

    def _is_similar(self, old_line: str, new_line: str) -> bool:
        """
        判断两行是否足够相似，值得做行内修改而非整行删除+新增。
        使用 SequenceMatcher.ratio() >= similarity_threshold 作为判断条件。
        """
        if old_line == new_line:
            return True
        if not old_line or not new_line:
            return False

        return difflib.SequenceMatcher(None, old_line, new_line).ratio() >= self._similarity_threshold

    # ----------------------------------------------------------------
    # 行内 diff（字符级）
    # ----------------------------------------------------------------

    def _inline_diff(
        self,
        file: str,
        old_line_nl: str,
        new_line_nl: str,
        line_no: int,
    ) -> List[object]:
        """对一对匹配行做字符级 diff，生成细粒度 Type/Delete 动作序列。"""
        old_text = old_line_nl.rstrip("\n")
        new_text = new_line_nl.rstrip("\n")
        old_has_nl = old_line_nl.endswith("\n")
        new_has_nl = new_line_nl.endswith("\n")

        actions: List[object] = []
        sm = difflib.SequenceMatcher(None, old_text, new_text)
        col = 1

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                col += i2 - i1
            elif tag == "delete":
                actions.append(
                    ForwardDeleteAction(
                        file=file, line=line_no, col=col, content=old_text[i1:i2]
                    )
                )
            elif tag == "insert":
                actions.append(
                    TypeAction(
                        file=file, line=line_no, col=col, content=new_text[j1:j2]
                    )
                )
                col += j2 - j1
            elif tag == "replace":
                actions.append(
                    ForwardDeleteAction(
                        file=file, line=line_no, col=col, content=old_text[i1:i2]
                    )
                )
                actions.append(
                    TypeAction(
                        file=file, line=line_no, col=col, content=new_text[j1:j2]
                    )
                )
                col += j2 - j1

        if old_has_nl and not new_has_nl:
            actions.append(
                ForwardDeleteAction(file=file, line=line_no, col=col, content="\n")
            )
        elif not old_has_nl and new_has_nl:
            actions.append(
                TypeAction(file=file, line=line_no, col=col, content="\n")
            )

        return actions

    # ----------------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------------

    def _apply_split(self, actions: List[object]) -> List[object]:
        """根据 split_* 配置，对单个 hunk 内的动作做拆分。"""
        if self._split_mode == "none":
            return actions

        result: List[object] = []
        for action in actions:
            if isinstance(action, (TypeAction, ForwardDeleteAction)):
                if self._split_mode == "random":
                    result.extend(self._split_action_random(action))
                elif self._split_mode == "every_n":
                    result.extend(self._split_action_every_n(action))
                else:
                    result.append(action)
            else:
                result.append(action)
        return result

    def _split_action_random(self, action: object) -> List[object]:
        """按随机概率将单个动作的 content 拆为多个子动作。"""
        content = getattr(action, "content", "")
        if not content:
            return [action]

        prob = self._split_random_prob
        chunks: List[str] = []
        current_chunk: List[str] = []

        for ch in content:
            if not current_chunk:
                current_chunk.append(ch)
                continue
            # 以 prob 的概率继续当前 chunk，否则开启新 chunk
            if random.random() < prob:
                current_chunk.append(ch)
            else:
                chunks.append("".join(current_chunk))
                current_chunk = [ch]
        if current_chunk:
            chunks.append("".join(current_chunk))

        result: List[object] = []
        line = action.line
        col = action.col
        for chunk in chunks:
            if isinstance(action, TypeAction):
                sub = TypeAction(file=action.file, line=line, col=col, content=chunk)
            else:
                sub = ForwardDeleteAction(
                    file=action.file, line=line, col=col, content=chunk
                )
            result.append(sub)
            line, col = sub.get_end_cursor()
        return result

    def _split_action_every_n(self, action: object) -> List[object]:
        """每 N 个字符拆分一次单个动作。"""
        n = max(1, int(self._split_every_n)) if self._split_every_n else 0
        content = getattr(action, "content", "")
        if not content or n <= 0 or len(content) <= n:
            return [action]

        result: List[object] = []
        line = action.line
        col = action.col
        remaining = content

        while remaining:
            chunk = remaining[:n]
            remaining = remaining[n:]
            if isinstance(action, TypeAction):
                sub = TypeAction(file=action.file, line=line, col=col, content=chunk)
            else:
                sub = ForwardDeleteAction(
                    file=action.file, line=line, col=col, content=chunk
                )
            result.append(sub)
            line, col = sub.get_end_cursor()
        return result

    def _apply_merge(self, actions: List[object]) -> List[object]:
        """根据 merge_* 配置，对单个 hunk 内的动作做合并。"""
        if self._merge_mode == "none":
            return actions

        result: List[object] = []
        current_group: List[object] = []

        def flush_group():
            if not current_group:
                return
            merged = self._merge_group(current_group)
            result.append(merged)
            current_group.clear()

        for action in actions:
            if not isinstance(action, (TypeAction, ForwardDeleteAction)):
                flush_group()
                result.append(action)
                continue

            if not current_group:
                current_group.append(action)
                continue

            last = current_group[-1]
            if not self._can_merge(last, action):
                flush_group()
                current_group.append(action)
                continue

            if self._merge_mode == "random":
                if random.random() < self._merge_random_prob:
                    current_group.append(action)
                else:
                    flush_group()
                    current_group.append(action)
            elif self._merge_mode == "full":
                current_group.append(action)
            elif self._merge_mode == "batch_n":
                max_size = max(1, int(self._merge_batch_size)) if self._merge_batch_size else 1
                if len(current_group) < max_size:
                    current_group.append(action)
                else:
                    flush_group()
                    current_group.append(action)
            else:
                current_group.append(action)

        flush_group()
        return result

    def _can_merge(self, a: object, b: object) -> bool:
        """判断两个动作是否可以合并。"""
        if type(a) is not type(b):
            return False
        if not isinstance(a, (TypeAction, ForwardDeleteAction)):
            return False
        if a.file != b.file:
            return False
        end_line, end_col = a.get_end_cursor()
        return (end_line, end_col) == (b.line, b.col)

    def _merge_group(self, group: List[object]) -> object:
        """将一组可合并的动作合并为单个动作。"""
        if len(group) == 1:
            return group[0]
        first = group[0]
        contents = [getattr(a, "content", "") for a in group]
        merged_content = "".join(contents)
        if isinstance(first, TypeAction):
            return TypeAction(
                file=first.file,
                line=first.line,
                col=first.col,
                content=merged_content,
            )
        return ForwardDeleteAction(
            file=first.file,
            line=first.line,
            col=first.col,
            content=merged_content,
        )

    def _apply_observe(self, actions: List[object]) -> List[object]:
        """在拆分/合并后的动作序列上插入 ObserveAction。"""
        # hunk_end 模式下，采样器永远返回 False，只在外层每个 hunk 末尾插一次
        sampler_mode = self._observe_mode if self._observe_mode != "hunk_end" else "none"
        sampler = _ObserveSampler(sampler_mode, self._observe_param)

        result: List[object] = []
        for action in actions:
            result.append(action)
            if isinstance(action, ObserveAction):
                continue
            if self._observe_mode == "hunk_end":
                continue
            if sampler.after_action():
                if isinstance(action, ForwardDeleteAction) and not self._observe_after_delete:
                    continue
                result.append(ObserveAction())
        return result
