# Cursor Position Tracker

轻量级光标位置跟踪插件，用于 VS Code / Cursor 等基于 VS Code 内核的编辑器。

插件会实时监听当前编辑器中的光标位置，并将**最新位置**写入一个本地 JSON 文件，供外部程序（例如 DataSynthesis）按需读取。

## 源码说明

本目录在仓库中**只保留 TypeScript 源码**（`src/`、`package.json`、`tsconfig.json` 等），**不包含** `node_modules/`、`out/` 以及打包生成的 `.vsix`。本地执行 `npm install` 与 `npm run compile` 后会生成 `out/`（`package.json` 的 `main` 指向 `./out/extension.js`）。上述产物已列入仓库根目录 `.gitignore`，请勿提交。

---

## 功能特性

- **实时光标跟踪**：记录当前活动编辑器的
  - 文件绝对路径 `filePath`
  - 行号 `line`（1-based）
  - 列号 `column`（1-based）
  - 时间戳 `timestamp`（ISO 8601）

- **轻量实现**：
  - 无 HTTP 服务器、无端口监听
  - 只在内存维护最新位置，按固定节流间隔写入本地文件
  - 退出编辑器时仅清理监听器和定时器，不做阻塞操作

- **为外部工具设计**：
  - 默认写入 `~/.cursor-position-tracker.json`
  - 外部程序只需读取此文件即可获取最新光标位置

---

## 安装与构建

### 1. 构建 VSIX

在插件目录下执行（假设路径为 `DataSynthesis/extension/cursor-position-tracker-extension`）：

```bash
cd /Users/fe/Desktop/DataSynthesis/extension/cursor-position-tracker-extension

# 安装依赖
npm install

# 编译 TypeScript
npm run compile

# 打包 VSIX
npm run package
```

完成后会生成类似 `cursor-position-tracker-1.0.0.vsix` 的文件。

### 2. 在 Cursor / VS Code 中安装

1. 打开 Cursor / VS Code  
2. 按 `Cmd+Shift+P`（macOS）或 `Ctrl+Shift+P`（Windows/Linux）  
3. 输入 `Extensions: Install from VSIX...`  
4. 选择刚生成的 `cursor-position-tracker-*.vsix`  
5. 安装完成后按提示 Reload 编辑器  

插件在启动后会**自动激活并开始工作**，无需手动启动命令。

### 3. 可选：从源码调试

1. 用 Cursor / VS Code **打开本插件目录**（含 `package.json` 的根目录）。  
2. 先执行 `npm install` 与 `npm run compile`。  
3. 按 `F5` 或运行 **Run Extension**，在新开的 Extension Development Host 窗口中验证行为。

---

## 工作机制

1. 插件激活后：
   - 通过 `CursorTracker` 监听：
     - `onDidChangeTextEditorSelection`
     - `onDidChangeActiveTextEditor`
   - 将最新光标位置保存在内存中（`CursorPosition`）

2. `PositionWriter` 每隔一定时间（默认 `50ms`）：
   - 读取当前内存中的光标位置
   - 写入临时文件 `~/.cursor-position-tracker.json.tmp`
   - 使用原子重命名覆盖 `~/.cursor-position-tracker.json`

3. 写入失败（例如权限问题）时静默忽略，不影响编辑器使用与退出。

---

## 输出文件格式

默认路径：`~/.cursor-position-tracker.json`（可通过配置修改）

内容示例：

```json
{
  "filePath": "/Users/fe/Desktop/DataSynthesis/data_synthesis/executors/executor.py",
  "line": 146,
  "column": 20,
  "timestamp": "2026-03-10T12:34:56.789Z"
}
```

字段说明：

- `filePath`：当前活动编辑器中文件的**绝对路径**
- `line`：当前光标所在行（1-based）
- `column`：当前光标所在列（1-based）
- `timestamp`：最近一次更新光标位置的时间（ISO 8601）

---

## 配置项

可以在设置中搜索 **“Cursor Position Tracker”** 或直接编辑 `settings.json`。

支持的配置项：

```jsonc
{
  "cursorPositionTracker.filePath": "~/.cursor-position-tracker.json", // 输出文件路径
  "cursorPositionTracker.throttleMs": 50                                // 写入节流间隔（毫秒）
}
```

- **`filePath`**：
  - 可以使用 `~` 表示用户主目录
  - 插件内部会展开成绝对路径
- **`throttleMs`**：
  - 控制写入频率，默认 50ms（最大约 20 次/秒）
  - 值越大，写入越少，越省 IO；外部读取到的位置“实时性”会略降低

---

## 与 DataSynthesis 的关系

这个扩展可以作为 DataSynthesis 生态里的一个辅助工具使用，用来把编辑器中的最新光标位置持续写到本地文件，方便实验、调试或后续扩展时读取。

但需要特别说明的是：

- 当前仓库中的 `data_synthesis` 主流程**并不依赖**这个扩展
- 当前 `Executor` 也**没有**在 `ObserveAction` 时读取本插件输出的 JSON 文件
- 因此，这个扩展更适合被理解为“可选的辅助能力”，而不是当前主链路的必需组件

如果你只是想跑通当前仓库的主流程，优先关注的是 `workspace-state-tracker-extension`，而不是本插件。

---

## 注意事项

- 当前设计假设**单窗口 + 单 pipeline** 使用场景：
  - 多窗口同时打开且安装本插件时，最后写入的窗口位置会覆盖前一个窗口的位置。
- 若需要跨项目或多窗口更精细的区分，可以在后续版本中扩展为：
  - 按 workspace 写不同路径  
  - 或输出中增加 `workspaceName`、`editorName` 等字段（DataSynthesis 可据此过滤）

---

## 许可证

MIT License

