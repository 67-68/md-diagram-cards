#!/usr/bin/env python3
"""验证正交表的媒体列（表头 `@[front, back=列头]`）。

钉死的口径：
- 媒体列**不出**普通的 `in [表题] [行实体]'s [列头] is?` 卡；
- 题面 = `{列头}{单元格值}'s {back 列头} is?`，答案 = 同一行 back 列的值；
- 一行多个媒体（`<br>`）→ 一个媒体一张卡；答案多值 → 自动 `[cloze]`；
- 标注写坏（缺 front / 缺 back / back 列不存在 / 认不出的写法）→ 警告 + 不产卡；
- 标注只用于表头，不影响正文里的 `@cat` 外链。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from md_diagram_cards import convert  # noqa: E402

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
        "缺 back=列头",
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

print()
if failed:
    print(f"FAILED: {len(failed)} 项 → {', '.join(failed)}")
    raise SystemExit(1)
print("OK — 媒体列一切正常")
