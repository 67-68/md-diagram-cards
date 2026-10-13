/** Python 那边 `--report json` 吐出来的结构化诊断（见 src/md_diagram_cards/report.py）。 */
export interface DiagramSummary {
  kind: string;
  kind_label: string;
  title: string;
  line: number;
  cards: number;
}

export interface ConversionWarning {
  message: string;
  line: number;
}

export interface ConversionReport {
  diagram_count: number;
  card_count: number;
  diagrams: DiagramSummary[];
  warnings: ConversionWarning[];
  hints: string[];
  input?: string;
  mode?: string;
  target?: string | null;
  written?: boolean;
}

function isReport(value: unknown): value is Partial<ConversionReport> {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<ConversionReport>;

  return typeof candidate.card_count === "number" && typeof candidate.diagram_count === "number";
}

/**
 * 从 stdout 里捞出那份报告。
 *
 * 从后往前找第一个像样的 JSON 行：万一将来 Python 侧往 stdout 多说了什么，
 * 也不至于把整次转换判成失败。
 */
function candidates(stdout: string): string[] {
  const lines = stdout
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("{"));

  // 先按"一行一份 JSON"找（Python 侧就是这么吐的），再退一步试整个 stdout。
  return [...lines.reverse(), stdout.trim()];
}

export function parseConversionReport(stdout: string): ConversionReport | null {
  for (const candidate of candidates(stdout)) {
    let parsed: unknown;

    try {
      parsed = JSON.parse(candidate);
    } catch {
      continue;
    }

    if (!isReport(parsed)) {
      continue;
    }

    return {
      diagram_count: parsed.diagram_count ?? 0,
      card_count: parsed.card_count ?? 0,
      diagrams: parsed.diagrams ?? [],
      warnings: parsed.warnings ?? [],
      hints: parsed.hints ?? [],
      input: parsed.input,
      mode: parsed.mode,
      target: parsed.target ?? null,
      written: parsed.written,
    };
  }

  return null;
}
