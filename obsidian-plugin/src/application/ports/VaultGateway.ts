export interface VaultGateway {
  /** vault 在本地文件系统上的根目录。非桌面端返回 null。 */
  basePath(): string | null;
  /** 所有 md 文件的相对路径。 */
  listMarkdownPaths(): string[];
  /** 所有文件夹的相对路径（不含 vault 根目录），已排序。 */
  listFolders(): string[];
  /** 相对路径 → 绝对路径。 */
  toAbsolute(relativePath: string): string | null;
}
