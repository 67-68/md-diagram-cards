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
  scopeMode: "include",
  includeFolders: [],
  excludeFolders: [],
  outputMode: "inplace",
  pythonPath: "python3",
  scriptPath: "",
  timeoutSeconds: 120,
};

function normalizeFolderList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim().replace(/^\/+|\/+$/g, ""))
    .filter((item) => item.length > 0);
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

/** 路径是否落在运行范围内（不含扩展名判断，由调用方保证是 md）。 */
export function isInScope(path: string, settings: PluginSettings): boolean {
  const inFolders = (folders: string[]): boolean =>
    folders.some((folder) => path === folder || path.startsWith(`${folder}/`));

  if (settings.scopeMode === "all") {
    return true;
  }

  if (settings.scopeMode === "include") {
    return inFolders(settings.includeFolders);
  }

  return !inFolders(settings.excludeFolders);
}
