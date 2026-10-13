// Python 报告解析的回归测试：插件能不能从 stdout 里正确捞到诊断。
import { parseConversionReport } from "@/application/model/ConversionReport";

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

const report = JSON.stringify({
  diagram_count: 2,
  card_count: 5,
  diagrams: [{ kind: "state", kind_label: "d-state 时间线/状态机", title: "x", line: 3, cards: 5 }],
  warnings: [{ message: "@member_amount 未解析到", line: 2 }],
  hints: [],
  input: "/v/a.md",
  mode: "inplace",
  target: "/v/a.md",
  written: true,
});

console.log("报告解析");

check("正常一行 JSON", parseConversionReport(`${report}\n`)?.card_count, 5);
check("前面有杂音也能捞出来", parseConversionReport(`下面是报告\n${report}\n`)?.card_count, 5);
check("警告一起带出来", parseConversionReport(report)?.warnings.length, 1);
check("结构明细一起带出来", parseConversionReport(report)?.diagrams[0]?.kind, "state");
check("多行 JSON 也能兜住", parseConversionReport(JSON.stringify(JSON.parse(report), null, 2))?.card_count, 5);
check("空 stdout → null", parseConversionReport(""), null);
check("坏 JSON → null", parseConversionReport('{"card_count": 1'), null);
check("不像报告的对象 → null", parseConversionReport('{"hello": 1}'), null);
check("缺 hints → 补空数组", parseConversionReport('{"diagram_count": 0, "card_count": 0}')?.hints, []);
check("0 卡片报告照收", parseConversionReport('{"diagram_count": 0, "card_count": 0}')?.card_count, 0);

if (failed > 0) {
  console.log(`\n失败 ${failed} 项`);
  process.exit(1);
}

console.log("\nOK — 报告解析全部通过");
