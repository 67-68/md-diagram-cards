// Category 表解析的回归测试：插件能不能从 `--list-categories` 的 stdout 里捞到内置表。
import { parseCategoryTable } from "@/application/model/CategoryTable";

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

const table = JSON.stringify({
  condition: "{key}'s condition is?",
  ability: "{key}'s ability is?",
  position: "{key}'s position is?",
  name: "{key}'s name is?",
});

console.log("Category 表解析");

check("正常一行 JSON", parseCategoryTable(`${table}\n`), JSON.parse(table));
check("前面有杂音也能捞出来", parseCategoryTable(`warning: blah\n${table}\n`)?.["ability"], "{key}'s ability is?");
check("多行 JSON 也能兜住", parseCategoryTable(JSON.stringify(JSON.parse(table), null, 2))?.["name"], "{key}'s name is?");
check("空 stdout → null", parseCategoryTable(""), null);
check("坏 JSON → null", parseCategoryTable('{"ability": "x"'), null);
check("数组 → null", parseCategoryTable("[]"), null);
check("非对象 → null", parseCategoryTable("42"), null);
check("空对象 → null", parseCategoryTable("{}"), null);
check("非字符串值被丢掉", parseCategoryTable('{"ability":"x","n":1}'), { ability: "x" });

console.log();

if (failed > 0) {
  console.log(`失败 ${failed} 项`);
  process.exitCode = 1;
} else {
  console.log("OK — Category 表解析全部通过");
}
