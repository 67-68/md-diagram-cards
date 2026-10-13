import { AbstractInputSuggest, prepareSimpleSearch, renderResults, type App, type SearchResult } from "obsidian";

interface Match {
  folder: string;
  result: SearchResult;
}

/**
 * 输入框 + 动态筛选下拉：边打字边按 fuzzy/simple search 过滤候选文件夹。
 *
 * 候选里找不到的路径也允许选中（会原样落到设置里），这样"文件夹还没建"
 * 或者磁盘上有、但 Obsidian 还没索引到的目录也能填进去。
 */
export class FolderSuggest extends AbstractInputSuggest<string> {
  private folders: string[] = [];

  constructor(
    app: App,
    inputEl: HTMLInputElement,
    private readonly onChoose: (folder: string) => void,
  ) {
    super(app, inputEl);
    this.limit = 50;
  }

  setFolders(folders: string[]): void {
    this.folders = [...folders].sort((left, right) => left.localeCompare(right));
  }

  protected getSuggestions(query: string): string[] {
    const trimmed = query.trim();

    if (!trimmed) {
      return this.folders;
    }

    const search = prepareSimpleSearch(trimmed);
    const matches: Match[] = [];

    for (const folder of this.folders) {
      const result = search(folder);

      if (result) {
        matches.push({ folder, result });
      }
    }

    matches.sort((left, right) => right.result.score - left.result.score);

    const suggestions = matches.map((match) => match.folder);

    if (!this.knows(trimmed)) {
      suggestions.push(trimmed);
    }

    return suggestions;
  }

  renderSuggestion(folder: string, el: HTMLElement): void {
    const query = this.getValue().trim();

    if (!this.knows(folder)) {
      el.setText(folder);
      el.createSpan({ cls: "md-diagram-cards-suggest-hint", text: "（按此路径匹配，不要求已存在）" });
      return;
    }

    const result = query ? prepareSimpleSearch(query)(folder) : null;

    if (result) {
      renderResults(el, folder, result);
      return;
    }

    el.setText(folder);
  }

  selectSuggestion(folder: string): void {
    // 先清空再关：setValue 会重新触发候选，反过来的话弹层会又冒出来。
    this.setValue("");
    this.close();
    this.onChoose(folder);
  }

  /** 设置页重画时调用：丢掉弹出层和监听，避免留下挂在已移除输入框上的句柄。 */
  dispose(): void {
    try {
      this.close();
    } catch {
      // 从没打开过时 close() 可能报错，无所谓。
    }
  }

  private knows(folder: string): boolean {
    const needle = folder.toLowerCase();

    return this.folders.some((known) => known.toLowerCase() === needle);
  }
}
