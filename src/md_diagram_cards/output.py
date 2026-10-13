"""输出层 —— 幂等的就地插入 / 新文件模式。

就地插入的形态：

    ### [d-state] Before 7 week war
    - [1865 Oct] Biarritz meeting

    <!-- BEGIN GENERATED -->
    #### [cloze] Before 7 week war
    - [1865 Oct] Biarritz meeting
    <!-- END GENERATED -->

每次生成前先剥掉所有受管理区块，所以重复跑结果一致（幂等）。
"""
from __future__ import annotations

import pathlib

from .format import format_diagram, merge_categories
from .parse import parse_document
from .render import render_cards
from .report import Conversion, DiagramSummary

BEGIN_MARK = "<!-- BEGIN GENERATED -->"
END_MARK = "<!-- END GENERATED -->"


def strip_generated(text: str) -> str:
    """删掉所有受管理的生成区块，以及它前后由我们引入的空行。

    一并清掉前后空行是幂等的关键：否则每跑一次，区块周围的空行就会累积一层。
    """
    kept: list[str] = []
    inside = False
    after_end = False

    for line in text.split("\n"):
        stripped = line.strip()

        if stripped == BEGIN_MARK:
            inside = True
            after_end = False
            while kept and not kept[-1].strip():
                kept.pop()
            continue

        if stripped == END_MARK:
            inside = False
            after_end = True
            continue

        if inside:
            continue

        if after_end:
            if not stripped:
                continue
            after_end = False

        kept.append(line)

    return "\n".join(kept)


def convert_inplace(text: str, categories: dict[str, str] | None = None) -> Conversion:
    """就地插入：每个 diagram 的卡片包在 BEGIN/END 里，插到该 diagram 之后。"""
    stripped = strip_generated(text)
    ctx = parse_document(stripped)
    ctx["categories"] = merge_categories(categories)
    lines = stripped.split("\n")
    insertions: list[tuple[int, list[str]]] = []
    summaries: list[DiagramSummary] = []

    for diagram in ctx["diagrams"]:
        cards = format_diagram(diagram, ctx)
        summaries.append(DiagramSummary(diagram.kind, diagram.title, diagram.line + 1, len(cards)))
        if not cards:
            continue
        body = render_cards(cards).rstrip("\n").split("\n")
        insertions.append((diagram.end_line, ["", BEGIN_MARK, *body, END_MARK, ""]))

    # 从后往前插，避免行号偏移
    for index, new_lines in sorted(insertions, key=lambda item: -item[0]):
        # 规范化插入点上方的空行，保证幂等
        while index > 0 and not lines[index - 1].strip():
            del lines[index - 1]
            index -= 1
        lines[index:index] = new_lines

    return Conversion(text="\n".join(lines), warnings=ctx["warnings"], diagrams=summaries)


def render_inplace(text: str, categories: dict[str, str] | None = None) -> tuple[str, list[dict]]:
    """`convert_inplace` 的旧签名（产物 + 警告）。"""
    conversion = convert_inplace(text, categories=categories)
    return conversion.text, conversion.warnings


def convert_new_file(text: str, categories: dict[str, str] | None = None) -> Conversion:
    """只输出卡片，不带任何维护标记。"""
    ctx = parse_document(text)
    ctx["categories"] = merge_categories(categories)
    cards = []
    summaries: list[DiagramSummary] = []

    for diagram in ctx["diagrams"]:
        produced = format_diagram(diagram, ctx)
        summaries.append(DiagramSummary(diagram.kind, diagram.title, diagram.line + 1, len(produced)))
        cards.extend(produced)

    return Conversion(text=render_cards(cards), warnings=ctx["warnings"], diagrams=summaries)


def render_new_file(text: str, categories: dict[str, str] | None = None) -> tuple[str, list[dict]]:
    """`convert_new_file` 的旧签名（产物 + 警告）。"""
    conversion = convert_new_file(text, categories=categories)
    return conversion.text, conversion.warnings


def new_file_path(source: pathlib.Path) -> pathlib.Path:
    """`notes.md` → `notes闪卡.md`"""
    return source.with_name(f"{source.stem}闪卡{source.suffix}")
