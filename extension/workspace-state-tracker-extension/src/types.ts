import * as vscode from "vscode";

export type WorkspaceStateEvent = "init" | "workspaceChanged" | "heartbeat";

export type WorkspaceStateKind = "closed" | "opened";

export interface WorkspaceStateSnapshot {
  schemaVersion: 2;
  editor: "cursor";
  pid: number;
  timestamp: number;
  event: WorkspaceStateEvent;
  state: WorkspaceStateKind;
  folder: string | null;
}

export interface ExtensionConfig {
  filePath: string;
  debounceMs: number;
  heartbeatMs: number;
}

function expandTilde(path: string): string {
  if (!path.startsWith("~")) return path;
  const home = process.env.HOME || process.env.USERPROFILE || "";
  if (!home) return path;
  if (path === "~") return home;
  if (path.startsWith("~/")) return `${home}${path.slice(1)}`;
  return path;
}

export function getExtensionConfig(): ExtensionConfig {
  const cfg = vscode.workspace.getConfiguration("workspaceStateTracker");
  const filePathRaw = cfg.get<string>("filePath", "~/.workspace-state.json");
  const debounceMsRaw = cfg.get<number>("debounceMs", 50);
  const heartbeatMsRaw = cfg.get<number>("heartbeatMs", 1000);

  const filePath = expandTilde(filePathRaw);
  const debounceMs = Number.isFinite(debounceMsRaw) ? Math.max(0, debounceMsRaw) : 50;
  const heartbeatMs = Number.isFinite(heartbeatMsRaw) ? Math.max(0, heartbeatMsRaw) : 1000;

  return { filePath, debounceMs, heartbeatMs };
}

export function getCurrentFolder(): string | null {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) return null;
  return folders[0].uri.fsPath;
}

export function getWorkspaceStateKind(folder: string | null): WorkspaceStateKind {
  return folder ? "opened" : "closed";
}

