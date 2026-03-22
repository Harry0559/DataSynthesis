"""Zeta 格式化共享实现：路径、diff、io 构造"""

from __future__ import annotations

import difflib
import random
from typing import Any, Dict, Optional, Tuple

from ...models.sample import StandardSample

INSTRUCTION_TEMPLATE = (
    "You are an {lang} code completion assistant and your task is to analyze "
    "user edits and then rewrite an excerpt that the user provides, suggesting "
    "the appropriate edits within the excerpt, taking into account the cursor "
    "location.\n"
)


def to_posix_path(path: str) -> str:
    """将路径中的反斜杠统一替换为正斜杠，用于 zeta 格式的展示与匹配。"""
    return path.replace("\\", "/")


def build_line_diff(prev_text: str, curr_text: str) -> str:
    """构造从 prev_text 到 curr_text 的行级 unified diff 字符串，仅保留从第一个 @@ 开始的部分。"""
    prev_lines = prev_text.splitlines()
    curr_lines = curr_text.splitlines()
    diff_lines = list(
        difflib.unified_diff(
            prev_lines,
            curr_lines,
            fromfile="prev",
            tofile="curr",
            lineterm="",
            n=3,
        )
    )
    start_idx = 0
    for i, line in enumerate(diff_lines):
        if line.startswith("@@"):
            start_idx = i
            break
    trimmed = diff_lines[start_idx:]
    return "\n".join(trimmed)


def build_zeta_io(
    standard_sample: StandardSample,
    source_metadata: Dict[str, Any],
    norm_file: str,
    region_radius_min: int,
    region_radius_max: int,
    context_radius_min: int,
    context_radius_max: int,
) -> Optional[Tuple[str, str, str]]:
    """
    一次性构造 zeta 的 input 与 ground_truth 字段。
    返回 (input, ground_truth, ground_truth_content)；若样本根据 patch/window 规则无效，则返回 None。
    """
    file = standard_sample.get("file")
    cursor = standard_sample.get("cursor") or {}
    prev_content = standard_sample.get("prev_content", "")
    content = standard_sample.get("content", "")
    model_output = standard_sample.get("model_output", "") or ""

    if not isinstance(file, str) or not file:
        return None

    cursor_line = cursor.get("line")
    cursor_col = cursor.get("col")
    if not isinstance(cursor_line, int) or not isinstance(cursor_col, int):
        return None

    lang = source_metadata.get("lang")
    if not isinstance(lang, str) or not lang.strip():
        return None

    # ===== Section 1: Instruction =====
    instruction_text = INSTRUCTION_TEMPLATE.format(lang=lang)
    section_instruction = "### Instruction:\n" + instruction_text.strip() + "\n"

    # ===== Section 2: User Edits =====
    user_edits_header = f'User edited "{norm_file}":'
    diff_str = build_line_diff(prev_content, content)
    section_user_edits = (
        "### User Edits:\n"
        f"{user_edits_header}\n"
        "```diff\n"
        f"{diff_str}\n"
        "```\n"
    )

    # ===== Section 3: User Excerpt =====
    lines = content.splitlines()
    line_count = len(lines)

    cursor_idx = max(0, min(line_count - 1, cursor_line - 1))
    col_idx = max(0, cursor_col - 1)

    line_text = lines[cursor_idx]
    if col_idx > len(line_text):
        col_idx = len(line_text)
    lines[cursor_idx] = (
        line_text[:col_idx]
        + "<|user_cursor_is_here|>"
        + line_text[col_idx:]
    )

    cursor_idx_marked = cursor_idx
    available_up = cursor_idx_marked
    available_down = line_count - 1 - cursor_idx_marked

    radius_ctx = random.randint(context_radius_min, context_radius_max)
    up = min(radius_ctx, available_up)
    down = min(radius_ctx, available_down)

    if up < radius_ctx:
        extra = radius_ctx - up
        down = min(radius_ctx + extra, available_down)
    if down < radius_ctx:
        extra = radius_ctx - down
        up = min(radius_ctx + extra, available_up)

    ctx_start_full = cursor_idx_marked - up
    ctx_end_full = cursor_idx_marked + down

    context_lines = lines[ctx_start_full : ctx_end_full + 1]

    MARK_START = "<|editable_region_start|>"
    MARK_END = "<|editable_region_end|>"

    def find_cursor_index_local(lines_: list[str]) -> int:
        for idx, t in enumerate(lines_):
            if "<|user_cursor_is_here|>" in t:
                return idx
        return 0

    cursor_local_idx = find_cursor_index_local(context_lines)

    radius_region = random.randint(region_radius_min, region_radius_max)
    editable_start_local = max(0, cursor_local_idx - radius_region)
    editable_end_local = min(len(context_lines) - 1, cursor_local_idx + radius_region)

    context_with_markers: list[str] = []
    for i, text in enumerate(context_lines):
        if i == editable_start_local:
            context_with_markers.append(MARK_START)
        context_with_markers.append(text)
        if i == editable_end_local:
            context_with_markers.append(MARK_END)

    user_excerpt_body = "\n".join(context_with_markers)

    section_user_excerpt = (
        "### User Excerpt:\n"
        f"```{norm_file}\n"
        f"{user_excerpt_body}\n"
        "```\n"
    )

    section_response = "### Response:\n\n"

    input_text = (
        section_instruction.rstrip()
        + "\n\n"
        + section_user_edits.rstrip()
        + "\n\n"
        + section_user_excerpt.rstrip()
        + "\n\n"
        + section_response.rstrip()
        + "\n"
    )

    win_start_full = ctx_start_full + editable_start_local
    win_end_full = ctx_start_full + editable_end_local

    content_lines = content.splitlines()
    total_lines = len(content_lines)
    if total_lines == 0:
        return None

    win_start_full = max(0, min(win_start_full, max(0, total_lines - 1)))
    win_end_full = max(0, min(win_end_full, max(0, total_lines - 1)))
    if win_start_full > win_end_full:
        win_start_full, win_end_full = win_end_full, win_start_full

    # ===== 解析 model_output 为 patch 序列 =====
    lines_mo = model_output.splitlines()

    patches: list[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for line in lines_mo:
        line = line.rstrip("\n")
        if line.startswith("@@"):
            if current is not None:
                patches.append(current)
            header = line[2:].strip()
            try:
                file_part, line_part = header.split(":", 1)
                start_line = int(line_part.strip())
            except Exception:
                current = None
                continue
            current = {
                "file": file_part.strip(),
                "start": start_line,
                "dels": [],
                "adds": [],
            }
        else:
            if current is None:
                continue
            if line.startswith("-|"):
                current["dels"].append(line[2:])
            elif line.startswith("+|"):
                current["adds"].append(line[2:])

    if current is not None:
        patches.append(current)

    filtered: list[Dict[str, Any]] = []
    for p in patches:
        p_file_norm = to_posix_path(p["file"])
        if not filtered:
            if p_file_norm == norm_file:
                filtered.append(p)
            else:
                break
        else:
            if p_file_norm == norm_file:
                filtered.append(p)
            else:
                break

    if not filtered:
        return None

    # ===== 应用 patch =====
    current_lines = list(content_lines)
    win_start = win_start_full
    win_end = win_end_full
    applied_any = False

    for p in filtered:
        start = p["start"]
        dels = p["dels"]
        adds = p["adds"]

        if start < 0 or start > len(current_lines):
            break

        del_count = len(dels)
        add_count = len(adds)

        if del_count == 0 and add_count > 0:
            if not (win_start <= start <= win_end + 1):
                break
            prefix = current_lines[:start]
            suffix = current_lines[start:]
            current_lines = prefix + list(adds) + suffix
            win_end += add_count
            applied_any = True
            continue

        if del_count > 0:
            del_start = start
            del_end = start + del_count - 1

            if not (win_start <= del_start and del_end <= win_end):
                break

            if del_end >= len(current_lines):
                break
            prefix = current_lines[:del_start]
            suffix = current_lines[del_end + 1 :]
            current_lines = prefix + suffix
            win_end -= del_count

            if add_count == 0:
                applied_any = True
                continue

            insert_pos = del_start
            if not (win_start <= insert_pos <= win_end + 1):
                break

            prefix = current_lines[:insert_pos]
            suffix = current_lines[insert_pos:]
            current_lines = prefix + list(adds) + suffix
            win_end += add_count
            applied_any = True

    if not applied_any:
        return None

    if win_start > win_end:
        body_lines = []
    else:
        win_start_clamped = max(0, min(win_start, max(0, len(current_lines) - 1)))
        win_end_clamped = max(0, min(win_end, max(0, len(current_lines) - 1)))
        if win_start_clamped > win_end_clamped:
            body_lines = []
        else:
            body_lines = current_lines[win_start_clamped : win_end_clamped + 1]

    gt_lines = ["<|editable_region_start|>"]
    gt_lines.extend(body_lines)
    gt_lines.append("<|editable_region_end|>")
    ground_truth = "\n".join(gt_lines)
    ground_truth_content = "\n".join(current_lines)

    return input_text, ground_truth, ground_truth_content
