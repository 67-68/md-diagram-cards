// 把 TS 测试打成临时 bundle 再跑（不引入测试框架，用 devDependencies 里的 esbuild）。
import { build } from "esbuild";

const CASES = [
  "tools/scope.test.ts",
  "tools/report.test.ts",
  "tools/categories.test.ts",
  "tools/pipeline.test.ts",
];

for (const [index, entry] of CASES.entries()) {
  const outfile = `.tmp/test-${index}.mjs`;

  await build({
    entryPoints: [entry],
    outfile,
    bundle: true,
    platform: "node",
    format: "esm",
    logLevel: "error",
    alias: { "@": "./src" },
  });

  await import(`../${outfile}`);
}
