"""
从原始 jsonl 提取并筛选 commit 数据，转换为标准 jsonl 数据源格式。

用法示例：

    python tools/filter_commit_jsonl/filter_commit_jsonl.py \
        --input /path/to/raw.jsonl \
        --output /path/to/output.jsonl \
        --same-file-only \
        --require-old-nonempty \
        --require-new-nonempty \
        --min-hunks 1 \
        --max-hunk-lines 5

所有筛选条件都是可选的；不传某个参数就表示不过滤该条件。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple
import difflib
import tempfile


@dataclass
class FilterConfig:
    same_file_only: bool = False
    require_old_nonempty: bool = False
    require_new_nonempty: bool = False
    min_hunks: int | None = None
    max_hunk_lines: int | None = None
    encoding: str = "utf-8"


def compute_hunks_stats(old_text: str, new_text: str) -> Tuple[int, List[int]]:
    """
    计算从 old_text 到 new_text 的行级 diff 的 hunk 数量和各 hunk 的"行数"。

    定义：
    - 先对按行拆分后的列表做 SequenceMatcher.get_opcodes()
    - 连续的非 equal opcodes 视为一个 hunk
    - 单个 hunk 的行数 = max(删除行数, 新增行数)
      删除行数：delete/replace 的 i2 - i1 之和
      新增行数：insert/replace 的 j2 - j1 之和
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    opcodes = sm.get_opcodes()

    hunks: List[List[Tuple[str, int, int, int, int]]] = []
    current_ops: List[Tuple[str, int, int, int, int]] = []

    # 把连续的非 equal opcodes 聚成若干 hunk
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            if current_ops:
                hunks.append(current_ops)
                current_ops = []
        else:
            current_ops.append((tag, i1, i2, j1, j2))
    if current_ops:
        hunks.append(current_ops)

    hunk_line_counts: List[int] = []
    for ops in hunks:
        del_lines = 0
        add_lines = 0
        for tag, i1, i2, j1, j2 in ops:
            if tag in ("delete", "replace"):
                del_lines += (i2 - i1)
            if tag in ("insert", "replace"):
                add_lines += (j2 - j1)
        hunk_line_counts.append(max(del_lines, add_lines))

    return len(hunks), hunk_line_counts


def render_human_diff(old_text: str, new_text: str) -> str:
    """
    生成从 old_text 到 new_text 的人类可读行级 diff 字符串。

    使用 unified diff 格式，每行前缀：
      - ' ' 相同
      - '-' 删除
      - '+' 新增
    """
    old_lines = old_text.splitlines(keepends=False)
    new_lines = new_text.splitlines(keepends=False)

    diff_lines = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="old",
        tofile="new",
        lineterm="",
        n=3,
    )

    return "\n".join(diff_lines)


def record_passes_filters(record: dict, cfg: FilterConfig) -> bool:
    """根据配置判断一条记录是否通过筛选。"""
    # 1) old_file 与 new_file 相等
    if cfg.same_file_only:
        if record.get("old_file") != record.get("new_file"):
            return False

    # 2) old_contents 非空
    if cfg.require_old_nonempty:
        old_contents = record.get("old_contents")
        if not isinstance(old_contents, str) or not old_contents.strip():
            return False

    # 3) new_contents 非空
    if cfg.require_new_nonempty:
        new_contents = record.get("new_contents")
        if not isinstance(new_contents, str) or not new_contents.strip():
            return False

    # 4) & 5) diff 相关
    need_diff_filter = (cfg.min_hunks is not None) or (cfg.max_hunk_lines is not None)
    if need_diff_filter:
        old_contents = record.get("old_contents", "")
        new_contents = record.get("new_contents", "")
        if not isinstance(old_contents, str) or not isinstance(new_contents, str):
            return False

        num_hunks, hunk_line_counts = compute_hunks_stats(old_contents, new_contents)

        if cfg.min_hunks is not None and num_hunks < cfg.min_hunks:
            return False

        if cfg.max_hunk_lines is not None:
            if not all(hc <= cfg.max_hunk_lines for hc in hunk_line_counts):
                return False

    return True


def iter_jsonl(path: Path, encoding: str) -> Iterable[dict]:
    """流式迭代 jsonl 文件中的记录，解析失败的行会被跳过。"""
    with path.open("r", encoding=encoding, errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # 如果存在坏行，直接跳过
                continue
            if isinstance(obj, dict):
                yield obj


def first_pass(input_path: Path, temp_path: Path, cfg: FilterConfig) -> int:
    """
    第一遍扫描：应用筛选条件，将通过的记录写入临时文件（不加 id）。
    返回保留记录数。
    """
    kept = 0
    with temp_path.open("w", encoding=cfg.encoding) as out_f:
        for record in iter_jsonl(input_path, cfg.encoding):
            if not record_passes_filters(record, cfg):
                continue
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1
    return kept


def second_pass(temp_path: Path, output_path: Path, kept: int, encoding: str) -> None:
    """
    第二遍扫描：读取临时文件，为每条记录分配字符串 id，并写入目标 jsonl。
    id 从 "0" 开始递增，宽度 = len(str(kept-1))。
    """
    if kept == 0:
        # 没有记录，输出空文件
        output_path.write_text("", encoding=encoding)
        return

    width = len(str(kept - 1))

    with temp_path.open("r", encoding=encoding) as in_f, output_path.open(
        "w", encoding=encoding
    ) as out_f:
        idx = 0
        for line in in_f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 计算 id
            record_id = str(idx).zfill(width)

            # 计算人类可读 diff
            old_contents = record.get("old_contents", "")
            new_contents = record.get("new_contents", "")
            if isinstance(old_contents, str) and isinstance(new_contents, str):
                diff_str = render_human_diff(old_contents, new_contents)
            else:
                diff_str = ""

            # 构造按顺序输出的 dict：
            # 1) id 作为第一个字段
            # 2) 其他原字段（去掉已有的 id/diff）
            # 3) diff 作为最后一个字段
            new_record: dict = {}

            # 1) id
            new_record["id"] = record_id

            # 2) 其他字段，保持原顺序，但排除 id / diff，避免覆盖
            for key, value in record.items():
                if key in ("id", "diff"):
                    continue
                new_record[key] = value

            # 3) diff
            new_record["diff"] = diff_str

            out_f.write(json.dumps(new_record, ensure_ascii=False) + "\n")
            idx += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="筛选并转换 commit jsonl，生成标准 jsonl 数据源。"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="输入 jsonl 文件路径（原始 commit 数据）。",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="输出 jsonl 文件路径（过滤后并加 id）。",
    )

    # 基础筛选条件
    parser.add_argument(
        "--same-file-only",
        action="store_true",
        help="仅保留 old_file 与 new_file 完全相同的记录。",
    )
    parser.add_argument(
        "--require-old-nonempty",
        action="store_true",
        help="要求 old_contents 非空（去掉空白字符后）。",
    )
    parser.add_argument(
        "--require-new-nonempty",
        action="store_true",
        help="要求 new_contents 非空（去掉空白字符后）。",
    )

    # diff 相关筛选
    parser.add_argument(
        "--min-hunks",
        type=int,
        default=None,
        help="要求从 old_contents 到 new_contents 的行级 diff hunk 数量至少为 N。",
    )
    parser.add_argument(
        "--max-hunk-lines",
        type=int,
        default=None,
        help=(
            "要求每个 hunk 的行数不超过 N，行数定义为 max(删除行数, 新增行数)。"
        ),
    )

    parser.add_argument(
        "--encoding",
        type=str,
        default="utf-8",
        help="输入/输出文件编码（默认 utf-8）。",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    if not input_path.is_file():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    cfg = FilterConfig(
        same_file_only=bool(args.same_file_only),
        require_old_nonempty=bool(args.require_old_nonempty),
        require_new_nonempty=bool(args.require_new_nonempty),
        min_hunks=args.min_hunks,
        max_hunk_lines=args.max_hunk_lines,
        encoding=args.encoding,
    )

    # 在同一目录下创建一个临时文件，用完即删
    with tempfile.NamedTemporaryFile(
        mode="w+", suffix=".jsonl.tmp", delete=False, dir=str(output_path.parent)
    ) as tmp:
        temp_path = Path(tmp.name)

    kept = first_pass(input_path, temp_path, cfg)
    second_pass(temp_path, output_path, kept, cfg.encoding)

    # 清理临时文件
    try:
        temp_path.unlink(missing_ok=True)  # type: ignore[call-arg]
    except TypeError:
        # Python < 3.8 没有 missing_ok
        if temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    main()
