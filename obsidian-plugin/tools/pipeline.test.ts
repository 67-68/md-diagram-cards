// 插件 ↔ Python 的契约检查：真跑 Python CLI，真解析它的 stdout。
//
// 这是两边最容易脱钩的地方（插件靠 --report json 的输出判断"到底出了几张卡"）。
// 需要能跑 python3，且仓库的 src 就在旁边；环境不满足时跳过而不算失败。
import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { parseConversionReport } from "@/application/model/ConversionReport";

const PLUGIN_DIR = process.cwd();
const REPO_DIR = path.resolve(PLUGIN_DIR, "..");
const SRC_DIR = path.join(REPO_DIR, "src");
const FIXTURES = path.join(REPO_DIR, "fixtures");

let failed = 0;

function check(label: string, actual: unknown, expected: unknown): void {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);

  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${ok ? "" : ` — 得到 ${JSON.stringify(actual)}，期望 ${JSON.stringify(expected)}`}`);

  if (!ok) {
    failed += 1;
  }
}

interface RunOutcome {
  stdout: string;
  code: number;
}

function run(file: string, mode: string): RunOutcome {
  try {
    return {
      stdout: execFileSync("python3", ["-m", "md_diagram_cards", file, "--mode", mode, "--report", "json"], {
        env: { ...process.env, PYTHONPATH: SRC_DIR },
        encoding: "utf8",
      }),
      code: 0,
    };
  } catch (error) {
    const failure = error as { stdout?: string; status?: number };

    return { stdout: failure.stdout ?? "", code: failure.status ?? 1 };
  }
}

function available(): boolean {
  if (!existsSync(path.join(SRC_DIR, "md_diagram_cards"))) {
    return false;
  }

  try {
    execFileSync("python3", ["-m", "md_diagram_cards", "--help"], {
      env: { ...process.env, PYTHONPATH: SRC_DIR },
      stdio: "ignore",
    });
    return true;
  } catch {
    return false;
  }
}

console.log("插件 ↔ Python 契约");

if (!available()) {
  console.log("  跳过：跑不了 python3 -m md_diagram_cards（需要 python3 且 src 在仓库里）");
} else {
  const work = mkdtempSync(path.join(tmpdir(), "mdc-pipeline-"));
  const fixture = path.join(FIXTURES, "04-timeline-group/input.md");

  // 1) 正常文件：报告数得上、真的插进去了、再跑一次还是老样子
  const inplaceFile = path.join(work, "notes.md");
  copyFileSync(fixture, inplaceFile);

  const first = run(inplaceFile, "inplace");
  const report = parseConversionReport(first.stdout);

  check("inplace 退出码 0", first.code, 0);
  check("报告解析成功", report !== null, true);
  check("结构数", report?.diagram_count, 1);
  check("卡片数", report?.card_count, 3);
  check("报告写了 written=true", report?.written, true);

  const afterFirst = readFileSync(inplaceFile, "utf8");
  check("插进了 BEGIN 标记", afterFirst.includes("<!-- BEGIN GENERATED -->"), true);

  run(inplaceFile, "inplace");
  check("幂等（BEGIN 只有一个）", readFileSync(inplaceFile, "utf8").match(/BEGIN GENERATED/g)?.length, 1);

  // 2) 没有 [d-*] 标记的普通笔记：必须说清"0 个结构"，且不许动文件
  const plainFile = path.join(work, "plain.md");
  const plainSource = "# 普通笔记\n\n| 竞争者 | 战略目标 |\n| --- | --- |\n| Austria | 保住霸主地位 |\n";
  writeFileSync(plainFile, plainSource, "utf8");

  const quiet = run(plainFile, "inplace");
  const quietReport = parseConversionReport(quiet.stdout);

  check("没标记也是退出码 0", quiet.code, 0);
  check("报告说 0 个结构", quietReport?.diagram_count, 0);
  check("报告说 0 张卡片", quietReport?.card_count, 0);
  check("报告带提示", (quietReport?.hints.length ?? 0) > 0, true);
  check("普通笔记没被动过", readFileSync(plainFile, "utf8"), plainSource);

  // 3) newfile 模式
  const newfileSource = path.join(work, "other.md");
  copyFileSync(fixture, newfileSource);

  const newfileReport = parseConversionReport(run(newfileSource, "newfile").stdout);

  check("newfile 产出 闪卡.md", path.basename(String(newfileReport?.target)), "other闪卡.md");
  check("newfile 真的写了卡片", readFileSync(path.join(work, "other闪卡.md"), "utf8").includes("#### [cloze]"), true);

  // 4) 警告要能带到插件这边
  const warnSource = path.join(work, "warn.md");
  copyFileSync(path.join(FIXTURES, "08-unresolved-link/input.md"), warnSource);
  const warned = parseConversionReport(run(warnSource, "inplace").stdout);

  check("警告进了报告", (warned?.warnings.length ?? 0) > 0, true);
}

if (failed > 0) {
  console.log(`\n失败 ${failed} 项`);
  process.exitCode = 1;
} else {
  console.log("\nOK — 契约一致");
}
