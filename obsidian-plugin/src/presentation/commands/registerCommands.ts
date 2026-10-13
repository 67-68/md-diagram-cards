import type MdDiagramCardsPlugin from "@/presentation/MdDiagramCardsPlugin";

export function registerCommands(plugin: MdDiagramCardsPlugin): void {
  plugin.addCommand({
    id: "convert-current-file",
    name: "转换当前文件为卡片",
    callback: () => {
      void plugin.runConvertCurrentFile();
    },
  });

  plugin.addCommand({
    id: "convert-vault",
    name: "转换整个库为卡片",
    callback: () => {
      void plugin.runConvertVault();
    },
  });

  plugin.addCommand({
    id: "open-log",
    name: "查看转换日志",
    callback: () => {
      void plugin.openLog();
    },
  });
}
