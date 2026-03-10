"""
配置模块

提供分层配置系统：默认值 → 配置文件 (YAML) → CLI 参数覆盖。
"""

from dataclasses import dataclass, fields
from typing import Any, Optional


@dataclass
class Config:
    """全局配置"""

    # 数据源
    source_type: str = "plan_file"
    repo_path: Optional[str] = None
    jsonl_path: Optional[str] = None
    plan_path: Optional[str] = None

    # 输入重放策略
    strategy: str = "diff_replay"
    observe_every: int = 5

    # 执行
    type_interval: float = 0.05
    vi_mode: Optional[bool] = None
    dry_run: bool = False

    # 采集
    collector_type: Optional[str] = None

    # 观察配置
    observe_timeout: float = 2.0
    observe_retry: int = 1
    observe_pre_wait: float = 0.1
    observe_post_wait: float = 0.1

    # 编辑器
    editor_type: str = "cursor"
    settings_check: bool = True

    # 输出（复现时 output_dir 由 plan 所在目录/reproduce 决定，不读此配置）
    output_dir: str = "output/collected"

    # 复现
    random_seed: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """从字典构建，忽略未知字段"""
        valid_field_names = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_field_names}
        return cls(**filtered)

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """从 YAML 文件加载"""
        # TODO: 实现 YAML 加载（需要 pyyaml 依赖）
        raise NotImplementedError("YAML 配置加载尚未实现")

    def merge(self, overrides: dict[str, Any]) -> "Config":
        """用覆盖值创建新 Config（CLI 参数覆盖配置文件）"""
        current = dict(self.__dict__)
        for k, v in overrides.items():
            if v is not None and k in current:
                current[k] = v
        return Config.from_dict(current)
