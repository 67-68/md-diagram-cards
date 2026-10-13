"""把 md 文本 parse 成卡片。"""
from .format import format_document
from .model import Card, Diagram, Inference, Item, Link, Row
from .parse import parse_document
from .render import render_cards

__all__ = [
    "Card",
    "Diagram",
    "Inference",
    "Item",
    "Link",
    "Row",
    "parse_document",
    "format_document",
    "render_cards",
]


def convert(text: str) -> tuple[str, list[dict]]:
    """文本 → (卡片 markdown, 警告列表)。"""
    ctx = parse_document(text)
    return render_cards(format_document(ctx)), ctx["warnings"]
