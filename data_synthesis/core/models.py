"""
核心数据结构

定义 Pipeline 中所有数据结构：
- Action 原语（TypeAction, ForwardDeleteAction, ObserveAction）
- TypePlan（统一中间格式，可序列化为 JSON）
- FileInitState, ObserveConfig
- WorkContext, Task
- FileChange, ChangeSet
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional, Sequence, Union


# ============================================================
# 操作原语
# ============================================================


@dataclass
class TypeAction:
    """键入动作：在指定位置输入一批字符"""

    file: str
    line: int
    col: int
    content: str
    type: Literal["type"] = field(default="type", init=False)


@dataclass
class ForwardDeleteAction:
    """删除动作：在指定位置向后删除若干字符（即 Delete 键）。
    命名显式为 ForwardDelete，与未来 BackwardDelete（向前删除，Backspace）区分。"""

    file: str
    line: int
    col: int
    count: int
    type: Literal["delete_forward"] = field(default="delete_forward", init=False)


@dataclass
class ObserveAction:
    """停顿观察：通知采集器做一次采集，可选覆盖全局配置"""

    timeout: Optional[float] = None
    retry_count: Optional[int] = None
    pre_wait: Optional[float] = None
    type: Literal["observe"] = field(default="observe", init=False)


Action = Union[TypeAction, ForwardDeleteAction, ObserveAction]


# ============================================================
# 环境与配置
# ============================================================


@dataclass
class FileInitState:
    """文件初始状态：描述一个文件在开始键入前应有的内容"""

    relative_path: str
    content: str
    is_new_file: bool = False


@dataclass
class FileFinalState:
    """文件最终状态：描述一次计划执行结束后该文件应有的内容"""

    relative_path: str
    content: str
    # 是否在计划结束时应当被删除（不存在）
    is_deleted: bool = False


@dataclass
class ObserveConfig:
    """Observe 全局默认配置"""

    timeout: float = 2.0
    retry_count: int = 1
    pre_wait: float = 0.1
    post_wait: float = 0.1


@dataclass
class WorkContext:
    """已就绪的工作环境（由 TaskProvider 准备好后交出）"""

    work_dir: str
    file_paths: dict[str, str] = field(default_factory=dict)
    # 用于 session 输出路径分层：由 Provider 按数据源类型约定填充，复现时为 None
    source_type: Optional[str] = None  # 例如 "git-repo"、"jsonl" 等，由 Provider 约定
    source_path_segments: Optional[Sequence[str]] = None  # 例如 ("repo_name", "commit_id")


@dataclass
class Task:
    """TaskProvider 交给下游的完整任务"""

    type_plan: "TypePlan"
    context: WorkContext


# ============================================================
# TypePlan —— Pipeline 核心中间格式
# ============================================================


@dataclass
class TypePlan:
    """
    完整的输入计划——Pipeline 的核心中间格式。

    可序列化为 JSON，支持"先生成计划 → 手工调整 → 再执行"的工作流。
    """

    file_init_states: list[FileInitState]
    actions: list[Action]
    file_final_states: list[FileFinalState] = field(default_factory=list)
    observe_config: ObserveConfig = field(default_factory=ObserveConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典"""
        return {
            "file_init_states": [
                {
                    "relative_path": f.relative_path,
                    "content": f.content,
                    "is_new_file": f.is_new_file,
                }
                for f in self.file_init_states
            ],
            "file_final_states": [
                {
                    "relative_path": f.relative_path,
                    "content": f.content,
                    "is_deleted": f.is_deleted,
                }
                for f in self.file_final_states
            ],
            "actions": [_action_to_dict(a) for a in self.actions],
            "observe_config": asdict(self.observe_config),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TypePlan":
        """从字典构建"""
        file_init_states = [
            FileInitState(**f) for f in data.get("file_init_states", [])
        ]
        file_final_states = [
            FileFinalState(**f) for f in data.get("file_final_states", [])
        ]
        actions = [_action_from_dict(a) for a in data.get("actions", [])]
        observe_config = (
            ObserveConfig(**data["observe_config"])
            if "observe_config" in data
            else ObserveConfig()
        )
        metadata = data.get("metadata", {})
        return cls(
            file_init_states=file_init_states,
            actions=actions,
            file_final_states=file_final_states,
            observe_config=observe_config,
            metadata=metadata,
        )

    def to_json(self, path: str) -> None:
        """序列化为 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, path: str) -> "TypePlan":
        """从 JSON 文件加载"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# ============================================================
# 数据源相关
# ============================================================


@dataclass
class FileChange:
    """单个文件的变更"""

    relative_path: str
    before_content: str
    after_content: str
    is_new_file: bool = False
    is_deleted: bool = False


@dataclass
class ChangeSet:
    """一次变更的完整描述。

    metadata 约定（由各 TaskProvider 在 _extract_changes 中填充）：
      - 必须包含：
        - source: 数据源类型（例如 "git-repo"、"jsonl"）
        - source_path: 数据源的绝对路径（例如 git 仓库根目录或 JSONL 文件绝对路径）
      - 其余字段（如 entry_id、commit_id 等）由具体 Provider 自行扩展。
    """

    file_changes: list[FileChange]
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# 序列化辅助函数
# ============================================================


def _action_to_dict(action: Action) -> dict[str, Any]:
    """将 Action 转为字典"""
    if isinstance(action, TypeAction):
        return {
            "type": "type",
            "file": action.file,
            "line": action.line,
            "col": action.col,
            "content": action.content,
        }
    elif isinstance(action, ForwardDeleteAction):
        return {
            "type": "delete_forward",
            "file": action.file,
            "line": action.line,
            "col": action.col,
            "count": action.count,
        }
    elif isinstance(action, ObserveAction):
        d: dict[str, Any] = {"type": "observe"}
        if action.timeout is not None:
            d["timeout"] = action.timeout
        if action.retry_count is not None:
            d["retry_count"] = action.retry_count
        if action.pre_wait is not None:
            d["pre_wait"] = action.pre_wait
        return d
    else:
        raise ValueError(f"未知的 Action 类型: {type(action)}")


def _action_from_dict(data: dict[str, Any]) -> Action:
    """从字典构建 Action，根据 type 字段分发"""
    action_type = data.get("type")
    if action_type == "type":
        return TypeAction(
            file=data["file"],
            line=data["line"],
            col=data["col"],
            content=data["content"],
        )
    elif action_type == "delete_forward":
        return ForwardDeleteAction(
            file=data["file"],
            line=data["line"],
            col=data["col"],
            count=data["count"],
        )
    elif action_type == "observe":
        return ObserveAction(
            timeout=data.get("timeout"),
            retry_count=data.get("retry_count"),
            pre_wait=data.get("pre_wait"),
        )
    else:
        raise ValueError(f"未知的 Action type: {action_type}")
