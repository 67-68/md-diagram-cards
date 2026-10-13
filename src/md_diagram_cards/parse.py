"""解析层 —— 自上而下，context 累加。

不追求严格层级：parse_item 是唯一的最小单元解析函数，
表格单元格 / 扁平 bullet / 嵌套树节点 全都走它。
"""
from __future__ import annotations

import re

from .model import Diagram, Inference, Item, Link, Row

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
DIAGRAM_MARKER_RE = re.compile(r"^\[d-([a-z]+)\]\s*(.*)$")
TIME_PREFIX_RE = re.compile(r"^\[([^\]]+)\]\s*(\S.*)$")
INFERENCE_RE = re.compile(r"^=>\s*(.*?)\s*=>\s*$")
BULLET_RE = re.compile(r"^([ \t]*)(?:[-*+]|\d+[.)])\s+(.*?)\s*$")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
BULLET_PREFIX_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")

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

def parse_information(blocks: list[dict]) -> dict:
    for block in blocks:
        if block["title"].strip().lower() == "information":
            return _parse_information_body(block["body"])
    return {}


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
        diagram = parse_table(block, title)
    elif kind == "state":
        diagram = parse_list(block, title)
    elif kind == "tree":
        diagram = parse_tree(block, title)
    else:
        return None

    diagram.end_line = block.get("end_line", block["line"] + 1)
    return diagram


# ---------------------------------------------------------------- 正交表

def parse_table(block: dict, title: str) -> Diagram:
    table_lines = [line for line in block["body"] if line.strip().startswith("|")]
    diagram = Diagram(kind="orthogonal", title=title, line=block["line"])

    if len(table_lines) < 2:
        return diagram

    diagram.headers = split_row(table_lines[0])

    for offset, raw in enumerate(table_lines[2:]):
        cells = split_row(raw)
        if not cells:
            continue

        entity = cells[0]
        if not entity:
            continue  # 行实体为空 → 跳过整行

        values = [split_cell_values(cell) for cell in cells[1:]]
        diagram.rows.append(Row(entity=entity, values=values, line=block["line"] + offset + 3))

    return diagram


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
