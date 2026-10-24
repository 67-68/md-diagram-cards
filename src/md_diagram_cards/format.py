"""格式化层 —— 递归，任意层级可产卡。

formatting 函数由上级调用，不对应最小单元：
format_list 既产「整张图的卡」，又在内部调用更细的 format_item。
"""
from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import warn
from .model import Card, Column, Diagram, Item, Link, MediaField, Row

# Category → 问题模板。模板里用 `{key}` 表示项名，`{value}` 表示外链的值。
CATEGORY_TEMPLATES: dict[str, str] = {
    "condition": "{key}'s condition is?",
    "member_amount": "Member count of [{key}]",
    "place": "[{key}]的地点是 {value}",
    "effect": "{key}'s effect is?",
    "ability": "{key}'s ability is?",
    "position": "{key}'s position is?",
    "name": "{key}'s name is?",
}

#: 模板里允许出现的占位符。
CATEGORY_PLACEHOLDERS = ("key", "value")

#: 答案 >= 2 时给题面加的前缀。输出层要靠它认出“同一张卡换了个成卡形态”，
#: 所以只在这里定义一份。
CLOZE_PREFIX = "[cloze]"


def merge_categories(custom: dict[str, str] | None = None) -> dict[str, str]:
    """内置表 + 自定义表。自定义按 key **覆盖**内置（方便改写措辞）。"""
    return {**CATEGORY_TEMPLATES, **(custom or {})}


def category_template(ctx: dict, name: str) -> str | None:
    """取某个 category 的问题模板；优先用 ctx 里合并好的表。"""
    templates = ctx.get("categories")
    if not isinstance(templates, dict):
        templates = CATEGORY_TEMPLATES
    return templates.get(name)


# ---------------------------------------------------------------- 总出口

def make_card(question: str, answers: list[str], line: int = 0) -> Card:
    """所有卡片唯一的出口，cloze 判定只写这一遍。"""
    answers = [answer for answer in answers if answer]
    if len(answers) >= 2:
        question = f"{CLOZE_PREFIX} {question}"
    return Card(question=question, answers=answers, line=line)


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

def format_document(ctx: dict, categories: dict[str, str] | None = None) -> list[Card]:
    # 合并好的 category 表写进 context，format_link 直接从 ctx 取。
    if categories is not None or not isinstance(ctx.get("categories"), dict):
        ctx["categories"] = merge_categories(categories)

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
    """第 1 列是行实体，不出卡；其余每列各出一张「某行的这列是什么」。

    表头带 `@[front..., back...]` 标注的列是**媒体列**，不出普通卡，改由
    ``format_media_cards`` 产卡（见 spec §3.4）。
    """
    cards: list[Card] = []
    columns = diagram.columns[1:]

    # 媒体列先解析一遍：标注写坏只警告一次，不用每行重复喊。
    media_plans = [
        resolve_media_column(diagram, column, ctx) if column.is_media else None
        for column in columns
    ]

    for row in diagram.rows:
        if not row.entity:
            continue
        for index, column in enumerate(columns):
            values = row.values[index] if index < len(row.values) else []
            if not column.header or column.exclude:
                continue
            if column.is_media:
                plan = media_plans[index]
                if plan is not None:
                    cards.extend(format_media_cards(row, column, values, plan, ctx))
                continue
            if not values:
                continue
            question = f"in [{diagram.title}] [{row.entity}]'s [{column.header}] is?"
            cards.append(make_card(question, values, row.line))

    return cards


@dataclass
class MediaPlan:
    """解析好的媒体列：题面（front）和答案（back）各从哪来。

    index = -1 表示用本列的单元格；label 是题面里要写出来的列名。
    """

    front_index: int
    front_label: str
    front: MediaField
    back_index: int
    back_label: str


def resolve_media_column(diagram: Diagram, column: Column, ctx: dict) -> MediaPlan | None:
    """把媒体列的两个方向都解析成下标；标注写坏 → 警告 + 返回 None（整列不出卡）。"""
    hint = "（写法: @[front, back=列头] 或 @[back, front=列头(y)]）"

    if column.front is None:
        warn(ctx, f"媒体列 [{column.header}] 缺 front，整列不出卡{hint}", diagram.line)
        return None

    if column.back is None:
        warn(ctx, f"媒体列 [{column.header}] 缺 back，整列不出卡{hint}", diagram.line)
        return None

    front_index = resolve_media_side(diagram, column, column.front, "front", ctx)
    back_index = resolve_media_side(diagram, column, column.back, "back", ctx)
    if front_index is None or back_index is None:
        return None

    if column.back.template:
        warn(
            ctx,
            f"媒体列 [{column.header}] 的 back={column.back.column}(...) 不支持模板"
            "（答案必须是原文），模板已忽略",
            diagram.line,
        )

    return MediaPlan(
        front_index=front_index,
        front_label=column.header if front_index < 0 else diagram.columns[1:][front_index].header,
        front=column.front,
        back_index=back_index,
        back_label=column.header if back_index < 0 else diagram.columns[1:][back_index].header,
    )


def resolve_media_side(diagram: Diagram, column: Column, field: MediaField, side: str, ctx: dict) -> int | None:
    """一侧指向的列下标；-1 = 本列。指不到 → 警告 + None。"""
    if field.own:
        return -1

    for index, other in enumerate(diagram.columns[1:]):
        if other.header == field.column:
            return index

    if diagram.columns and diagram.columns[0].header == field.column:
        warn(
            ctx,
            f"媒体列 [{column.header}] 的 {side}={field.column} 是第 1 列（行实体），不能当值来源",
            diagram.line,
        )
        return None

    warn(ctx, f"媒体列 [{column.header}] 的 {side}={field.column} 找不到同名列", diagram.line)
    return None


def format_media_cards(
    row: Row, column: Column, own_values: list[str], plan: MediaPlan, ctx: dict
) -> list[Card]:
    """媒体列：题面里放 front 那一侧的值，答案取 back 那一侧的值。

    - 本列这一格是空的 → 这一行没有例子，安静跳过；
    - front 引用了别的列、而那一列这行是空的 → 警告 + 跳过；
    - 答案那侧是空的（有例子没答案，多半是漏填）→ 警告 + 跳过；
    - 题面里的值有多个（`<br>`）→ 一个值一张卡；答案多值 → 自动 `[cloze]`。
    """
    if not own_values:
        return []

    if plan.front_index < 0:
        front_values = own_values
    else:
        front_values = _row_values(row, plan.front_index)
        if not front_values:
            warn(
                ctx,
                f"媒体列 [{column.header}] 的 front={plan.front.column} 这一行是空的，已跳过（行: {row.entity}）",
                row.line,
            )
            return []

    answers = own_values if plan.back_index < 0 else _row_values(row, plan.back_index)
    if not answers:
        warn(
            ctx,
            f"媒体列 [{column.header}] 的答案列 [{plan.back_label}] 这一行是空的，已跳过（行: {row.entity}）",
            row.line,
        )
        return []

    # 有模板时模板本身就是完整题面，不再加列名前缀。
    prefix = "" if plan.front.template else plan.front_label

    return [
        make_card(f"{prefix}{plan.front.render(value)}'s {plan.back_label} is?", answers, row.line)
        for value in front_values
    ]


def _row_values(row: Row, index: int) -> list[str]:
    return row.values[index] if index < len(row.values) else []


# ---------------------------------------------------------------- 外链

def format_link(link: Link, item: Item, ctx: dict) -> list[Card]:
    if link.category == "exclude":
        warn(ctx, "@exclude 目前只对正交表的行生效（写在某行第 1 列），列表条目上写了不会跳过", item.line)
        return []

    if link.category == "custom":
        values = lookup(ctx, item.name, link.value)
        if values is None:
            warn(ctx, f"@custom({link.value}) 未在 Information 区（### [information]）中解析到 (item: {item.name})", item.line)
            return []
        return [make_card(f"[{link.value}] for [{item.name}]", as_list(values), item.line)]

    template = category_template(ctx, link.category)
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

    try:
        question = template.format(key=item.name, value=values[0] if values else "")
    except (KeyError, IndexError, ValueError) as error:
        allowed = " / ".join("{" + name + "}" for name in CATEGORY_PLACEHOLDERS)
        warn(
            ctx,
            f"category @{link.category} 的模板占位符有误（只支持 {allowed}）：{template!r} ({error})",
            item.line,
        )
        return []

    return [make_card(question, values, item.line)]
