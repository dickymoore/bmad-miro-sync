from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re


HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*\s*$")


@dataclass(slots=True)
class MarkdownSection:
    slug: str
    title: str
    heading_level: int
    content: str
    parent_slug: str | None = None
    path: tuple[str, ...] = ()
    title_path: tuple[str, ...] = ()
    node_slug: str = ""
    sibling_index: int = 1
    lineage_key: str = ""


def split_markdown_sections(content: str) -> list[MarkdownSection]:
    lines = content.splitlines()
    headings = [
        (index, len(match.group(1)), _normalize_heading_title(match.group(2)))
        for index, line in enumerate(lines)
        if (match := HEADING_RE.match(line.strip()))
    ]
    if not headings:
        body = content.strip()
        if not body:
            return []
        return [
            MarkdownSection(
                slug="overview",
                title="Overview",
                heading_level=0,
                content=body,
                path=("overview",),
                title_path=("Overview",),
                node_slug="overview",
                lineage_key=_lineage_key(body),
            )
        ]

    sections: list[MarkdownSection] = []
    child_slug_counts: dict[str | None, dict[str, int]] = {}
    preamble = "\n".join(lines[: headings[0][0]]).strip()
    if preamble:
        sections.append(
            MarkdownSection(
                slug="overview",
                title="Overview",
                heading_level=0,
                content=preamble,
                path=("overview",),
                title_path=("Overview",),
                node_slug="overview",
                lineage_key=_lineage_key(preamble),
            )
        )
        child_slug_counts[None] = {"overview": 1}

    parent_stack: list[tuple[int, MarkdownSection]] = []

    for index, (line_index, heading_level, heading_title) in enumerate(headings):
        next_heading_index = len(lines)
        if index + 1 < len(headings):
            next_heading_index = headings[index + 1][0]

        subtree_end_index = len(lines)
        for future_line_index, future_level, _future_title in headings[index + 1 :]:
            if future_level <= heading_level:
                subtree_end_index = future_line_index
                break

        while parent_stack and parent_stack[-1][0] >= heading_level:
            parent_stack.pop()
        parent = parent_stack[-1][1] if parent_stack else None
        parent_slug = parent.slug if parent else None
        parent_path = parent.path if parent else ()
        parent_title_path = parent.title_path if parent else ()

        node_slug = _slugify(heading_title) or f"section-{index + 1}"
        sibling_counts = child_slug_counts.setdefault(parent_slug, {})
        sibling_index = sibling_counts.get(node_slug, 0) + 1
        sibling_counts[node_slug] = sibling_index
        segment = node_slug if sibling_index == 1 else f"{node_slug}-{sibling_index}"

        path = parent_path + (segment,)
        title_path = parent_title_path + (heading_title,)

        section_lines = lines[line_index:next_heading_index]
        section_content = "\n".join(section_lines).strip()
        subtree_lines = lines[line_index:subtree_end_index]
        section = MarkdownSection(
            slug="/".join(path),
            title=heading_title,
            heading_level=heading_level,
            content=section_content,
            parent_slug=parent_slug,
            path=path,
            title_path=title_path,
            node_slug=node_slug,
            sibling_index=sibling_index,
            lineage_key=_section_lineage_key(section_lines, subtree_lines),
        )
        sections.append(section)
        parent_stack.append((heading_level, section))

    return sections


def _normalize_heading_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def _section_lineage_key(section_lines: list[str], subtree_lines: list[str]) -> str:
    direct_body = "\n".join(section_lines[1:]).strip()
    subtree_body = "\n".join(subtree_lines[1:]).strip()
    if direct_body:
        return _lineage_key(direct_body)
    if subtree_body:
        return _lineage_key(subtree_body)
    return _lineage_key("")


def _lineage_key(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
