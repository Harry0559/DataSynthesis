import * as vscode from "vscode";
import { CursorPosition } from "./types";

/**
 * 光标位置跟踪器：监听编辑器事件并维护当前光标位置（仅保存在内存中）。
 */
export class CursorTracker implements vscode.Disposable {
  private currentPosition: CursorPosition | null = null;
  private disposables: vscode.Disposable[] = [];
  private lastUpdateTime = 0;
  // 内存层面的最小更新时间间隔（毫秒）
  private readonly MIN_UPDATE_INTERVAL = 50;

  constructor() {
    this.initialize();
  }

  private initialize(): void {
    const selectionDisposable = vscode.window.onDidChangeTextEditorSelection(
      this.onSelectionChanged,
      this
    );
    this.disposables.push(selectionDisposable);

    const activeEditorDisposable = vscode.window.onDidChangeActiveTextEditor(
      this.onActiveEditorChanged,
      this
    );
    this.disposables.push(activeEditorDisposable);

    // 初始时若已有活动编辑器，立即记录一次
    if (vscode.window.activeTextEditor) {
      this.updatePosition(vscode.window.activeTextEditor);
    }
  }

  private onSelectionChanged(
    event: vscode.TextEditorSelectionChangeEvent
  ): void {
    const now = Date.now();
    if (now - this.lastUpdateTime < this.MIN_UPDATE_INTERVAL) {
      return;
    }
    this.updatePosition(event.textEditor);
  }

  private onActiveEditorChanged(
    editor: vscode.TextEditor | undefined
  ): void {
    if (editor) {
      this.updatePosition(editor);
    } else {
      this.currentPosition = null;
    }
  }

  private updatePosition(editor: vscode.TextEditor): void {
    try {
      const document = editor.document;
      const selection = editor.selection;
      const position = selection.active;

      this.currentPosition = {
        filePath: document.uri.fsPath,
        line: position.line + 1,
        column: position.character + 1,
        timestamp: new Date().toISOString(),
      };

      this.lastUpdateTime = Date.now();
    } catch {
      // 静默失败，保持上一次有效位置
    }
  }

  getPosition(): CursorPosition | null {
    return this.currentPosition;
  }

  dispose(): void {
    for (const d of this.disposables) {
      d.dispose();
    }
    this.disposables = [];
    this.currentPosition = null;
  }
}

