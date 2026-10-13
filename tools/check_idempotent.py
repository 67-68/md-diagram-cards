#!/usr/bin/env python3
"""验证 inplace 模式幂等：跑两次结果必须一致。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from md_diagram_cards.output import render_inplace  # noqa: E402


def main() -> int:
    failed = []

    for folder in sorted((ROOT / "fixtures").iterdir()):
        input_path = folder / "input.md"
        if not folder.is_dir() or not input_path.exists():
            continue

        source = input_path.read_text(encoding="utf-8")
        once, _ = render_inplace(source)
        twice, _ = render_inplace(once)

        if once == twice:
            print(f"  PASS  {folder.name}")
        else:
            failed.append(folder.name)
            print(f"  FAIL  {folder.name}")
            print("        --- 第一次 ---")
            for line in once.split("\n"):
                print(f"        {line}")
            print("        --- 第二次 ---")
            for line in twice.split("\n"):
                print(f"        {line}")

    print()
    if failed:
        print(f"FAILED: {len(failed)} → {', '.join(failed)}")
        return 1
    print("OK — all idempotent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
