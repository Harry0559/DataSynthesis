"""
核心数据结构

定义 Pipeline 中所有数据结构：
- Action 原语（TypeAction, ForwardDeleteAction, ObserveAction）
- TypePlan（统一中间格式，可序列化为 JSON）
- FileInitState, ObserveConfig
- WorkContext, Task
- FileChange, ChangeSet
- SessionConfig, BatchConfig
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

    def get_end_cursor(self) -> tuple[int, int]:
        """
        返回本动作执行完后，光标的行列位置。
        假设执行前光标已经在 (self.line, self.col)。
        """
        line = self.line
        col = self.col
        for ch in self.content:
            if ch == "\n":
                line += 1
                col = 1
            else:
                col += 1
        return line, col


@dataclass
class ForwardDeleteAction:
    """删除动作：在指定位置向后删除一段文本（即 Delete 键）。

    content 字段表示从 (line, col) 开始、向后被删除的原始文本内容，
    可包含换行符；对于光标位置而言，Delete 键删除的是“光标之后”的内容，
    光标本身停留在起始位置不动。
    """

    file: str
    line: int
    col: int
    content: str
    type: Literal["delete_forward"] = field(default="delete_forward", init=False)

    def get_end_cursor(self) -> tuple[int, int]:
        """
        返回本动作执行完后，光标的行列位置。
        假设执行前光标已经在 (self.line, self.col)。
        Delete 删除的是光标之后的文本，光标本身不移动。
        """
        return self.line, self.col


@dataclass
class ObserveAction:
    """停顿观察：表示在此处做一次采集。行为统一由 ObserveConfig（或 CLI）控制，无 per-action 覆盖。"""

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
    """Observe 全局配置，所有 ObserveAction 共用；可由 CLI 覆盖（当前未提供）。"""

    # 预留：未来可在 Collector/Executor 中用于单次采集超时（如轮询日志文件的上限）
    timeout: float = 2.0
    # 预留：未来可在采集失败时重试次数
    retry_count: int = 1
    # Executor 在 save_file 后、调用 collect 前 sleep 的秒数
    pre_wait: float = 1.5
    # Executor 在 collect 完成后、继续下一动作前 sleep 的秒数
    post_wait: float = 0.05


@dataclass
class SessionConfig:
    """run_session 的运行配置，封装执行/输出等可扩展参数。

    新增配置项只需在此添加字段，run_session 签名无需变动。
    """

    type_interval: float = 0.01
    delete_interval: float = 0.01
    dry_run: bool = False
    output_dir: str = "output/collected"


@dataclass
class BatchConfig:
    """批量运行配置：仅负责超时与总次数刹车。"""

    # 整个批量运行的时间上限（秒），None 表示不限制
    max_duration_seconds: Optional[float] = None
    # 全局最多执行多少条 pipeline（跨所有文件/数据源），None 表示不限制
    max_items_total: Optional[int] = None


@dataclass
class WorkContext:
    """已就绪的工作环境（由 TaskProvider 准备好后交出）"""

    work_dir: str
    file_paths: dict[str, str] = field(default_factory=dict)
    # 用于 session 输出路径分层：由 Provider 按数据源类型约定填充，无则为 None
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
            "content": action.content,
        }
    elif isinstance(action, ObserveAction):
        return {"type": "observe"}
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
            content=data["content"],
        )
    elif action_type == "observe":
        return ObserveAction()
    else:
        raise ValueError(f"未知的 Action type: {action_type}")
