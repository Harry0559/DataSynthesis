import * as fs from "fs";
import * as path from "path";
import { CursorPosition, expandUserPath } from "./types";

/**
 * 周期性将最新光标位置写入 JSON 文件（原子覆盖）。
 */
export class PositionWriter {
  private readonly filePath: string;
  private readonly throttleMs: number;
  private readonly getPosition: () => CursorPosition | null;
  private timer: NodeJS.Timeout | null = null;

  constructor(
    filePath: string,
    throttleMs: number,
    getPosition: () => CursorPosition | null
  ) {
    this.filePath = expandUserPath(filePath);
    this.throttleMs = Math.max(10, throttleMs);
    this.getPosition = getPosition;
  }

  start(): void {
    // 立即尝试写一次
    this.writeOnce();
    // 周期性写入
    this.timer = setInterval(() => {
      this.writeOnce();
    }, this.throttleMs);
  }

  private writeOnce(): void {
    const pos = this.getPosition();
    if (!pos) {
      return;
    }

    const dir = path.dirname(this.filePath);
    const tmpPath = this.filePath + ".tmp";
    const payload = JSON.stringify(
      {
        filePath: pos.filePath,
        line: pos.line,
        column: pos.column,
        timestamp: pos.timestamp,
      },
      null,
      2
    );

    try {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(tmpPath, payload, { encoding: "utf8" });
      fs.renameSync(tmpPath, this.filePath);
    } catch {
      // 静默失败，避免影响 IDE 退出/性能
    }
  }

  dispose(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}

