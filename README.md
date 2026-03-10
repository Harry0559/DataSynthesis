# DataSynthesis

跨 IDE 代码输入模拟与数据采集工具。

## 快速开始

```bash
# dry-run 模式验证 pipeline
python -m data_synthesis --load-plan examples/sample_plan.json --dry-run
```

## 架构概览

```
数据源 → TaskProvider → TypePlan(JSON) → Executor → EditorAdapter → Platform
                              ↑                         ↓
                        PlanStrategy              Collector（采集日志）
```

**核心概念**：

- **TypePlan**：统一中间格式，描述"文件初始状态 + 有序操作链"，可序列化为 JSON
- **TaskProvider**：处理数据源 + 生成计划 + 管理环境（准备/恢复）
- **PlanStrategy**：可插拔的输入重放策略（将文件变更转为操作序列）
- **Executor**：按操作序列驱动编辑器（Type / Delete / Observe）
- **Collector**：在 Observe 点采集数据（日志、截图等）
- **EditorAdapter**：IDE 适配层（Cursor / VSCode / ...）
- **Platform**：OS 适配层（macOS / Linux / Windows）

## 项目结构

```
data_synthesis/
├── core/           # 数据结构 + 编排 + 配置
├── providers/      # 数据源（git_repo / jsonl / plan_file）
├── strategies/     # 输入重放策略（diff_replay / batch）
├── executors/      # 执行器
├── collectors/     # 采集器（tab_log）
├── editors/        # IDE 适配（cursor）
├── platform/       # OS 适配（darwin / linux / windows）
├── git/            # Git 操作
└── utils/          # 通用工具（diff 计算等）
```

## 开发状态

- [x] 核心数据结构（TypePlan + Action + 序列化）
- [x] Pipeline 编排（session.py）
- [x] Executor 核心循环（含 dry-run）
- [x] PlanFileProvider（从 JSON 加载）
- [ ] GitRepoProvider（从 git 仓库提取）
- [ ] JsonlProvider（从 JSONL 提取）
- [ ] PlanStrategy 实现（diff_replay / batch）
- [ ] CursorAdapter（Cursor IDE 适配）
- [ ] TabLogCollector（Tab/Output 日志采集，跨 IDE）
- [ ] Platform 实现（darwin / linux / windows）
- [ ] 配置系统（YAML 加载）
