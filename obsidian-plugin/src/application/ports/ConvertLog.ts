import type { ConversionReport } from "@/application/model/ConversionReport";

/** 一次转换（一个文件）的日志记录。 */
export interface ConvertLogEntry {
  /** ISO 时间戳。 */
  at: string;
  /** vault 相对路径。 */
  file: string;
  ok: boolean;
  code: number | null;
  mode: string;
  report: ConversionReport | null;
  stderr: string;
}

export interface ConvertLog {
  /** 日志文件的绝对路径（不可用时也给一个给人看的名字）。 */
  path(): string;
  /** 能否写盘（拿不到 vault 本地路径时为 false，比如手机端）。 */
  available(): boolean;
  append(entries: ConvertLogEntry[]): Promise<void>;
  read(): Promise<string>;
  clear(): Promise<void>;
}
