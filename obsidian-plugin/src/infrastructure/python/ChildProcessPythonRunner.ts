import { execFile } from "node:child_process";
import path from "node:path";

import type { PluginSettings } from "@/application/config/PluginSettings";
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
    return this.run(["-m", "md_diagram_cards", absolutePath, "--mode", settings.outputMode]);
  }

  probe(): Promise<PythonRunResult> {
    return this.run(["-m", "md_diagram_cards", "--help"]);
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
