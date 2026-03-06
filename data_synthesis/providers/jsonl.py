"""
JsonlProvider：从 JSONL 文件加载变更记录

JSONL 约定：
- 每行是一个变更记录（单文件变更）
- 必含字段：
  - "id": 样本 ID（字符串）
  - "old_file": 变更前文件路径
  - "new_file": 变更后文件路径
  - "old_contents": 变更前文件完整内容（字符串，可为空串）
  - "new_contents": 变更后文件完整内容（字符串，可为空串）
  其余字段（commit/subject/lang 等）作为元数据保留在 ChangeSet.metadata 中。

Session 路径约定（在 _manage_environment 中 yield WorkContext 时需设置）：
- source_type = "jsonl"
- source_path_segments = (jsonl_basename, entry_id)
  - jsonl_basename: 文件名，如 os.path.basename(jsonl_path)
  - entry_id: 该条记录的 "id" 字段值

sample_index / random_seed 语义：
- sample_index: 0-base 样本索引（选第几条记录）
- random_seed: 未指定 sample_index 时，用于可复现地随机选择一条记录；
  若 random_seed 也未提供，则当场生成一个 seed（记录在 ChangeSet.metadata 中）。
"""

import json
import os
import random
import tempfile
from contextlib import contextmanager
from typing import Generator, Optional

from ..core.models import ChangeSet, FileChange, ObserveConfig, TypePlan, WorkContext
from ..strategies.base import PlanStrategy
from .base import TaskProvider


class JsonlProvider(TaskProvider):
    """从 JSONL 文件加载变更记录的 Provider"""

    def __init__(
        self,
        jsonl_path: str,
        plan_strategy: PlanStrategy,
        observe_config: Optional[ObserveConfig] = None,
        sample_index: Optional[int] = None,
        random_seed: Optional[int] = None,
    ):
        super().__init__(plan_strategy=plan_strategy, observe_config=observe_config)
        self.jsonl_path = jsonl_path
        self.sample_index = sample_index
        self.random_seed = random_seed
        # 供 _manage_environment / 调试使用的最近一次选择结果
        self._selected_entry_id: Optional[str] = None
        self._selected_index: Optional[int] = None
        self._selected_seed: Optional[int] = None

    @property
    def name(self) -> str:
        return "jsonl"

    def _extract_changes(self) -> ChangeSet:
        """
        从 JSONL 文件提取文件变更。

        流程：
        1. 读取 JSONL 文件，解析为记录列表
        2. 选择一条记录：
           - 若 sample_index 不为 None，则按 0-base 索引选取对应记录
           - 否则，根据 random_seed（或现场生成的 seed）随机选一条记录
        3. 从记录中的 old_contents / new_contents 构造单个 FileChange
        4. 将样本元信息（id / commit 等）以及实际使用的 index / seed 写入 ChangeSet.metadata
        """
        records = []
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"JSONL 解析失败: {self.jsonl_path} 中存在无效 JSON 行: {e}"
                    ) from e

        if not records:
            raise ValueError(f"JSONL 文件为空或无有效记录: {self.jsonl_path}")

        # 选择样本
        if self.sample_index is not None:
            if not (0 <= self.sample_index < len(records)):
                raise IndexError(
                    f"sample_index 越界: {self.sample_index}, 总记录数: {len(records)}"
                )
            index = self.sample_index
            seed_used = None
        else:
            # 随机选择一条记录，使用 random_seed（若有）或现场生成的 seed
            seed_used = self.random_seed if self.random_seed is not None else random.randint(
                0, 2**31 - 1
            )
            rng = random.Random(seed_used)
            index = rng.randrange(len(records))

        record = records[index]
        entry_id = record.get("id")
        if entry_id is None:
            raise KeyError(
                f"JSONL 记录缺少必需字段 'id'（索引 {index}，文件 {self.jsonl_path}）"
            )

        old_contents = record.get("old_contents", "")
        new_contents = record.get("new_contents", "")
        old_file = record.get("old_file")
        new_file = record.get("new_file")

        if not old_file and not new_file:
            raise KeyError(
                f"JSONL 记录缺少 'old_file' / 'new_file'，无法确定 relative_path（id={entry_id})"
            )

        # 选择相对路径：优先使用 new_file（存在/非删除场景），删除场景则回退到 old_file
        if new_contents != "" and new_file:
            relative_path = new_file
        elif old_file:
            relative_path = old_file
        else:
            # 理论上不会到这里，上一段已校验 old_file/new_file 至少其一存在
            relative_path = new_file or old_file  # type: ignore[assignment]

        is_new_file = old_contents == "" and new_contents != ""
        is_deleted = old_contents != "" and new_contents == ""

        file_change = FileChange(
            relative_path=relative_path,
            before_content=old_contents,
            after_content=new_contents,
            is_new_file=is_new_file,
            is_deleted=is_deleted,
        )

        # 记录最近一次选择结果，供后续 _manage_environment / 调试使用
        self._selected_entry_id = entry_id
        self._selected_index = index
        self._selected_seed = seed_used

        metadata = {
            "source": "jsonl",
            "source_path": os.path.abspath(self.jsonl_path),
            "entry_id": entry_id,
            "index": index,
        }
        if seed_used is not None:
            metadata["random_seed"] = seed_used

        # 保留原始记录中的部分有用字段，方便调试或后续分析
        for key in ("commit", "old_file", "new_file", "subject", "message", "lang", "license", "repos"):
            if key in record:
                metadata[key] = record[key]

        return ChangeSet(file_changes=[file_change], metadata=metadata)

    @contextmanager
    def _manage_environment(
        self, type_plan: TypePlan
    ) -> Generator[WorkContext, None, None]:
        """
        创建临时工作目录。

        1. 创建临时目录
        2. 按 file_init_states 写入文件
        3. 构造带 source 信息的 WorkContext
        4. 退出时删除临时目录
        """
        with tempfile.TemporaryDirectory(prefix="data_synthesis_") as tmp_dir:
            file_paths: dict[str, str] = {}

            # 按 TypePlan 初始状态写入文件
            for file_state in type_plan.file_init_states:
                abs_path = os.path.join(tmp_dir, file_state.relative_path)
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(file_state.content)
                file_paths[file_state.relative_path] = abs_path
                print(
                    f"  写入文件: {file_state.relative_path} "
                    f"({len(file_state.content)} 字符)"
                )

            # 组装 WorkContext 的 source 信息（目录名使用去掉扩展名的文件名）
            base_name = os.path.basename(self.jsonl_path)
            jsonl_basename, _ = os.path.splitext(base_name)

            entry_id = self._selected_entry_id
            if entry_id is None:
                # 防御性回退：从 TypePlan.metadata 中尝试获取
                entry_id = (
                    type_plan.metadata.get("source_metadata", {})
                    .get("entry_id")
                )

            source_type = "jsonl"
            if entry_id is not None:
                source_path_segments = (jsonl_basename, entry_id)
            else:
                # 极端情况下没有 entry_id，则仅按文件名分层
                source_path_segments = (jsonl_basename,)

            context = WorkContext(
                work_dir=tmp_dir,
                file_paths=file_paths,
                source_type=source_type,
                source_path_segments=source_path_segments,
            )

            yield context
            print("  临时目录已清理")
