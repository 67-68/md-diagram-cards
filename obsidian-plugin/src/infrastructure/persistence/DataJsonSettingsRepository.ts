import type { Plugin } from "obsidian";

import { normalizePluginSettings, type PluginSettings } from "@/application/config/PluginSettings";

interface PluginData {
  settings?: Partial<PluginSettings>;
}

export class DataJsonSettingsRepository {
  constructor(private readonly plugin: Plugin) {}

  async load(): Promise<PluginSettings> {
    const data = (await this.plugin.loadData()) as PluginData | null;
    return normalizePluginSettings(data?.settings);
  }

  async save(settings: PluginSettings): Promise<void> {
    const data = ((await this.plugin.loadData()) as PluginData | null) ?? {};
    await this.plugin.saveData({ ...data, settings });
  }
}
