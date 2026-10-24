#!/usr/bin/env python3
"""验证正交表的两条「表格专属」规矩。

媒体列（表头 `@[front, back=列头]`）：
- 媒体列**不出**普通的 `in [表题] [行实体]'s [列头] is?` 卡；
- 题面 = `{列头}{单元格值}'s {back 列头} is?`，答案 = 同一行 back 列的值；
- 一行多个媒体（`<br>`）→ 一个媒体一张卡；答案多值 → 自动 `[cloze]`；
- 标注写坏（缺 front / 缺 back / back 列不存在 / 认不出的写法）→ 警告 + 不产卡；
- 标注只用于表头，不影响正文里的 `@cat` 外链。

`@exclude`（标了什么就整个跳过什么）：
- 表头标了 `@exclude`（`备注@exclude` / `备注@[exclude]`）→ **整列不出卡**；
- 第 1 列（行实体）标了 `@exclude` → **整行不出卡**，普通卡和媒体卡都不出；
- 行不进入 `diagram.rows`，列不参与产卡；报告里分别计 `excluded` / `excluded_columns`；
- 行标在别的列 → 警告（会被当成正文）；写在列表条目上 → 警告（只支持表格）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from md_diagram_cards import convert  # noqa: E402
from md_diagram_cards.output import convert_inplace  # noqa: E402

HEAD = "### [d-orthogonal] T\n\n"

failed: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        failed.append(label)
        if detail:
            print(f"        {detail}")


def _questions(cards: str) -> list[str]:
    return [line[len("#### "):] for line in cards.split("\n") if line.startswith("#### ")]


print("媒体列产卡")
cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[front, back=频段] |
| --- | --- | --- |
| 沉闷 | 低频 | muddy-01.mp3 |
| 明亮 | 中高频<br>高频 | bright-01.mp3<br>air-01.mp3 |
"""
)
_check("无警告", warnings == [], f"{warnings}")
_check(
    "媒体列不出普通卡（没有「效果's 例子音频」）",
    not any("例子音频] is?" in question for question in _questions(cards)),
    f"{_questions(cards)}",
)
_check(
    "题面 = 列头+音频文件名+'s 频段 is?",
    "#### 例子音频muddy-01.mp3's 频段 is?\n- 低频" in cards,
    cards,
)
_check(
    "一个媒体一张卡（两个音频 → 两张卡）",
    "#### [cloze] 例子音频bright-01.mp3's 频段 is?" in cards
    and "#### [cloze] 例子音频air-01.mp3's 频段 is?" in cards,
    cards,
)
_check(
    "答案多值 → cloze",
    "#### [cloze] 例子音频air-01.mp3's 频段 is?\n- 中高频\n- 高频" in cards,
    cards,
)
_check(
    "普通列照旧出卡",
    "#### in [T] [沉闷]'s [频段] is?\n- 低频" in cards
    and "#### [cloze] in [T] [明亮]'s [频段] is?\n- 中高频\n- 高频" in cards,
    cards,
)

print("\n空值")
cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[front, back=频段] |
| --- | --- | --- |
| 沉闷 | 低频 | |
"""
)
_check("媒体格为空 → 该行不出媒体卡（也不报警）", "例子音频" not in cards and warnings == [], f"{cards} / {warnings}")

print("\n标注写坏 → 警告 + 不产卡")
cases = {
    "缺 front": (
        "| 效果 | 频段 | 例子音频@[back=频段] |\n| --- | --- | --- |\n| 沉闷 | 低频 | a.mp3 |\n",
        "缺 front",
    ),
    "缺 back": (
        "| 效果 | 频段 | 例子音频@[front] |\n| --- | --- | --- |\n| 沉闷 | 低频 | a.mp3 |\n",
        "缺 back",
    ),
    "back 列不存在": (
        "| 效果 | 频段 | 例子音频@[front, back=音色] |\n| --- | --- | --- |\n| 沉闷 | 低频 | a.mp3 |\n",
        "找不到同名列",
    ),
    "认不出的写法": (
        "| 效果 | 频段 | 例子音频@[front, foo] |\n| --- | --- | --- |\n| 沉闷 | 低频 | a.mp3 |\n",
        "认不出的写法",
    ),
    "back 指向行实体列": (
        "| 效果 | 频段 | 例子音频@[front, back=效果] |\n| --- | --- | --- |\n| 沉闷 | 低频 | a.mp3 |\n",
        "行实体",
    ),
    "答案列这行是空的": (
        "| 效果 | 频段 | 例子音频@[front, back=频段] |\n| --- | --- | --- |\n| 沉闷 | | a.mp3 |\n",
        "是空的",
    ),
}
for label, (table, expected_hint) in cases.items():
    cards, warnings = convert(HEAD + table)
    _check(
        f"{label} → 警告里有「{expected_hint}」",
        any(expected_hint in warning["message"] for warning in warnings),
        f"{warnings}",
    )
    _check(f"{label} → 媒体列不产普通卡", "例子音频] is?" not in cards, f"{cards}")

print("\n第 1 列是行实体，标了也忽略")
cards, warnings = convert(
    HEAD + "| 效果@[front, back=频段] | 频段 |\n| --- | --- |\n| 沉闷 | 低频 |\n"
)
_check("第 1 列标注 → 警告", any("行实体" in warning["message"] for warning in warnings), f"{warnings}")
_check("第 1 列标注不影响其余卡片", cards == "#### in [T] [沉闷]'s [频段] is?\n- 低频\n", f"{cards!r}")

print("\n表头标注只对表头生效，不影响别处的 @ 外链")
cards, warnings = convert(
    """### [d-orthogonal] T

| 效果 | 频段 | 例子音频@[front, back=频段] |
| --- | --- | --- |
| 沉闷 | 低频 | a.mp3 |

### [d-state] S

- Biarritz meeting @condition: France neutralized
"""
)
_check(
    "同一个文件里的 @condition 外链照旧出卡",
    "#### Biarritz meeting's condition is?\n- France neutralized" in cards,
    f"{cards}",
)
_check("仍然无警告", warnings == [], f"{warnings}")

print("\n认不出的写法 + front/back 都在 → 警告但不影响这一列")
cards, warnings = convert(
    HEAD + "| 效果 | 频段 | 例子音频@[front, back=频段, foo] |\n| --- | --- | --- |\n| 沉闷 | 低频 | a.mp3 |\n"
)
_check("认不出的写法 → 警告", any("认不出的写法" in warning["message"] for warning in warnings), f"{warnings}")
_check("能认出的部分照常产卡", "#### 例子音频a.mp3's 频段 is?\n- 低频" in cards, f"{cards}")

print("\n反向写法：值进答案、题面由别的列拼出来")
BACK_TABLE = """| 效果 | 频段 | 例子音频@[back, front=频段(y)] |
| --- | --- | --- |
| 沉闷 | 低频 | muddy-01.mp3 |
| 明亮 | 高频 | bright-01.mp3 |
"""
cards, warnings = convert(HEAD + BACK_TABLE)
_check("无警告", warnings == [], f"{warnings}")
_check(
    "题面 = 频段(低频)'s 例子音频 is?",
    "#### 频段(低频)'s 例子音频 is?\n- muddy-01.mp3" in cards,
    f"{cards}",
)
_check(
    "答案就是本列（媒体列）的值",
    "#### 频段(高频)'s 例子音频 is?\n- bright-01.mp3" in cards,
    f"{cards}",
)
_check(
    "反向写法同样不出普通表格卡",
    not any("例子音频] is?" in question for question in _questions(cards)),
    f"{_questions(cards)}",
)
_check(
    "两种方向可以共存：这一列反向，另一列正向",
    len(_questions(cards)) == 4,
    f"{_questions(cards)}",
)

cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[front, back=频段] | 反向音频@[back, front=频段(y)] |
| --- | --- | --- | --- |
| 沉闷 | 低频 | a.mp3 | b.mp3 |
"""
)
_check(
    "同一张表里正反两种媒体列同时工作",
    "#### 例子音频a.mp3's 频段 is?\n- 低频" in cards
    and "#### 频段(低频)'s 反向音频 is?\n- b.mp3" in cards,
    f"{cards}",
)

cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[back, front=频段(y)] |
| --- | --- | --- |
| 沉闷 | 低频<br>中频 | a.mp3 |
"""
)
_check(
    "front 引用的列多值 → 一个值一张卡",
    "#### 频段(低频)'s 例子音频 is?\n- a.mp3" in cards
    and "#### 频段(中频)'s 例子音频 is?\n- a.mp3" in cards,
    f"{cards}",
)

cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[back, front=频段(y)] |
| --- | --- | --- |
| 沉闷 |  | a.mp3 |
"""
)
_check(
    "front 引用的列这行为空 → 警告 + 跳过",
    any("front=频段 这一行是空的" in warning["message"] for warning in warnings) and "例子音频" not in cards,
    f"{warnings} / {cards}",
)

cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[back, front=频段(x)] |
| --- | --- | --- |
| 沉闷 | 低频 | a.mp3 |
"""
)
_check(
    "模板里没有 y → 警告（值不会出现在题面里）",
    any("没有 y 占位符" in warning["message"] for warning in warnings),
    f"{warnings}",
)

cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[back, front=频段(约 {value})] |
| --- | --- | --- |
| 沉闷 | 低频 | a.mp3 |
"""
)
_check(
    "{value} 也能当占位符（题面里有 y 字面量时用它）",
    "#### 频段(约 低频)'s 例子音频 is?\n- a.mp3" in cards,
    f"{cards}",
)

cards, warnings = convert(
    HEAD
    + """| 效果 | 频段 | 例子音频@[back, front=频段(y), back=频段(约 y)] |
| --- | --- | --- |
| 沉闷 | 低频 | a.mp3 |
"""
)
_check(
    "同一侧写两次 → 警告",
    any("写了不止一次" in warning["message"] for warning in warnings),
    f"{warnings}",
)

print("\n@exclude：整行不算进表格")
EXCLUDED_TABLE = """| 效果 | 频段 | 例子音频@[front, back=频段] |
| --- | --- | --- |
| 沉闷 | 低频 | muddy-01.mp3 |
| 备注 @exclude | 只是辅助理解 | ambient.mp3 |
| 明亮 | 高频 | bright-01.mp3 |
"""
cards, warnings = convert(HEAD + EXCLUDED_TABLE)
_check("没有警告", warnings == [], f"{warnings}")
_check(
    "被排除的行一张卡都不出（普通卡 + 媒体卡都没有）",
    "沉闷" in cards
    and "明亮" in cards
    and "备注" not in cards
    and "ambient" not in cards
    and len(_questions(cards)) == 4,
    f"{cards}",
)
_check(
    "其余行照常出卡",
    "#### in [T] [沉闷]'s [频段] is?\n- 低频" in cards
    and "#### 例子音频bright-01.mp3's 频段 is?\n- 高频" in cards,
    f"{cards}",
)
_check(
    "@exclude 不占行实体（不会因为排除行把别行挤错）",
    "#### in [T] [备注]'s [频段] is?" not in cards and "@exclude" not in cards,
    f"{cards}",
)

cards, warnings = convert(HEAD + EXCLUDED_TABLE)
conversion = convert_inplace(HEAD + EXCLUDED_TABLE)
_check("报告里 excluded 计数 = 1", conversion.to_dict()["diagrams"][0]["excluded"] == 1, f"{conversion.to_dict()}")
_check("部分排除不产生提示", conversion.hints == [], f"{conversion.hints}")

conversion = convert_inplace(HEAD + """| 效果 | 频段 |
| --- | --- |
| a @exclude | x |
| b @exclude | y |
""")
_check("全排除 → 0 张卡 + 专门的提示", conversion.card_count == 0 and "@exclude" in conversion.hints[0], f"{conversion.hints}")

print("\n@exclude：整列不算进卡片")
COLUMN_TABLE = """| 效果 | 频段 | 备注@exclude | 例子音频@[back, front=频段(y)] |
| --- | --- | --- | --- |
| 沉闷 | 低频 | 自己记的：偏闷 | muddy-01.mp3 |
| 明亮 | 高频 | 自己记的：有点刺 | bright-01.mp3 |
"""
cards, warnings = convert(HEAD + COLUMN_TABLE)
_check("无警告", warnings == [], f"{warnings}")
_check(
    "被排除的列一张卡都不出",
    "备注" not in cards and "自己记的" not in cards,
    f"{cards}",
)
_check(
    "其余列照常出卡",
    "#### in [T] [沉闷]'s [频段] is?\n- 低频" in cards
    and "#### 频段(低频)'s 例子音频 is?\n- muddy-01.mp3" in cards,
    f"{cards}",
)
_check("列排除后卡数正确（2 行 × 2 列）", len(_questions(cards)) == 4, f"{_questions(cards)}")

conversion = convert_inplace(HEAD + COLUMN_TABLE)
diagram = conversion.to_dict()["diagrams"][0]
_check("报告里 excluded_columns = 1", diagram["excluded_columns"] == 1, f"{diagram}")
_check("列排除不算「行排除」", diagram["excluded"] == 0, f"{diagram}")
_check("报告摘要带「跳过 1 列」", "跳过 1 列" in conversion.excluded_note, conversion.excluded_note)

cards, warnings = convert(
    HEAD + """| 效果 | 频段 | 备注@[exclude] |
| --- | --- | --- |
| 沉闷 | 低频 | note |
"""
)
_check("括号写法 @[exclude] 等价", "备注" not in cards and "note" not in cards, f"{cards}")

cards, warnings = convert(
    HEAD + """| 效果 | 频段 | 例子音频@[front, back=频段, exclude] |
| --- | --- | --- |
| 沉闷 | 低频 | a.mp3 |
"""
)
_check(
    "@exclude 和 @[...] 同时写 → 警告 + 整列不出卡",
    any("同时写了 @exclude" in warning["message"] for warning in warnings) and "a.mp3" not in cards,
    f"{warnings} / {cards}",
)

cards, warnings = convert(
    HEAD + """| 效果@exclude | 频段 |
| --- | --- |
| 沉闷 | 低频 |
"""
)
_check(
    "第 1 列写 @exclude → 警告（本来就不出卡）",
    any("本来就不出卡" in warning["message"] for warning in warnings),
    f"{warnings}",
)
_check("第 1 列写 @exclude 不影响其余卡片", "#### in [T] [沉闷]'s [频段] is?\n- 低频" in cards, f"{cards}")

cards, warnings = convert(
    HEAD + """| 效果 | 频段 | 备注@exclude | 例子音频@[back, front=备注(y)] |
| --- | --- | --- | --- |
| 沉闷 | 低频 | 偏闷 | a.mp3 |
"""
)
_check(
    "被排除的列仍可以当值来源",
    "#### 偏闷(y)'s 例子音频 is?" in cards or "#### 备注(偏闷)'s 例子音频 is?" in cards,
    f"{cards}",
)

print("\n@exclude 写错地方")
cards, warnings = convert(HEAD + """| 效果 | 频段 | 例子音频@[front, back=频段] |
| --- | --- | --- |
| 沉闷 | 低频 | a.mp3 @exclude |
""")
_check(
    "写在别的列 → 警告（那列照旧是正文）",
    any("只对第 1 列" in warning["message"] for warning in warnings),
    f"{warnings}",
)

cards, warnings = convert("### [d-state] S\n\n- [t1] A @exclude\n- [t2] B\n")
_check(
    "写在列表条目上 → 警告说只支持表格行",
    any("只对正交表的行生效" in warning["message"] for warning in warnings),
    f"{warnings}",
)
_check("列表条目不会被跳过", "#### A at\n- t1" in cards, f"{cards}")

print()
if failed:
    print(f"FAILED: {len(failed)} 项 → {', '.join(failed)}")
    raise SystemExit(1)
print("OK — 正交表规矩一切正常")
