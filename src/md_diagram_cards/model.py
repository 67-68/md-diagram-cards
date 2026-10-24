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
class MediaField:
    """媒体列的一侧（front / back）：值从哪来、要不要套模板。

    三种写法对应三种 MediaField：

        front         → own=True                    本列单元格的值
        back=频段      → column="频段"                那一列的值，原样用
        front=频段(y)  → column="频段", template="频段(y)"  套模板

    模板里 `y`（或 `{value}`）是值占位符。
    """

    own: bool = False
    column: str = ""
    template: str = ""

    def render(self, value: str) -> str:
        """把一个值套进模板。没有模板就原样返回。"""
        if not self.template:
            return value
        if "{value}" in self.template:
            # 写了 {value} 就只认它，模板里其它的 y 保持原样。
            return self.template.replace("{value}", value)
        return self.template.replace("y", value)


@dataclass
class Column:
    """正交表的一列（表头单元格）。

    表头可以带 `@[front..., back...]` 标注，标成**媒体列**：

        | 效果 | 频段 | 例子音频@[front, back=频段] |
        | 效果 | 频段 | 例子音频@[back, front=频段(y)] |

    - ``header`` 是剥掉标注后的列名（题面、`=` 后面的列名都按它匹配）；
    - ``front`` / ``back`` 各自说明「题面」「答案」从哪来（见 MediaField）。

    媒体列**不出**普通的 `in [表题] [行实体]'s [列头] is?` 卡。
    """

    header: str = ""
    front: MediaField | None = None
    back: MediaField | None = None

    @property
    def is_media(self) -> bool:
        return self.front is not None or self.back is not None


@dataclass
class Row:
    """正交表的一行。values 与 columns[1:] 对齐（第 1 列被抽成 entity）。

    标了 `@exclude` 的行放在 ``Diagram.excluded`` 里：它不算进表格，
    只当辅助说明，一行卡都不出（``values`` 也不填）。
    """

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
    columns: list[Column] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    excluded: list[Row] = field(default_factory=list)  # 标了 @exclude、整行跳过的行

    @property
    def headers(self) -> list[str]:
        """各列的列名（已剥掉 `@[...]` 标注）。"""
        return [column.header for column in self.columns]


@dataclass
class Card:
    question: str
    answers: list[str] = field(default_factory=list)
    line: int = 0

    @property
    def is_cloze(self) -> bool:
        return len(self.answers) >= 2
