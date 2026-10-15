"""输出层 —— 幂等的就地插入 / 新文件模式。

就地插入的形态：

    ### [d-state] Before 7 week war
    - [1865 Oct] Biarritz meeting

    <!-- BEGIN GENERATED -->
    #### [cloze] Before 7 week war
    - [1865 Oct] Biarritz meeting
    <!-- END GENERATED -->

重复执行时只重写发生变化的 diagram 区块；没变化的卡片块（包括
Anki Heading Sync 写在卡片末尾的 ``<!--ID: ...-->`` 标记）保持原样。
这样下一次 sync 能靠稳定 noteId 增量更新，而不是新建重复卡片。
"""
from __future__ import annotations

import pathlib
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .format import format_diagram, merge_categories
from .parse import DIAGRAM_MARKER_RE, HEADING_RE, parse_document
from .render import render_card, render_cards
from .report import Conversion, DiagramSummary

BEGIN_MARK = "<!-- BEGIN GENERATED -->"
END_MARK = "<!-- END GENERATED -->"

# Anki Heading Sync 当前主链 marker，以及旧版 AHS marker。
# 只认这些行，避免误吞卡片正文里的普通 HTML 注释。
_CARD_MARKER_RE = re.compile(r"^\s*<!--\s*(?:ID:|AHS:).*?-->\s*$", re.IGNORECASE)

# 匹配“改动很小的同一张卡”：先匹配正文完全相同，再允许题面改词但答案保持。
_MIN_SIMILARITY = 0.2


@dataclass
class _GeneratedBlock:
    start: int  # 0-based，BEGIN 行
    end: int  # 0-based，END 行（inclusive）；AHS 写在 END 后的 marker 也算进来
    lines: list[str]
    trailing_lines: list[str] = field(default_factory=list)


def _scan_generated(text: str) -> tuple[str, list[_GeneratedBlock], list[int]]:
    """扫描 text，返回 (去掉受管理区块后的文本, 区块, kept 行原始下标)。

    Anki Heading Sync 会把最后一张卡的 ``<!--ID: ...-->`` 写在
    ``<!-- END GENERATED -->`` 后面（它把 END 当作最后一张卡的正文）。
    这里把 END 后紧跟的 marker（以及 marker 之间的空行）也归入该块，
    否则下一步合并时最后一张卡会丢失身份。
    """
    lines = text.split("\n")
    kept: list[str] = []
    kept_original_line_indexes: list[int] = []
    blocks: list[_GeneratedBlock] = []

    inside = False
    after_end = False
    current_start: int | None = None
    current_lines: list[str] = []
    current_trailing: list[str] = []
    pending_blanks: list[str] = []

    def finish_block() -> None:
        nonlocal current_start, current_lines, current_trailing, after_end
        if current_start is None:
            return

        all_lines = [*current_lines, *current_trailing]
        blocks.append(_GeneratedBlock(
            current_start,
            current_start + len(all_lines) - 1,
            all_lines,
            list(current_trailing),
        ))
        current_start = None
        current_lines = []
        current_trailing = []
        after_end = False

    for index, line in enumerate(lines):
        stripped = line.strip()

        if stripped == BEGIN_MARK:
            # 容忍前一个块没有正常收尾、或两个受管理块直接相邻的情况：
            # 先把前一个块收掉，再开始新块。
            if current_start is not None:
                finish_block()
            inside = True
            after_end = False
            current_start = index
            current_lines = [line]
            current_trailing = []
            pending_blanks = []
            while kept and not kept[-1].strip():
                kept.pop()
                kept_original_line_indexes.pop()
            continue

        if stripped == END_MARK and inside:
            inside = False
            after_end = True
            current_lines.append(line)
            pending_blanks = []
            continue

        if inside:
            current_lines.append(line)
            continue

        if after_end:
            if not stripped:
                pending_blanks.append(line)
                continue

            if _is_marker_line(line):
                current_trailing.extend(pending_blanks)
                pending_blanks = []
                current_trailing.append(line)
                continue

            # 普通正文：结束当前块。END 后为分隔而存在的空行照旧丢弃。
            finish_block()
            pending_blanks = []

        kept.append(line)
        kept_original_line_indexes.append(index)

    if inside and current_start is not None:
        # 容忍文件末尾缺 END 的异常情况。
        finish_block()
    elif after_end and current_start is not None:
        finish_block()

    return "\n".join(kept), blocks, kept_original_line_indexes


def strip_generated(text: str) -> str:
    """删掉所有受管理的生成区块，以及它前后由我们引入的空行。"""
    return _scan_generated(text)[0]


def convert_inplace(text: str, categories: dict[str, str] | None = None) -> Conversion:
    """就地插入/更新：只重写发生变化的 diagram 区块，保留其他区块原样。"""
    stripped, blocks, kept_line_indexes = _scan_generated(text)
    ctx = parse_document(stripped)
    ctx["categories"] = merge_categories(categories)
    diagrams = ctx["diagrams"]
    summaries: list[DiagramSummary] = []
    produced_cards = []

    for diagram in diagrams:
        cards = format_diagram(diagram, ctx)
        summaries.append(DiagramSummary(diagram.kind, diagram.title, diagram.line + 1, len(cards)))
        produced_cards.append(cards)

    lines = text.split("\n")
    heading_positions = _collect_heading_positions(lines, blocks)
    diagram_heading_positions = _collect_diagram_heading_positions(heading_positions)
    original_to_stripped = {original: stripped_index for stripped_index, original in enumerate(kept_line_indexes)}
    diagram_index_by_stripped_line = {diagram.line: index for index, diagram in enumerate(diagrams)}

    # 每个 diagram 对应的原始输入标题行（可能因为 fence / unknown d-* 为空）。
    diagram_original_heading: list[int | None] = [None] * len(diagrams)
    for original_line, _title in diagram_heading_positions:
        stripped_line = original_to_stripped.get(original_line)
        if stripped_line is None:
            continue
        diagram_index = diagram_index_by_stripped_line.get(stripped_line)
        if diagram_index is not None and diagram_original_heading[diagram_index] is None:
            diagram_original_heading[diagram_index] = original_line

    blocks_by_diagram: dict[int, list[_GeneratedBlock]] = defaultdict(list)
    unassociated_blocks: list[_GeneratedBlock] = []
    for block in blocks:
        preceding = [(line, title) for line, title in diagram_heading_positions if line < block.start]
        if not preceding:
            unassociated_blocks.append(block)
            continue

        heading_line, _title = max(preceding, key=lambda item: item[0])
        stripped_line = original_to_stripped.get(heading_line)
        diagram_index = diagram_index_by_stripped_line.get(stripped_line) if stripped_line is not None else None
        if diagram_index is None:
            unassociated_blocks.append(block)
            continue

        blocks_by_diagram[diagram_index].append(block)

    operations: list[tuple[int, int, list[str], bool]] = []

    for diagram_index, cards in enumerate(produced_cards):
        associated = blocks_by_diagram.get(diagram_index, [])
        if not cards:
            for block in associated:
                operations.append(_removal_operation(lines, block))
            continue

        if associated:
            # 一个 diagram 理论上只有一个受管理块。多余块按旧行为清掉，
            # 但保留第一个块里的 note marker。
            first, *extra_blocks = associated
            merged = _merge_block(first.lines, cards)
            if merged != first.lines:
                operations.append((first.start, first.end + 1, merged, False))
            for block in extra_blocks:
                operations.append(_removal_operation(lines, block))
            continue

        insert_at = _insertion_index(
            diagram_original_heading[diagram_index] if diagram_index < len(diagram_original_heading) else None,
            heading_positions,
            len(lines),
        )
        body = render_cards(cards).rstrip("\n").split("\n")
        operations.append((insert_at, insert_at, ["", BEGIN_MARK, *body, END_MARK, ""], True))

    for block in unassociated_blocks:
        operations.append(_removal_operation(lines, block))

    _apply_operations(lines, operations)

    return Conversion(text="\n".join(lines), warnings=ctx["warnings"], diagrams=summaries)


def _collect_heading_positions(lines: list[str], blocks: list[_GeneratedBlock]) -> list[tuple[int, int, str]]:
    """收集受管理块之外的标题行，返回 (原始 0-based 行号, 层级, 标题文字)。"""
    inside_block = [False] * len(lines)
    for block in blocks:
        for index in range(max(0, block.start), min(len(lines), block.end + 1)):
            inside_block[index] = True

    headings: list[tuple[int, int, str]] = []
    in_fence = False

    for index, line in enumerate(lines):
        if inside_block[index]:
            continue

        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        match = HEADING_RE.match(line)
        if not match:
            continue

        level = len(match.group(1))
        title = re.sub(r"\s*#+\s*$", "", match.group(2)).strip()
        headings.append((index, level, title))

    return headings


def _collect_diagram_heading_positions(headings: list[tuple[int, int, str]]) -> list[tuple[int, str]]:
    return [(line, title) for line, _level, title in headings if DIAGRAM_MARKER_RE.match(title)]


def _insertion_index(original_heading: int | None, headings: list[tuple[int, int, str]], total_lines: int) -> int:
    """新块插到当前 diagram 的第一个下级标题之前；没有标题则插到文末。"""
    if original_heading is None:
        return total_lines

    for line, _level, _title in headings:
        if line > original_heading:
            return line
    return total_lines


def _removal_operation(lines: list[str], block: _GeneratedBlock) -> tuple[int, int, list[str], bool]:
    """删块，并连同块前后的空行一起删掉，保持旧幂等语义。"""
    start = block.start
    end = block.end + 1

    while start > 0 and not lines[start - 1].strip():
        start -= 1
    while end < len(lines) and not lines[end].strip():
        end += 1

    return start, end, [], False


def _apply_operations(lines: list[str], operations: list[tuple[int, int, list[str], bool]]) -> None:
    for start, end, new_lines, trim_blank_before in sorted(
        operations,
        key=lambda operation: (operation[0], operation[1]),
        reverse=True,
    ):
        if trim_blank_before:
            while start > 0 and not lines[start - 1].strip():
                start -= 1
                end -= 1

        lines[start:end] = new_lines


def _is_marker_line(line: str) -> bool:
    return bool(_CARD_MARKER_RE.match(line))


def _visible_lines(chunk: list[str]) -> tuple[str, ...]:
    """卡片正文：标题 + 答案行；忽略空行和 AHS note marker。"""
    return tuple(line.rstrip() for line in chunk if line.strip() and not _is_marker_line(line))


def _split_card_chunks(body_lines: list[str]) -> list[list[str]]:
    """把 BEGIN/END 之间的正文切成一张张 ``#### `` 卡片块。"""
    chunks: list[list[str]] = []
    current: list[str] = []

    for line in body_lines:
        if not current and not line.strip():
            continue
        if line.startswith("#### "):
            if current:
                _append_chunk(chunks, current)
            current = [line]
        elif current:
            current.append(line)
        else:
            current = [line]

    if current:
        _append_chunk(chunks, current)

    return chunks


def _find_end_marker_index(lines: list[str]) -> int | None:
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip() == END_MARK:
            return index
    return None


def _append_chunk(chunks: list[list[str]], chunk: list[str]) -> None:
    while chunk and not chunk[-1].strip():
        chunk.pop()
    if chunk:
        chunks.append(chunk)


def _same_visible_cards(old_chunks: list[list[str]], new_chunks: list[list[str]]) -> bool:
    if len(old_chunks) != len(new_chunks):
        return False

    return all(
        _visible_lines(old_chunks[index]) == tuple(line.rstrip() for line in new_chunks[index])
        for index in range(len(new_chunks))
    )


def _merge_block(old_lines: list[str], cards) -> list[str]:
    """合并旧块与本次新卡片。返回值与原列表相同则调用方不会写文件。"""
    end_marker_index = _find_end_marker_index(old_lines)
    if len(old_lines) < 2 or old_lines[0] != BEGIN_MARK or end_marker_index is None:
        body = render_cards(cards).rstrip("\n").split("\n") if cards else []
        return [BEGIN_MARK, *body, END_MARK]

    trailing_lines = old_lines[end_marker_index + 1:]
    old_chunks = _split_card_chunks(old_lines[1:end_marker_index])
    new_chunks = [render_card(card).split("\n") for card in cards]

    # AHS 可能把最后一张卡的 marker 写在 END 后面。把这个 marker 视为
    # 最后一张旧卡的 marker，参与匹配；重建时它会被移回卡片正文末尾。
    trailing_markers = [line for line in trailing_lines if _is_marker_line(line)]
    if old_chunks and trailing_markers:
        old_chunks[-1] = [*old_chunks[-1], *trailing_markers]

    # 完全没变时保留整块，包括 AHS 写入的空行和 END 后 marker 布局。
    if _same_visible_cards(old_chunks, new_chunks):
        return list(old_lines)

    matches = _match_chunks(old_chunks, new_chunks)
    merged_chunks: list[list[str]] = []

    for index, new_chunk in enumerate(new_chunks):
        old_index = matches[index]
        if old_index is None:
            merged_chunks.append(new_chunk)
            continue

        old_chunk = old_chunks[old_index]
        markers = [line for line in old_chunk if _is_marker_line(line)]
        merged_chunks.append([*new_chunk, *markers])

    merged_body: list[str] = []
    for index, chunk in enumerate(merged_chunks):
        if index:
            merged_body.append("")
        merged_body.extend(chunk)

    return [old_lines[0], *merged_body, old_lines[end_marker_index]]


def _match_chunks(old_chunks: list[list[str]], new_chunks: list[list[str]]) -> list[int | None]:
    """把新卡片按“先精确、再同序号、最后相似度”的顺序匹配到旧卡片。"""
    matches: list[int | None] = [None] * len(new_chunks)
    used_old: set[int] = set()

    exact_buckets: dict[tuple[str, ...], deque[int]] = defaultdict(deque)
    for old_index, chunk in enumerate(old_chunks):
        exact_buckets[_visible_lines(chunk)].append(old_index)

    for new_index, chunk in enumerate(new_chunks):
        key = tuple(line.rstrip() for line in chunk)
        bucket = exact_buckets.get(key)
        if bucket:
            old_index = bucket.popleft()
            matches[new_index] = old_index
            used_old.add(old_index)

    remaining_new = [index for index, old_index in enumerate(matches) if old_index is None]
    remaining_old = [index for index in range(len(old_chunks)) if index not in used_old]

    if not remaining_new or not remaining_old:
        return matches

    # 表头改名这类改动：数量通常不变，旧的“其他卡片”已经精确匹配掉，
    # 剩下的旧/新卡片按原顺序一一对应，避免把 marker 串给别的卡。
    if len(remaining_new) == len(remaining_old):
        for new_index, old_index in zip(remaining_new, remaining_old):
            matches[new_index] = old_index
        return matches

    # 增删行/列：按答案和题面相似度贪心匹配，没匹配上的旧卡删 marker。
    for new_index in remaining_new:
        best_old: int | None = None
        best_score = _MIN_SIMILARITY

        for old_index in remaining_old:
            if old_index in used_old:
                continue
            score = _chunk_similarity(old_chunks[old_index], new_chunks[new_index])
            if score > best_score:
                best_score = score
                best_old = old_index

        if best_old is not None:
            matches[new_index] = best_old
            used_old.add(best_old)

    return matches


def _chunk_similarity(old_chunk: list[str], new_chunk: list[str]) -> float:
    old_visible = list(_visible_lines(old_chunk))
    new_visible = [line.rstrip() for line in new_chunk]

    if old_visible == new_visible:
        return 1.0

    old_answers = [line for line in old_visible if line.startswith("- ")]
    new_answers = [line for line in new_visible if line.startswith("- ")]
    old_question = old_visible[0] if old_visible else ""
    new_question = new_visible[0] if new_visible else ""

    if old_answers == new_answers:
        answer_score = 0.6
    else:
        answer_score = 0.4 * SequenceMatcher(None, old_answers, new_answers).ratio()

    question_score = 0.4 * SequenceMatcher(None, old_question, new_question).ratio()
    return answer_score + question_score


def render_inplace(text: str, categories: dict[str, str] | None = None) -> tuple[str, list[dict]]:
    """`convert_inplace` 的旧签名（产物 + 警告）。"""
    conversion = convert_inplace(text, categories=categories)
    return conversion.text, conversion.warnings


def convert_new_file(text: str, categories: dict[str, str] | None = None) -> Conversion:
    """只输出卡片，不带任何维护标记。"""
    ctx = parse_document(text)
    ctx["categories"] = merge_categories(categories)
    cards = []
    summaries: list[DiagramSummary] = []

    for diagram in ctx["diagrams"]:
        produced = format_diagram(diagram, ctx)
        summaries.append(DiagramSummary(diagram.kind, diagram.title, diagram.line + 1, len(produced)))
        cards.extend(produced)

    return Conversion(text=render_cards(cards), warnings=ctx["warnings"], diagrams=summaries)


def render_new_file(text: str, categories: dict[str, str] | None = None) -> tuple[str, list[dict]]:
    """`convert_new_file` 的旧签名（产物 + 警告）。"""
    conversion = convert_new_file(text, categories=categories)
    return conversion.text, conversion.warnings


def new_file_path(source: pathlib.Path) -> pathlib.Path:
    """`notes.md` → `notes闪卡.md`"""
    return source.with_name(f"{source.stem}闪卡{source.suffix}")
