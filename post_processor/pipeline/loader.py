"""输入源抽象与加载"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Iterator, Protocol, Union

from ..models.input import ProcessingUnit
from pydantic import ValidationError

from ..models.sample import (
    FORMAT_NAMES,
    FORMAT_VALIDATORS,
    RAW,
    STANDARD,
    StandardSample,
    ZetaSample,
)

logger = logging.getLogger(__name__)

COLLECTED_FILENAME = "collected.jsonl"
TYPE_PLAN_FILENAME = "type_plan.json"
SESSION_META_FILENAME = "session_meta.json"

SESSION_DIR_PATTERN = re.compile(r"^session_(\d{8}_\d{6})$")


class InputSource(Protocol):
    """输入源抽象"""

    input_type: str  # RAW 或 STANDARD/ZETA

    def iter_items(
        self,
    ) -> Iterator[Union[ProcessingUnit, StandardSample, ZetaSample]]:
        ...


class FolderInputSource:
    """文件夹输入：递归查找 session 目录，产出 ProcessingUnit"""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self.input_type = RAW

    def iter_items(self) -> Iterator[ProcessingUnit]:
        for session_dir in _iter_session_dirs(self._root):
            type_plan = _load_json(session_dir / TYPE_PLAN_FILENAME)
            session_meta = _load_json(session_dir / SESSION_META_FILENAME)
            for idx, record in enumerate(_iter_collected_records(session_dir / COLLECTED_FILENAME)):
                yield ProcessingUnit(
                    record=record,
                    type_plan=type_plan,
                    session_meta=session_meta,
                    collected_idx=idx,
                )


class JsonlInputSource:
    """JSONL 文件输入：逐行解析，按指定格式校验，只产出符合条件的行"""

    def __init__(self, path: Path, input_format: str = STANDARD) -> None:
        self._path = path.resolve()
        if input_format not in FORMAT_NAMES:
            raise ValueError(
                f"input_format 必须是 {list(FORMAT_NAMES)} 之一，当前: {input_format!r}"
            )
        self.input_type = input_format
        self._validator = FORMAT_VALIDATORS[input_format]

    def iter_items(self) -> Iterator[Union[StandardSample, ZetaSample]]:
        with self._path.open("r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "丢弃第 %d 行（JSON 解析失败）: %s | 行内容预览: %.200s...",
                        line_num,
                        e,
                        line,
                    )
                    continue
                if not isinstance(obj, dict):
                    logger.warning("丢弃第 %d 行（非对象类型）", line_num)
                    continue
                try:
                    validated = self._validator.validate_python(obj)
                except ValidationError as e:
                    logger.warning(
                        "丢弃第 %d 行（格式 %s 校验失败）: %s | 行内容预览: %.200s...",
                        line_num,
                        self.input_type,
                        e,
                        line,
                    )
                    continue
                yield validated


def _iter_session_dirs(root: Path) -> Iterator[Path]:
    """
    递归查找 session 目录（含三文件且命名为 session_YYYYMMDD_HHMMSS）。
    同一 commit 文件夹（会话目录的父目录）下若有多个会话，只取时间戳最新的一个。
    """
    root = root.resolve()
    candidates: list[tuple[Path, Path, str]] = []  # (commit_dir, session_dir, ts)

    for dirpath, _, filenames in os.walk(root):
        files = set(filenames)
        if not (
            COLLECTED_FILENAME in files
            and TYPE_PLAN_FILENAME in files
            and SESSION_META_FILENAME in files
        ):
            continue
        session_dir = Path(dirpath)
        m = SESSION_DIR_PATTERN.match(session_dir.name)
        if not m:
            continue
        ts = m.group(1)
        commit_dir = session_dir.parent
        candidates.append((commit_dir, session_dir, ts))

    # 每个 commit 只保留 ts 最大的 session
    best: dict[Path, tuple[Path, str]] = {}
    for commit_dir, session_dir, ts in candidates:
        if commit_dir not in best or ts > best[commit_dir][1]:
            best[commit_dir] = (session_dir, ts)

    for commit_dir in sorted(best.keys()):
        session_dir, _ = best[commit_dir]
        yield session_dir


def _load_json(path: Path) -> dict:
    """加载 JSON 文件"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _iter_collected_records(path: Path) -> Iterator[dict]:
    """逐行读取 collected.jsonl"""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def create_input_source(path: Path, input_format: str = STANDARD) -> InputSource:
    """根据路径类型创建输入源"""
    path = path.resolve()
    if path.is_dir():
        return FolderInputSource(path)
    if path.is_file():
        if path.suffix != ".jsonl":
            raise ValueError(
                f"输入文件必须是 .jsonl 格式，当前: {path.name}"
            )
        if input_format not in FORMAT_NAMES:
            raise ValueError(
                f"input_format 必须是 {list(FORMAT_NAMES)} 之一，当前: {input_format!r}"
            )
        return JsonlInputSource(path, input_format)
    raise FileNotFoundError(f"输入路径不存在: {path}")
