import { Modal, type App } from "obsidian";

import type { ConvertLogEntry } from "@/application/ports/ConvertLog";

const MAX_ENTRIES = 200;

function clockOf(iso: string): string {
  const date = new Date(iso);

  if (Number.isNaN(date.getTime())) {
    return iso;
  }

  return date.toLocaleString();
}

function describe(entry: ConvertLogEntry): string {
  if (!entry.ok) {
    return `❌ 失败（退出码 ${entry.code}）${entry.stderr ? ` — ${entry.stderr}` : ""}`;
  }

  if (!entry.report) {
    return "✅ 成功（这一版 Python 还没吐报告，看不出卡片数）";
  }

  return `✅ ${entry.report.diagram_count} 个结构 → ${entry.report.card_count} 张卡片`;
}

/** 把一行 JSONL 读成人话；解析不动就原样显示。 */
function parseEntry(line: string): ConvertLogEntry | null {
  try {
    return JSON.parse(line) as ConvertLogEntry;
  } catch {
    return null;
  }
}

export class LogModal extends Modal {
  constructor(
    app: App,
    private readonly logPath: string,
    private readonly raw: string,
  ) {
    super(app);
  }

  onOpen(): void {
    const { contentEl } = this;

    contentEl.createEl("h2", { text: "转换日志" });
    contentEl.createEl("div", { cls: "md-diagram-cards-log-path", text: this.logPath });

    const lines = this.raw.split("\n").filter((line) => line.trim().length > 0);

    if (lines.length === 0) {
      contentEl.createEl("p", {
        text: "日志还是空的。跑一次「转换当前文件为卡片」或「转换整个库为卡片」就会有记录。",
      });
      return;
    }

    const recent = lines.slice(-MAX_ENTRIES);

    contentEl.createEl("p", {
      cls: "md-diagram-cards-log-note",
      text: `共 ${lines.length} 条记录，显示最近 ${recent.length} 条。`,
    });

    const listEl = contentEl.createDiv({ cls: "md-diagram-cards-log-list" });

    for (const line of recent.reverse()) {
      const entry = parseEntry(line);
      const rowEl = listEl.createDiv({ cls: "md-diagram-cards-log-row" });

      if (!entry) {
        rowEl.createDiv({ cls: "md-diagram-cards-log-line", text: line });
        continue;
      }

      const headEl = rowEl.createDiv({ cls: "md-diagram-cards-log-line" });
      headEl.createSpan({ cls: "md-diagram-cards-log-time", text: clockOf(entry.at) });
      headEl.createSpan({ cls: "md-diagram-cards-log-file", text: entry.file });
      headEl.createSpan({ cls: "md-diagram-cards-log-result", text: describe(entry) });

      for (const hint of entry.report?.hints ?? []) {
        rowEl.createDiv({ cls: "md-diagram-cards-log-hint", text: `提示：${hint}` });
      }

      for (const warning of entry.report?.warnings ?? []) {
        rowEl.createDiv({
          cls: "md-diagram-cards-log-hint",
          text: `警告：${warning.message}${warning.line ? `（第 ${warning.line} 行）` : ""}`,
        });
      }
    }
  }

  onClose(): void {
    this.contentEl.empty();
  }
}
