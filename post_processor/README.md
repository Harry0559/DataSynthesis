# post_processor

`post_processor` 是本仓库的第二阶段管线：把 `data_synthesis` 产生的原始 session 数据整合成结构化样本，再继续做过滤、格式化、去重和排序，最终输出 JSONL。

## 模块在整体管线中的位置

项目主链路如下：

```text
JSONL 样本
  -> data_synthesis
  -> output/collected/.../session_xxx
  -> post_processor
  -> standard / zeta / zeta_debug JSONL
```

如果说 `data_synthesis` 负责“采”，那么 `post_processor` 负责“整理和筛选”。

## 支持的输入类型

当前模块支持两类输入：

### 1. 采集目录输入

输入一个目录时，`post_processor` 会递归查找合法的 `session_*` 目录，并读取其中的三类文件：

- `type_plan.json`
- `session_meta.json`
- `collected.jsonl`

然后把每一条 `collected.jsonl` 记录组合成一个最小处理单元，再交给 pipeline 处理。

### 2. 已有 JSONL 输入

输入一个 `.jsonl` 文件时，模块会自动根据第一条有效记录推断输入格式，并按对应 schema 校验：

- `standard`
- `zeta`
- `zeta_debug`

这意味着你可以把第一次处理后的数据继续喂给新的 pipeline。

## Pipeline 模型

`post_processor` 把处理步骤分成 5 类：

- `integrate`：把原始 session 三件套整合成标准样本
- `filter`：按规则保留或丢弃样本
- `format`：把样本转换成目标格式
- `dedup`：去重
- `sort`：在最终输出前重排顺序

命令行中通过 `--pipeline` 指定步骤序列，例如：

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,format:zeta"
```

## Pipeline 规则

这部分是最需要新人看清楚的地方。

### 目录输入时

- 输入是原始采集目录
- 第一个步骤必须是 `integrate`

### JSONL 输入时

- 输入已经是结构化数据
- 管线中不能再出现 `integrate`

### 排序步骤

- `sort` 只能放在末尾
- 可以有多个排序器串联，但它们必须都在最后

## 当前内置步骤

### `integrate:default`

把原始 `ProcessingUnit` 整合成 `standard` 样本，主要补齐：

- 初始内容
- 上一次观察后的内容
- 当前内容
- 最终内容
- 编辑历史
- 来源元信息

### `filter:capture_ok`

基于 `extra.capture_ok` 处理采集失败样本。

- 默认行为：丢弃采集失败样本
- 可通过参数改成“只保留采集失败样本”

### `filter:edit`

保留编辑类样本，过滤掉续写类样本。

### `filter:cont`

保留续写类样本，过滤掉编辑类样本。

### `filter:diff`

检查样本中的改动方向是否与最终目标一致，用于过滤明显无效或偏离目标的样本。

### `filter:llm`

调用外部 LLM 对 `zeta_debug` 样本打分，并按分数范围过滤。

这个步骤依赖 `.env` 中的模型配置，下面会单独说明。

### `format:zeta_debug`

把 `standard` 样本转换成 `zeta_debug`，保留更多调试字段，适合做规则过滤和人工检查。

### `format:zeta`

把 `standard` 或 `zeta_debug` 转成最终 `zeta` 格式，得到更精简的训练/分析样本。

### `dedup`

当前实现是 SimHash 去重，用于去掉高相似样本。

### `sort`

当前内置的是 `shuffle`，用于随机打乱输出顺序。

## 常用 recipes

### 从采集目录直接生成 zeta

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,format:zeta"
```

### 先转成 zeta_debug 再筛选编辑样本

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,format:zeta_debug,filter:edit"
```

### 一个更完整的生产链路

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,filter:capture_ok,format:zeta_debug,filter:edit,filter:diff,format:zeta,dedup"
```

### 对已有 zeta_debug JSONL 继续处理

```bash
python -m post_processor \
  --input ./data/zeta_debug.jsonl \
  --pipeline "filter:edit,filter:diff,format:zeta,dedup"
```

### 生成随机打乱后的输出

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,format:zeta,dedup,sort:shuffle"
```

## 参数覆盖

步骤参数通过额外命令行参数传入，格式大致是：

```text
--<step-type>-<step-name>.<param> <value>
```

例如：

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,filter:capture_ok,format:zeta" \
  --filter-capture_ok.keep_capture_fail_only true
```

再例如：

```bash
python -m post_processor \
  --input ./output/collected \
  --pipeline "integrate,format:zeta,dedup" \
  --dedup-simhash.threshold 0.9
```

## `filter:llm` 的环境变量要求

如果要使用 `filter:llm`，需要先在 `.env` 中配置：

- `LLM_API_KEY`
- `LLM_API_URL`
- `LLM_MODEL`

这是当前代码中的硬要求；缺少这些配置时，`LlmFilter` 无法正常初始化。

## 输出文件说明

如果没有显式传 `--output`，默认会输出到：

```text
output/data/<format>_data_<timestamp>.jsonl
```

例如：

- `output/data/zeta_data_20260408_120000.jsonl`
- `output/data/zeta_debug_data_20260408_120000.jsonl`

如果你想指定输出路径，可以直接传：

```bash
python -m post_processor \
  --input ./output/collected \
  --output ./output/data/final_zeta.jsonl \
  --pipeline "integrate,format:zeta"
```

## 常见使用建议

- 如果你的输入是原始采集目录，优先从 `integrate,format:zeta_debug` 开始，先确认数据是否合理
- 如果你要做规则过滤，通常先得到 `zeta_debug` 再过滤更方便
- 如果你已经有结构化 JSONL，不要再把 `integrate` 放回 pipeline
- 如果你只想快速得到最终格式，可以直接用 `integrate,format:zeta`

如果你还没跑过采集阶段，请先回到仓库根目录阅读 `../data_synthesis/README.md`。
