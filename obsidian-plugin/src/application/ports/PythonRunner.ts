export interface PythonRunResult {
  ok: boolean;
  code: number | null;
  stdout: string;
  stderr: string;
}

export interface PythonRunner {
  /** 对单个 md 文件跑一次转换。Python 侧自己负责写盘。 */
  convertFile(absolutePath: string): Promise<PythonRunResult>;
  /** 解释器与脚本能否跑起来。 */
  probe(): Promise<PythonRunResult>;
}
