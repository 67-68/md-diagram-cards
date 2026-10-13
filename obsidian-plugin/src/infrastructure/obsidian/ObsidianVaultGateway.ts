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

  toAbsolute(relativePath: string): string | null {
    const base = this.basePath();
    if (!base) {
      return null;
    }

    return `${base}/${relativePath}`;
  }
}
