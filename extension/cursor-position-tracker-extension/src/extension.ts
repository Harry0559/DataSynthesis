import * as vscode from "vscode";
import { CursorTracker } from "./cursorTracker";
import { PositionWriter } from "./positionWriter";
import { getExtensionConfig } from "./types";

let cursorTracker: CursorTracker | undefined;
let positionWriter: PositionWriter | undefined;

export async function activate(
  context: vscode.ExtensionContext
): Promise<void> {
  const cfg = getExtensionConfig();

  cursorTracker = new CursorTracker();
  positionWriter = new PositionWriter(
    cfg.filePath,
    cfg.throttleMs,
    () => cursorTracker!.getPosition()
  );
  positionWriter.start();

  // 可选：提供一个命令用于快速查看当前光标位置（调试用）
  const showStatusCommand = vscode.commands.registerCommand(
    "cursorPositionTracker.showStatus",
    () => {
      const pos = cursorTracker?.getPosition();
      if (!pos) {
        vscode.window.showInformationMessage(
          "Cursor Position Tracker: 当前无活动编辑器或光标位置。"
        );
        return;
      }
      vscode.window.showInformationMessage(
        `Cursor Position Tracker: ${pos.filePath} @ (${pos.line}, ${pos.column})`
      );
    }
  );

  context.subscriptions.push({
    dispose: () => {
      if (positionWriter) {
        positionWriter.dispose();
      }
      if (cursorTracker) {
        cursorTracker.dispose();
      }
    },
  });
  context.subscriptions.push(showStatusCommand);
}

export async function deactivate(): Promise<void> {
  // 真正的清理通过 context.subscriptions 完成，这里仅作防御
  if (positionWriter) {
    positionWriter.dispose();
    positionWriter = undefined;
  }
  if (cursorTracker) {
    cursorTracker.dispose();
    cursorTracker = undefined;
  }
}

