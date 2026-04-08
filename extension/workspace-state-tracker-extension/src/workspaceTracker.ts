import * as vscode from "vscode";

import {
  WorkspaceStateEvent,
  WorkspaceStateSnapshot,
  getCurrentFolder,
  getWorkspaceStateKind,
} from "./types";

export class WorkspaceTracker {
  public snapshot(event: WorkspaceStateEvent): WorkspaceStateSnapshot {
    const folder = getCurrentFolder();
    return {
      schemaVersion: 2,
      editor: "cursor",
      pid: process.pid,
      timestamp: Date.now(),
      event,
      state: getWorkspaceStateKind(folder),
      folder,
    };
  }

  public onDidChangeWorkspaceFolders(
    handler: () => void
  ): vscode.Disposable {
    return vscode.workspace.onDidChangeWorkspaceFolders(() => handler());
  }
}

