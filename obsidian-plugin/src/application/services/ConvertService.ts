import { isInScope, type PluginSettings } from "@/application/config/PluginSettings";
import { parseConversionReport } from "@/application/model/ConversionReport";
import type { ConvertLog, ConvertLogEntry } from "@/application/ports/ConvertLog";
import type { PythonRunner } from "@/application/ports/PythonRunner";
import type { VaultGateway } from "@/application/ports/VaultGateway";

/** 一次转换里某个文件的位置信息（相对路径给日志和范围判断用）。 */
interface SourceFile {
  relative: string;
  absolute: string;
}

export interface ConvertSummary {
  total: number;
  succeeded: number;
  failed: number;
  /** 产出的卡片总数。 */
  cards: number;
  /** 识别到的结构总数。 */
  diagrams: number;
  warningCount: number;
  /** 汇总后的提示（去重，最多留几条）。 */
  hints: string[];
  /** 失败文件的错误信息。 */
  errors: string[];
  /** 日志文件路径，出问题时让人知道去哪儿看。 */
  logPath: string;
}

export class RunScopeNotConfiguredError extends Error {
  constructor() {
    super("运行范围内没有 md 文件。");
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

const MAX_HINTS = 4;

export class ConvertService {
  constructor(
    private readonly vault: VaultGateway,
    private readonly python: PythonRunner,
    private readonly log: ConvertLog,
  ) {}

  async convertCurrentFile(relativePath: string, settings: PluginSettings): Promise<ConvertSummary> {
    if (!isInScope(relativePath, settings)) {
      throw new CurrentFileOutOfScopeError();
    }

    const absolutePath = this.vault.toAbsolute(relativePath);

    if (!absolutePath) {
      return this.emptySummary([`无法解析路径: ${relativePath}`], 1);
    }

    return this.runBatch([{ relative: relativePath, absolute: absolutePath }], settings);
  }

  async convertVault(settings: PluginSettings): Promise<ConvertSummary> {
    const paths = listInScope(this.vault.listMarkdownPaths(), settings);

    if (paths.length === 0) {
      throw new RunScopeNotConfiguredError();
    }

    const files: SourceFile[] = [];

    for (const relative of paths) {
      const absolute = this.vault.toAbsolute(relative);

      if (absolute) {
        files.push({ relative, absolute });
      }
    }

    return this.runBatch(files, settings);
  }

  private async runBatch(files: SourceFile[], settings: PluginSettings): Promise<ConvertSummary> {
    const entries: ConvertLogEntry[] = [];
    const errors: string[] = [];
    const hints = new Set<string>();
    let succeeded = 0;
    let cards = 0;
    let diagrams = 0;
    let warningCount = 0;

    for (const file of files) {
      const result = await this.python.convertFile(file.absolute);
      const report = parseConversionReport(result.stdout);
      const stderr = result.stderr.trim();

      entries.push({
        at: new Date().toISOString(),
        file: file.relative,
        ok: result.ok,
        code: result.code,
        mode: settings.outputMode,
        report,
        stderr,
      });

      if (!result.ok) {
        errors.push(`${file.relative}: ${stderr || `退出码 ${result.code}`}`);
        continue;
      }

      succeeded += 1;
      cards += report?.card_count ?? 0;
      diagrams += report?.diagram_count ?? 0;
      warningCount += report?.warnings.length ?? 0;

      for (const hint of report?.hints ?? []) {
        if (hints.size < MAX_HINTS) {
          hints.add(hint);
        }
      }
    }

    await this.log.append(entries);

    return {
      total: files.length,
      succeeded,
      failed: files.length - succeeded,
      cards,
      diagrams,
      warningCount,
      hints: [...hints],
      errors,
      logPath: this.log.path(),
    };
  }

  private emptySummary(errors: string[], total: number): ConvertSummary {
    return {
      total,
      succeeded: 0,
      failed: total,
      cards: 0,
      diagrams: 0,
      warningCount: 0,
      hints: [],
      errors,
      logPath: this.log.path(),
    };
  }
}
