"""解析层 —— 自上而下，context 累加。

不追求严格层级：parse_item 是唯一的最小单元解析函数，
表格单元格 / 扁平 bullet / 嵌套树节点 全都走它。
"""
from __future__ import annotations

import re

from .diagnostics import warn
from .model import Column, Diagram, Inference, Item, Link, MediaField, Row

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
DIAGRAM_MARKER_RE = re.compile(r"^\[d-([a-z]+)\]\s*(.*)$")
# Information 块的专属标记：`### [information]`（大小写不敏感，标题层级不限）。
INFORMATION_MARKER_RE = re.compile(r"^\[information\]\s*(.*)$", re.IGNORECASE)
TIME_PREFIX_RE = re.compile(r"^\[([^\]]+)\]\s*(\S.*)$")
INFERENCE_RE = re.compile(r"^=>\s*(.*?)\s*=>\s*$")
BULLET_RE = re.compile(r"^([ \t]*)(?:[-*+]|\d+[.)])\s+(.*?)\s*$")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
BULLET_PREFIX_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")

# 表头标注：`例子音频@[front, back=频段]` / `例子音频@[back, front=频段(y)]`。
# 只对表头单元格生效，和正文里的 `@cat` 外链是两套语法，互不影响。
COLUMN_SPEC_RE = re.compile(r"^(?P<header>.*?)\s*@\[(?P<spec>[^\[\]]*)\]\s*$")
# 标注里的一侧：`front` / `back=列头` / `front=列头(模板)`。
MEDIA_FIELD_RE = re.compile(
    r"^(?P<side>front|back)\s*(?:=\s*(?P<target>[^()]*?)\s*(?:\((?P<template>.*)\))?)?$"
)

# 整行跳过：`@exclude` 写在正交表某行的第 1 列（行实体）上。
EXCLUDE_RE = re.compile(r"@exclude\b", re.IGNORECASE)

CUSTOM_RE = re.compile(r"@custom\(\s*([^)]*?)\s*\)")
CAT_VALUE_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^@]*)")
CAT_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")


# ---------------------------------------------------------------- 文档切块

def split_blocks(lines: list[str]) -> list[dict]:
    """按标题切成块。代码围栏内的 # 不算标题。"""
    blocks: list[dict] = []
    current: dict | None = None
    in_fence = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if current is not None:
                current["body"].append(line)
            continue

        if in_fence:
            if current is not None:
                current["body"].append(line)
            continue

        match = HEADING_RE.match(line)
        if match:
            title = re.sub(r"\s*#+\s*$", "", match.group(2)).strip()
            if current is not None:
                current["end_line"] = index
            current = {"level": len(match.group(1)), "title": title, "line": index, "body": []}
            blocks.append(current)
        elif current is not None:
            current["body"].append(line)

    if current is not None:
        current["end_line"] = len(lines)

    return blocks


# ---------------------------------------------------------------- Information

def is_information_block(title: str) -> bool:
    """判断一个标题是不是 Information 块。

    推荐写法是专属标记 `### [information]`；纯 `Information` 标题是旧写法，
    继续兼容（大小写、层级都不敏感）。
    """
    text = title.strip()
    if INFORMATION_MARKER_RE.match(text):
        return True
    return text.lower() == "information"


def parse_information(blocks: list[dict]) -> dict:
    """收集文档里**所有** Information 块，按顺序合并成一个大 dict。

    合并规则：`项 → {外链 → 值}`。同一个项出现在多个块里时，后者按外链覆盖前者，
    不同外链取并集。后出现的块优先。
    """
    merged: dict[str, dict] = {}
    for block in blocks:
        if is_information_block(block["title"]):
            _merge_information(merged, _parse_information_body(block["body"]))
    return merged


def _merge_information(target: dict[str, dict], incoming: dict[str, dict]) -> None:
    for item_name, links in incoming.items():
        target.setdefault(item_name, {}).update(links)


def _parse_information_body(lines: list[str]) -> dict:
    info: dict[str, dict] = {}
    depths: list[int] = []
    current_key: str | None = None
    current_sub: str | None = None

    def depth_of(indent: int) -> int:
        if indent not in depths:
            depths.append(indent)
            depths.sort()
        return depths.index(indent)

    for line in lines:
        match = BULLET_RE.match(line)
        if not match:
            continue

        depth = depth_of(len(match.group(1).expandtabs(4)))
        text = match.group(2).strip()

        # 空 bullet（例如行尾多敲了一个 `- `）不产生任何条目。
        if not text:
            continue

        if depth == 0:
            current_key = text
            current_sub = None
            info.setdefault(current_key, {})
            continue

        if current_key is None:
            continue

        if depth == 1:
            if ":" in text:
                name, _, value = text.partition(":")
                current_sub = name.strip()
                info[current_key][current_sub] = value.strip() if value.strip() else []
            else:
                current_sub = text
                info[current_key][text] = []
            continue

        # depth >= 2 → 给当前子键追加值
        if current_sub is not None:
            slot = info[current_key][current_sub]
            if isinstance(slot, list):
                slot.append(text)
            else:
                info[current_key][current_sub] = [slot, text]

    return info


# ---------------------------------------------------------------- Diagram 分派

def parse_document(text: str) -> dict:
    """解析整份文档，返回 context dict。"""
    blocks = split_blocks(text.split("\n"))
    ctx: dict = {
        "information": parse_information(blocks),
        "diagrams": [],
        "warnings": [],
    }
    for block in blocks:
        diagram = parse_diagram(block, ctx)
        if diagram is not None:
            ctx["diagrams"].append(diagram)
    return ctx


def parse_diagram(block: dict, ctx: dict) -> Diagram | None:
    match = DIAGRAM_MARKER_RE.match(block["title"])
    if not match:
        return None

    kind = match.group(1)
    title = match.group(2).strip()
    ctx["diagram_kind"] = kind
    ctx["表头"] = title

    if kind == "orthogonal":
        diagram = parse_table(block, title, ctx)
    elif kind == "state":
        diagram = parse_list(block, title)
    elif kind == "tree":
        diagram = parse_tree(block, title)
    else:
        return None

    diagram.end_line = block.get("end_line", block["line"] + 1)
    return diagram


# ---------------------------------------------------------------- 正交表

def parse_table(block: dict, title: str, ctx: dict | None = None) -> Diagram:
    # 保留每行在原文里的 1-based 行号，警告/报告都靠它指位置。
    table_lines = [
        (block["line"] + 1 + offset + 1, line)
        for offset, line in enumerate(block["body"])
        if line.strip().startswith("|")
    ]
    diagram = Diagram(kind="orthogonal", title=title, line=block["line"])

    if len(table_lines) < 2:
        return diagram

    header_line = table_lines[0][0]
    columns = [parse_column(cell, ctx, header_line) for cell in split_row(table_lines[0][1])]

    # 第 1 列是行实体，不产卡，标了媒体列也是白标。
    if columns and columns[0].is_media:
        if ctx is not None:
            warn(ctx, "表格第 1 列是行实体，不能写 @[...] 媒体列标注（已忽略）", header_line)
        columns[0] = Column(header=columns[0].header)

    diagram.columns = columns

    for line_no, raw in table_lines[2:]:
        cells = split_row(raw)
        if not cells:
            continue

        entity_cell = cells[0]
        if EXCLUDE_RE.search(entity_cell):
            # 整行只是给人看的辅助说明：不算进表格，一行卡都不出。
            diagram.excluded.append(Row(entity=EXCLUDE_RE.sub("", entity_cell).strip(), line=line_no))
            continue

        entity = entity_cell.strip()
        if not entity:
            continue  # 行实体为空 → 跳过整行

        if ctx is not None and any(EXCLUDE_RE.search(cell) for cell in cells[1:]):
            warn(ctx, "@exclude 只对第 1 列（行实体）生效，其他列里写了会被当成正文", line_no)

        values = [split_cell_values(cell) for cell in cells[1:]]
        diagram.rows.append(Row(entity=entity, values=values, line=line_no))

    return diagram


def parse_column(cell: str, ctx: dict | None = None, line: int = 0) -> Column:
    """解析表头单元格：`列头` 或 `列头@[front, back=列头]`（媒体列）。

    标注写法逗号分隔，只支持 `front` 和 `back=列头` 两种。认不出的写法 →
    警告，但不影响这一列本身（该列仍按能认出来的部分处理）。
    """
    text = cell.strip()
    match = COLUMN_SPEC_RE.match(text)
    if not match:
        return Column(header=text)

    column = Column(header=match.group("header").strip())

    for raw in match.group("spec").split(","):
        spec = raw.strip()
        if not spec:
            continue

        field = parse_media_field(spec, column.header, ctx, line)
        if field is None:
            continue

        side, value = field
        if getattr(column, side) is not None and ctx is not None:
            warn(ctx, f"表头 [{column.header}] 的 @[...] 里 {side} 写了不止一次（用最后一次）", line)
        setattr(column, side, value)

    return column


def parse_media_field(spec: str, header: str, ctx: dict | None, line: int = 0) -> tuple[str, MediaField] | None:
    """解析标注里的一侧：`front` / `back=列头` / `front=列头(模板)`。

    认不出来 → 警告 + 返回 None（这一侧当没写）。
    """
    match = MEDIA_FIELD_RE.match(spec)
    if not match:
        if ctx is not None:
            warn(
                ctx,
                f"表头 [{header}] 的 @[...] 标注里有认不出的写法: {spec}"
                "（只支持 front / back / back=列头 / front=列头(y)）",
                line,
            )
        return None

    side = match.group("side")
    target = (match.group("target") or "").strip()
    inner = match.group("template")

    if not target:
        if inner is not None and ctx is not None:
            warn(
                ctx,
                f"表头 [{header}] 的 @[...] 里 {side}({inner}) 少了列名"
                f"（想用本列的值就写 {side}）",
                line,
            )
        return side, MediaField(own=True)

    # `front=频段(y)` 的题面文字是**整个 `频段(y)`**，`y` 才是值的位置。
    template = f"{target}({inner})" if inner is not None else ""
    if template and "y" not in template and "{value}" not in template and ctx is not None:
        warn(
            ctx,
            f"表头 [{header}] 的 @[...] 里模板 {template} 没有 y 占位符，值不会出现在题面里",
            line,
        )

    return side, MediaField(column=target, template=template)


def split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip() for cell in text.split("|")]


def split_cell_values(cell: str) -> list[str]:
    """单元格内的多值：按 <br> 或换行切分，丢弃空片段，剥掉列表前缀。"""
    values = []
    for part in BR_RE.split(cell):
        for piece in part.split("\n"):
            piece = BULLET_PREFIX_RE.sub("", piece.strip()).strip()
            if piece:
                values.append(piece)
    return values


# ---------------------------------------------------------------- [d-state]

def parse_list(block: dict, title: str) -> Diagram:
    diagram = Diagram(kind="state", title=title, line=block["line"])

    for offset, line in enumerate(block["body"]):
        line_no = block["line"] + offset + 1

        inference = INFERENCE_RE.match(line.strip())
        if inference:
            diagram.inferences.append(
                Inference(text=inference.group(1).strip(), prev_index=len(diagram.items) - 1, line=line_no)
            )
            continue

        match = BULLET_RE.match(line)
        if not match:
            continue

        diagram.items.append(parse_item(match.group(2), line_no))

    return diagram


# ---------------------------------------------------------------- [d-tree]

def parse_tree(block: dict, title: str) -> Diagram:
    diagram = Diagram(kind="tree", title=title, line=block["line"])
    stack: list[tuple[int, Item]] = []

    for offset, line in enumerate(block["body"]):
        match = BULLET_RE.match(line)
        if not match:
            continue

        indent = len(match.group(1).expandtabs(4))
        item = parse_item(match.group(2), block["line"] + offset + 1)
        item.indent = indent

        while stack and stack[-1][0] >= indent:
            stack.pop()

        if stack:
            stack[-1][1].children.append(item)
        else:
            diagram.items.append(item)

        stack.append((indent, item))

    return diagram


# ---------------------------------------------------------------- 最小单元

def parse_item(text: str, line: int = 0) -> Item:
    """解析 `key: description @links`。唯一的「最小单元解析函数」。"""
    text = text.strip()
    time = ""

    match = TIME_PREFIX_RE.match(text)
    if match:
        time = match.group(1).strip()
        text = match.group(2).strip()

    name, desc, links = parse_key_desc_links(text)
    return Item(name=name, time=time, desc=desc, links=links, line=line)


def parse_key_desc_links(text: str) -> tuple[str, str, list[Link]]:
    at = text.find("@")
    head = text if at < 0 else text[:at]
    link_part = "" if at < 0 else text[at:]

    if ":" in head:
        name, _, desc = head.partition(":")
    else:
        name, desc = head, ""

    return name.strip(), desc.strip(), parse_links(link_part)


def parse_links(text: str) -> list[Link]:
    links: list[Link] = []
    cursor = 0

    while cursor < len(text):
        if text[cursor] != "@":
            cursor += 1
            continue

        rest = text[cursor:]

        match = CUSTOM_RE.match(rest)
        if match:
            links.append(Link(category="custom", value=match.group(1).strip()))
            cursor += match.end()
            continue

        match = CAT_VALUE_RE.match(rest)
        if match:
            links.append(Link(category=match.group(1), value=match.group(2).strip(), inline=True))
            cursor += match.end()
            continue

        match = CAT_RE.match(rest)
        if match:
            links.append(Link(category=match.group(1)))
            cursor += match.end()
            continue

        cursor += 1

    return links
