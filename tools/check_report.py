#!/usr/bin/env python3
"""验证转换报告的口径：报告的卡片数必须和 expected.md 里的卡片条数对得上。

顺带钉死"没有标记 → 0 个结构 → 给出提示"这条路径（用户踩过的坑：
提示成功但什么都没生成，因为文件里根本没有 [d-*] 标记）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from md_diagram_cards.output import convert_inplace  # noqa: E402

NO_MARKER = """# 普通笔记

| 竞争者 | 战略目标 |
| --- | --- |
| Austria | 保住霸主地位 |
"""


def count_cards(text: str) -> int:
    return sum(1 for line in text.split("\n") if line.startswith("#### "))


def main() -> int:
    failed: list[str] = []

    for folder in sorted((ROOT / "fixtures").iterdir()):
        input_path = folder / "input.md"
        expected_path = folder / "expected.md"

        if not folder.is_dir() or not input_path.exists() or not expected_path.exists():
            continue

        conversion = convert_inplace(input_path.read_text(encoding="utf-8"))
        expected = count_cards(expected_path.read_text(encoding="utf-8"))
        ok = conversion.card_count == expected

        print(f"  {'PASS' if ok else 'FAIL'}  {folder.name}  报告 {conversion.card_count} 张 / expected {expected} 张")

        if not ok:
            failed.append(folder.name)

    # 没有 [d-*] 标记的普通文档：0 个结构、0 张卡、且必须给出提示
    conversion = convert_inplace(NO_MARKER)
    ok = conversion.diagram_count == 0 and conversion.card_count == 0 and len(conversion.hints) == 1

    print(f"  {'PASS' if ok else 'FAIL'}  无标记文档 → 0 个结构 + 提示")
    if not ok:
        failed.append("无标记文档")

    if failed:
        print(f"\n失败: {', '.join(failed)}")
        return 1

    print("\nOK — 报告口径一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
