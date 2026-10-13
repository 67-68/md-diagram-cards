/**
 * Python `--list-categories` 吐出来的内置 category 表。
 *
 * 形态是一行 JSON：`{"ability": "{key}'s ability is?", ...}`。
 * 解析逻辑和 ConversionReport 一样：从 stdout 里从后往前找第一个像样的 JSON，
 * 容忍前面有杂音。
 */
export type CategoryTable = Record<string, string>;

export function parseCategoryTable(stdout: string): CategoryTable | null {
  const lines = stdout
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("{"));

  // 先按"一行一份 JSON"找，再退一步试整个 stdout。
  for (const candidate of [...lines.reverse(), stdout.trim()]) {
    let parsed: unknown;

    try {
      parsed = JSON.parse(candidate);
    } catch {
      continue;
    }

    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      continue;
    }

    const table: CategoryTable = {};

    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value === "string") {
        table[key] = value;
      }
    }

    if (Object.keys(table).length > 0) {
      return table;
    }
  }

  return null;
}
