import { appendFile, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import type { ConvertLog, ConvertLogEntry } from "@/application/ports/ConvertLog";

export const LOG_FILE_NAME = "convert.log";

/** 超过这个大小就裁掉老记录，免得日志无限长大。 */
const MAX_BYTES = 2 * 1024 * 1024;
const KEEP_LINES = 500;

/**
 * 一行一条 JSON（JSONL）追加到 <plugin dir>/convert.log。
 * 排查"提示成功但没产出卡片"靠它。
 */
export class ConvertLogFile implements ConvertLog {
  constructor(private readonly directory: string | null) {}

  path(): string {
    return this.directory ? path.join(this.directory, LOG_FILE_NAME) : LOG_FILE_NAME;
  }

  available(): boolean {
    return this.directory !== null;
  }

  async append(entries: ConvertLogEntry[]): Promise<void> {
    if (!this.directory || entries.length === 0) {
      return;
    }

    const body = `${entries.map((entry) => JSON.stringify(entry)).join("\n")}\n`;

    try {
      await mkdir(this.directory, { recursive: true });
      await this.trimIfHuge();
      await appendFile(this.path(), body, "utf8");
    } catch (error) {
      console.error("写转换日志失败。", error);
    }
  }

  async read(): Promise<string> {
    if (!this.directory) {
      return "";
    }

    try {
      return await readFile(this.path(), "utf8");
    } catch {
      // 文件还不存在（一次都没转过）算正常。
      return "";
    }
  }

  async clear(): Promise<void> {
    if (!this.directory) {
      return;
    }

    try {
      await mkdir(this.directory, { recursive: true });
      await writeFile(this.path(), "", "utf8");
    } catch (error) {
      console.error("清空转换日志失败。", error);
    }
  }

  private async trimIfHuge(): Promise<void> {
    let size = 0;

    try {
      size = (await stat(this.path())).size;
    } catch {
      return;
    }

    if (size <= MAX_BYTES) {
      return;
    }

    const lines = (await readFile(this.path(), "utf8")).split("\n").filter((line) => line.length > 0);

    await writeFile(this.path(), `${lines.slice(-KEEP_LINES).join("\n")}\n`, "utf8");
  }
}
