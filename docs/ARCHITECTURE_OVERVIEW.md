# DataSynthesis Architecture Overview

本文档描述当前仓库中已经落地的整体架构，重点是帮助读者理解两阶段数据管线如何串起来，以及当前实现的边界在哪里。

如果你想先快速上手，请优先阅读仓库根目录 `README.md`。本文更偏向内部结构说明，而不是快速开始指南。

## 1. 当前架构范围

当前仓库的稳定主链路是：

```text
JSONL 样本
  -> data_synthesis
  -> output/collected/.../session_xxx
  -> post_processor
  -> standard / zeta / zeta_debug JSONL
```

这条链路的当前实现范围是：

- 输入源：`jsonl`
- 编辑器：`Cursor`
- 平台：`macOS`
- 采集方式：`tab-log`
- 后处理：目录输入或已有 JSONL 输入

接口层面保留了更广的扩展空间，但这篇文档只把当前代码里已经能对外说明的部分当作“当前实现”。

## 2. 两阶段管线

### 阶段一：`data_synthesis`

第一阶段负责把一条代码变更样本转成编辑计划，并在真实编辑器中执行。

核心流程：

```text
JSONL record
  -> JsonlProvider
  -> PlanStrategy
  -> TypePlan
  -> Executor
  -> CursorAdapter + DarwinPlatformHandler
  -> TabLogCollector
  -> session output
```

这一阶段的产物是一个 session 目录，通常包含：

- `type_plan.json`
- `session_meta.json`
- `collected.jsonl`

### 阶段二：`post_processor`

第二阶段负责把原始 session 数据整理成更适合分析、筛选或训练使用的 JSONL。

核心流程：

```text
session folder or JSONL
  -> loader
  -> integrate / filter / format / dedup / sort
  -> output JSONL
```

## 3. 第一阶段的核心数据

### 3.1 `ChangeSet`

`JsonlProvider` 会先把一条 JSONL 记录转成统一的 `ChangeSet`：

- `FileChange`
  - `relative_path`
  - `before_content`
  - `after_content`
  - `is_new_file`
  - `is_deleted`
- `metadata`
  - 来源路径
  - entry id
  - 采样索引
  - 可选的 commit / lang 等补充信息

### 3.2 `TypePlan`

`TypePlan` 是 `data_synthesis` 阶段最重要的统一中间格式，主要包括：

- `file_init_states`
- `file_final_states`
- `actions`
- `observe_config`
- `metadata`

其中 `actions` 是一串有序动作，当前动作原语为：

- `TypeAction`
- `ForwardDeleteAction`
- `ObserveAction`

### 3.3 session 产物

真实运行时，一个 session 目录通常长这样：

```text
output/collected/jsonl/<jsonl_basename>/<entry_id>/session_YYYYMMDD_HHMMSS/
  ├── type_plan.json
  ├── session_meta.json
  └── collected.jsonl
```

`collected.jsonl` 中每条记录对应一次 `ObserveAction` 的采集结果，包含：

- 当前动作索引
- 文件路径
- 光标位置
- 上一轮与当前轮的文件内容
- 解析出的模型输出
- 采集是否成功

## 4. 第一阶段的主要模块

### 4.1 `providers`

`TaskProvider` 负责：

1. 从数据源提取变更
2. 调用策略生成 `TypePlan`
3. 准备工作目录
4. yield `Task(type_plan, context)`

当前主链路实际使用的是：

- `JsonlProvider`
- `JsonlBatchProvider`

它们会把 JSONL 记录写入临时工作目录，并通过 `WorkContext` 告诉后续阶段：

- 工作目录在哪里
- 各文件的绝对路径是什么
- 当前 session 应如何分层输出

### 4.2 `strategies`

`PlanStrategy` 负责把 `ChangeSet` 转成 `TypePlan`。

当前公开主链路的策略有两种：

- `DiffHunkStrategy`
  - 基于行级 diff
  - 每个 hunk 结束后插入一次 `ObserveAction`
- `SimilarityStrategy`
  - 对 replace 块做更细粒度的行匹配和行内 diff
  - 支持控制 observe、split、merge 等行为

### 4.3 `core/session.py`

`run_session()` 负责把一次完整执行串起来：

1. 通过 `TaskProvider.provide()` 获取任务
2. 准备编辑器环境
3. 创建 session 输出目录
4. 初始化采集器
5. 调用 `Executor.execute(type_plan)`
6. 结束后清理环境

### 4.4 `executors/executor.py`

`Executor` 负责遍历动作序列并真正执行。

当前行为是：

- `TypeAction`：切换文件、定位、输入字符
- `ForwardDeleteAction`：切换文件、定位、向后删除
- `ObserveAction`：保存文件、等待、调用采集器、继续执行

`Executor` 也支持 `dry-run`，用于在不驱动编辑器的情况下验证计划生成和动作序列。

### 4.5 `collectors/tab_log.py`

`TabLogCollector` 是当前主链路中的采集器实现。

它会在每个 Observe 点：

1. 读取当前文件内容
2. 调用 `editor.capture_tab_log(...)`
3. 将采集结果追加写入 `collected.jsonl`

如果采集失败，它会降级为空输出并记录错误信息，而不是让整条 pipeline 中断。

### 4.6 `editors/cursor.py`

`CursorAdapter` 是当前主链路中的编辑器适配层。

它负责：

- 重启并打开工作目录
- 打开文件
- 跳转到指定行列
- 输入与删除字符
- 保存文件
- 通过 Output 面板导出并解析 Tab 日志

这里的 `capture_tab_log()` 是 `tab-log` 采集链路的核心。

### 4.7 `platform/darwin.py`

`DarwinPlatformHandler` 是当前实际使用的平台实现。

它基于 macOS 的 `Quartz`、`AppKit` 等系统接口完成：

- 按键发送
- 组合快捷键
- 剪贴板粘贴
- 激活窗口
- 打开应用并加载目录
- 退出应用

这也是为什么当前主链路明确限定在 `macOS` 上。

## 5. 第二阶段的主要模块

### 5.1 `pipeline/loader.py`

输入可以是两类：

- session 目录：读取三件套文件并产出 `ProcessingUnit`
- 已有 JSONL：自动推断是 `standard`、`zeta` 还是 `zeta_debug`

### 5.2 `steps`

`post_processor` 把步骤分成五类：

- `integrate`
- `filter`
- `format`
- `dedup`
- `sort`

这几个类别共同决定了 pipeline 的类型链。

### 5.3 `pipeline/validator.py`

校验器会强约束 pipeline 是否合法，例如：

- 目录输入时必须先 `integrate`
- JSONL 输入时不能再 `integrate`
- `sort` 只能出现在末尾

### 5.4 `pipeline/runner.py`

执行器会把各步骤串起来，按流式处理的方式逐条处理样本。

常见的输出路径包括：

- `standard`
- `zeta_debug`
- `zeta`

如果没有指定 `--output`，默认会写到 `output/data/<format>_data_<timestamp>.jsonl`。

## 6. 当前实现边界

为了避免读者把“接口预留”误认为“当前支持”，这里把边界单独列出来。

### 当前已经实现并建议对外介绍的部分

- `jsonl` 输入源
- `diff-hunk`、`similarity` 两种策略
- `batch-mode`
- `CursorAdapter`
- `DarwinPlatformHandler`
- `TabLogCollector`
- `post_processor` 的目录输入 / JSONL 输入与标准后处理链路

### 当前不应当写成已支持的部分

- `git-repo` 数据源
- 以 `--plan` 为主的公开运行模式
- 多 IDE 支持
- 多平台支持
- 其他仍处于骨架状态的策略或 Provider

## 7. 如何理解整个项目

如果只用一句话概括当前仓库：

> 它是一个把 JSONL 中的代码变更样本重放到真实 Cursor 中采集原始日志，再把这些日志整理成结构化训练/分析数据的两阶段管线。

理解顺序建议是：

1. 先看根目录 `README.md`
2. 再看 `data_synthesis/README.md`
3. 再看 `post_processor/README.md`
4. 最后再把本文当作架构索引使用

