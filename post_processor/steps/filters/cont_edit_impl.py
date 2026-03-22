"""续写/编辑过滤的共享逻辑"""

from __future__ import annotations

from ...models.sample import ZetaDebugSample


def is_continuation(sample: ZetaDebugSample) -> bool:
    """
    判断是否为续写数据：根据 cursor 在 content 中定位，切分为 prefix 与 suffix，
    若二者分别在 ground_truth_content 的首尾匹配成功则视为续写。
    返回 True=续写，False=编辑或无效。
    """
    content = sample.get("content")
    ground_truth_content = sample.get("ground_truth_content")
    cursor = sample.get("cursor") or {}

    if not content:
        return False

    line = cursor.get("line")
    col = cursor.get("col")

    lines = content.split("\n")
    if line < 1 or line > len(lines):
        return False

    offset = sum(len(lines[i]) + 1 for i in range(line - 1)) + min(
        col - 1, len(lines[line - 1])
    )
    prefix = content[:offset]
    suffix = content[offset:]

    return ground_truth_content.startswith(prefix) and ground_truth_content.endswith(
        suffix
    )
