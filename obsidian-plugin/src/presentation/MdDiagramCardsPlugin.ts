import path from "node:path";

import { Plugin } from "obsidian";

import { DEFAULT_SETTINGS, normalizePluginSettings, type PluginSettings } from "@/application/config/PluginSettings";
import {
  ConvertService,
  CurrentFileOutOfScopeError,
  RunScopeNotConfiguredError,
} from "@/application/services/ConvertService";
import { ObsidianVaultGateway } from "@/infrastructure/obsidian/ObsidianVaultGateway";
import { ConvertLogFile } from "@/infrastructure/persistence/ConvertLogFile";
import { DataJsonSettingsRepository } from "@/infrastructure/persistence/DataJsonSettingsRepository";
import { ChildProcessPythonRunner } from "@/infrastructure/python/ChildProcessPythonRunner";
import { registerCommands } from "@/presentation/commands/registerCommands";
import { LogModal } from "@/presentation/modals/LogModal";
import { NoticeService } from "@/presentation/notices/NoticeService";
import { MdDiagramCardsSettingTab } from "@/presentation/settings/PluginSettingTab";

export default class MdDiagramCardsPlugin extends Plugin {
  settings: PluginSettings = DEFAULT_SETTINGS;

  private readonly noticeService = new NoticeService();
  private settingsRepository?: DataJsonSettingsRepository;
  private convertService?: ConvertService;
  private pythonRunner?: ChildProcessPythonRunner;
  private vaultGateway?: ObsidianVaultGateway;
  private convertLog?: ConvertLogFile;

  async onload(): Promise<void> {
    this.settingsRepository = new DataJsonSettingsRepository(this);

    try {
      this.settings = await this.settingsRepository.load();
    } catch (error) {
      console.error("加载设置失败，回退到默认值。", error);
      this.settings = DEFAULT_SETTINGS;
      this.noticeService.error("设置损坏，已回退到默认值。");
    }

    this.vaultGateway = new ObsidianVaultGateway(this.app);
    this.pythonRunner = new ChildProcessPythonRunner(() => this.settings);
    this.convertLog = new ConvertLogFile(this.resolveLogDirectory());
    this.convertService = new ConvertService(this.vaultGateway, this.pythonRunner, this.convertLog);

    registerCommands(this);
    this.addSettingTab(new MdDiagramCardsSettingTab(this));
  }

  async updateSettings(partialSettings: Partial<PluginSettings>): Promise<void> {
    if (!this.settingsRepository) {
      return;
    }

    // 存之前先归一化：清掉首尾斜杠/空白，否则 `笔记/` 这种写法会匹配不上文件路径。
    const next = normalizePluginSettings({ ...this.settings, ...partialSettings });

    try {
      await this.settingsRepository.save(next);
      this.settings = next;
    } catch (error) {
      console.error("保存设置失败。", error);
      this.noticeService.error("保存设置失败。");
    }
  }

  /** vault 里现有的文件夹，给设置界面的下拉列表当候选。 */
  listVaultFolders(): string[] {
    try {
      return this.vaultGateway?.listFolders() ?? [];
    } catch (error) {
      console.error("读取文件夹列表失败。", error);
      return [];
    }
  }

  // ------------------------------------------------------------ 日志

  logPath(): string {
    return this.convertLog?.path() ?? "(不可用)";
  }

  logAvailable(): boolean {
    return this.convertLog?.available() ?? false;
  }

  /** 打开日志窗口：卡片数为 0 的时候，答案基本都在这里。 */
  async openLog(): Promise<void> {
    if (!this.convertLog) {
      this.noticeService.error("日志未初始化。");
      return;
    }

    try {
      const raw = await this.convertLog.read();
      new LogModal(this.app, this.convertLog.path(), raw).open();
    } catch (error) {
      console.error("读取转换日志失败。", error);
      this.noticeService.error(`读取日志失败，见控制台。路径：${this.convertLog.path()}`);
    }
  }

  async clearLog(): Promise<void> {
    if (!this.convertLog) {
      return;
    }

    await this.convertLog.clear();
    this.noticeService.info("转换日志已清空。");
  }

  private resolveLogDirectory(): string | null {
    const basePath = this.vaultGateway?.basePath();

    if (!basePath || !this.manifest.dir) {
      return null;
    }

    return path.join(basePath, this.manifest.dir);
  }

  // ------------------------------------------------------------ 命令

  async runConvertCurrentFile(): Promise<void> {
    const activeFile = this.app.workspace.getActiveFile();

    if (!activeFile || activeFile.extension.toLowerCase() !== "md") {
      this.noticeService.error("没有打开的 markdown 文件。");
      return;
    }

    if (!this.convertService) {
      this.noticeService.error("转换服务未初始化。");
      return;
    }

    if (!this.vaultGateway?.basePath()) {
      this.noticeService.error("无法获取 vault 的本地路径（仅桌面端支持）。");
      return;
    }

    try {
      const summary = await this.convertService.convertCurrentFile(activeFile.path, this.settings);
      this.noticeService.showConvertSummary("当前文件", summary);
    } catch (error) {
      if (error instanceof CurrentFileOutOfScopeError || error instanceof RunScopeNotConfiguredError) {
        this.noticeService.info(error.message);
        return;
      }

      console.error("转换当前文件失败。", error);
      this.noticeService.error("转换当前文件失败，详见控制台。");
    }
  }

  async runConvertVault(): Promise<void> {
    if (!this.convertService) {
      this.noticeService.error("转换服务未初始化。");
      return;
    }

    if (!this.vaultGateway?.basePath()) {
      this.noticeService.error("无法获取 vault 的本地路径（仅桌面端支持）。");
      return;
    }

    try {
      const summary = await this.convertService.convertVault(this.settings);
      this.noticeService.showConvertSummary("全库", summary);
    } catch (error) {
      if (error instanceof RunScopeNotConfiguredError) {
        this.noticeService.info(error.message);
        return;
      }

      console.error("全库转换失败。", error);
      this.noticeService.error("全库转换失败，详见控制台。");
    }
  }

  async testPython(): Promise<void> {
    if (!this.pythonRunner) {
      this.noticeService.error("Python 运行器未初始化。");
      return;
    }

    const result = await this.pythonRunner.probe();

    if (result.ok) {
      this.noticeService.info(`Python 可用：${this.settings.pythonPath}`);
      return;
    }

    this.noticeService.error(`Python 不可用（退出码 ${result.code}）\n${result.stderr.trim()}`);
  }
}
