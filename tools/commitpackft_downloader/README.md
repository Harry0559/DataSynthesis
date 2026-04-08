# commitpackft_downloader

从 Hugging Face 的 `bigcode/commitpackft` 数据集中下载指定语言子集，并保存为本地 JSONL 文件。

## 功能

- **按语言下载**：基于 `bigcode/commitpackft` 的子集（subset），按语言维度下载，如 `python`、`java`、`javascript` 等；
- **保存为 JSONL**：将样本逐行写入本地 `.jsonl` 文件，每行一个 JSON 对象，字段与原数据集保持一致；
- **可选限量导出**：可通过参数限制导出前 N 条样本，用于快速调试；
- **可指定输出路径**：输出文件可以写到任意指定路径。

## 依赖

需要安装 Hugging Face Datasets：

```bash
pip install datasets
```

建议将 `datasets` 加入项目的 `requirements.txt`。

## 用法

在项目根目录执行（路径根据实际情况调整）：

```bash
python tools/commitpackft_downloader/download_commitpackft.py \
  --lang python
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `--lang` | 语言子集名称（如 `python`、`java`、`javascript`、`yaml` 等），对应 Hugging Face 数据卡上的 Subset 名称（见 `bigcode/commitpackft` 页面） |
| `--split` | 数据集 split，默认为 `train` |
| `--output` | 输出 JSONL 文件路径；若不指定，则默认为 `./commitpackft_<lang>.jsonl` |
| `--max-samples` | 限制最多导出的样本数量，仅用于调试；默认不限制，导出整个 subset |

### 示例

导出所有 Python 样本到当前目录：

```bash
python tools/commitpackft_downloader/download_commitpackft.py \
  --lang python
```

导出 Java 样本到指定路径，只拿前 50k 条：

```bash
python tools/commitpackft_downloader/download_commitpackft.py \
  --lang java \
  --output /data/commitpackft_java_50k.jsonl \
  --max-samples 50000
```

## 输出格式

输出的 JSONL 文件中，每行是一个样本，字段与原数据集保持一致，例如（摘自官方数据卡）：

```json
{
  "commit": "0c17311f7fd511f5dae8f8e4acc2dce1a2de3cf5",
  "old_file": "main.py",
  "new_file": "main.py",
  "old_contents": "import numpy as np\n...",
  "new_contents": "import math\nimport numpy as np\n...",
  "subject": "Change to sin() function with noise",
  "message": "Change to sin() function with noise\n",
  "lang": "Python",
  "license": "mit",
  "repos": "MorganR/basic-gaussian-process"
}
```

这些字段可以直接作为后续 DataSynthesis 输入或中间数据源使用。

