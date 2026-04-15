from __future__ import annotations

from dataclasses import dataclass
import re


HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*\s*$")


@dataclass(slots=True)
class MarkdownSection:
    slug: str
    title: str
    heading_level: int
    content: str
    parent_slug: str | None = None


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
        return [MarkdownSection(slug="overview", title="Overview", heading_level=0, content=body)]

    sections: list[MarkdownSection] = []
    seen_slugs: dict[str, int] = {}
    preamble = "\n".join(lines[: headings[0][0]]).strip()
    if preamble:
        sections.append(MarkdownSection(slug="overview", title="Overview", heading_level=0, content=preamble))

    parent_stack: list[tuple[int, str]] = []
    promoted_indices = [idx for idx, (_, level, _) in enumerate(headings) if level <= 2]
    if not promoted_indices:
        promoted_indices = [0]

    for pos, promoted_idx in enumerate(promoted_indices):
        line_index, heading_level, heading_title = headings[promoted_idx]
        next_line_index = len(lines)
        if pos + 1 < len(promoted_indices):
            next_line_index = headings[promoted_indices[pos + 1]][0]

        while parent_stack and parent_stack[-1][0] >= heading_level:
            parent_stack.pop()
        parent_slug = parent_stack[-1][1] if parent_stack else None
        slug = _unique_slug(_slugify(heading_title) or f"section-{pos + 1}", seen_slugs)
        section_lines = lines[line_index:next_line_index]
        section_content = "\n".join(section_lines).strip()
        sections.append(
            MarkdownSection(
                slug=slug,
                title=heading_title,
                heading_level=heading_level,
                content=section_content,
                parent_slug=parent_slug,
            )
        )
        parent_stack.append((heading_level, slug))

    return sections


def _normalize_heading_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def _unique_slug(slug: str, seen_slugs: dict[str, int]) -> str:
    count = seen_slugs.get(slug, 0) + 1
    seen_slugs[slug] = count
    if count == 1:
        return slug
    return f"{slug}-{count}"
