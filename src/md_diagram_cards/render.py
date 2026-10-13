"""渲染层 —— Card 列表 → markdown 文本。"""
from __future__ import annotations

from .model import Card


def render_card(card: Card) -> str:
    lines = [f"#### {card.question}"]
    lines.extend(f"- {answer}" for answer in card.answers)
    return "\n".join(lines)


def render_cards(cards: list[Card]) -> str:
    if not cards:
        return ""
    return "\n\n".join(render_card(card) for card in cards) + "\n"


def render_warnings(warnings: list[dict]) -> str:
    return "\n".join(f"<!-- WARNING: {w['message']} -->" for w in warnings)
