"""
TabLogCollector：跨 IDE 的 Tab/Output 日志采集器

依赖注入的 EditorAdapter.capture_tab_log(current_file_abs_path) 获取模型/补全日志，
具体日志来源与解析由各 Editor 子类实现；本采集器仅按约定格式写入 session 目录下 collected.jsonl。
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from ..core.models import ObserveConfig, WorkContext
from ..editors.base import EditorAdapter
from .base import Collector

COLLECTED_JSONL_FILENAME = "collected.jsonl"


class TabLogCollector(Collector):
    """通过 Editor 的 capture_tab_log 获取模型/补全日志并写入 session jsonl 的采集器，与具体 IDE 无关。"""

    def __init__(self, editor: EditorAdapter) -> None:
        self._editor = editor
        self._session_dir = ""
        self._observe_config = ObserveConfig()
        self._work_context: Optional[WorkContext] = None
        self._collect_count = 0
        self._collect_error_count = 0
        self._collect_error_samples: list[str] = []
        self._error_sample_limit = 5
        # key: relative_path, value: 上一次 observe 时的完整文本内容
        self._last_content: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "tab_log"

    def init_session(
        self,
        session_dir: str,
        observe_config: ObserveConfig,
        work_context: Optional[WorkContext] = None,
        initial_contents: Optional[dict[str, str]] = None,
    ) -> None:
        """保存会话目录与 work_context，并在 session_dir 下创建空 collected.jsonl。"""
        self._session_dir = session_dir
        self._observe_config = observe_config
        self._work_context = work_context
        self._collect_count = 0
        self._collect_error_count = 0
        self._collect_error_samples = []
        # 初始化 last_content：若传入初始内容则从此开始，否则为空，首次 observe 时 prev_content 为空串
        self._last_content = dict(initial_contents or {})
        output_path = os.path.join(session_dir, COLLECTED_JSONL_FILENAME)
        with open(output_path, "w", encoding="utf-8") as _:
            pass

    def collect(
        self,
        relative_path: str,
        action_index: int,
        line: int,
        col: int,
    ) -> None:
        """读当前文件内容、调 editor.capture_tab_log 获取模型输出，追加一条 record 到 collected.jsonl。"""
        if self._work_context is None:
            return

        # 1. 上一次 observe 时的内容（无则为空串或初始内容）
        prev_content = self._last_content.get(relative_path, "")

        abs_path = self._work_context.file_paths.get(relative_path) or os.path.join(
            self._work_context.work_dir, relative_path
        )
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            content = ""
        capture_ok = True
        capture_error_type: Optional[str] = None
        capture_error_message: Optional[str] = None
        try:
            model_output = self._editor.capture_tab_log(abs_path)
        except Exception as exc:
            # 采集是非关键链路：降级为空输出并记录错误，避免中断整条 pipeline
            model_output = ""
            capture_ok = False
            capture_error_type = type(exc).__name__
            capture_error_message = str(exc)
            self._collect_error_count += 1
            if len(self._collect_error_samples) < self._error_sample_limit:
                self._collect_error_samples.append(
                    f"{capture_error_type}: {capture_error_message}"
                )
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record = {
            "action_index": action_index,
            "file": relative_path,
            "cursor": {"line": line, "col": col},
            "prev_content": prev_content,
            "content": content,
            "model_output": model_output,
            "timestamp": timestamp,
            "format": "tab_log/v1",
            "extra": {
                "capture_ok": capture_ok,
                "capture_error_type": capture_error_type,
                "capture_error_message": capture_error_message,
            },
        }
        output_path = os.path.join(self._session_dir, COLLECTED_JSONL_FILENAME)
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._collect_count += 1

        # 更新该文件的 last snapshot
        self._last_content[relative_path] = content

    def finalize(self) -> None:
        """打印本会话采集条数。"""
        if self._collect_count > 0:
            path = os.path.join(self._session_dir, COLLECTED_JSONL_FILENAME)
            print(f"  采集完成: 共 {self._collect_count} 条记录 → {path}")
            if self._collect_error_count > 0:
                ratio = self._collect_error_count / self._collect_count
                print(
                    "  采集异常: "
                    f"{self._collect_error_count} 条 "
                    f"({ratio:.2%})，已按降级策略继续执行"
                )
                for i, sample in enumerate(self._collect_error_samples, start=1):
                    print(f"    [{i}] {sample}")
