"""命令行入口。

    python -m md_diagram_cards notes.md                          # 输出到 stdout
    python -m md_diagram_cards notes.md --mode newfile           # 生成 notes闪卡.md
    python -m md_diagram_cards notes.md --mode inplace           # 就地插入（幂等）
    python -m md_diagram_cards notes.md --mode inplace --dry-run # 只预览不写
    python -m md_diagram_cards notes.md --mode inplace --report json
                                                                 # 额外吐一行 JSON 报告（给插件用）

诊断信息（几个结构、几张卡片、警告、提示）走 stderr；
stdout 只在 --mode stdout 时给卡片正文，或 --report json 时给一行 JSON。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from .output import convert_inplace, convert_new_file, new_file_path
from .render import render_warnings
from .report import Conversion


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
    parser.add_argument(
        "--report",
        choices=["json"],
        help="转完后往 stdout 吐一行 JSON 报告（需要配合 newfile / inplace 模式）",
    )
    parser.add_argument("--quiet", action="store_true", help="不出诊断信息")
    return parser


def emit_report(args: argparse.Namespace, conversion: Conversion, target: pathlib.Path | None, written: bool) -> None:
    """诊断输出。json → stdout 一行；否则 → stderr 给人看。"""
    payload = conversion.to_dict(
        input=str(args.input),
        mode=args.mode,
        target=str(target) if target else None,
        written=written,
    )

    if args.report == "json":
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    if args.quiet:
        return

    scope = f"{conversion.diagram_count} 个结构 → {conversion.card_count} 张卡片"

    if not written:
        print(f"md-diagram-cards: {scope}（只预览，未写入）", file=sys.stderr)
    elif target is not None:
        print(f"md-diagram-cards: {scope} → {target}", file=sys.stderr)

    for hint in conversion.hints:
        print(f"提示: {hint}", file=sys.stderr)

    for warning in conversion.warnings:
        line = f"（第 {warning['line']} 行）" if warning.get("line") else ""
        print(f"警告: {warning['message']}{line}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.report and (args.mode == "stdout" or args.dry_run):
        print("--report json 不能和 --mode stdout / --dry-run 一起用", file=sys.stderr)
        return 2

    source = pathlib.Path(args.input)
    if not source.is_file():
        print(f"不是文件: {source}", file=sys.stderr)
        return 1

    text = source.read_text(encoding="utf-8")

    if args.mode == "inplace":
        conversion = convert_inplace(text)
        target = source
    elif args.mode == "newfile":
        conversion = convert_new_file(text)
        target = new_file_path(source)
    else:
        conversion = convert_new_file(text)
        target = pathlib.Path(args.out) if args.out else None

    output = conversion.text

    if args.warnings and conversion.warnings:
        if output and not output.endswith("\n"):
            output += "\n"
        output += "\n" + render_warnings(conversion.warnings) + "\n"

    if target is None or args.dry_run:
        sys.stdout.write(output)
        emit_report(args, conversion, target, written=False)
        return 0

    target.write_text(output, encoding="utf-8")
    emit_report(args, conversion, target, written=True)
    return 0
