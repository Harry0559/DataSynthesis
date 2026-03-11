"""
DataSynthesis CLI 入口

用法：
  python -m data_synthesis --source jsonl --source-path <file> --strategy diff-hunk [选项]

完整参数见 --help。
"""

import argparse
import sys

from .core.models import SessionConfig
from .core.session import run_session
from .providers.jsonl import JsonlProvider
from .strategies import DiffHunkStrategy


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DataSynthesis — 代码输入模拟与模型输出采集工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # dry-run 验证（不启动编辑器，无需指定 --editor 和 --collector）
  python -m data_synthesis \\
      --source jsonl --source-path input/jsonl/test.jsonl \\
      --strategy diff-hunk --dry-run

  # 实机执行 + 日志采集
  python -m data_synthesis \\
      --source jsonl --source-path input/jsonl/test.jsonl \\
      --strategy diff-hunk --editor cursor --collector tab-log

  # 指定样本索引
  python -m data_synthesis \\
      --source jsonl --source-path input/jsonl/test.jsonl \\
      --strategy diff-hunk --editor cursor --collector none \\
      --sample-index 3
""",
    )

    # ── 数据源 ──
    src = parser.add_argument_group("数据源")
    src.add_argument(
        "--source",
        required=True,
        choices=["jsonl"],
        metavar="TYPE",
        help="数据源类型（必填）",
    )
    src.add_argument(
        "--source-path",
        required=True,
        metavar="PATH",
        help="数据源路径（必填）",
    )

    # ── 数据源 / JSONL 参数 ──
    jsonl = parser.add_argument_group("数据源 / JSONL 参数")
    jsonl.add_argument(
        "--sample-index",
        type=int,
        metavar="IDX",
        help="样本索引（0-base，优先于 --random-seed）",
    )
    jsonl.add_argument(
        "--random-seed",
        type=int,
        metavar="SEED",
        help="随机选择样本的种子",
    )

    # ── 输入重放策略 ──
    strat = parser.add_argument_group("输入重放策略")
    strat.add_argument(
        "--strategy",
        required=True,
        choices=["diff-hunk"],
        metavar="NAME",
        help="TypePlan 生成策略（必填）",
    )

    # ── 编辑器 ──
    ed = parser.add_argument_group("编辑器")
    ed.add_argument(
        "--editor",
        choices=["cursor"],
        metavar="NAME",
        help="编辑器类型（非 dry-run 时必填）",
    )

    # ── 采集器 ──
    col = parser.add_argument_group("采集器")
    col.add_argument(
        "--collector",
        choices=["none", "tab-log"],
        metavar="NAME",
        help="采集方式（非 dry-run 时必填）",
    )

    # ── 执行配置 ──
    exe = parser.add_argument_group("执行配置")
    exe.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印操作日志，不驱动编辑器",
    )
    exe.add_argument(
        "--type-interval",
        type=float,
        default=0.02,
        metavar="SEC",
        help="字符输入间隔秒数（默认: 0.02）",
    )
    exe.add_argument(
        "--delete-interval",
        type=float,
        default=0.02,
        metavar="SEC",
        help="字符删除间隔秒数（默认: 0.02）",
    )

    # ── 输出配置 ──
    out = parser.add_argument_group("输出配置")
    out.add_argument(
        "--output-dir",
        default="output/collected",
        metavar="DIR",
        help="输出根目录（默认: output/collected）",
    )

    return parser


def _validate(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.sample_index is not None and args.sample_index < 0:
        parser.error("--sample-index 必须为非负整数")

    if not args.dry_run:
        if args.editor is None:
            parser.error("非 dry-run 模式下必须指定 --editor")
        if args.collector is None:
            parser.error("非 dry-run 模式下必须指定 --collector")


def _build_task_provider(args: argparse.Namespace):
    if args.source == "jsonl":
        strategy = {"diff-hunk": DiffHunkStrategy}[args.strategy]()
        return JsonlProvider(
            jsonl_path=args.source_path,
            plan_strategy=strategy,
            sample_index=args.sample_index,
            random_seed=args.random_seed,
        )
    raise ValueError(f"未支持的数据源类型: {args.source}")


def _build_editor(args: argparse.Namespace):
    if args.dry_run or args.editor is None:
        return None
    if args.editor == "cursor":
        from .platform import create_default_platform
        from .editors.cursor import CursorAdapter

        return CursorAdapter(platform=create_default_platform())
    raise ValueError(f"未支持的编辑器类型: {args.editor}")


def _build_collector(args: argparse.Namespace, editor):
    if args.dry_run or args.collector is None or args.collector == "none":
        return None
    if args.collector == "tab-log":
        from .collectors.tab_log import TabLogCollector

        return TabLogCollector(editor=editor)
    raise ValueError(f"未支持的采集器类型: {args.collector}")


def main():
    parser = _build_parser()
    args = parser.parse_args()
    _validate(parser, args)

    task_provider = _build_task_provider(args)
    editor = _build_editor(args)
    collector = _build_collector(args, editor)

    config = SessionConfig(
        type_interval=args.type_interval,
        delete_interval=args.delete_interval,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )

    success = run_session(
        task_provider=task_provider,
        config=config,
        editor=editor,
        collector=collector,
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
