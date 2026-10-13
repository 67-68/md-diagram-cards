#!/usr/bin/env python3
"""跑 fixture 回归：input.md → 卡片，与 expected.md 逐行比对。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from md_diagram_cards import convert  # noqa: E402


def normalize(text: str) -> list[str]:
    """去掉 HTML 注释整块、行尾空白、尾部空行。"""
    lines: list[str] = []
    in_comment = False

    for line in text.split("\n"):
        stripped = line.strip()
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        lines.append(line.rstrip())

    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    return lines


def main() -> int:
    failed: list[str] = []

    for folder in sorted((ROOT / "fixtures").iterdir()):
        if not folder.is_dir():
            continue
        input_path = folder / "input.md"
        expected_path = folder / "expected.md"
        if not input_path.exists() or not expected_path.exists():
            continue

        actual, warnings = convert(input_path.read_text())
        expected_lines = normalize(expected_path.read_text())
        actual_lines = normalize(actual)

        if actual_lines == expected_lines:
            note = f"  ({len(warnings)} warning)" if warnings else ""
            print(f"  PASS  {folder.name}{note}")
            continue

        failed.append(folder.name)
        print(f"  FAIL  {folder.name}")
        print("        --- expected ---")
        for line in expected_lines:
            print(f"        {line}")
        print("        --- actual ---")
        for line in actual_lines:
            print(f"        {line}")
        print()

    print()
    if failed:
        print(f"FAILED: {len(failed)} → {', '.join(failed)}")
        return 1
    print("OK — all fixtures pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
