export type ScopeMode = "all" | "include" | "exclude";
export type OutputMode = "inplace" | "newfile";

export interface PluginSettings {
  scopeMode: ScopeMode;
  includeFolders: string[];
  excludeFolders: string[];
  outputMode: OutputMode;
  pythonPath: string;
  scriptPath: string;
  timeoutSeconds: number;
}

export const DEFAULT_SETTINGS: PluginSettings = {
  scopeMode: "all",
  includeFolders: [],
  excludeFolders: [],
  outputMode: "inplace",
  pythonPath: "python3",
  scriptPath: "",
  timeoutSeconds: 120,
};

/**
 * 把用户输入或 vault 里的路径收敛成统一的相对路径：
 * 去掉首尾空白、把 `\` 换成 `/`、去掉开头的 `./`、合并重复 `/`、去掉首尾 `/`。
 */
export function normalizeVaultPath(path: string): string {
  return path
    .trim()
    .replace(/\\/g, "/")
    .replace(/^(\.\/)+/, "")
    .replace(/\/{2,}/g, "/")
    .replace(/^\/+|\/+$/g, "");
}

function normalizeFolderList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const seen = new Set<string>();
  const result: string[] = [];

  for (const item of value) {
    if (typeof item !== "string") {
      continue;
    }

    const folder = normalizeVaultPath(item);
    const key = folder.toLowerCase();

    if (!folder || seen.has(key)) {
      continue;
    }

    seen.add(key);
    result.push(folder);
  }

  return result;
}

export function normalizePluginSettings(settings: Partial<PluginSettings> | null | undefined): PluginSettings {
  const merged = { ...DEFAULT_SETTINGS, ...(settings ?? {}) };

  return {
    scopeMode: merged.scopeMode === "all" || merged.scopeMode === "exclude" ? merged.scopeMode : "include",
    includeFolders: normalizeFolderList(merged.includeFolders),
    excludeFolders: normalizeFolderList(merged.excludeFolders),
    outputMode: merged.outputMode === "newfile" ? "newfile" : "inplace",
    pythonPath: typeof merged.pythonPath === "string" && merged.pythonPath.trim() ? merged.pythonPath.trim() : DEFAULT_SETTINGS.pythonPath,
    scriptPath: typeof merged.scriptPath === "string" ? merged.scriptPath.trim() : "",
    timeoutSeconds:
      Number.isFinite(merged.timeoutSeconds) && merged.timeoutSeconds > 0
        ? Math.floor(merged.timeoutSeconds)
        : DEFAULT_SETTINGS.timeoutSeconds,
  };
}

function normalizeForCompare(path: string): string {
  // vault 跑在大小写不敏感的文件系统上时，用户手打的 `Notes` 应该匹配磁盘上的 `notes`。
  return normalizeVaultPath(path).toLowerCase();
}

function matchesFolder(path: string, folders: string[]): boolean {
  return folders.some((folder) => {
    const candidate = normalizeForCompare(folder);

    return candidate.length > 0 && (path === candidate || path.startsWith(`${candidate}/`));
  });
}

/** 路径是否落在运行范围内（不含扩展名判断，由调用方保证是 md）。 */
export function isInScope(path: string, settings: PluginSettings): boolean {
  const normalized = normalizeForCompare(path);

  if (!normalized) {
    return false;
  }

  if (settings.scopeMode === "all") {
    return true;
  }

  if (settings.scopeMode === "include") {
    // 没挑任何文件夹时不当成"什么都不转换"，否则刚装好插件会莫名其妙提示"不在范围内"。
    return settings.includeFolders.length === 0 || matchesFolder(normalized, settings.includeFolders);
  }

  return !matchesFolder(normalized, settings.excludeFolders);
}
