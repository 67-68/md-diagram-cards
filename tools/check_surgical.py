#!/usr/bin/env python3
"""验证 inplace 的“外科手术式更新”。

重点保护 Anki Heading Sync 的 noteId marker：
- 没改的卡片块（包括 marker）保持原样；
- 改表头只影响引用该表头的卡片；
- 新增卡片不带旧 marker，删除卡片才丢 marker；
- AHS 写在 `<!-- END GENERATED -->` 后的最后一张卡 marker 也不会丢。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from md_diagram_cards.output import END_MARK, _split_card_chunks, convert_inplace  # noqa: E402

SOURCE = """### [d-orthogonal] situation

| 竞争者 | 战略目标 | 硬实力优势 |
| --- | --- | --- |
| Austria | preserve dominance | |
| Prussia | settle duchies | 6times steel |
"""


def _inject_ahs_markers(text: str, *, last_after_end: bool = False) -> str:
    """模拟 AHS 在主链写 marker 的形态，便于测试。"""
    lines = text.split("\n")
    begin = lines.index("<!-- BEGIN GENERATED -->")
    end = lines.index(END_MARK)
    chunks = _split_card_chunks(lines[begin + 1:end])

    body: list[str] = []
    next_note_id = 101
    last_note_id = 0

    for chunk_index, chunk in enumerate(chunks):
        while chunk and not chunk[-1].strip():
            chunk.pop()

        body.extend(chunk)
        is_last = chunk_index == len(chunks) - 1
        last_note_id = next_note_id
        if not (is_last and last_after_end):
            body.append(f"<!--ID: {next_note_id}-->")
        next_note_id += 1

        if chunk_index != len(chunks) - 1:
            body.append("")

    tail = [END_MARK]
    if last_after_end and chunks:
        tail.append(f"<!--ID: {last_note_id}-->")

    return "\n".join([*lines[: begin + 1], *body, *tail, *lines[end + 1:]])


def _check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition and detail:
        print(f"        {detail}")
    return condition


def main() -> int:
    failures = 0

    base, _ = convert_inplace(SOURCE).text, None
    marked = _inject_ahs_markers(base)

    # 1. 改一个表头：只重写引用该表头的两个 heading，其他卡片块不动。
    renamed = marked.replace("| 竞争者 | 战略目标 | 硬实力优势 |", "| 竞争者 | 战略目标2 | 硬实力优势 |")
    unchanged_after_rename, _ = convert_inplace(renamed).text, None
    failures += not _check(
        "表头改名后 marker 全部保留",
        all(marker in unchanged_after_rename for marker in ("<!--ID: 101-->", "<!--ID: 102-->", "<!--ID: 103-->")),
    )
    failures += not _check(
        "表头改名只影响两张相关卡片",
        unchanged_after_rename.count("[战略目标2] is?") == 2 and "[硬实力优势] is?" in unchanged_after_rename,
    )
    failures += not _check(
        "未涉及的卡片正文保持原样",
        "#### in [situation] [Prussia]'s [硬实力优势] is?\n- 6times steel\n<!--ID: 103-->" in unchanged_after_rename,
    )
    third, _ = convert_inplace(unchanged_after_rename).text, None
    failures += not _check("改动后再跑一次幂等", third == unchanged_after_rename)

    # 2. AHS 把最后一张卡的 marker 写在 END 后面时，不丢；后续重建时移到 END 前。
    trailing_marker = _inject_ahs_markers(base, last_after_end=True)
    unchanged_trailing, _ = convert_inplace(trailing_marker).text, None
    failures += not _check("END 后 marker 未变时不丢", unchanged_trailing == trailing_marker)

    edited_trailing = trailing_marker.replace(
        "| Prussia | settle duchies | 6times steel |",
        "| Prussia | settle duchies | 7times steel |",
    )
    rebuilt_trailing, _ = convert_inplace(edited_trailing).text, None
    failures += not _check(
        "重建后 END 后 marker 归到最后一张卡",
        "<!--ID: 103-->" in rebuilt_trailing
        and rebuilt_trailing.index("<!--ID: 103-->") < rebuilt_trailing.index(END_MARK),
    )

    # 3. 新增一列：旧 marker 全部保留，新卡片没有旧 marker。
    added_source = marked.replace("| 竞争者 | 战略目标 | 硬实力优势 |", "| 竞争者 | 战略目标 | 硬实力优势 | 经济 |")
    added_source = added_source.replace("| Austria | preserve dominance | |", "| Austria | preserve dominance | | poor |")
    added_source = added_source.replace("| Prussia | settle duchies | 6times steel |", "| Prussia | settle duchies | 6times steel | rich |")
    added, _ = convert_inplace(added_source).text, None
    failures += not _check(
        "新增列保留旧 marker",
        all(marker in added for marker in ("<!--ID: 101-->", "<!--ID: 102-->", "<!--ID: 103-->")),
    )
    failures += not _check(
        "新增列的新卡片没有旧 marker",
        "[经济] is?" in added and added.count("<!--ID:") == 3,
    )

    # 4. 给 diagram 添一条内容：新卡绝不继承旧 noteId，旧卡 marker 原位不动。
    #    回归：之前的“同序号 / 相似度”兜底会把新增卡配给另一张旧卡，于是
    #    新卡顶着一张已入库的 noteId（AHS 下次 sync 会 update 别人的 note），
    #    真正该保留 marker 的那张卡反而丢了身份、被重新 create 成重复卡。
    state_source = """### [d-state] S

- [t1] A
- [t2] B: db
"""
    state_marked = _inject_ahs_markers(convert_inplace(state_source).text, last_after_end=True)
    state_added = state_marked.replace("- [t1] A\n", "- [t1] A: da\n")
    state_result = convert_inplace(state_added).text

    failures += not _check(
        "新增卡（A means）不继承任何 noteId",
        "#### A means\n- da\n\n" in state_result,
    )
    failures += not _check(
        "新增内容时旧卡 marker 一张都不串位",
        all(
            chunk in state_result
            for chunk in (
                "#### [cloze] S\n- [t1] A\n- [t2] B\n<!--ID: 101-->",
                "#### A at\n- t1\n<!--ID: 102-->",
                "#### B at\n- t2\n<!--ID: 103-->",
                "#### B means\n- db\n<!--ID: 104-->",
            )
        ),
    )
    failures += not _check(
        "新增内容后 noteId 不重复",
        sorted(re.findall(r"<!--ID: (\d+)-->", state_result)) == ["101", "102", "103", "104"],
    )

    # 4b. 同一个文件里“加一条 + 改一条”最常见：新加的 Z at 不能抢走 A at 的 marker。
    mixed_source = """### [d-state] S

- [t1] A
- [t2] B
"""
    mixed_marked = _inject_ahs_markers(convert_inplace(mixed_source).text, last_after_end=True)
    mixed_edited = mixed_marked.replace("- [t1] A\n", "- [t9] Z\n- [t1] A2\n")
    mixed_result = convert_inplace(mixed_edited).text
    failures += not _check(
        "新加的卡不带 noteId",
        "#### Z at\n- t9\n\n" in mixed_result,
    )
    failures += not _check(
        "改名的卡仍保住自己的 noteId",
        "#### A2 at\n- t1\n<!--ID: 102-->" in mixed_result
        and "#### B at\n- t2\n<!--ID: 103-->" in mixed_result
        and "#### [cloze] S\n- [t9] Z\n- [t1] A2\n- [t2] B\n<!--ID: 101-->" in mixed_result,
    )

    # 5. 只改内容、题面没变：同一张卡的 marker 必须跟着走（AHS 走 update）。
    state_edited = state_marked.replace("- [t2] B: db\n", "- [t2] B: db edited\n")
    state_edited_result = convert_inplace(state_edited).text
    failures += not _check(
        "内容改写、题面不变的卡片保留原 marker",
        "#### B means\n- db edited\n<!--ID: 104-->" in state_edited_result,
    )

    print()
    if failures:
        print(f"FAILED: {failures} 项")
        return 1

    print("OK — surgical inplace behavior")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
