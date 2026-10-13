// 运行范围匹配的回归测试：`npm test`
//
// 起因：install.sh 早期版本给新装用户写的是 scopeMode=include + includeFolders=[]，
// 于是任何文件都会被判成"不在范围内"。这些用例把当时的坑钉死。
import {
  categoryRecord,
  DEFAULT_SETTINGS,
  isInScope,
  normalizeCategories,
  normalizePluginSettings,
  normalizeVaultPath,
} from "@/application/config/PluginSettings";

let failed = 0;

function check(label: string, actual: unknown, expected: unknown): void {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);

  if (!ok) {
    failed += 1;
    console.log(`  FAIL  ${label} — 得到 ${JSON.stringify(actual)}，期望 ${JSON.stringify(expected)}`);
    return;
  }

  console.log(`  PASS  ${label}`);
}

function settings(partial: Partial<typeof DEFAULT_SETTINGS>) {
  return normalizePluginSettings({ ...DEFAULT_SETTINGS, ...partial });
}

console.log("运行范围");

check("默认设置不限制任何文件", isInScope("任意/文件.md", normalizePluginSettings(DEFAULT_SETTINGS)), true);
check("include + 空列表 = 不限制", isInScope("笔记/文件.md", settings({ scopeMode: "include", includeFolders: [] })), true);
check("include 命中子目录", isInScope("笔记/子目录/文件.md", settings({ scopeMode: "include", includeFolders: ["笔记"] })), true);
check("include 未命中", isInScope("别的/文件.md", settings({ scopeMode: "include", includeFolders: ["笔记"] })), false);
check("include 容忍首尾斜杠", isInScope("笔记/文件.md", settings({ scopeMode: "include", includeFolders: ["/笔记/"] })), true);
check("include 大小写不敏感", isInScope("Notes/a.md", settings({ scopeMode: "include", includeFolders: ["notes"] })), true);
check("include 容忍 ./ 前缀", isInScope("笔记/文件.md", settings({ scopeMode: "include", includeFolders: ["./笔记"] })), true);
check("include 容忍反斜杠", isInScope("笔记/文件.md", settings({ scopeMode: "include", includeFolders: ["笔记\\"] })), true);
check("exclude 命中", isInScope("草稿/文件.md", settings({ scopeMode: "exclude", excludeFolders: ["草稿"] })), false);
check("exclude 未命中", isInScope("笔记/文件.md", settings({ scopeMode: "exclude", excludeFolders: ["草稿"] })), true);
check("exclude 不误伤同前缀兄弟目录", isInScope("草稿本/文件.md", settings({ scopeMode: "exclude", excludeFolders: ["草稿"] })), true);

console.log("设置归一化");

check("去重 + 去斜杠", normalizePluginSettings({ includeFolders: ["笔记", "笔记/", "/笔记"] }).includeFolders, ["笔记"]);
check("normalizeVaultPath", normalizeVaultPath("  ./a//b//  "), "a/b");
check("坏值回落到默认", normalizePluginSettings({ scopeMode: "nope" as never, timeoutSeconds: -1 }).timeoutSeconds, DEFAULT_SETTINGS.timeoutSeconds);

console.log("Category 归一化");

check(
  "去空白 + 丢空行",
  normalizeCategories([
    { key: " ability ", template: " {key} x " },
    { key: "", template: "no key" },
    { key: "motto", template: "" },
    "nonsense",
  ] as never),
  [{ key: "ability", template: "{key} x" }],
);
check(
  "同名（忽略大小写）后者覆盖",
  normalizeCategories([
    { key: "ability", template: "first" },
    { key: "Ability", template: "second" },
  ]),
  [{ key: "Ability", template: "second" }],
);
check("默认空列表", normalizePluginSettings(DEFAULT_SETTINGS).categories, []);
check(
  "列表转 Python 用的 record",
  categoryRecord([
    { key: "ability", template: "a" },
    { key: "motto", template: "m" },
  ]),
  { ability: "a", motto: "m" },
);

if (failed > 0) {
  console.log(`\n失败 ${failed} 项`);
  process.exit(1);
}

console.log("\nOK — 运行范围全部通过");
