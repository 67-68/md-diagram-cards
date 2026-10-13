"""命令行入口。

    python -m md_diagram_cards notes.md                          # 输出到 stdout
    python -m md_diagram_cards notes.md --mode newfile           # 生成 notes闪卡.md
    python -m md_diagram_cards notes.md --mode inplace           # 就地插入（幂等）
    python -m md_diagram_cards notes.md --mode inplace --dry-run # 只预览不写
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from .output import new_file_path, render_inplace, render_new_file
from .render import render_warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md_diagram_cards",
        description="把 md 里的 [d-state] / [d-tree] / [d-orthogonal] 结构转成卡片",
    )
    parser.add_argument("input", help="输入 md 文件")
    parser.add_argument(
        "--mode",
        choices=["stdout", "newfile", "inplace"],
        default="stdout",
        help="stdout=打印(默认) / newfile=生成 xxx闪卡.md / inplace=就地插入",
    )
    parser.add_argument("-o", "--out", help="stdout 模式下的输出文件")
    parser.add_argument("--warnings", action="store_true", help="末尾附上警告（HTML 注释）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    source = pathlib.Path(args.input)
    if not source.is_file():
        print(f"不是文件: {source}", file=sys.stderr)
        return 1

    text = source.read_text(encoding="utf-8")

    if args.mode == "inplace":
        output, warnings = render_inplace(text)
        target = source
    elif args.mode == "newfile":
        output, warnings = render_new_file(text)
        target = new_file_path(source)
    else:
        output, warnings = render_new_file(text)
        target = pathlib.Path(args.out) if args.out else None

    if args.warnings and warnings:
        if output and not output.endswith("\n"):
            output += "\n"
        output += "\n" + render_warnings(warnings) + "\n"

    if target is None or args.dry_run:
        sys.stdout.write(output)
        if target is not None:
            print(f"\n[dry-run] 未写入 {target}", file=sys.stderr)
        return 0

    target.write_text(output, encoding="utf-8")
    print(f"{source} → {target}", file=sys.stderr)
    return 0
