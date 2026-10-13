"""把 md 文本 parse 成卡片。"""
from .format import format_document
from .model import Card, Diagram, Inference, Item, Link, Row
from .output import convert_inplace, convert_new_file
from .parse import parse_document
from .render import render_cards
from .report import Conversion, DiagramSummary

__all__ = [
    "Card",
    "Conversion",
    "Diagram",
    "DiagramSummary",
    "Inference",
    "Item",
    "Link",
    "Row",
    "convert",
    "convert_inplace",
    "convert_new_file",
    "format_document",
    "parse_document",
    "render_cards",
]


def convert(text: str) -> tuple[str, list[dict]]:
    """文本 → (卡片 markdown, 警告列表)。"""
    ctx = parse_document(text)
    return render_cards(format_document(ctx)), ctx["warnings"]
