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
    return blocks


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
