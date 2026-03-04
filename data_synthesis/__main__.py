"""
DataSynthesis CLI 入口

运行模式互斥，例如：
  - 全新采集：指定数据源 --source（如 git-repo、jsonl 等）+ --source-path
  - 复现：指定 plan 文件 --plan，输出写入 plan 所在目录下的 reproduce/ 子目录
"""

import argparse
import os
import sys

from .core.session import run_session
from .providers.plan_file import PlanFileProvider
from .providers.git_repo import GitRepoProvider
from .providers.jsonl import JsonlProvider
from .strategies import DiffHunkStrategy

REPRODUCE_SUBDIR = "reproduce"


def main():
    parser = argparse.ArgumentParser(
        description="DataSynthesis - 跨 IDE 代码输入模拟与数据采集工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式（互斥，例如）:
  - 全新采集：--source git-repo --source-path /path/to/repo
             或 --source jsonl --source-path /path/to/file.jsonl
  - 复现：   --plan /path/to/type_plan.json（输出到 plan 所在目录/reproduce/）

示例:
  python -m data_synthesis --source git-repo --source-path ./my-repo --dry-run
  python -m data_synthesis --source jsonl --source-path ./input.jsonl --strategy diff-hunk --dry-run
  python -m data_synthesis --plan output/collected/git-repo/repo1/abc1234/session_xxx/type_plan.json --dry-run
""",
    )

    # 模式与数据源（与 --plan 互斥）
    source_group = parser.add_argument_group("模式与数据源")
    source_group.add_argument(
        "--source",
        type=str,
        choices=["git-repo", "jsonl"],
        metavar="TYPE",
        help="数据源类型（如 git-repo、jsonl 等）",
    )
    source_group.add_argument(
        "--source-path",
        type=str,
        metavar="PATH",
        help="数据源路径（仓库目录或 JSONL 文件路径）",
    )
    source_group.add_argument(
        "--strategy",
        type=str,
        choices=["diff-hunk"],
        metavar="NAME",
        help="当 --source=jsonl 时使用的计划策略（当前支持: diff-hunk）",
    )
    source_group.add_argument(
        "--plan",
        type=str,
        metavar="PATH",
        help="复现模式：指定 type_plan.json 路径，输出写入该文件所在目录/reproduce/",
    )

    # JSONL 样本选择（仅在 --source=jsonl 时生效）
    jsonl_group = parser.add_argument_group("JSONL 样本选择（仅 --source=jsonl 时生效）")
    jsonl_group.add_argument(
        "--sample-index",
        type=int,
        metavar="IDX",
        help="JSONL 样本索引（0-base）；指定时优先于 random_seed",
    )
    jsonl_group.add_argument(
        "--random-seed",
        type=int,
        metavar="SEED",
        help="在未指定 sample_index 时，用于可复现地随机选择样本",
    )

    # 执行
    exec_group = parser.add_argument_group("执行")
    exec_group.add_argument(
        "--dry-run",
        action="store_true",
        help="dry-run 模式（不操作编辑器，只打印操作日志）",
    )
    exec_group.add_argument(
        "--type-interval",
        type=float,
        default=0.05,
        metavar="SEC",
        help="字符输入间隔秒数（默认: 0.05）",
    )
    exec_group.add_argument(
        "--editor",
        type=str,
        choices=["cursor"],
        default="cursor",
        metavar="NAME",
        help="编辑器适配器类型（当前仅支持: cursor）",
    )

    # 输出（全新采集时生效；复现时固定为 plan 所在目录/reproduce/）
    output_group = parser.add_argument_group("输出")
    output_group.add_argument(
        "--output-dir",
        type=str,
        default="output/collected",
        metavar="DIR",
        help="全新采集时的输出根目录（默认: output/collected）；复现时忽略",
    )

    args = parser.parse_args()

    # ========== 模式互斥校验 ==========
    has_source = args.source is not None and args.source_path is not None
    has_plan = args.plan is not None

    if has_source and has_plan:
        parser.error("不能同时指定 --source/--source-path 与 --plan，请只指定其中一种")
    if not has_source and not has_plan:
        parser.error(
            "需指定数据源或复现用的 plan："
            "  --source TYPE --source-path PATH  或  --plan PATH"
        )
    if has_source and (args.source is None or args.source_path is None):
        parser.error("使用全新采集时需同时指定 --source 和 --source-path")
    if args.sample_index is not None and args.sample_index < 0:
        parser.error("--sample-index 必须为非负整数（0-base 索引）")
    if has_source and args.source == "jsonl" and args.strategy is None:
        parser.error("--source=jsonl 时必须指定 --strategy（当前仅支持: diff-hunk）")

    # ========== 组装 TaskProvider 与 output_dir ==========
    if has_plan:
        task_provider = PlanFileProvider(plan_path=args.plan)
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(args.plan)), REPRODUCE_SUBDIR
        )
    else:
        from .strategies.base import PlanStrategy

        class _PlaceholderStrategy(PlanStrategy):
            @property
            def name(self) -> str:
                return "placeholder"

            def generate(self, change_set, observe_config):
                raise NotImplementedError(
                    f"{args.source} 数据源尚未实现，请实现对应 Provider 与 PlanStrategy"
                )

        if args.source == "git-repo":
            task_provider = GitRepoProvider(
                repo_path=args.source_path,
                plan_strategy=_PlaceholderStrategy(),
            )
        else:  # jsonl
            # 当前仅支持 diff-hunk 策略
            plan_strategy = DiffHunkStrategy()
            task_provider = JsonlProvider(
                jsonl_path=args.source_path,
                plan_strategy=plan_strategy,
                sample_index=args.sample_index,
                random_seed=args.random_seed,
            )
        output_dir = args.output_dir

    # ========== 组装 Editor ==========
    editor = None
    if not args.dry_run:
        # 根据 CLI 选择编辑器类型，并为其注入默认 PlatformHandler
        if args.editor == "cursor":
            from .platform import create_default_platform
            from .editors.cursor import CursorAdapter

            platform = create_default_platform()
            editor = CursorAdapter(platform=platform)
        else:
            parser.error(f"未知的编辑器类型: {args.editor}")

    # ========== 组装 Collector ==========
    collector = None

    # ========== 运行 ==========
    success = run_session(
        task_provider=task_provider,
        editor=editor,
        collector=collector,
        type_interval=args.type_interval,
        dry_run=args.dry_run,
        output_dir=output_dir,
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
