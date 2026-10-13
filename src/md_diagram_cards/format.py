"""格式化层 —— 递归，任意层级可产卡。

formatting 函数由上级调用，不对应最小单元：
format_list 既产「整张图的卡」，又在内部调用更细的 format_item。
"""
from __future__ import annotations

from .model import Card, Diagram, Item, Link

# Category → 问题模板（预定义 K-V，只收录例子里出现过的）
CATEGORY_TEMPLATES: dict[str, str] = {
    "condition": "{key}'s condition is?",
    "member_amount": "Member count of [{key}]",
    "place": "[{key}]的地点是 {value}",
    "effect": "{key}'s effect is?",
}


# ---------------------------------------------------------------- 总出口

def make_card(question: str, answers: list[str], line: int = 0) -> Card:
    """所有卡片唯一的出口，cloze 判定只写这一遍。"""
    answers = [answer for answer in answers if answer]
    if len(answers) >= 2:
        question = f"[cloze] {question}"
    return Card(question=question, answers=answers, line=line)


def warn(ctx: dict, message: str, line: int = 0) -> None:
    ctx["warnings"].append({"message": message, "line": line})


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def lookup(ctx: dict, item_name: str, key: str):
    node = ctx["information"].get(item_name)
    if not isinstance(node, dict):
        return None
    return node.get(key)


# ---------------------------------------------------------------- 分派

def format_document(ctx: dict) -> list[Card]:
    cards: list[Card] = []
    for diagram in ctx["diagrams"]:
        cards.extend(format_diagram(diagram, ctx))
    return cards


def format_diagram(diagram: Diagram, ctx: dict) -> list[Card]:
    if diagram.kind == "orthogonal":
        return format_table(diagram, ctx)
    if diagram.kind == "tree":
        return format_tree(diagram, ctx)
    return format_list(diagram, ctx)


# ---------------------------------------------------------------- [d-state]

def format_list(diagram: Diagram, ctx: dict) -> list[Card]:
    cards: list[Card] = []

    # ① 整张 diagram 自己产一张卡
    if diagram.items:
        cards.append(make_card(diagram.title, [item.label for item in diagram.items], diagram.line))

    # ② 再逐条交给下级
    for item in diagram.items:
        cards.extend(format_item(item, ctx, parent=diagram.title, mode="state"))

    # ③ 推论行
    cards.extend(format_inferences(diagram, ctx))

    return cards


def format_item(item: Item, ctx: dict, parent: str, mode: str) -> list[Card]:
    cards: list[Card] = []

    if item.time:
        cards.append(make_card(f"{item.name} at", [item.time], item.line))

    if item.desc:
        if mode == "tree":
            cards.append(make_card(f"[{item.name}] in [{parent}] means", [item.desc], item.line))
        else:
            cards.append(make_card(f"{item.name} means", [item.desc], item.line))

    for link in item.links:
        cards.extend(format_link(link, item, ctx))

    return cards


def format_inferences(diagram: Diagram, ctx: dict) -> list[Card]:
    cards: list[Card] = []

    for inference in diagram.inferences:
        prev_index = inference.prev_index
        next_index = prev_index + 1

        if prev_index < 0 or next_index >= len(diagram.items):
            warn(ctx, f"推论行缺少前项或后项，已跳过: {inference.text}", inference.line)
            continue

        prev_item = diagram.items[prev_index]
        next_item = diagram.items[next_index]
        question = f"{prev_item.label} 的什么推论导致了 {next_item.label}？"
        cards.append(make_card(question, [inference.text], inference.line))

    return cards


# ---------------------------------------------------------------- [d-tree]

def format_tree(diagram: Diagram, ctx: dict) -> list[Card]:
    cards: list[Card] = []

    # 根节点（diagram title）问它的顶层子节点
    if diagram.items:
        cards.append(make_card(diagram.title, [node.label for node in diagram.items], diagram.line))

    for node in diagram.items:
        cards.extend(format_node(node, ctx, parent=diagram.title))

    return cards


def format_node(node: Item, ctx: dict, parent: str) -> list[Card]:
    cards: list[Card] = []

    # ① 父问子
    if node.children:
        cards.append(make_card(node.name, [child.label for child in node.children], node.line))

    # ② ③ 自身的 description 与外链
    cards.extend(format_item(node, ctx, parent=parent, mode="tree"))

    # ④ 递归子节点
    for child in node.children:
        cards.extend(format_node(child, ctx, parent=node.name))

    return cards


# ---------------------------------------------------------------- [d-orthogonal]

def format_table(diagram: Diagram, ctx: dict) -> list[Card]:
    cards: list[Card] = []

    for row in diagram.rows:
        if not row.entity:
            continue
        for index, values in enumerate(row.values):
            header_index = index + 1
            if header_index >= len(diagram.headers):
                continue
            header = diagram.headers[header_index]
            if not header or not values:
                continue
            question = f"in [{diagram.title}] [{row.entity}]'s [{header}] is?"
            cards.append(make_card(question, values, row.line))

    return cards


# ---------------------------------------------------------------- 外链

def format_link(link: Link, item: Item, ctx: dict) -> list[Card]:
    if link.category == "custom":
        values = lookup(ctx, item.name, link.value)
        if values is None:
            warn(ctx, f"@custom({link.value}) 未在 Information 区（### [information]）中解析到 (item: {item.name})", item.line)
            return []
        return [make_card(f"[{link.value}] for [{item.name}]", as_list(values), item.line)]

    template = CATEGORY_TEMPLATES.get(link.category)
    if template is None:
        warn(ctx, f"未知 category @{link.category} (item: {item.name})", item.line)
        return []

    if link.inline:
        values = [link.value]
    else:
        values = lookup(ctx, item.name, link.category)
        if values is None:
            warn(ctx, f"@{link.category} 未在 Information 区（### [information]）中解析到 (item: {item.name})", item.line)
            return []

    values = as_list(values)
    question = template.format(key=item.name, value=values[0] if values else "")
    return [make_card(question, values, item.line)]
