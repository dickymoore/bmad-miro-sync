from __future__ import annotations

import re


CODE_BLOCK_SUMMARY = "[Code-heavy block omitted from Miro sync; see the source artifact for full details.]"
HTML_PAYLOAD_SUMMARY = "[Raw HTML/CSS payload omitted from Miro sync; see the source artifact for full details.]"


def sanitize_markdown_for_miro(content: str, *, include_payload_notes: bool = True) -> str:
    content = strip_yaml_front_matter(content)
    sanitized_lines: list[str] = []
    removed_web_payload = False
    in_code = False
    in_raw_html_block = False
    raw_html_block_tag = ""
    fence_marker = "```"
    code_lang = ""
    code_buffer: list[str] = []

    def flush_removed_payload_note() -> None:
        nonlocal removed_web_payload
        if include_payload_notes and removed_web_payload and (not sanitized_lines or sanitized_lines[-1] != HTML_PAYLOAD_SUMMARY):
            sanitized_lines.append(HTML_PAYLOAD_SUMMARY)
        removed_web_payload = False

    def flush_code_block() -> None:
        nonlocal code_buffer
        nonlocal code_lang
        block_text = "\n".join(code_buffer)
        if should_summarize_code_block(block_text, code_lang):
            flush_removed_payload_note()
            if include_payload_notes and (not sanitized_lines or sanitized_lines[-1] != CODE_BLOCK_SUMMARY):
                sanitized_lines.append(CODE_BLOCK_SUMMARY)
        else:
            flush_removed_payload_note()
            sanitized_lines.append(f"{fence_marker}{code_lang}".rstrip())
            sanitized_lines.extend(code_buffer)
            sanitized_lines.append(fence_marker)
        code_buffer = []
        code_lang = ""

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = "```" if stripped.startswith("```") else "~~~"
            if in_code and marker == fence_marker:
                flush_code_block()
                in_code = False
                continue
            flush_removed_payload_note()
            in_code = True
            fence_marker = marker
            code_lang = stripped[len(marker) :].strip().lower()
            code_buffer = []
            continue
        if in_code:
            code_buffer.append(raw_line)
            continue
        if in_raw_html_block:
            removed_web_payload = True
            if closes_raw_html_block(stripped, raw_html_block_tag):
                in_raw_html_block = False
                raw_html_block_tag = ""
            continue
        block_tag = opens_raw_html_block(stripped)
        if block_tag:
            removed_web_payload = True
            if not closes_raw_html_block(stripped, block_tag):
                in_raw_html_block = True
                raw_html_block_tag = block_tag
            continue
        if is_raw_html_payload_line(raw_line):
            removed_web_payload = True
            continue
        flush_removed_payload_note()
        sanitized_lines.append(raw_line)

    if in_code:
        flush_code_block()
    flush_removed_payload_note()
    sanitized = "\n".join(sanitized_lines).strip()
    if sanitized:
        return sanitized
    if include_payload_notes:
        return HTML_PAYLOAD_SUMMARY
    return ""


def strip_yaml_front_matter(content: str) -> str:
    lines = content.splitlines()
    if len(lines) < 3:
        return content
    if lines[0].strip() != "---":
        return content
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return content


def should_summarize_code_block(block_text: str, language: str) -> bool:
    normalized_language = language.lower()
    if normalized_language in {"html", "xml", "svg", "css", "scss", "less"}:
        return True
    if len(block_text) > 1600 or len(block_text.splitlines()) > 40:
        return True
    return looks_like_web_payload(block_text)


def is_raw_html_payload_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    lower = stripped.lower()
    if lower.startswith(("<!doctype", "<html", "</html", "<head", "</head", "<body", "</body", "<style", "</style", "<script", "</script")):
        return True
    if lower.startswith("<?xml"):
        return True
    if lower.startswith("<") and re.match(r"^</?[a-z][a-z0-9:_-]*(\s|>|/)", lower):
        return True
    if looks_like_css_payload(stripped):
        return True
    return False


def opens_raw_html_block(line: str) -> str:
    lower = line.lower()
    for tag in ("style", "script", "svg"):
        if lower.startswith(f"<{tag}") and not lower.startswith(f"</{tag}"):
            return tag
    return ""


def closes_raw_html_block(line: str, tag: str) -> bool:
    return f"</{tag}" in line.lower()


def looks_like_web_payload(text: str) -> bool:
    sample = text.strip()
    if not sample:
        return False
    if "<html" in sample.lower() or "<style" in sample.lower() or "<script" in sample.lower():
        return True
    if sample.count("{") >= 3 and sample.count("}") >= 3 and sample.count(";") >= 3:
        return True
    if sample.count("<") >= 5 and sample.count(">") >= 5:
        return True
    return False


def looks_like_css_payload(line: str) -> bool:
    if len(line) < 40:
        return False
    return (
        line.count("{") >= 1
        and line.count("}") >= 1
        and line.count(":") >= 2
        and line.count(";") >= 2
    )
