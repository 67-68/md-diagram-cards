import { Notice } from "obsidian";

import type { ConvertSummary } from "@/application/services/ConvertService";

const ERROR_TIMEOUT = 12000;
const HINT_TIMEOUT = 10000;

/** 卡片数的说法：0 张卡是重点，单独给提示。 */
export class NoticeService {
  info(message: string): void {
    new Notice(message);
  }

  error(message: string): void {
    new Notice(`❌ ${message}`, ERROR_TIMEOUT);
  }

  showConvertSummary(scopeLabel: string, summary: ConvertSummary): void {
    if (summary.failed > 0) {
      const detail = summary.errors.slice(0, 3).join("\n");
      const more = summary.errors.length > 3 ? `\n…还有 ${summary.errors.length - 3} 条` : "";
      this.error(`${scopeLabel}：失败 ${summary.failed} / ${summary.total}\n${detail}${more}`);
      return;
    }

    const head = `${scopeLabel}：${summary.cards} 张卡片（${summary.diagrams} 个结构 / ${summary.succeeded} 个文件）`;

    if (summary.cards === 0) {
      const hints = summary.hints.length > 0 ? `\n${summary.hints.join("\n")}` : "";
      new Notice(`${head}${hints}\n日志：${summary.logPath}`, HINT_TIMEOUT);
      return;
    }

    const warning = summary.warningCount > 0 ? `\n⚠ ${summary.warningCount} 条警告，见日志` : "";
    this.info(`${head}${warning}`);
  }
}
