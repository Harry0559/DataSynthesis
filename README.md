# DataSynthesis

`DataSynthesis` 是一个两阶段数据管线：先在真实 `Cursor` 编辑器中重放代码编辑并采集模型输出，再把原始 session 数据整理成适合分析或训练使用的 JSONL 数据。

当前仓库的主线是：

```text
JSONL 样本
  -> data_synthesis
  -> output/collected/.../session_xxx
  -> post_processor
  -> standard / zeta / zeta_debug JSONL
```

## 当前支持范围

当前已经实现、并适合在 README 中对外介绍的能力如下。

### `data_synthesis`

- 输入源：`jsonl`
- 重放策略：`diff-hunk`、`similarity`
- 运行模式：单条运行、`batch-mode`
- 编辑器：`Cursor`
- 平台：`macOS`
- 采集方式：`tab-log`

### `post_processor`

- 支持从采集目录读取原始 session 数据
- 支持从已有 `.jsonl` 继续处理
- 支持整合、过滤、格式化、去重、排序
- 支持输出 `standard`、`zeta`、`zeta_debug` 等格式

### 其他目录

- `tools/`：准备或筛选上游 JSONL 数据的辅助脚本
- `extension/`：为真机运行和实验辅助提供的 Cursor / VS Code 扩展

## 这个项目在做什么

如果把项目拆成两个阶段来看：

1. `data_synthesis` 负责把一条代码变更样本转成可执行的编辑计划，在真实 `Cursor` 中执行输入、删除和观察动作，并把每次观察到的模型输出记录下来。
2. `post_processor` 负责把这些原始 session 记录整合成结构化样本，再按规则过滤、格式化、去重，输出成后续可直接使用的 JSONL 文件。

## 最小可运行快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备输入 JSONL

`data_synthesis` 当前要求输入是 JSONL 文件，每行是一条单文件变更记录，至少需要包含这些字段：

- `id`
- `old_file`
- `new_file`
- `old_contents`
- `new_contents`

更完整的字段约定见 `data_synthesis/README.md`。

### 3. 先用 dry-run 验证链路

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy diff-hunk \
  --dry-run
```

这一步不会驱动编辑器，只会验证样本读取、计划生成和执行流程是否正常。

### 4. 运行一次真实采集

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy diff-hunk \
  --editor cursor \
  --collector tab-log
```

真实采集前请确认：

- 运行环境是 `macOS`
- 已安装并可正常使用 `Cursor`
- 已安装 `extension/workspace-state-tracker-extension`
- 终端或宿主应用具备系统自动化相关权限

采集完成后，结果会写到类似下面的目录中：

```text
output/collected/jsonl/<jsonl文件名>/<entry_id>/session_YYYYMMDD_HHMMSS/
  ├── type_plan.json
  ├── session_meta.json
  └── collected.jsonl
```

### 5. 对采集结果做后处理

最小示例：

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,format:zeta"
```

一个更接近实际筛选流程的示例：

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,filter:capture_ok,format:zeta_debug,filter:edit,filter:diff,format:zeta,dedup"
```

## 仓库结构

```text
data_synthesis/   # 第 1 阶段：生成编辑计划、驱动 Cursor、采集原始日志
post_processor/   # 第 2 阶段：整合、过滤、格式化、去重
tools/            # 数据准备与转换脚本
extension/        # 真机运行和实验辅助扩展
docs/             # 架构说明与历史设计背景
```

## 建议阅读顺序

- 先看 `data_synthesis/README.md`：了解输入格式、策略、运行方式和输出目录
- 再看 `post_processor/README.md`：了解 pipeline 规则和常用 recipes
- 需要进一步理解内部结构时，再看 `docs/ARCHITECTURE_OVERVIEW.md`
- 想了解项目为什么这样设计，再看 `docs/DESIGN_CONTEXT.md`
