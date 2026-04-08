# Workspace State Tracker

轻量 VS Code 内核扩展（Cursor 可用），将 **workspace folder 的最新状态** 写入本地 JSON，供外部自动化（例如 DataSynthesis）轮询，用于判断：

- Close Folder 是否完成（workspace 为空）
- 用指定目录启动 Cursor 是否已成功打开 workspace（路径匹配）
- （可选）插件是否仍在运行（心跳）

## 源码说明

本目录在仓库中**只保留 TypeScript 源码**（`src/`、`package.json`、`package-lock.json`、`tsconfig.json` 等），**不包含** `node_modules/`、`out/` 以及 `.vsix`。本地执行 `npm install` 与 `npm run compile` 后会生成 `out/`（`main` 为 `./out/extension.js`）。这些产物已列入仓库根目录 `.gitignore`，请勿提交。

---

## 安装与构建

在仓库根目录下，进入本扩展目录（路径按你的克隆位置调整）：

```bash
cd extension/workspace-state-tracker-extension
```

### 1. 安装依赖并编译

```bash
npm install
npm run compile
```

### 2. 打包 VSIX（推荐分发方式）

```bash
npm run package
```

会生成类似 `workspace-state-tracker-1.0.0.vsix` 的文件（勿提交到 Git）。

### 3. 安装到 Cursor / VS Code

1. 打开 Cursor / VS Code  
2. `Cmd+Shift+P`（macOS）或 `Ctrl+Shift+P`（Windows/Linux）  
3. 选择 **Extensions: Install from VSIX...**  
4. 选中上一步生成的 `.vsix`  
5. 按提示 **Reload** 窗口  

扩展在启动后会自动激活。

### 4. 可选：从源码调试

1. 用编辑器**打开本扩展目录**（含 `package.json` 的根目录）。  
2. 执行 `npm install` 与 `npm run compile`。  
3. 按 `F5` 运行 **Run Extension**，在 Extension Development Host 中验证。

---

## 输出文件

默认写入：`~/.workspace-state.json`  

采用覆盖写，并用 `*.tmp` → `rename` 尽量保证原子性，避免外部读到半截 JSON。

## JSON 格式（schemaVersion=2）

示例：

```json
{
  "schemaVersion": 2,
  "editor": "cursor",
  "pid": 12345,
  "timestamp": 1777777777777,
  "event": "workspaceChanged",
  "state": "opened",
  "folder": "/Users/fe/Desktop/DataSynthesis"
}
```

`state` 取值：

- `closed`：当前无 workspace folder（Close Folder 完成）
- `opened`：至少 1 个 workspace folder 已打开（多 workspace 时仅取第一个作为 `folder`）

## 配置项

在设置中搜索 **Workspace State Tracker**：

- `workspaceStateTracker.filePath` — 默认 `~/.workspace-state.json`
- `workspaceStateTracker.debounceMs` — 默认 `50`，workspace 变化去抖（毫秒）
- `workspaceStateTracker.heartbeatMs` — 默认 `1000`，心跳间隔；`0` 关闭

## 使用建议（给外部轮询）

- Close Folder 完成：`state === "closed"`
- Open Folder 成功：`state === "opened"` 且 `folder` 为目标目录绝对路径
- 心跳：观察 `timestamp` 是否持续更新

## 许可证

见 `LICENSE`（MIT）。
