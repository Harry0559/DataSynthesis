"""
Post-processor CLI 入口

用法：
  python -m post_processor --input <path> --pipeline "integrate,filter:llm,format:zeta,dedup" [选项]

完整参数见 --help。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .models.config import PipelineConfig
from .models.sample import FORMAT_NAMES, STANDARD
from .pipeline.runner import run_postprocessor
from .steps import parse_pipeline, parse_step_params_from_argv


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Post-processor：整合/过滤/格式化/去重，输出 JSONL。",
        epilog="""
示例:
  # 从文件夹整合并输出 zeta 格式
  python -m post_processor --input ./output/collected --pipeline "integrate,format:zeta"

  # 从文件夹到 zeta 格式并去重
  python -m post_processor --input ./output/collected --pipeline "integrate,filter:llm,format:zeta,dedup" \\
    --format-zeta.region-radius 15,15 --dedup-simhash.threshold 0.9

  # 从已有 jsonl 继续处理
  python -m post_processor --input ./data/standard.jsonl --pipeline "filter:edit,format:zeta,dedup"
""",
    )
    p.add_argument("--input", required=True, help="输入路径（文件夹或 jsonl 文件）")
    p.add_argument(
        "--output",
        default=None,
        help="输出路径（默认 output/data/<format>_data_<timestamp>.jsonl）",
    )
    p.add_argument(
        "--input-format",
        default=STANDARD,
        choices=list(FORMAT_NAMES),
        help="jsonl 输入时的格式（默认 standard，可选 standard/zeta）",
    )
    p.add_argument(
        "--pipeline",
        required=True,
        help='管线字符串，如 "integrate,filter:llm,format:zeta,dedup"',
    )
    return p


def main() -> None:
    parser = _build_parser()
    args, unknown = parser.parse_known_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        repo_root = Path(__file__).resolve().parents[1]
        input_path = (repo_root / args.input).resolve()

    if not input_path.exists():
        print(f"[post_processor] 错误: 输入路径不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = None
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            repo_root = Path(__file__).resolve().parents[1]
            output_path = (repo_root / args.output).resolve()

    try:
        steps = parse_pipeline(args.pipeline)
        step_params = parse_step_params_from_argv(unknown)
    except ValueError as e:
        print(f"[post_processor] 错误: {e}", file=sys.stderr)
        sys.exit(1)

    config = PipelineConfig(
        input_path=input_path,
        output_path=output_path,
        input_format=args.input_format,
        steps=steps,
        step_params=step_params,
    )

    try:
        stats = run_postprocessor(config)
    except Exception as e:
        print(f"[post_processor] 错误: {e}", file=sys.stderr)
        sys.exit(1)

    print("[post_processor] 完成")
    print(f"  输入: {stats.input_count}")
    print(f"  输出: {stats.output_count}")
    if stats.dropped_by_integrate:
        print(f"  整合丢弃: {stats.dropped_by_integrate}")
    if stats.dropped_by_filter:
        print(f"  过滤丢弃: {stats.dropped_by_filter}")
    if stats.dropped_by_formatter:
        print(f"  格式化丢弃: {stats.dropped_by_formatter}")
    if stats.dropped_by_dedup:
        print(f"  去重丢弃: {stats.dropped_by_dedup}")


if __name__ == "__main__":
    main()
