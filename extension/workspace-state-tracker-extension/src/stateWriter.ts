import * as fs from "fs";
import * as path from "path";

import { WorkspaceStateSnapshot } from "./types";

function ensureParentDir(filePath: string): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

function writeFileAtomically(targetPath: string, content: string): void {
  ensureParentDir(targetPath);
  const tmpPath = `${targetPath}.tmp`;
  fs.writeFileSync(tmpPath, content, { encoding: "utf-8" });
  fs.renameSync(tmpPath, targetPath);
}

export class StateWriter {
  private lastWrittenJson: string | undefined;

  public write(targetPath: string, snapshot: WorkspaceStateSnapshot): void {
    const json = JSON.stringify(snapshot, null, 2) + "\n";
    // 防抖之外的额外保护：状态完全相同则不重复写（降低 IO 与磁盘抖动）
    if (json === this.lastWrittenJson) return;
    this.lastWrittenJson = json;
    writeFileAtomically(targetPath, json);
  }
}

