from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True, frozen=True)
class MarkdownBlock:
    block_type: str
    content: str
    sentence_count: int
    item_count: int = 0


def content_body_without_heading(content: str) -> str:
    lines = content.splitlines()
    started = False
    for index, line in enumerate(lines):
        if not started and not line.strip():
            continue
        started = True
        if line.lstrip().startswith("#"):
            return "\n".join(lines[index + 1 :]).strip()
        break
    return content.strip()


def extract_markdown_blocks(body: str) -> list[MarkdownBlock]:
    blocks: list[MarkdownBlock] = []
    if not body.strip():
        return blocks
    chunks = re.split(r"\n\s*\n", body.strip())
    for chunk in chunks:
        lines = [line.rstrip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if all(is_list_line(line) for line in lines):
            blocks.append(
                MarkdownBlock(
                    block_type="list",
                    content="\n".join(line.strip() for line in lines).strip(),
                    sentence_count=sentence_count(" ".join(strip_list_prefix(line) for line in lines).strip()),
                    item_count=len(lines),
                )
            )
            continue
        if all(line.lstrip().startswith(">") for line in lines):
            text = "\n".join(line.rstrip() for line in lines).strip()
            blocks.append(
                MarkdownBlock(
                    block_type="quote",
                    content=text,
                    sentence_count=sentence_count(" ".join(line.lstrip()[1:].strip() for line in lines).strip()),
                )
            )
            continue
        if len(lines) >= 2 and all("|" in line for line in lines):
            text = "\n".join(line.rstrip() for line in lines).strip()
            blocks.append(
                MarkdownBlock(
                    block_type="table",
                    content=text,
                    sentence_count=sentence_count(" ".join(lines).strip()),
                )
            )
            continue
        text = re.sub(r"\s+", " ", " ".join(lines)).strip()
        blocks.append(
            MarkdownBlock(
                block_type="paragraph",
                content=text,
                sentence_count=sentence_count(text),
            )
        )
    return _merge_label_led_blocks(blocks)


def _merge_label_led_blocks(blocks: list[MarkdownBlock]) -> list[MarkdownBlock]:
    merged: list[MarkdownBlock] = []
    index = 0
    while index < len(blocks):
        current = blocks[index]
        if _is_label_only_paragraph(current.content):
            grouped_block, consumed = _collect_labeled_group(blocks, index)
            if grouped_block is not None:
                merged.append(grouped_block)
                index += consumed
                continue
        merged.append(current)
        index += 1
    return merged


def _collect_labeled_group(
    blocks: list[MarkdownBlock],
    index: int,
) -> tuple[MarkdownBlock | None, int]:
    if index + 1 >= len(blocks):
        return None, 0
    if _starts_repeated_labeled_series(blocks, index + 1):
        return None, 0

    grouped_contents = [blocks[index].content]
    total_sentences = blocks[index].sentence_count
    total_items = 0
    total_chars = len(blocks[index].content)
    consumed = 1
    merged_body_blocks = 0

    while index + consumed < len(blocks):
        candidate = blocks[index + consumed]
        if not _is_groupable_following_block(candidate):
            break
        if candidate.block_type == "paragraph" and _is_label_only_paragraph(candidate.content):
            break
        if candidate.block_type == "paragraph" and _starts_repeated_labeled_series(blocks, index + consumed):
            break
        next_chars = total_chars + len(candidate.content)
        next_sentences = total_sentences + candidate.sentence_count
        next_items = total_items + candidate.item_count
        if next_chars > 1800:
            break
        if next_sentences > 16:
            break
        if candidate.block_type == "list" and next_items > 8:
            break
        grouped_contents.append(candidate.content)
        total_chars = next_chars
        total_sentences = next_sentences
        total_items = next_items
        consumed += 1
        merged_body_blocks += 1
        if merged_body_blocks >= 3:
            break

    if merged_body_blocks <= 0:
        return None, 0
    return (
        MarkdownBlock(
            block_type="compound",
            content="\n\n".join(grouped_contents).strip(),
            sentence_count=total_sentences,
            item_count=total_items,
        ),
        consumed,
    )


def _is_groupable_following_block(block: MarkdownBlock) -> bool:
    if block.block_type == "list":
        return block.item_count <= 8 and len(block.content) <= 1400
    if block.block_type == "paragraph":
        return block.sentence_count <= 8 and len(block.content) <= 900
    return False


def _starts_repeated_labeled_series(blocks: list[MarkdownBlock], start_index: int) -> bool:
    window = blocks[start_index : start_index + 3]
    labeled_count = 0
    for block in window:
        if block.block_type != "paragraph":
            break
        if not _is_inline_labeled_paragraph(block.content):
            break
        labeled_count += 1
    return labeled_count >= 2


def _is_label_only_paragraph(text: str) -> bool:
    stripped = text.strip()
    return re.fullmatch(r"\*\*.+?\*\*:?\s*", stripped) is not None


def _is_inline_labeled_paragraph(text: str) -> bool:
    stripped = text.strip()
    return re.match(r"^\*\*.+?\*\*:?\s+\S+", stripped) is not None


def is_list_line(line: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith(("- ", "* ", "+ ")):
        return True
    return re.match(r"^\d+\.\s+", stripped) is not None


def strip_list_prefix(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith(("- ", "* ", "+ ")):
        return stripped[2:].strip()
    match = re.match(r"^\d+\.\s+(?P<body>.+)$", stripped)
    if match:
        return match.group("body").strip()
    return stripped


def sentence_count(text: str) -> int:
    candidates = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return len(candidates)
