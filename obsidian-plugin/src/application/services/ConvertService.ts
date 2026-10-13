import { isInScope, type PluginSettings } from "@/application/config/PluginSettings";
import type { PythonRunner } from "@/application/ports/PythonRunner";
import type { VaultGateway } from "@/application/ports/VaultGateway";

export interface ConvertSummary {
  total: number;
  succeeded: number;
  failed: number;
  errors: string[];
}

export class RunScopeNotConfiguredError extends Error {
  constructor() {
    super("运行范围为空：include 模式下没有配置任何文件夹。");
    this.name = "RunScopeNotConfiguredError";
  }
}

export class CurrentFileOutOfScopeError extends Error {
  constructor() {
    super("当前文件不在运行范围内。");
    this.name = "CurrentFileOutOfScopeError";
  }
}

export function listInScope(paths: string[], settings: PluginSettings): string[] {
  return paths.filter((path) => isInScope(path, settings));
}

export class ConvertService {
  constructor(
    private readonly vault: VaultGateway,
    private readonly python: PythonRunner,
  ) {}

  async convertCurrentFile(relativePath: string, settings: PluginSettings): Promise<ConvertSummary> {
    if (!isInScope(relativePath, settings)) {
      throw new CurrentFileOutOfScopeError();
    }

    const absolutePath = this.vault.toAbsolute(relativePath);
    if (!absolutePath) {
      return { total: 1, succeeded: 0, failed: 1, errors: [`无法解析路径: ${relativePath}`] };
    }

    return this.runBatch([absolutePath]);
  }

  async convertVault(settings: PluginSettings): Promise<ConvertSummary> {
    const paths = listInScope(this.vault.listMarkdownPaths(), settings);
    if (paths.length === 0) {
      throw new RunScopeNotConfiguredError();
    }

    const absolutePaths = paths
      .map((path) => this.vault.toAbsolute(path))
      .filter((path): path is string => path !== null);

    return this.runBatch(absolutePaths);
  }

  private async runBatch(absolutePaths: string[]): Promise<ConvertSummary> {
    const errors: string[] = [];
    let succeeded = 0;

    for (const absolutePath of absolutePaths) {
      const result = await this.python.convertFile(absolutePath);
      if (result.ok) {
        succeeded += 1;
        continue;
      }
      errors.push(`${absolutePath}: ${result.stderr.trim() || `退出码 ${result.code}`}`);
    }

    return {
      total: absolutePaths.length,
      succeeded,
      failed: absolutePaths.length - succeeded,
      errors,
    };
  }
}
