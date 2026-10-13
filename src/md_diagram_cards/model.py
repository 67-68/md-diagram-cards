"""数据类型 —— 纯数据结构，不含逻辑。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Link:
    """一条外链。

    三种合法形态：
      @cat            → category="cat", inline=False, value 从 Information 查
      @cat: value     → category="cat", inline=True,  value="value"
      @custom(KEY)    → category="custom", inline=False, value="KEY"
    """

    category: str
    value: str = ""
    inline: bool = False

    def __str__(self) -> str:
        if self.category == "custom":
            return f"@custom({self.value})"
        if self.inline:
            return f"@{self.category}: {self.value}"
        return f"@{self.category}"


@dataclass
class Item:
    """一个被记录的内容：key + description + 外链。

    time 非空表示带 [时间] 前缀（只出现在 [d-state]）。
    children 非空表示树状图的子节点（只出现在 [d-tree]）。
    """

    name: str
    time: str = ""
    desc: str = ""
    links: list[Link] = field(default_factory=list)
    children: list["Item"] = field(default_factory=list)
    indent: int = 0
    line: int = 0

    @property
    def key(self) -> str:
        """全局寻址名（不含时间前缀）。"""
        return self.name

    @property
    def label(self) -> str:
        """完整标签（含时间前缀），用于「分组卡」的答案。"""
        return f"[{self.time}] {self.name}" if self.time else self.name


@dataclass
class Inference:
    """推论行 `=> X =>`，夹在 items[prev_index] 与 items[prev_index+1] 之间。"""

    text: str
    prev_index: int
    line: int = 0


@dataclass
class Row:
    """正交表的一行。values 与 headers[1:] 对齐（第 1 列被抽成 entity）。"""

    entity: str
    values: list[list[str]] = field(default_factory=list)
    line: int = 0


@dataclass
class Diagram:
    """一个 [d-*] 结构。"""

    kind: str  # "state" | "tree" | "orthogonal"
    title: str = ""
    line: int = 0
    end_line: int = 0  # 本块结束行（下一个标题所在行）
    # state / tree
    items: list[Item] = field(default_factory=list)
    inferences: list[Inference] = field(default_factory=list)
    # orthogonal
    headers: list[str] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)


@dataclass
class Card:
    question: str
    answers: list[str] = field(default_factory=list)
    line: int = 0

    @property
    def is_cloze(self) -> bool:
        return len(self.answers) >= 2
