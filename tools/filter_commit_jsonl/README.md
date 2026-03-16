# filter_commit_jsonl

从原始 commit 类 JSONL 中筛选记录，并转换为 DataSynthesis 使用的标准 JSONL 数据源格式（每条带 `id`、`diff` 等字段）。

## 功能

- **筛选**：按可选条件过滤记录（同文件、内容非空、hunk 数量/行数等）
- **转换**：为每条保留的记录分配字符串 `id`（从 `"0"` 起、前导零对齐），并生成人类可读的 `diff` 字段（unified diff）
- **输出**：写入标准 JSONL，可直接作为 `data_synthesis --source jsonl --source-path <输出文件>` 的输入

## 输入格式约定

每行一个 JSON 对象，建议包含：

- `old_file` / `new_file`：变更前后文件路径
- `old_contents` / `new_contents`：变更前后文件完整内容（字符串，可为空）
- 其他字段（如 `commit`、`subject`、`message` 等）会原样保留到输出

解析失败或非对象行会被跳过。

## 用法

```bash
# 在项目根目录或任意位置执行（请将路径改为你的实际路径）
python tools/filter_commit_jsonl/filter_commit_jsonl.py \
    --input /path/to/raw_commits.jsonl \
    --output /path/to/output.jsonl
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `--input` | 输入 JSONL 文件路径（必填） |
| `--output` | 输出 JSONL 文件路径（必填） |
| `--same-file-only` | 仅保留 `old_file == new_file` 的记录 |
| `--require-old-nonempty` | 要求 `old_contents` 去空白后非空 |
| `--require-new-nonempty` | 要求 `new_contents` 去空白后非空 |
| `--min-hunks N` | 要求行级 diff 的 hunk 数量 ≥ N |
| `--max-hunk-lines N` | 要求每个 hunk 行数 ≤ N（行数 = max(删除行数, 新增行数)） |
| `--encoding` | 输入/输出编码（默认 `utf-8`） |

所有筛选条件均为可选；不传则不做该条件过滤。

### 示例

仅保留「同文件、前后内容都非空、至少 1 个 hunk、每个 hunk 不超过 5 行」的记录：

```bash
python tools/filter_commit_jsonl/filter_commit_jsonl.py \
    --input /path/to/raw.jsonl \
    --output output/filtered.jsonl \
    --same-file-only \
    --require-old-nonempty \
    --require-new-nonempty \
    --min-hunks 1 \
    --max-hunk-lines 5
```

## 输出格式

每行一个 JSON 对象，字段顺序约定为：

1. `id`：字符串，从 `"0"` 起递增，宽度与记录数对齐（如 3 条则为 `"0"`,`"1"`,`"2"`）
2. 输入中的其他字段（除 `id`、`diff` 外）原样保留
3. `diff`：从 `old_contents` 到 `new_contents` 的 unified diff 字符串（人类可读）

该格式符合 DataSynthesis `JsonlProvider` 对 `id`、`old_file`/`new_file`、`old_contents`/`new_contents` 等的约定。

## 依赖

仅使用 Python 标准库（`argparse`、`json`、`dataclasses`、`pathlib`、`difflib`、`tempfile`），无需额外安装。
