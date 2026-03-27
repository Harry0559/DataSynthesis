"""
DataSynthesis CLI 入口

用法：
  python -m data_synthesis --source jsonl --source-path <file> --strategy <NAME> [选项]

完整参数见 --help。
"""

import argparse
import sys

from .core.batch import run_batch
from .core.models import BatchConfig, SessionConfig
from .core.session import run_session
from .providers.jsonl import JsonlBatchProvider, JsonlProvider
from .strategies import DiffHunkStrategy, SimilarityStrategy


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
    jsonl.add_argument(
        "--batch-max-items-per-file",
        type=int,
        metavar="N",
        help="批量模式下，每个 JSONL 文件最多执行的条目数（默认不限制）",
    )
    jsonl.add_argument(
        "--batch-random-sample",
        action="store_true",
        help="批量模式下，每个 JSONL 文件内随机选取条目（无放回）；默认按行序选取",
    )

    # ── 输入重放策略 ──
    strat = parser.add_argument_group("输入重放策略")
    strat.add_argument(
        "--strategy",
        required=True,
        choices=["diff-hunk", "similarity"],
        metavar="NAME",
        help="TypePlan 生成策略（必填）",
    )

    # ── 输入重放策略 / similarity 参数 ──
    fd = parser.add_argument_group("输入重放策略 / similarity 参数（仅 --strategy similarity 时生效）")
    fd.add_argument(
        "--observe-mode",
        choices=["all", "random", "hunk_end", "every_n"],
        default="all",
        metavar="MODE",
        help="观察模式：all=每个动作后 | random=按概率 | hunk_end=每块末尾 | every_n=每N个动作（默认: all）",
    )
    fd.add_argument(
        "--observe-param",
        type=float,
        default=0.3,
        metavar="VAL",
        help="观察参数：random 时为概率(0-1)，every_n 时为间隔N（默认: 0.3）",
    )
    fd.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.75,
        metavar="RATIO",
        help="行匹配 SequenceMatcher.ratio 阈值（默认: 0.75）",
    )
    fd.add_argument(
        "--split-mode",
        choices=["none", "random", "every_n"],
        default="none",
        metavar="MODE",
        help="similarity 策略的动作拆分模式：none=不拆分 | random=随机拆分 | every_n=每N个字符拆分（默认: none）",
    )
    fd.add_argument(
        "--split-random-prob",
        type=float,
        default=0.5,
        metavar="P",
        help="split-mode=random 时，继续与前一字符同组的概率，越大每个片段越长（默认: 0.5）",
    )
    fd.add_argument(
        "--split-every-n",
        type=int,
        default=0,
        metavar="N",
        help="split-mode=every_n 时，每个动作 content 每 N 个字符拆分一次（默认: 0 表示不生效）",
    )
    fd.add_argument(
        "--merge-mode",
        choices=["none", "random", "full", "batch_n"],
        default="none",
        metavar="MODE",
        help="similarity 策略的动作合并模式：none=不合并 | random=随机合并 | full=尽量合并 | batch_n=每组最多N个（默认: none）",
    )
    fd.add_argument(
        "--merge-random-prob",
        type=float,
        default=0.5,
        metavar="P",
        help="merge-mode=random 时，在可合并前提下实际合并的概率（默认: 0.5）",
    )
    fd.add_argument(
        "--merge-batch-size",
        type=int,
        default=0,
        metavar="N",
        help="merge-mode=batch_n 时，单次最多合并的连续动作数（默认: 0 表示不限制）",
    )
    fd.add_argument(
        "--no-observe-after-delete",
        action="store_true",
        help="禁用删除动作后的观察（默认: 删除后允许在该动作后插入 ObserveAction）",
    )
    fd.add_argument(
        "--split-merge-order",
        choices=["none", "split_only", "merge_only", "split_then_merge", "merge_then_split"],
        default="none",
        metavar="MODE",
        help=(
            "similarity 策略的拆分/合并整体顺序："
            "none=不拆分不合并 | split_only=仅拆分 | merge_only=仅合并 | "
            "split_then_merge=先拆分后合并 | merge_then_split=先合并后拆分（默认: none）"
        ),
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
        default=0.01,
        metavar="SEC",
        help="字符输入间隔秒数（默认: 0.01）",
    )
    exe.add_argument(
        "--delete-interval",
        type=float,
        default=0.01,
        metavar="SEC",
        help="字符删除间隔秒数（默认: 0.01）",
    )
    exe.add_argument(
        "--batch-mode",
        action="store_true",
        help="启用批量模式：遍历数据源的多个条目，按时间/条数/概率配置批量执行 pipeline",
    )
    exe.add_argument(
        "--batch-max-duration",
        type=float,
        metavar="SEC",
        help="批量运行的时间上限（秒），默认不限制；达到上限后在下一条任务开始前停止",
    )
    exe.add_argument(
        "--batch-max-items-total",
        type=int,
        metavar="N",
        help="批量模式下最多执行的 pipeline 条目总数（默认不限制）",
    )
    exe.add_argument(
        "--batch-cooldown-every",
        type=int,
        metavar="N",
        help="批量模式下每执行 N 条 pipeline 后冷却一次（默认不启用）",
    )
    exe.add_argument(
        "--batch-cooldown-seconds",
        type=float,
        default=0.0,
        metavar="SEC",
        help="批量模式每次冷却时长（秒，默认: 0.0）",
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

    if args.batch_cooldown_every is not None and args.batch_cooldown_every <= 0:
        parser.error("--batch-cooldown-every 必须为正整数")
    if args.batch_cooldown_seconds < 0:
        parser.error("--batch-cooldown-seconds 必须为非负数")
    if args.batch_cooldown_every is not None and args.batch_cooldown_seconds == 0:
        parser.error("启用 --batch-cooldown-every 时，--batch-cooldown-seconds 不能为 0")

    if not args.dry_run:
        if args.editor is None:
            parser.error("非 dry-run 模式下必须指定 --editor")
        if args.collector is None:
            parser.error("非 dry-run 模式下必须指定 --collector")


def _build_strategy(args: argparse.Namespace):
    strategy_map = {
        "diff-hunk": lambda: DiffHunkStrategy(),
        "similarity": lambda: SimilarityStrategy(
            observe_mode=args.observe_mode,
            observe_param=args.observe_param,
            similarity_threshold=args.similarity_threshold,
            split_mode=args.split_mode,
            split_random_prob=args.split_random_prob,
            split_every_n=args.split_every_n,
            merge_mode=args.merge_mode,
            merge_random_prob=args.merge_random_prob,
            merge_batch_size=args.merge_batch_size,
            observe_after_delete=not args.no_observe_after_delete,
            split_merge_order=args.split_merge_order,
        ),
    }
    return strategy_map[args.strategy]()


def _build_task_provider(args: argparse.Namespace):
    if args.source == "jsonl":
        strategy = _build_strategy(args)
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

    editor = _build_editor(args)
    collector = _build_collector(args, editor)

    config = SessionConfig(
        type_interval=args.type_interval,
        delete_interval=args.delete_interval,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )

    if args.batch_mode:
        if args.source != "jsonl":
            parser.error("当前仅 jsonl 数据源支持 --batch-mode")

        batch_provider = JsonlBatchProvider(
            source_path=args.source_path,
            plan_strategy_factory=lambda: _build_strategy(args),
            observe_config=None,
            max_items_per_file=args.batch_max_items_per_file,
            random_sample=args.batch_random_sample,
        )

        batch_config = BatchConfig(
            max_duration_seconds=args.batch_max_duration,
            max_items_total=args.batch_max_items_total,
            cooldown_every_n=args.batch_cooldown_every,
            cooldown_seconds=args.batch_cooldown_seconds,
        )

        run_batch(
            batch_provider=batch_provider,
            config=config,
            editor=editor,
            collector=collector,
            batch_config=batch_config,
        )
    else:
        task_provider = _build_task_provider(args)
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
