#!/usr/bin/env python3
"""验证 category 表：内置项、自定义覆盖、以及坏模板占位符的兜底。

- 内置 category 必须包含例子用到的 ability / position / name
- `--categories-json` 能覆盖内置 / 新增自定义
- 模板里出现 {key} / {value} 之外的占位符 → 警告 + 跳过，不许崩
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from md_diagram_cards import convert  # noqa: E402
from md_diagram_cards.format import CATEGORY_TEMPLATES, merge_categories  # noqa: E402

SAMPLE = """### [d-tree] demo

- King of Prus @ability @motto
"""

failed: list[str] = []


def check(label: str, actual, expected) -> None:
    ok = actual == expected
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f" — 得到 {actual!r}，期望 {expected!r}"))
    if not ok:
        failed.append(label)


print("内置 category")
for name in ("condition", "member_amount", "place", "effect", "ability", "position", "name"):
    check(f"内置含 {name}", name in CATEGORY_TEMPLATES, True)

print("\n自定义覆盖 / 新增")
merged = merge_categories({"ability": "{key} 的能力是 {value}", "motto": "{key} 的座右铭是 {value}"})
check("自定义覆盖内置", merged["ability"], "{key} 的能力是 {value}")
check("自定义新增", merged["motto"], "{key} 的座右铭是 {value}")
check("未覆盖的内置保留", merged["condition"], CATEGORY_TEMPLATES["condition"])

print("\n自定义产卡")
cards, warnings = convert(
    SAMPLE + "\n### [information]\n\n- King of Prus\n\t- ability: can fight\n\t- motto: 铁与血\n",
    categories={"ability": "{key} 的能力是 {value}", "motto": "{key} 的座右铭是 {value}"},
)
check("无警告", warnings, [])
check("覆盖后的 ability 出卡", "King of Prus 的能力是 can fight" in cards, True)
check("新增的 motto 出卡", "King of Prus 的座右铭是 铁与血" in cards, True)

print("\n坏模板兜底")
cards, warnings = convert(
    SAMPLE + "\n### [information]\n\n- King of Prus\n\t- ability: x\n\t- motto: y\n",
    categories={"ability": "{foo} {key}", "motto": "{key}"},
)
check("坏占位符 → 警告而不是崩", any("占位符有误" in w["message"] for w in warnings), True)
check("坏模板不产卡", "ability" in cards and "motto" in cards, False)

print("\nCLI --list-categories")
proc = subprocess.run(
    [sys.executable, "-m", "md_diagram_cards", "--list-categories"],
    env={"PYTHONPATH": str(ROOT / "src")},
    capture_output=True,
    text=True,
)
check("退出码 0", proc.returncode, 0)
check("输出 JSON 含 ability", "ability" in json.loads(proc.stdout), True)

print()
if failed:
    print(f"FAILED: {len(failed)} → {', '.join(failed)}")
    raise SystemExit(1)
print("OK — category 表一切正常")
