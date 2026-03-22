"""输出写入：创建目录、覆盖 jsonl"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class Writer:
    """JSONL 写入器：目录不存在则创建，文件存在则覆盖"""

    def __init__(self, path: Path) -> None:
        self._path = path.resolve()
        self._file = None

    def __enter__(self) -> "Writer":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("w", encoding="utf-8")
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def write(self, sample: Dict[str, Any]) -> None:
        """写入一条记录"""
        if self._file is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self._path.open("w", encoding="utf-8")
        self._file.write(json.dumps(sample, ensure_ascii=False) + "\n")

    def close(self) -> None:
        """关闭文件"""
        if self._file is not None:
            self._file.close()
            self._file = None
