import * as vscode from "vscode";

export interface CursorPosition {
  /** 文件绝对路径 */
  filePath: string;
  /** 行号 (1-based) */
  line: number;
  /** 列号 (1-based) */
  column: number;
  /** 时间戳 (ISO 8601) */
  timestamp: string;
}

export interface ExtensionConfig {
  /** 光标位置 JSON 文件路径（可包含 ~） */
  filePath: string;
  /** 写入节流间隔（毫秒） */
  throttleMs: number;
}

export function expandUserPath(p: string): string {
  if (p.startsWith("~")) {
    const home = process.env.HOME || process.env.USERPROFILE || "";
    return home ? p.replace("~", home) : p;
  }
  return p;
}

export function getExtensionConfig(): ExtensionConfig {
  const config = vscode.workspace.getConfiguration("cursorPositionTracker");
  const filePath = config.get<string>(
    "filePath",
    "~/.cursor-position-tracker.json"
  )!;
  const throttleMs = config.get<number>("throttleMs", 50)!;
  return {
    filePath,
    throttleMs,
  };
}

