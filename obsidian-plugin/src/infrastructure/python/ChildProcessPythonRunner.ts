import { execFile } from "node:child_process";
import path from "node:path";

import { categoryRecord, type PluginSettings } from "@/application/config/PluginSettings";
import type { PythonRunResult, PythonRunner } from "@/application/ports/PythonRunner";

const MAX_BUFFER = 10 * 1024 * 1024;

function exitCodeOf(error: unknown): number | null {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as { code?: unknown }).code;
    if (typeof code === "number") {
      return code;
    }
  }

  return error ? 1 : 0;
}

export class ChildProcessPythonRunner implements PythonRunner {
  constructor(private readonly getSettings: () => PluginSettings) {}

  convertFile(absolutePath: string): Promise<PythonRunResult> {
    const settings = this.getSettings();
    // --report json：让 Python 把"几个结构、几张卡片、警告、提示"打包成一行 JSON 回来，
    // 否则"成功但 0 张卡片"这种事在外面完全看不出来。
    const args = [
      "-m",
      "md_diagram_cards",
      absolutePath,
      "--mode",
      settings.outputMode,
      "--report",
      "json",
    ];

    // 自定义 category 每次转换都随参数传给 Python；Python 无状态，不需要"存回去"。
    const categories = categoryRecord(settings.categories);

    if (Object.keys(categories).length > 0) {
      args.push("--categories-json", JSON.stringify(categories));
    }

    return this.run(args);
  }

  probe(): Promise<PythonRunResult> {
    return this.run(["-m", "md_diagram_cards", "--help"]);
  }

  listCategories(): Promise<PythonRunResult> {
    return this.run(["-m", "md_diagram_cards", "--list-categories"]);
  }

  private run(args: string[]): Promise<PythonRunResult> {
    const settings = this.getSettings();

    return new Promise((resolve) => {
      execFile(
        settings.pythonPath,
        args,
        {
          env: this.buildEnv(settings),
          timeout: settings.timeoutSeconds * 1000,
          maxBuffer: MAX_BUFFER,
        },
        (error, stdout, stderr) => {
          resolve({
            ok: !error,
            code: exitCodeOf(error),
            stdout,
            stderr,
          });
        },
      );
    });
  }

  private buildEnv(settings: PluginSettings): NodeJS.ProcessEnv {
    const env = { ...process.env };

    if (settings.scriptPath) {
      const existing = env.PYTHONPATH;
      env.PYTHONPATH = existing
        ? `${settings.scriptPath}${path.delimiter}${existing}`
        : settings.scriptPath;
    }

    return env;
  }
}
