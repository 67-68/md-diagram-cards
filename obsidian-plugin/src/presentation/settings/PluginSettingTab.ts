import { PluginSettingTab, Setting } from "obsidian";

import type { OutputMode, PluginSettings, ScopeMode } from "@/application/config/PluginSettings";
import type MdDiagramCardsPlugin from "@/presentation/MdDiagramCardsPlugin";
import { FolderSuggest } from "@/presentation/settings/FolderSuggest";

const SCOPE_OPTIONS: Record<ScopeMode, string> = {
  all: "全部 md 文件",
  include: "只转换指定文件夹",
  exclude: "转换除指定文件夹以外的",
};

const OUTPUT_OPTIONS: Record<OutputMode, string> = {
  inplace: "就地插入（BEGIN/END 包裹，幂等）",
  newfile: "生成「原文件名闪卡.md」",
};

interface FolderPickerOptions {
  name: string;
  desc: string;
  placeholder: string;
  emptyHint: string;
  selected: string[];
  onChange: (folders: string[]) => Promise<void>;
}

interface GuideSample {
  label: string;
  code: string;
}

const MARKER_ROWS: string[][] = [
  ["### [d-state] 标题", "时间线 / 状态机", "bullet 列表；条目可带 [时间] 前缀；行间可夹 => 推论 =>"],
  ["### [d-tree] 标题", "树状图", "嵌套 bullet 列表；缩进表示层级"],
  ["### [d-orthogonal] 标题", "正交表", "标准 markdown 表格"],
];

const STATE_SAMPLE: GuideSample[] = [
  {
    label: "写这样",
    code: `### [d-state] Before 7 week war

- [1865 Oct] Biarritz meeting
- [1866 Apr] Italy Prussian Alliance`,
  },
  {
    label: "出这样",
    code: `#### [cloze] Before 7 week war
- [1865 Oct] Biarritz meeting
- [1866 Apr] Italy Prussian Alliance

#### Biarritz meeting at
- 1865 Oct

#### Italy Prussian Alliance at
- 1866 Apr`,
  },
];

const TABLE_SAMPLE: GuideSample[] = [
  {
    label: "写这样",
    code: `### [d-orthogonal] 战前形势

| 竞争者 | 战略目标 |
| --- | --- |
| Austria | 保住霸主地位 |
| Prussia | 统一德意志<br>夺回两公国 |`,
  },
  {
    label: "出这样",
    code: `#### in [战前形势] [Austria]'s [战略目标] is?
- 保住霸主地位

#### [cloze] in [战前形势] [Prussia]'s [战略目标] is?
- 统一德意志
- 夺回两公国`,
  },
];

const TREE_SAMPLE: GuideSample[] = [
  {
    label: "写这样",
    code: `### [d-tree] 支持普鲁士的因素

- Zollverein: 普鲁士主导的经济同盟
- 1861 军事改革`,
  },
  {
    label: "出这样",
    code: `#### [cloze] 支持普鲁士的因素
- Zollverein
- 1861 军事改革

#### [Zollverein] in [支持普鲁士的因素] means
- 普鲁士主导的经济同盟`,
  },
];

const INFORMATION_SAMPLE: GuideSample[] = [
  {
    label: "写这样",
    code: `### [d-tree] Structure of Nor Ger Conf

- King of Prus @custom(ability) @custom(position)

### [information]

- King of Prus
    - ability: declare war and make peace

### [information]

- King of Prus
    - position: president of the confederation`,
  },
  {
    label: "出这样",
    code: `#### Structure of Nor Ger Conf
- King of Prus

#### [ability] for [King of Prus]
- declare war and make peace

#### [position] for [King of Prus]
- president of the confederation`,
  },
];

const RULE_LINES: string[] = [
  "cloze：答案有 2 个及以上，标题自动加 [cloze]；只有 1 个就不加。",
  "表格：每行都必须以 | 开头和结尾；第 1 列是实体轴，本身不出卡；表头为空、第 1 列为空、单元格为空 → 跳过。",
  "表格单元格里的多值用 <br> 分隔，行首的 - 会被剥掉。",
  "Information 区：用 ### [information] 声明（层级不限）。一份文档可以写多个，会自动合并成一个全局字典 —— 同名项的不同外链取并集，同名外链后者覆盖前者。",
  "Information 写法：- 项 是父节点；- 外链: 值 是单值；- 外链: 后接缩进列表是列表值。空 bullet 会被忽略。",
  "指针：值从 Information 区里取。合法的只有 @cat、@cat: value、@custom(KEY) 三种；@[KEY] 和 @time: [KEY] 不是合法写法。",
  "内置 category 只有 condition / member_amount / place / effect 四个。写别的（如 @ability）会变成警告，要用 @custom(ability) 这种形式去引用 Information 里的自定义外链。",
  "就地输出：卡片包在 <!-- BEGIN GENERATED --> 与 <!-- END GENERATED --> 之间，重复运行结果一致（幂等），改格式不会碰你手写的内容。",
  "没有 [d-state] / [d-tree] / [d-orthogonal] 标记的标题不出卡 —— 这是「提示成功但没有卡片」最常见的原因。",
];

export class MdDiagramCardsSettingTab extends PluginSettingTab {
  private suggests: FolderSuggest[] = [];

  constructor(private readonly plugin: MdDiagramCardsPlugin) {
    super(plugin.app, plugin);
  }

  display(): void {
    this.closeSuggests();

    const { containerEl } = this;
    containerEl.empty();

    this.renderSyntaxGuide(containerEl);

    new Setting(containerEl).setName("运行范围").setHeading();

    new Setting(containerEl)
      .setName("范围模式")
      .setDesc("全库转换时扫描哪些文件")
      .addDropdown((dropdown) =>
        dropdown
          .addOptions(SCOPE_OPTIONS)
          .setValue(this.plugin.settings.scopeMode)
          .onChange(async (value) => {
            await this.plugin.updateSettings({ scopeMode: value as ScopeMode });
          }),
      );

    this.renderFolderPicker({
      name: "包含的文件夹",
      desc: "在输入框里打字即可从下拉列表筛选文件夹；留空表示不限制。",
      placeholder: "输入以筛选文件夹…",
      emptyHint: "未选择任何文件夹 —— 此时不限制范围。",
      selected: this.plugin.settings.includeFolders,
      onChange: (folders) => this.plugin.updateSettings({ includeFolders: folders }),
    });

    this.renderFolderPicker({
      name: "排除的文件夹",
      desc: "在输入框里打字即可从下拉列表筛选文件夹。",
      placeholder: "输入以筛选文件夹…",
      emptyHint: "未选择任何文件夹 —— 此时不排除任何文件。",
      selected: this.plugin.settings.excludeFolders,
      onChange: (folders) => this.plugin.updateSettings({ excludeFolders: folders }),
    });

    new Setting(containerEl).setName("输出").setHeading();

    new Setting(containerEl)
      .setName("输出模式")
      .setDesc("卡片写到哪里")
      .addDropdown((dropdown) =>
        dropdown
          .addOptions(OUTPUT_OPTIONS)
          .setValue(this.plugin.settings.outputMode)
          .onChange(async (value) => {
            await this.plugin.updateSettings({ outputMode: value as OutputMode });
          }),
      );

    new Setting(containerEl).setName("Python").setHeading();

    new Setting(containerEl)
      .setName("解释器路径")
      .setDesc("默认 python3")
      .addText((text) =>
        text
          .setPlaceholder("python3")
          .setValue(this.plugin.settings.pythonPath)
          .onChange(async (value) => {
            await this.plugin.updateSettings({ pythonPath: value });
          }),
      );

    new Setting(containerEl)
      .setName("脚本路径")
      .setDesc("md-diagram-cards 仓库的 src 目录（留空则依赖已安装的包）")
      .addText((text) =>
        text
          .setPlaceholder("/path/to/md-diagram-cards/src")
          .setValue(this.plugin.settings.scriptPath)
          .onChange(async (value) => {
            await this.plugin.updateSettings({ scriptPath: value });
          }),
      );

    new Setting(containerEl)
      .setName("超时（秒）")
      .addText((text) =>
        text
          .setValue(String(this.plugin.settings.timeoutSeconds))
          .onChange(async (value) => {
            const seconds = Number(value);

            if (!Number.isFinite(seconds) || seconds <= 0) {
              return;
            }

            await this.plugin.updateSettings({ timeoutSeconds: seconds });
          }),
      );

    new Setting(containerEl)
      .setName("测试连接")
      .setDesc("跑一次 python -m md_diagram_cards --help")
      .addButton((button) =>
        button.setButtonText("测试").onClick(() => {
          void this.plugin.testPython();
        }),
      );

    this.renderLogSection(containerEl);
  }

  // ------------------------------------------------------------ 语法速查

  private renderSyntaxGuide(containerEl: HTMLElement): void {
    const detailsEl = containerEl.createEl("details", { cls: "md-diagram-cards-guide" });
    detailsEl.createEl("summary", { text: "语法速查 —— 写什么格式、出什么卡片" });

    const bodyEl = detailsEl.createDiv({ cls: "md-diagram-cards-guide-body" });

    bodyEl.createEl("p", {
      text: "标记写在标题里（# 后面紧跟）。带标记的标题会被解析成卡片，普通标题只作组织用、不出卡。",
    });

    this.renderGuideTable(bodyEl, MARKER_ROWS);
    this.renderGuideSamples(bodyEl, "时间线 / 状态机", STATE_SAMPLE);
    this.renderGuideSamples(bodyEl, "正交表", TABLE_SAMPLE);
    this.renderGuideSamples(bodyEl, "树状图", TREE_SAMPLE);
    this.renderGuideSamples(bodyEl, "Information 区（外链取值）", INFORMATION_SAMPLE);

    bodyEl.createEl("h4", { text: "几条规则" });
    const rulesEl = bodyEl.createEl("ul", { cls: "md-diagram-cards-guide-rules" });

    for (const rule of RULE_LINES) {
      rulesEl.createEl("li", { text: rule });
    }
  }

  private renderGuideTable(parentEl: HTMLElement, rows: string[][]): void {
    const tableEl = parentEl.createEl("table", { cls: "md-diagram-cards-guide-table" });
    const headRowEl = tableEl.createEl("thead").createEl("tr");

    for (const header of ["标记", "形态", "正文怎么写"]) {
      headRowEl.createEl("th", { text: header });
    }

    const bodyEl = tableEl.createEl("tbody");

    for (const [marker, kind, body] of rows) {
      const rowEl = bodyEl.createEl("tr");
      rowEl.createEl("td").createEl("code", { text: marker });
      rowEl.createEl("td", { text: kind });
      rowEl.createEl("td", { text: body });
    }
  }

  private renderGuideSamples(parentEl: HTMLElement, title: string, samples: GuideSample[]): void {
    parentEl.createEl("h4", { text: title });

    const gridEl = parentEl.createDiv({ cls: "md-diagram-cards-guide-samples" });

    for (const sample of samples) {
      const cellEl = gridEl.createDiv({ cls: "md-diagram-cards-guide-sample" });
      cellEl.createDiv({ cls: "md-diagram-cards-guide-sample-label", text: sample.label });
      cellEl.createEl("pre").createEl("code", { text: sample.code });
    }
  }

  // ------------------------------------------------------------ 日志

  private renderLogSection(containerEl: HTMLElement): void {
    const available = this.plugin.logAvailable();

    new Setting(containerEl).setName("日志").setHeading();

    new Setting(containerEl)
      .setName("转换日志")
      .setDesc(
        available
          ? `每次转换追加一行（JSON）：结构数、卡片数、警告、提示。显示「成功但没有卡片」时先看这里。\n${this.plugin.logPath()}`
          : "拿不到 vault 的本地路径（仅桌面端），日志不可用。",
      )
      .addButton((button) =>
        button
          .setButtonText("查看最近日志")
          .setDisabled(!available)
          .onClick(() => {
            void this.plugin.openLog();
          }),
      )
      .addButton((button) =>
        button
          .setButtonText("清空")
          .setWarning()
          .setDisabled(!available)
          .onClick(() => {
            void this.plugin.clearLog();
          }),
      );
  }

  // ------------------------------------------------------------ 文件夹选择

  private renderFolderPicker(options: FolderPickerOptions): void {
    const knownFolders = this.plugin.listVaultFolders();

    new Setting(this.containerEl)
      .setName(options.name)
      .setDesc(options.desc)
      .addSearch((search) => {
        search.setPlaceholder(options.placeholder);

        const suggest = new FolderSuggest(this.app, search.inputEl, (folder) => {
          void this.changeFolders(options, "add", folder);
        });

        // 已经选过的就不用再出现在候选里了。
        suggest.setFolders(knownFolders.filter((folder) => !this.contains(options.selected, folder)));
        this.suggests.push(suggest);
      });

    const chipsEl = this.containerEl.createDiv({ cls: "md-diagram-cards-chips" });

    if (options.selected.length === 0) {
      chipsEl.createDiv({ cls: "md-diagram-cards-chips-empty", text: options.emptyHint });
      return;
    }

    for (const folder of options.selected) {
      const chipEl = chipsEl.createDiv({ cls: "md-diagram-cards-chip" });
      chipEl.createSpan({ cls: "md-diagram-cards-chip-label", text: folder });

      const removeEl = chipEl.createEl("button", {
        cls: "md-diagram-cards-chip-remove",
        text: "✕",
        attr: { "aria-label": `移除 ${folder}` },
      });
      removeEl.onclick = () => {
        void this.changeFolders(options, "remove", folder);
      };
    }
  }

  private async changeFolders(options: FolderPickerOptions, action: "add" | "remove", folder: string): Promise<void> {
    const next =
      action === "add"
        ? [...options.selected, folder]
        : options.selected.filter((item) => item !== folder);

    await options.onChange(next);
    // 重画一遍，让 chip 列表和候选列表跟上最新设置。
    this.display();
  }

  private contains(folders: string[], folder: string): boolean {
    const needle = folder.toLowerCase();

    return folders.some((item) => item.toLowerCase() === needle);
  }

  private closeSuggests(): void {
    for (const suggest of this.suggests) {
      suggest.dispose();
    }

    this.suggests = [];
  }
}
