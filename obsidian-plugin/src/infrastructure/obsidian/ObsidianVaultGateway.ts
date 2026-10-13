import { FileSystemAdapter, type App } from "obsidian";

import type { VaultGateway } from "@/application/ports/VaultGateway";

export class ObsidianVaultGateway implements VaultGateway {
  constructor(private readonly app: App) {}

  basePath(): string | null {
    const adapter = this.app.vault.adapter;

    if (adapter instanceof FileSystemAdapter) {
      return adapter.getBasePath();
    }

    return null;
  }

  listMarkdownPaths(): string[] {
    return this.app.vault.getMarkdownFiles().map((file) => file.path);
  }

  listFolders(): string[] {
    // includeRoot=false：根目录不是一个能用来过滤的前缀。
    return this.app.vault
      .getAllFolders(false)
      .map((folder) => folder.path)
      .sort((left, right) => left.localeCompare(right));
  }

  toAbsolute(relativePath: string): string | null {
    const base = this.basePath();
    if (!base) {
      return null;
    }

    return `${base}/${relativePath}`;
  }
}
