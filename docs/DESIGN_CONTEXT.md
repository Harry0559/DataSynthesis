# DataSynthesis 设计上下文

本文档记录项目从构思到第一版落地的完整设计讨论与决策，供后续在新工程中延续上下文、继续优化代码时参考。

---

## 一、背景与动机

### 1.1 从 CursorSynthesis 到新方案

原工程（CursorSynthesis）主要做两件事：

- **代码输入练习**：在 Cursor 中自动逐字输入，模拟真实编码
- **Ghost Text 数据采集**：通过 YOLO 检测 + 区域 OCR（LLM）从截图中提取补全建议

新方案的目标变化：

- **不再依赖视觉链路**：不需要 YOLO、OCR、截图
- **采集方式改为**：每次敲入字符后，通过「快捷键保存 Cursor Tab 日志」的方式捕获当前模型输出并记录
- **保留并复用**：选 commit 构造样本、typer 逐字符输入、session 管理等能力

### 1.2 方案选择：新工程 vs 改旧工程

结论：**新开工程更合适**。

原因简要：

- 旧工程中采集与 vision 深度耦合：session 直接造 ghost/screenshot 的 callback 工厂并 import vision、typer 的 `type_with_collection` 与 `GhostCollectResult`/Tab 接受强绑定。
- 若在旧工程上删 vision、改采集，会留下大量死代码和 `if not use_vision` 分支，Session 和 Typer 都要大改。
- 新工程可以只实现「快捷键保存 Tab 日志 + 读日志写 jsonl」这一条采集路径，依赖少、结构清晰，策略/模式/平台等概念可拷贝或精简复用。

---

## 二、旧工程（CursorSynthesis）流程与问题

### 2.1 整体流程

```
__main__ → run_auto_type_session / run_ghost_text_collection_session / run_screenshot_collection_session
         → _run_session_core(...)
```

- **阶段一**：校验 Cursor 配置 → `strategy.git_session()` → `strategy.prepare()` → `mode.process()` → 创建 session 目录、写 meta、生成复现命令
- **阶段二**：`restart_cursor(repo_path)`
- **阶段三**：对每个 segment：`open_and_locate` → `typer.type_with_collection()` 或 `typer.type_content()` → `save_file()`
- **阶段四**：退出 `with git_session` 时恢复 .git 与原始状态

### 2.2 冗余与耦合（为何难以在旧工程上改）

| 问题 | 说明 |
|------|------|
| 三个入口函数重复 | `run_auto_type_session` / `run_ghost_text_collection_session` / `run_screenshot_collection_session` 参数列表绝大部分相同，仅 session_type、collect_callback_factory 等不同 |
| Session 既编排又管采集实现 | `_create_ghost_text_callback_factory`、`_create_screenshot_callback_factory` 写在 session.py，直接 import vision、editor.typers.collection |
| Typer 与 Ghost+Tab 接受绑死 | `type_with_collection` 的 callback 返回 `GhostCollectResult`，用于写 jsonl 且驱动 try_tab_accept；新方案只需「通知采集」不需要返回值参与 Tab 逻辑 |
| create_typer 按是否 ghost 分支 | 无采集：`create_typer(strategy)`；Ghost：`create_typer(strategy, op_logger, history_tracker)` |
| 复现命令生成集中在 Session | `_generate_reproduce_commands` 写死所有策略/模式/采集参数，加新选项就要改 Session |
| 目录与元数据与采集类型绑定 | session_meta 里 session_type、collect_interval、auto_accept 等与具体采集方式耦合 |

---

## 三、新方案核心思路

### 3.1 数据源与统一格式

- **数据源多样**：已下载的若干工程文件夹（含真实 commit）、或整理好的 JSONL 文件（记录某工程某 commit 下的单文件修改）。
- **统一加工**：有统一模块处理这些数据源，输出**可实际操作的具体任务**；加工方法多样（选 commit、选样本、规划操作顺序等），但**交给下游的产物格式统一**。
- **统一格式**：即 **TypePlan**：文件初始状态 + 有序操作链（TypeAction / DeleteAction / ObserveAction）+ 观察配置与元数据，且**可序列化为 JSON**。

### 3.2 准备与还原归属

- 处理数据源的模块**同时具备准备和还原能力**：下游拿着它的输出，能清楚如何在编辑器中准备好初始环境（切 commit 或建临时单文件）、并在实验结束后无感恢复。
- **设计结论**：不把「如何准备」写进 TypePlan（不在 TypePlan 里塞 SetupInstructions）。改为 **TaskProvider 内部自己准备环境**，只交出「已就绪的工作目录 + TypePlan」；Session/Executor 只消费 `Task(type_plan, context)`，不关心环境是怎么准备的。这样加新数据源只需新 TaskProvider，执行层零改动。

### 3.3 操作链与 Observe

- 操作链显式包含**何时停顿观察**：例如「先在第 5 行第 6 列快速键入 5 个字符 → 观察日志 → 再在第 8 行第 10 列键入 10 个字符 → 观察」。
- 抽象为有序 **Action 序列**：`TypeAction`、`DeleteAction`、`ObserveAction`，Executor 按序执行；遇 `ObserveAction` 则通知 Collector 做一次采集。
- **ObserveAction 设计**：采用「方式三」——全局 `ObserveConfig` 做默认；每个 `ObserveAction` 可带可选覆盖字段（`timeout`、`retry_count`、`pre_wait`），未指定则用全局默认。这样起步时所有 observe 行为一致，将来若某几个采集点需要更长等待，只需在该 action 上覆盖即可。

### 3.4 跨平台、跨 IDE、配置

- 目标：跨平台、跨 IDE，通过简单配置即可在不同环境运行。
- 配置：分层——默认值 → 配置文件（如 YAML）→ CLI 参数覆盖；参数丰富、层次清晰，支持通过配置文件或 CLI 灵活控制。

---

## 四、核心数据结构（TypePlan 与 Action）

### 4.1 Action 原语

- **TypeAction**：`file`, `line`, `col`, `content`（可单字符可一批）
- **DeleteAction**：`file`, `line`, `col`, `count`（向后删除）
- **ObserveAction**：无必填参数；可选 `timeout`, `retry_count`, `pre_wait` 覆盖全局配置

Action 序列可跨文件交替（每个 Action 带 `file`），Executor 在 `file` 变化时切换当前文件。

### 4.2 TypePlan（唯一交接物）

- **file_init_states**：各文件初始内容（声明「应该有什么」）
- **actions**：有序操作链
- **observe_config**：Observe 全局默认
- **metadata**：来源、策略、seed 等，仅记录用

不含「如何准备环境」的过程性信息；准备由 TaskProvider 在内部完成。

### 4.3 数据源侧：ChangeSet

- **FileChange**：`relative_path`, `before_content`, `after_content`, `is_new_file`, `is_deleted`
- **ChangeSet**：`file_changes` + `metadata`

DataSource 产出 ChangeSet；PlanStrategy 消费 ChangeSet 产出 TypePlan。

### 4.4 Task 与 WorkContext

- **WorkContext**：`work_dir`（已就绪的工作目录）、`file_paths`（relative → absolute）；可选 `source_type`、`source_path_segments`（全新采集时由 Provider 填充，用于 session 输出路径分层；复现时为 None）。
- **Task**：`type_plan` + `context`

TaskProvider 通过 `provide()` 上下文管理器 yield `Task`；退出 with 时自动恢复环境。

---

## 五、模块职责与扩展点

### 5.1 TaskProvider（扩展点①）

- 职责：从数据源提取变更 → 调用 PlanStrategy 生成 TypePlan → 准备环境 → yield Task → 退出时恢复。
- 子类实现：`_extract_changes()`、`_manage_environment(type_plan)`。
- 实现：`PlanFileProvider`（从 JSON 加载，无 Strategy）、`GitRepoProvider`（TODO）、`JsonlProvider`（TODO）。

### 5.2 PlanStrategy（扩展点②）

- 职责：`generate(change_set, observe_config) -> TypePlan`。
- 实现：`DiffReplayStrategy`（TODO）、`BatchStrategy`（TODO）等。

### 5.3 Executor

- 职责：遍历 `type_plan.actions`，按类型 dispatch：Type → 定位+输入，Delete → 定位+删除，Observe → 保存文件+调用 Collector。
- 支持 dry-run（不操作编辑器，只打印日志）。

### 5.4 Collector（扩展点③）

- 职责：`init_session(session_dir, observe_config)`；`collect(file_path, char_index)`；`finalize()`。
- 实现：`TabLogCollector`（跨 IDE，依赖 editor.capture_tab_log + 写 jsonl）。

### 5.5 EditorAdapter（扩展点④）

- 职责：`restart(work_dir)`、`open_file`、`goto`、`type_text`、`delete_chars`、`save_file`、`send_hotkey`、`validate_settings`。
- 实现：`CursorAdapter`（TODO）等。

### 5.6 Platform

- 职责：OS 级键盘、窗口、启动/退出应用等。
- 实现：`DarwinPlatformHandler`（TODO）、Linux、Windows。

---

## 六、Session 编排

- **阶段一**：通过 TaskProvider.provide() 获取 Task（内部完成提取+生成+准备）。
- **阶段二**：创建 session 目录（若非 dry-run）、保存 meta、**在 session 目录内自动保存 type_plan.json**；`editor.restart(context.work_dir)`。
- **阶段三**：Collector.init_session；Executor.execute(type_plan, context)；Collector.finalize。
- **阶段四**：退出 provide() 的 with 时，TaskProvider 自动恢复环境。

Session 不 import 任何具体 Provider/Strategy/Collector/Editor 实现，只依赖抽象；具体实现由入口组装注入。

### 6.1 CLI 与输出目录管理

- **运行模式互斥，例如**：
  1. **全新采集**：`--source`（如 git-repo、jsonl 等）+ `--source-path PATH`；输出根目录由 `--output-dir` 指定（默认 `output/collected`）。
  2. **复现**：`--plan PATH`（指定某次 session 的 type_plan.json）；输出根目录固定为 **plan 所在目录下的 `reproduce/` 子目录**，每次复现在该目录下再建 `session_YYYYMMDD_HHMMSS/`。

- **Session 路径分层**（全新采集时；复现时为 `reproduce/session_xxx`）：
  - 在 `output_dir` 下按数据源类型与标识分子目录，再在最小单位下建 `session_xxx`。当前包括例如：
  - **git-repo**：`output_dir/git-repo/<仓库名>/<commit_id>/session_xxx/`。仓库名 = 仓库目录名；commit_id = 短 hash（无前缀）。
  - **jsonl**：`output_dir/jsonl/<jsonl 文件名>/<条目 id>/session_xxx/`。条目 id = 该条记录的 `id` 字段值。

- **Plan 文件**：每次非 dry-run 运行会在**当前 session 目录内**自动写入 `type_plan.json`，不提供 `--save-plan` 参数；plan 作为当次 pipeline 的留存与复现依据，与 session_meta、采集数据同目录。

---

## 七、ObserveAction 设计（方式三）详解

- **全局配置**：`ObserveConfig(timeout, retry_count, pre_wait, post_wait)` 作为默认值。
- **ObserveAction**：可带可选字段 `timeout`, `retry_count`, `pre_wait`；为 None 时表示用全局默认。
- **合并逻辑**：Executor/Collector 在每次 Observe 时：`effective_timeout = action.timeout if action.timeout is not None else observe_config.timeout`，其他同理。
- **好处**：起步时所有 observe 一致（全不填即可）；后续若个别采集点需更长等待，只需在该 ObserveAction 上写 `timeout: 5.0` 等，无需改架构。

---

## 八、Cursor 配置校验（参考旧工程）

旧工程中 `validate_cursor_settings()` 校验的配置（新工程若需可复用或精简）：

- **关闭自动补全/建议**：`editor.quickSuggestions` 全 off、`editor.suggestOnTriggerCharacters` false、`editor.wordBasedSuggestions` "off"、`editor.hover.enabled` false、`editor.parameterHints.enabled` false。
- **关闭自动闭合/包围**：`editor.autoClosingBrackets` 等均为 "never"。
- **关闭自动缩进**：`editor.autoIndent` "none"。
- **显示空白**：`editor.renderWhitespace` "all"。
- **HTML/JS/TS**：`html.autoClosingTags`、`javascript.autoClosingTags`、`typescript.autoClosingTags` 等 false。

目的：避免自动补全、自动闭合、自动缩进干扰「逐字输入」和采集结果。

---

## 九、配置系统

- 优先级：**CLI 参数 > 配置文件 > 默认值**。
- Config 包含：数据源类型与路径、策略名与参数、执行参数（type_interval、vi_mode、dry_run）、采集器类型与参数、observe 配置、编辑器类型、输出目录、复现用 random_seed 等。
- 第一版：Config dataclass 与 merge 逻辑已存在；YAML 加载可后续实现。

---

## 十、最终架构视图

### 10.1 概念全景

```
数据输入（Git 工程 / JSONL）→ TaskProvider（提取+计划+准备）→ TypePlan → Executor + Collector
                                                                  ↑
                                                           可序列化 JSON
                                                           PlanStrategy 可插拔
```

### 10.2 数据流

```
阶段一：TaskProvider.provide() 内：extract_changes → plan_strategy.generate → _manage_environment → yield Task
阶段二：Session：create_session_dir，editor.restart(work_dir)
阶段三：Executor.execute(actions)；遇 ObserveAction → Collector.collect
阶段四：退出 with → TaskProvider 恢复环境
```

### 10.3 模块依赖方向

- `core/models`：纯数据，被所有人引用，不引用任何人。
- `core/session`：只依赖抽象（TaskProvider、EditorAdapter、Collector、Executor），不依赖具体实现。
- 具体实现（PlanFileProvider、GitRepoProvider、CursorAdapter、TabLogCollector 等）由 `__main__` 组装后注入；**箭头只向下，无环**。

### 10.4 扩展点小结

| 扩展点 | 抽象 | 已实现 | TODO |
|--------|------|--------|------|
| 数据源 | TaskProvider | PlanFileProvider | GitRepoProvider, JsonlProvider |
| 加工策略 | PlanStrategy | （基类） | DiffReplayStrategy, BatchStrategy |
| 采集 | Collector | （基类） | TabLogCollector |
| 编辑器 | EditorAdapter | （基类） | CursorAdapter |
| 平台 | PlatformHandler | （基类） | DarwinPlatformHandler 等 |

---

## 十一、第一版实现范围

### 11.1 已实现（可运行）

- **core/models.py**：TypePlan、Action、FileInitState、ObserveConfig、WorkContext（含可选 source_type、source_path_segments）、Task、ChangeSet、FileChange；`to_json`/`from_json`、`to_dict`/`from_dict`。
- **core/session.py**：`run_session()` 四阶段编排；按 context 建 session 路径分层；session 目录内自动写 type_plan.json；无 save_plan_path 参数。
- **core/config.py**：Config dataclass、from_dict、merge。
- **providers/plan_file.py**：从 JSON 加载 TypePlan，建临时目录写 file_init_states，yield Task（无 source 信息，用于复现）。
- **executors/executor.py**：Action 循环、dry_run 模式。
- **__main__.py**：两模式——全新采集 `--source`+`--source-path`、复现 `--plan`；`--output-dir`、`--dry-run`、`--type-interval`；复现时输出根为 plan 所在目录/reproduce/。
- **examples/sample_plan.json**：示例计划。

### 11.2 TODO 骨架（待补充）

- **providers/git_repo.py**：_extract_changes（选 commit、算 diff、建 ChangeSet）、_manage_environment（checkout、隐藏 .git、恢复）；yield WorkContext 时设置 source_type="git-repo"，source_path_segments=(repo_name, commit_id)，其中 repo_name=仓库目录名、commit_id=短 hash 无前缀。
- **providers/jsonl.py**：_extract_changes（读 JSONL、选样本，条目需含 "id" 字段）、_manage_environment（临时目录）；yield WorkContext 时设置 source_type="jsonl"，source_path_segments=(jsonl_basename, entry_id)。
- **strategies/diff_replay.py**、**batch.py**：generate(change_set, observe_config) -> TypePlan。
- **collectors/tab_log.py**：TabLogCollector，init_session、collect（调 editor.capture_tab_log、读文件、写 jsonl）、finalize。
- **editors/cursor.py**：restart、open_file、goto、type_text、delete_chars、save_file、send_hotkey、validate_settings。
- **platform/darwin.py**：type_char、send_key、send_hotkey、activate_window、launch_app、quit_app。
- **git/manager.py**：get_commits、get_diff、checkout、hide_git_dir、restore_git_dir 等。
- **utils/diff.py**：compute_line_diff、compute_char_diff 等。

### 11.3 验证方式

```bash
cd /path/to/DataSynthesis
python -m data_synthesis --plan examples/sample_plan.json --dry-run
```

应完成：加载 JSON → 建临时目录并写文件 → Executor 按序列打印所有 Action → 清理临时目录。复现模式输出根目录为 `examples/reproduce/`（dry-run 不写文件）。

---

## 十二、对话中的其他要点

- **跨文件交替**：Action 序列已支持（每个 Action 带 `file`）；Executor 在 `action.file != current_file` 时切换文件；当前可不实现复杂场景，但结构已预留。
- **DeleteAction**：需要保留；diff 重放时会有先删后加。
- **序列化**：TypePlan 设计为易序列化（所有 Action 有 `type` 字段，便于 JSON 序列化/反序列化分发）。
- **单文件数据源**：当前设想为手动提供 before/after 两份内容；未来若有从 diff patch 或其它格式解析，可再扩展 SingleFileSource/JsonlProvider。

---

## 十三、文档与后续使用

- 在新工程（DataSynthesis）中开新对话时，可 **@docs/DESIGN_CONTEXT.md** 让模型加载本设计上下文，便于延续架构约束、实现 TODO、做优化而不偏离既定设计。
- 若增删扩展点或调整交互方式，建议同步更新本文档。
