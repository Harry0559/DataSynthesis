#!/usr/bin/env python
"""
从 Hugging Face bigcode/commitpackft 下载指定语言子集，并保存为本地 JSONL 文件。

示例：

    python tools/commitpackft_downloader/download_commitpackft.py --lang python
    python tools/commitpackft_downloader/download_commitpackft.py \
        --lang java \
        --output /data/commitpackft_java_50k.jsonl \
        --max-samples 50000
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from datasets import load_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download bigcode/commitpackft subset and save as JSONL."
    )
    parser.add_argument(
        "--lang",
        required=True,
        help=(
            "语言子集名称（如 python, java, javascript 等），"
            "对应 Hugging Face 数据卡上的 subset 名。"
        ),
    )
    parser.add_argument(
        "--split",
        type=str,
        default="train",
        help="数据集 split，默认为 train。",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 JSONL 文件路径；若不指定，则默认为 ./commitpackft_<lang>.jsonl。",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="最多导出的样本数量（仅用于调试，默认导出整个 subset）。",
    )
    return parser.parse_args()


def resolve_output_path(lang: str, output_arg: Optional[str]) -> Path:
    if output_arg:
        path = Path(output_arg).expanduser()
    else:
        path = Path.cwd() / f"commitpackft_{lang}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    args = parse_args()
    lang = args.lang

    print(f"[commitpackft] 准备下载数据集: lang={lang}, split={args.split}")

    try:
        ds = load_dataset("bigcode/commitpackft", lang, split=args.split)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(
            f"加载数据集失败：{e}\n"
            "请确认语言子集名称是否正确（可在 Hugging Face 数据卡的 Subset 列查看，"
            "如 python/java/javascript/yaml 等）。"
        ) from e

    output_path = resolve_output_path(lang, args.output)
    print(f"[commitpackft] 输出路径: {output_path}")

    max_samples = args.max_samples
    # datasets 对象通常实现了 __len__，但保险起见做一次保护
    try:
        total = len(ds)  # type: ignore[arg-type]
    except TypeError:
        total = -1

    if max_samples is not None:
        print(f"[commitpackft] 将最多导出前 {max_samples} 条样本。")
    else:
        if total >= 0:
            print(f"[commitpackft] 将导出整个 subset（样本数约 {total} 条，可能较大）。")
        else:
            print("[commitpackft] 将导出整个 subset（流式模式，样本数未知）。")

    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        for i, example in enumerate(ds):
            if max_samples is not None and i >= max_samples:
                break
            # example 是普通 dict，直接写入
            f.write(json.dumps(example, ensure_ascii=False) + "\n")
            count += 1
            if count % 10000 == 0:
                print(f"[commitpackft] 已写入 {count} 条样本...")

    print(f"[commitpackft] 完成，最终导出样本数: {count}")


if __name__ == "__main__":
    main()

