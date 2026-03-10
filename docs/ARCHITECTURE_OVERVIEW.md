# DataSynthesis 架构与项目介绍

> 跨 IDE 的「代码输入模拟 + 日志采集」基础设施：  
> 把各种数据源（Git/JSONL/已有计划）统一转换成可执行的键盘操作序列，在真实 IDE 里逐字重放，并在指定观察点采集模型输出日志。

---

## 1. 适用场景与目标

- **代码输入重放**：在 Cursor 等 IDE 中逐字模拟真实开发者的输入过程。
- **模型输出采集**：在输入过程中的关键位置触发采集，将模型补全/输出记录到结构化日志（如 JSONL）。
- **可复现实验**：对某次输入过程保存为 `TypePlan`，后续可以在同/异环境中复现。
- **跨数据源统一处理**：无论是 Git 仓库变更、预处理好的 JSONL 样本，还是已有 `type_plan.json`，下游都只看统一的中间格式。

设计目标：

- **统一格式**：中间产物用 `TypePlan(JSON)` 表达「文件初始状态 + 有序操作链」。
- **强可复现**：`TypePlan + WorkContext` 即可在任意支持的 IDE + 平台上重放。
- **可插拔扩展**：数据源、规划策略、采集器、编辑器适配器、平台适配器都通过抽象接口扩展。
- **跨 IDE / 跨平台**：当前聚焦 Cursor + macOS，接口设计上预留 VSCode / Linux / Windows。

---

## 2. 端到端流程总览

整体流水线可以概括为：

```text
数据源 → TaskProvider → TypePlan(JSON) → Executor → EditorAdapter → Platform
                              ↑                         ↓
                        PlanStrategy              Collector（采集日志）
```

### 2.1 两种运行模式

- **全新采集模式（from 数据源）**
  - CLI：`--source TYPE --source-path PATH [--strategy NAME]`
  - 例：从 JSONL 样本生成 TypePlan 并在 Cursor 中执行、采集日志。
- **复现模式（from TypePlan）**
  - CLI：`--plan /path/to/type_plan.json`
  - 用于重放已有计划，验证结果或做对比实验。

### 2.2 高层阶段（由 `run_session` 编排）

1. **阶段一：任务就绪**
   - 通过 `TaskProvider.provide()`：
     - 从数据源提取变更（`ChangeSet`）
     - 通过 `PlanStrategy` 生成 `TypePlan`
     - 准备临时工作目录，写入初始文件
     - 组装 `Task(type_plan, context)`
2. **阶段二：准备编辑器**
   - `editor.restart(context.work_dir)` 打开 IDE 并加载工作目录。
3. **阶段三：执行 + 采集**
   - 创建 session 输出目录（含 `type_plan.json` 和 `session_meta.json`）。
   - `Collector.init_session(...)` 初始化采集。
   - `Executor.execute(type_plan)` 逐个执行 `Action`：
     - `TypeAction` / `ForwardDeleteAction`：编辑器内输入/删除。
     - `ObserveAction`：保存文件并触发采集器。
4. **阶段四：清理与恢复**
   - 退出 `TaskProvider.provide()` 的 `with` 块时自动恢复环境（删除临时目录等）。

---

## 3. 核心概念与数据结构

### 3.1 TypePlan：唯一交接物

`TypePlan` 是数据源侧和执行侧之间的**唯一交接格式**，核心字段：

- **`file_init_states`**：每个文件的初始内容（声明「最开始应该是什么」）。
- **`actions`**：有序操作链，元素为以下几种 `Action`：
  - `TypeAction`：在某文件的 `(line, col)` 输入一段 `content`。
  - `ForwardDeleteAction`：在 `(line, col)` 向后删除若干字符。
  - `ObserveAction`：表示「在这里停一下并采集」。
- **`observe_config`**：Observe 全局默认配置（`timeout`, `pre_wait`, `post_wait` 等）。
- **`metadata`**：来源数据源信息、策略名、随机种子等，主要用于调试和分析。

`TypePlan` 支持 `to_json` / `from_json`，可以持久化到磁盘作为复现依据。

### 3.2 ChangeSet 与 FileChange

数据源侧的统一抽象：

- **`FileChange`**：单文件的变更，包含
  - `relative_path`
  - `before_content` / `after_content`
  - `is_new_file` / `is_deleted`
- **`ChangeSet`**：一组 `FileChange` + `metadata`

`PlanStrategy` 从 `ChangeSet` 出发产出 `TypePlan`。

### 3.3 Task 与 WorkContext

- **`WorkContext`**
  - `work_dir`：当前运行所用的工作目录（通常是临时目录）。
  - `file_paths`：`relative_path -> absolute_path` 的映射表。
  - 可选 `source_type`、`source_path_segments`：用于在输出目录中进行分层（例如 `jsonl/<文件名>/<entry_id>/session_xxx`）。
- **`Task`**
  - `type_plan`：要执行的计划。
  - `context`：与该计划对应的工作目录及源信息。

`TaskProvider.provide()` yield 的就是 `Task` 实例。

---

## 4. 模块与职责

### 4.1 `core`：数据模型与 Session 编排

- `core/models.py`：定义 `TypePlan` / 各类 `Action` / `ObserveConfig` / `WorkContext` / `Task` / `ChangeSet` / `FileChange` 等。
- `core/session.py`：实现 `run_session()`，负责四个阶段：
  - 获取任务（通过 `TaskProvider.provide()`）
  - 准备编辑器（`editor.restart`）
  - 执行计划并采集（`Executor` + `Collector`）
  - 恢复环境（`TaskProvider` 的上下文退出）

### 4.2 TaskProvider：数据源适配层

抽象基类：`providers/base.py`，子类负责：

1. 从数据源抽取 `ChangeSet`（或直接加载现有 `TypePlan`）。
2. 调 `PlanStrategy.generate()` 生成 `TypePlan`（对于已有 plan 的情况可跳过）。
3. 管理运行时环境（创建/清理临时目录、写文件、提供 `WorkContext`）。

当前主要实现：

- **`PlanFileProvider`**
  - 直接从 JSON 文件加载 `TypePlan`。
  - 在临时目录中按 `file_init_states` 写出文件。
  - 适用于「先离线生成/编辑 plan，再复现」的场景。
- **`JsonlProvider`**
  - 从 JSONL 文件中选择一条记录（`sample_index` 或 `random_seed`）。
  - 从记录里构造 `FileChange`/`ChangeSet`，并通过策略生成 `TypePlan`。
  - 在临时目录中写入初始文件。
  - 输出的 `WorkContext.source_type = "jsonl"`，并按文件名 + entry id 分层。
- （预留）`GitRepoProvider`
  - 面向 Git 仓库 + commit 的数据源，目前为占位/规划状态。

### 4.3 PlanStrategy：变更 → TypePlan 的策略

抽象基类：`strategies/base.py`，核心方法：

- `generate(change_set: ChangeSet, observe_config: ObserveConfig) -> TypePlan`

当前主要实现：

- **`DiffHunkStrategy`**
  - 基于 `difflib.SequenceMatcher` 的行级 diff，把 `FileChange` 拆成若干 hunk。
  - 每个 hunk 内按顺序：
    - 删除 before 段中的旧行（`ForwardDeleteAction`）
    - 插入 after 段中的新行（`TypeAction`）
    - 在 hunk 结束时插入一次 `ObserveAction`，便于在每个逻辑变更块后采集日志。

未来可扩展为更细粒度（按 token / 字符）或不同节奏（batch typing）策略。

### 4.4 Executor：在编辑器中执行 TypePlan

所在文件：`executors/executor.py`。

职责：

- 遍历 `type_plan.actions`，根据类型分发：
  - `TypeAction`：切换文件 → 定位 → 逐字输入（带 `type_interval`）。
  - `ForwardDeleteAction`：切换文件 → 定位 → 向后删除指定字符数。
  - `ObserveAction`：保存当前文件 → 等待 `pre_wait` → 调 `Collector.collect(...)` → 等待 `post_wait`。
- 支持 **`dry_run` 模式**：只打印日志，不对真实编辑器发键盘操作；适合验证 pipeline。

### 4.5 Collector：采集机制（TabLogCollector）

抽象基类：`collectors/base.py`。

当前实现：

- **`TabLogCollector`**
  - 依赖注入的 `EditorAdapter.capture_tab_log(current_file_abs_path)`。
  - 在每个 `ObserveAction` 时：
    1. 读取当前文件内容。
    2. 调 editor 的 `capture_tab_log`，从 IDE 的 Output/Tab 日志中抓取最新模型输出。
    3. 以一条 record 追加写入 `collected.jsonl`：
       - 文件路径 / 光标位置 / action_index
       - 当前文件内容
       - 解析后的模型输出
       - 时间戳、格式版本等元信息。

Collector 的实现与具体 IDE 解耦，IDE 特定逻辑由 `EditorAdapter` 负责。

### 4.6 EditorAdapter：IDE 适配层（Cursor）

抽象基类：`editors/base.py`。

当前实现：

- **`CursorAdapter`**
  - `restart(work_dir)`：通过平台层操作（激活、关闭、重新打开工作目录）重启 Cursor。
  - `open_file(relative_path)` / `goto(line, col)`：通过 Quick Open 和跳转定位到指定文件/位置。
  - `type_char` / `delete_chars_forward` / `save_file`：封装最小的编辑操作。
  - `capture_tab_log(current_file_abs_path)`：
    - 使用一组 Cursor 内自定义快捷键打开 Output 面板、保存当前 Output 为 `Cursor Tab.log`、清空 Output。
    - 在当前文件目录下等待 `Cursor Tab.log` 出现并读取内容。
    - 解析日志中「Model output」区块，得到模型输出文本。
    - 删除临时日志文件。

这些高阶操作都通过 `PlatformHandler` 调用系统 API 实现。

### 4.7 Platform：操作系统适配层（Darwin）

抽象基类：`platform/base.py`。

当前实现：

- **`DarwinPlatformHandler`（macOS）**
  - 基于 AppleScript + `System Events`：
    - `type_char`：按字符输入（含对回车、Tab、非 ASCII 文本的特殊处理）。
    - `send_key`：按 key code 发送特殊键（Delete、方向键等）。
    - `send_hotkey`：发送组合快捷键（如 Cmd+S / Cmd+Option+Shift+O）。
  - `activate_window` / `open_app_with_folder` / `quit_app`：通过 `open -a` 与 AppleScript 控制 Cursor 应用。
  - `get_modifier_key()`：macOS 返回 `"command"`，其他平台实现时可返回 `"control"` 等。

---

## 5. CLI 用法与示例

### 5.1 模式与数据源

入口：`data_synthesis/__main__.py`。

主要参数组：

- **模式与数据源**
  - `--source {git-repo,jsonl}`：指定数据源类型。
  - `--source-path PATH`：数据源路径（如 JSONL 文件）。
  - `--strategy diff-hunk`：当 `--source=jsonl` 时必填。
  - `--plan PATH`：复现模式，指定某次 session 的 `type_plan.json`。
- **JSONL 样本选择**
  - `--sample-index`：指定第几条记录（0-base）。
  - `--random-seed`：未指定 `sample_index` 时用于可复现地随机选择一条。
- **执行**
  - `--dry-run`：只打印执行计划，不真正操作编辑器。
  - `--type-interval`：字符输入间隔（秒）。
  - `--editor cursor`：选择编辑器适配器（当前实现为 Cursor）。
- **采集**
  - `--collector {none,tab-log}`：启用/关闭 TabLog 采集。
- **输出**
  - `--output-dir DIR`：全新采集时输出根目录（默认 `output/collected`）。

### 5.2 示例命令

**1）JSONL + diff-hunk + dry-run 验证**

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path input/jsonl/test.jsonl \
  --strategy diff-hunk \
  --dry-run
```

**2）JSONL + diff-hunk + Cursor 实机执行 + TabLog 采集**

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path input/jsonl/test.jsonl \
  --strategy diff-hunk \
  --editor cursor \
  --collector tab-log \
  --type-interval 0.05
```

**3）从已有 TypePlan 复现（不采集，仅验证）**

```bash
python -m data_synthesis \
  --plan output/collected/jsonl/test/003/session_xxx/type_plan.json \
  --dry-run
```

---

## 6. 输出目录与数据格式

### 6.1 Session 目录结构

- 全新采集：

```text
<output-dir>/jsonl/<jsonl 文件名>/<entry_id>/session_YYYYMMDD_HHMMSS/
  ├── type_plan.json
  ├── session_meta.json
  └── collected.jsonl      # 若启用 TabLogCollector
```

- 复现模式：

```text
<plan 所在目录>/reproduce/session_YYYYMMDD_HHMMSS/
  ├── type_plan.json       # 复用原 plan
  ├── session_meta.json
  └── collected.jsonl      # 若启用 TabLogCollector
```

### 6.2 `collected.jsonl` 记录格式（TabLogCollector）

每条记录示意：

```json
{
  "action_index": 10,
  "file": "books/services.py",
  "cursor": {"line": 0, "col": 0},
  "content": "<当前文件完整内容>",
  "model_output": "<解析后的模型输出>",
  "timestamp": "2026-03-06T11:59:43Z",
  "format": "tab_log/v1",
  "extra": {}
}
```

---

## 7. 当前进度与后续规划（简版）

### 7.1 当前已实现（关键能力）

- 数据模型：`TypePlan` / `Action` / `ChangeSet` / `WorkContext` 等。
- Session 编排：`run_session()` 四阶段流水线。
- 执行器：`Executor` 支持 Type/Delete/Observe + dry-run。
- Provider：
  - `PlanFileProvider`：从 JSON plan 加载。
  - `JsonlProvider` + `DiffHunkStrategy`：从 JSONL 样本生成 TypePlan。
- 采集：
  - `TabLogCollector`：基于编辑器 `capture_tab_log` 的 Tab/Output 日志采集。
- 编辑器适配：
  - `CursorAdapter`：Cursor IDE 适配（基于快捷键和 Output 日志）。
- 平台适配：
  - `DarwinPlatformHandler`：macOS 下基于 AppleScript 的键盘/窗口控制。

### 7.2 后续扩展方向

- 丰富数据源与策略：
  - 完成 `GitRepoProvider`，支持从真实仓库 + commit 直接生成 TypePlan。
  - 更多 `PlanStrategy`：更细粒度、不同节奏的 Type/Observe 策略。
- 扩展 IDE 与平台：
  - VSCode / 其他 IDE 的 EditorAdapter。
  - Linux / Windows 的 PlatformHandler。
- 观测与可视化：
  - 对 `collected.jsonl` 的分析工具与简单可视化（如一个小 viewer）。

---

## 8. 面向分享时可以怎么讲

你可以用一句话概括这个项目：

> **它是一个「把代码变更统一转成键盘操作计划，在真实 IDE 里重放并采集模型输出日志」的基础设施。**

然后按下面这个顺序讲解：

1. **动机**：从 CursorSynthesis 演化而来，抛弃视觉链路（YOLO+OCR），改用 IDE 自带的 Tab/Output 日志。
2. **统一中间格式**：无论 Git/JSONL/已有计划，最终都变成 `TypePlan(JSON)`。
3. **执行与采集**：Executor 驱动 EditorAdapter 真正「敲键盘」，Collector 在 Observe 点采集日志。
4. **扩展性**：TaskProvider / PlanStrategy / Collector / EditorAdapter / Platform 五大扩展点，方便未来接更多数据源和 IDE。
5. **当前状态**：JSONL + Cursor + macOS 链路已经打通，可做真实数据的自动化实验；Git 数据源与多平台支持是后续重点。

