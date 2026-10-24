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


NOTE_ID_RE = re.compile(r"^\s*<!--\s*ID:\s*(\d+)\s*-->\s*$")


def _inject_ahs_markers(text: str, *, last_after_end: bool = False) -> str:
    """模拟 AHS 在主链写 marker 的形态，便于测试。

    真实的 AHS 会**复用**已有 marker，只给还没有身份的新卡发号，所以这里
    也照做：已经有 `<!--ID: n-->` 的卡片原样保留，编号从已有的最大号往后排。
    """
    lines = text.split("\n")
    begin = lines.index("<!-- BEGIN GENERATED -->")
    end = lines.index(END_MARK)
    chunks = _split_card_chunks(lines[begin + 1:end])

    body: list[str] = []
    # 已经有身份的卡片先占号，新卡从“已有的最大号 + 1”往后发，避免撞号。
    known_ids = [int(m.group(1)) for chunk in chunks for line in chunk if (m := NOTE_ID_RE.match(line))]
    next_note_id = max([101, *(known_id + 1 for known_id in known_ids)])
    last_note_id = 0

    for chunk_index, chunk in enumerate(chunks):
        while chunk and not chunk[-1].strip():
            chunk.pop()

        existing = [int(match.group(1)) for line in chunk if (match := NOTE_ID_RE.match(line))]
        is_last = chunk_index == len(chunks) - 1

        body.extend(chunk)

        if existing:
            last_note_id = existing[-1]
            next_note_id = max(next_note_id, last_note_id + 1)
        else:
            last_note_id = next_note_id
            if not (is_last and last_after_end):
                body.append(f"<!--ID: {next_note_id}-->")
            next_note_id += 1

        if not is_last:
            body.append("")

    tail = [END_MARK]
    if last_after_end and chunks:
        tail.append(f"<!--ID: {last_note_id}-->")

    # END 后面原本可能已经躺着一个 marker（上一次 AHS 写的），重排后由上面重新发。
    leftovers = [line for line in lines[end + 1:] if not NOTE_ID_RE.match(line)]

    return "\n".join([*lines[: begin + 1], *body, *tail, *leftovers])


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

    # 6. 给已有表格加一个媒体列（`列头@[front, back=列头]`）：
    #    旧卡的 marker 留在原卡上，新产出的媒体卡不带 marker。
    media_source = """### [d-orthogonal] bands

| 效果 | 频段 |
| --- | --- |
| 沉闷 | low |
| 明亮 | high |
"""
    media_marked = _inject_ahs_markers(convert_inplace(media_source).text, last_after_end=True)
    media_added = (
        media_marked
        .replace("| 效果 | 频段 |", "| 效果 | 频段 | 例子音频@[front, back=频段] |")
        .replace("| 沉闷 | low |", "| 沉闷 | low | low-01.mp3 |")
        .replace("| 明亮 | high |", "| 明亮 | high | high-01.mp3 |")
    )
    media_result = convert_inplace(media_added).text

    failures += not _check(
        "新增媒体列后旧 marker 原位不动",
        "#### in [bands] [沉闷]'s [频段] is?\n- low\n<!--ID: 101-->" in media_result
        and "#### in [bands] [明亮]'s [频段] is?\n- high\n<!--ID: 102-->" in media_result,
    )
    failures += not _check(
        "新增的媒体卡不带旧 marker",
        "#### 例子音频low-01.mp3's 频段 is?\n- low\n\n" in media_result
        and "#### 例子音频high-01.mp3's 频段 is?\n- high\n" in media_result
        and sorted(re.findall(r"<!--ID: (\d+)-->", media_result)) == ["101", "102"],
    )
    failures += not _check(
        "媒体列不出「效果's 例子音频 is?」这种卡",
        "例子音频] is?" not in media_result,
    )

    # 6b. 媒体卡入库之后：只改答案列的值（题面没变）→ 媒体卡保住 marker。
    media_synced = _inject_ahs_markers(media_result, last_after_end=True)
    media_tuned = media_synced.replace("| 沉闷 | low |", "| 沉闷 | low freq |")
    media_tuned_result = convert_inplace(media_tuned).text
    failures += not _check(
        "答案改写、题面不变 → 媒体卡与普通卡都保住 marker",
        "#### in [bands] [沉闷]'s [频段] is?\n- low freq\n<!--ID: 101-->" in media_tuned_result
        and "#### 例子音频low-01.mp3's 频段 is?\n- low freq\n<!--ID: 103-->" in media_tuned_result
        and "#### 例子音频high-01.mp3's 频段 is?\n- high\n<!--ID: 104-->" in media_tuned_result,
    )

    # 6c. 只改音频文件名、答案没变 → 视作“改名”，marker 跟着走（AHS 走 update）。
    media_renamed = media_synced.replace("| 明亮 | high | high-01.mp3 |", "| 明亮 | high | high-01b.mp3 |")
    media_renamed_result = convert_inplace(media_renamed).text
    failures += not _check(
        "换音频文件名（答案没变）→ marker 跟着走",
        "#### 例子音频high-01b.mp3's 频段 is?\n- high\n<!--ID: 104-->" in media_renamed_result,
    )

    # 6d. 音频和答案都换了 → 判不准，一律当新卡：新卡不带任何旧 marker。
    media_replaced = media_synced.replace("| 明亮 | high | high-01.mp3 |", "| 明亮 | mid | high-02.mp3 |")
    media_replaced_result = convert_inplace(media_replaced).text
    failures += not _check(
        "音频和答案都换了 → 新卡不带 marker，旧 marker 丢弃",
        "#### 例子音频high-02.mp3's 频段 is?\n- mid\n<!-- END GENERATED -->" in media_replaced_result
        and sorted(re.findall(r"<!--ID: (\d+)-->", media_replaced_result)) == ["101", "102", "103"],
    )

    # 7. 给某一行加 @exclude：那一行的卡（连 marker）一起消失，别的卡 marker 原位不动。
    excluded_source = media_synced.replace("| 明亮 | high | high-01.mp3 |", "| 明亮 @exclude | high | high-01.mp3 |")
    excluded_result = convert_inplace(excluded_source).text
    excluded_generated = excluded_result.split("<!-- BEGIN GENERATED -->")[1] if "<!-- BEGIN GENERATED -->" in excluded_result else ""

    failures += not _check(
        "@exclude 那一行的卡被删掉（普通卡 + 媒体卡）",
        "明亮" not in excluded_generated and "high-01" not in excluded_generated,
        excluded_generated,
    )
    failures += not _check(
        "@exclude 不影响其他行的 marker",
        "#### in [bands] [沉闷]'s [频段] is?\n- low\n<!--ID: 101-->" in excluded_result
        and "#### 例子音频low-01.mp3's 频段 is?\n- low\n<!--ID: 103-->" in excluded_result,
        excluded_result,
    )

    # 8. 反向媒体列（@[back, front=列头(y)]）同样按卡保 marker：
    #    加一行 → 旧 marker 原位不动；只改音频文件名（题面不变）→ marker 保住。
    back_source = """### [d-orthogonal] bands

| 效果 | 频段 | 例子音频@[back, front=频段(y)] |
| --- | --- | --- |
| 沉闷 | low | a.mp3 |
| 明亮 | high | b.mp3 |
"""
    back_marked = _inject_ahs_markers(convert_inplace(back_source).text, last_after_end=True)
    back_added = convert_inplace(back_marked.replace("| 明亮 | high | b.mp3 |", "| 明亮 | high | b.mp3 |\n| 中性 | mid | c.mp3 |")).text
    failures += not _check(
        "反向媒体列：加一行后旧 marker 一张不串位",
        all(
            chunk in back_added
            for chunk in (
                "#### in [bands] [沉闷]'s [频段] is?\n- low\n<!--ID: 101-->",
                "#### 频段(low)'s 例子音频 is?\n- a.mp3\n<!--ID: 102-->",
                "#### in [bands] [明亮]'s [频段] is?\n- high\n<!--ID: 103-->",
                "#### 频段(high)'s 例子音频 is?\n- b.mp3\n<!--ID: 104-->",
            )
        )
        and sorted(re.findall(r"<!--ID: (\d+)-->", back_added)) == ["101", "102", "103", "104"],
        back_added,
    )

    back_edited = convert_inplace(back_marked.replace("| 沉闷 | low | a.mp3 |", "| 沉闷 | low | a2.mp3 |")).text
    failures += not _check(
        "反向媒体列：只改音频文件名 → 题面不变，marker 保住",
        "#### 频段(low)'s 例子音频 is?\n- a2.mp3\n<!--ID: 102-->" in back_edited,
        back_edited,
    )

    # 9. 给某一列加 @exclude：那一列的卡（连 marker）一起消失，别的列 marker 原位不动。
    column_excluded = media_synced.replace("例子音频@[front, back=频段]", "例子音频@exclude")
    column_excluded_result = convert_inplace(column_excluded).text
    column_generated = (
        column_excluded_result.split("<!-- BEGIN GENERATED -->")[1]
        if "<!-- BEGIN GENERATED -->" in column_excluded_result
        else ""
    )

    failures += not _check(
        "@exclude 那一列的卡被删掉（媒体卡不再产出）",
        "例子音频" not in column_generated,
        column_generated,
    )
    failures += not _check(
        "@exclude 列不影响别的列的 marker",
        "#### in [bands] [沉闷]'s [频段] is?\n- low\n<!--ID: 101-->" in column_excluded_result
        and "#### in [bands] [明亮]'s [频段] is?\n- high\n<!--ID: 102-->" in column_excluded_result
        and sorted(re.findall(r"<!--ID: (\d+)-->", column_excluded_result)) == ["101", "102"],
        column_excluded_result,
    )

    print()
    if failures:
        print(f"FAILED: {failures} 项")
        return 1

    print("OK — surgical inplace behavior")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
