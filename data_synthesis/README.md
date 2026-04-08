# data_synthesis

`data_synthesis` 是本仓库的第一阶段管线：从 JSONL 样本生成编辑计划，在真实 `Cursor` 中执行输入和删除动作，并在观察点采集模型输出日志。

## 当前已实现能力

当前模块已经实现的主链路如下：

- 输入源：`jsonl`
- 策略：`diff-hunk`、`similarity`
- 运行方式：单条运行、批量运行
- 编辑器：`Cursor`
- 平台：`macOS`
- 采集方式：`tab-log`

这也是当前仓库中推荐的使用方式。其他 Provider、策略或平台层骨架不属于当前公开主流程。

## 输入 JSONL 格式

当前 `JsonlProvider` 约定每行是一条单文件变更记录，至少包含以下字段：

- `id`：样本 ID，字符串
- `old_file`：变更前文件路径
- `new_file`：变更后文件路径
- `old_contents`：变更前完整内容
- `new_contents`：变更后完整内容

其他字段会作为元信息保留在 `metadata` 中，常见如：

- `commit`
- `subject`
- `message`
- `lang`
- `license`
- `repos`

一个最小示例如下：

```json
{
  "id": "003",
  "old_file": "pkg/example.py",
  "new_file": "pkg/example.py",
  "old_contents": "print('old')\n",
  "new_contents": "print('new')\n",
  "commit": "abc123",
  "lang": "Python"
}
```

## 核心流程

运行时的大致流程是：

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

其中几个最重要的概念是：

- `TypePlan`：统一中间格式，包含文件初始状态、动作序列、最终状态和观察配置
- `TypeAction` / `ForwardDeleteAction` / `ObserveAction`：执行器真正消费的动作原语
- `ObserveAction`：在这里保存文件并采集一次日志
- `collected.jsonl`：每次 Observe 的原始采集结果

## 当前可用策略

### `diff-hunk`

`diff-hunk` 会基于行级 diff 把文件变更拆成若干 hunk，并按顺序：

1. 删除旧内容
2. 插入新内容
3. 在每个 hunk 末尾插入一次 `ObserveAction`

适合想快速跑通链路、并使用较稳定粗粒度编辑计划的场景。

示例：

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy diff-hunk \
  --dry-run
```

### `similarity`

`similarity` 会在行级 diff 基础上，对 replace 块进一步做相似行匹配和行内字符级 diff，因此生成的编辑轨迹更细。

它还支持控制：

- 观察模式
- 动作拆分
- 动作合并
- 删除后是否观察

示例：

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy similarity \
  --observe-mode hunk_end \
  --split-merge-order split_then_merge \
  --editor cursor \
  --collector tab-log
```

## 单条运行与批量运行

### 单条运行

默认会从指定 JSONL 中选取一条样本运行。你可以用：

- `--sample-index` 指定样本下标
- `--random-seed` 在未指定 `--sample-index` 时可复现地随机选样本

示例：

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy diff-hunk \
  --sample-index 3 \
  --dry-run
```

### 批量运行

启用 `--batch-mode` 后，会遍历多个样本依次执行 pipeline。

- `--source-path` 可以是单个 `.jsonl` 文件，也可以是包含多个 `.jsonl` 文件的目录
- 可以限制总条数、每文件条数、总时长，并设置周期性冷却

示例：

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/jsonl_dir \
  --strategy similarity \
  --editor cursor \
  --collector tab-log \
  --batch-mode \
  --batch-max-items-total 100 \
  --batch-max-items-per-file 20 \
  --batch-cooldown-every 10 \
  --batch-cooldown-seconds 30
```

## 真实运行前提

当前主链路的运行前提比较明确：

- 平台必须是 `macOS`
- 编辑器必须是 `Cursor`
- 需要安装 `extension/workspace-state-tracker-extension`
- 运行环境需要系统自动化相关权限，否则键盘事件和窗口激活可能失败

另外，`tab-log` 采集依赖 `CursorAdapter.capture_tab_log()` 所使用的一组 Output 面板操作快捷键，因此真实运行前建议先做一次小规模验证。

## 输出目录结构

真实运行时，session 输出目录会按 `jsonl/<文件名>/<entry_id>/session_xxx` 分层。

目录结构如下：

```text
output/collected/jsonl/<jsonl_basename>/<entry_id>/session_YYYYMMDD_HHMMSS/
  ├── type_plan.json
  ├── session_meta.json
  └── collected.jsonl
```

其中：

- `type_plan.json`：本次执行对应的动作计划
- `session_meta.json`：运行元信息
- `collected.jsonl`：Observe 阶段采集到的原始日志记录

## `collected.jsonl` 字段说明

`TabLogCollector` 当前写出的记录大致包含这些字段：

- `action_index`：对应的动作下标
- `file`：相对文件路径
- `cursor`：采集时的光标行列
- `prev_content`：上一次 Observe 后的文件内容
- `content`：当前 Observe 时的文件内容
- `model_output`：从 Cursor Output 日志中解析出的模型输出
- `timestamp`：UTC 时间戳
- `format`：当前固定为 `tab_log/v1`
- `extra.capture_ok`：本次日志采集是否成功

## 常用命令

### dry-run 验证

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy diff-hunk \
  --dry-run
```

### 真机采集

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy diff-hunk \
  --editor cursor \
  --collector tab-log
```

### 指定样本

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/input.jsonl \
  --strategy diff-hunk \
  --sample-index 3 \
  --editor cursor \
  --collector tab-log
```

### 批量模式

```bash
python -m data_synthesis \
  --source jsonl \
  --source-path /path/to/jsonl_dir \
  --strategy similarity \
  --editor cursor \
  --collector tab-log \
  --batch-mode \
  --batch-max-items-total 50
```

## 当前限制

以下内容目前不应被视为当前公开主流程的一部分：

- `git-repo` 数据源未实现
- `PlanFileProvider` 虽然存在，但不是当前 CLI 主入口
- 其他策略骨架不代表当前可用策略
- 当前没有对多 IDE 或多平台做对外承诺

如果你接下来要处理采集结果，请继续阅读 `post_processor/README.md`。
