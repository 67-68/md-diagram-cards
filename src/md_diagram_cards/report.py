"""转换报告 —— 一次转换到底看到了什么、产出了什么。

CLI 的 `--report json` 和 Obsidian 插件的日志都吃这个结构：
"提示成功但什么都没生成" 这类问题只能靠它定位。
"""
from __future__ import annotations

from dataclasses import dataclass, field

KIND_LABELS = {
    "state": "d-state 时间线/状态机",
    "tree": "d-tree 树状图",
    "orthogonal": "d-orthogonal 正交表",
}

NO_DIAGRAM_HINT = (
    "没有找到任何 [d-state] / [d-tree] / [d-orthogonal] 结构。"
    "标记要写在标题开头，例如 `### [d-state] Before 7 week war`；"
    "不带标记的普通标题不出卡。"
)

NO_CARD_HINT = (
    "找到了结构但没产出卡片 —— 正文多半是空的，"
    "或者表格缺表头 / 第 1 列（行实体）为空（表格每行都要以 `|` 开头和结尾）。"
)


@dataclass
class DiagramSummary:
    """一张结构图解析出了什么。line 是 1-based 的行号。"""

    kind: str
    title: str
    line: int
    cards: int

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "kind_label": self.kind_label,
            "title": self.title,
            "line": self.line,
            "cards": self.cards,
        }


@dataclass
class Conversion:
    """一次转换的产物 + 诊断。"""

    text: str = ""
    warnings: list[dict] = field(default_factory=list)
    diagrams: list[DiagramSummary] = field(default_factory=list)

    @property
    def diagram_count(self) -> int:
        return len(self.diagrams)

    @property
    def card_count(self) -> int:
        return sum(diagram.cards for diagram in self.diagrams)

    @property
    def empty_diagrams(self) -> list[DiagramSummary]:
        return [diagram for diagram in self.diagrams if diagram.cards == 0]

    @property
    def hints(self) -> list[str]:
        """给用户看的下一步提示 —— 只在真的可疑时才出现。"""
        if self.diagram_count == 0:
            return [NO_DIAGRAM_HINT]

        if self.card_count == 0:
            return [NO_CARD_HINT]

        empty = self.empty_diagrams
        if empty:
            titles = "、".join(diagram.title or "(无标题)" for diagram in empty[:3])
            more = f" 等 {len(empty)} 个" if len(empty) > 3 else ""
            return [f"有 {len(empty)} 个结构没产出卡片：{titles}{more}（正文或表格是空的？）"]

        return []

    def to_dict(self, **extra) -> dict:
        payload = {
            "diagram_count": self.diagram_count,
            "card_count": self.card_count,
            "diagrams": [diagram.to_dict() for diagram in self.diagrams],
            "warnings": self.warnings,
            "hints": self.hints,
        }
        payload.update(extra)
        return payload
