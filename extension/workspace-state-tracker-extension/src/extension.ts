import * as vscode from "vscode";

import { StateWriter } from "./stateWriter";
import { WorkspaceTracker } from "./workspaceTracker";
import { ExtensionConfig, getExtensionConfig } from "./types";

let tracker: WorkspaceTracker | undefined;
let writer: StateWriter | undefined;

let debounceTimer: NodeJS.Timeout | undefined;
let heartbeatTimer: NodeJS.Timeout | undefined;
let cfg: ExtensionConfig | undefined;

function scheduleWrite(event: "init" | "workspaceChanged" | "heartbeat"): void {
  if (!tracker || !writer || !cfg) return;

  const doWrite = () => {
    try {
      writer!.write(cfg!.filePath, tracker!.snapshot(event));
    } catch (e) {
      // 避免异常导致插件崩溃；必要时可在 Output 中提示，但这里保持静默以免干扰用户
    }
  };

  if (event === "workspaceChanged" && cfg.debounceMs > 0) {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      debounceTimer = undefined;
      doWrite();
    }, cfg.debounceMs);
    return;
  }

  doWrite();
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  cfg = getExtensionConfig();
  tracker = new WorkspaceTracker();
  writer = new StateWriter();

  // 1) 启动即写入一次当前状态，避免外部读到旧文件
  scheduleWrite("init");

  // 2) workspace 变更事件：去抖合并后写入
  const workspaceDisposable = tracker.onDidChangeWorkspaceFolders(() => {
    scheduleWrite("workspaceChanged");
  });
  context.subscriptions.push(workspaceDisposable);

  // 3) 心跳：用于外部判断插件仍在运行（可配置关闭）
  if (cfg.heartbeatMs > 0) {
    heartbeatTimer = setInterval(() => {
      scheduleWrite("heartbeat");
    }, cfg.heartbeatMs);
  }

  context.subscriptions.push({
    dispose: () => {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
        debounceTimer = undefined;
      }
      if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = undefined;
      }
    },
  });
}

export async function deactivate(): Promise<void> {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = undefined;
  }
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = undefined;
  }
  tracker = undefined;
  writer = undefined;
  cfg = undefined;
}

