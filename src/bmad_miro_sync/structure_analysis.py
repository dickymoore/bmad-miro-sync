from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import re
from statistics import median
from typing import Any

from .config import SyncConfig
from .content_sanitizer import sanitize_markdown_for_miro
from .discovery import discover_artifacts
from .markdown import split_markdown_sections
from .miro_api import (
    _meaningful_summary_bullets,
    _meaningful_summary_paragraphs,
    _markdown_to_simple_html,
    _truncate_text,
)
from .planner import _MAX_DOC_HTML_CHARS


@dataclass(slots=True)
class BlockMetric:
    block_type: str
    char_count: int
    sentence_count: int
    item_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SectionMetric:
    artifact_id: str
    title: str
    heading_level: int
    section_path: tuple[str, ...]
    raw_char_count: int
    body_char_count: int
    sentence_count: int
    paragraph_count: int
    paragraph_char_count: int
    paragraph_char_max: int
    list_block_count: int
    list_item_count: int
    list_char_count: int
    table_block_count: int
    quote_block_count: int
    publishable: bool
    rendered_html_char_count: int
    current_summary_chars_lost: int
    current_summary_uses_fallback: bool
    blocks: list[BlockMetric] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["section_path"] = list(self.section_path)
        payload["blocks"] = [block.to_dict() for block in self.blocks]
        return payload


@dataclass(slots=True)
class SourceMetric:
    source_artifact_id: str
    relative_path: str
    artifact_class: str
    phase_zone: str
    workstream: str
    source_title: str
    section_count: int
    publishable_section_count: int
    suppressed_section_count: int
    total_body_chars: int
    total_sentences: int
    total_paragraphs: int
    total_list_items: int
    sections_over_miro_limit: int
    current_truncated_section_count: int
    current_summary_chars_lost: int
    section_metrics: list[SectionMetric] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["section_metrics"] = [section.to_dict() for section in self.section_metrics]
        return payload


@dataclass(slots=True)
class AlternativeModelEstimate:
    model_id: str
    label: str
    total_cards: int
    section_header_cards: int
    paragraph_cards: int
    list_cards: int
    list_item_cards: int
    sections_over_miro_limit: int
    max_card_body_chars: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Recommendation:
    recommended_model_id: str
    rationale: list[str]
    implementation_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StructureAnalysisReport:
    project_root: str
    config_path: str
    source_count: int
    section_count: int
    publishable_section_count: int
    suppressed_section_count: int
    total_body_chars: int
    total_sentences: int
    total_paragraphs: int
    total_list_items: int
    current_model_cards: int
    current_truncated_section_count: int
    current_summary_chars_lost: int
    sources: list[SourceMetric] = field(default_factory=list)
    alternatives: list[AlternativeModelEstimate] = field(default_factory=list)
    recommendation: Recommendation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "config_path": self.config_path,
            "source_count": self.source_count,
            "section_count": self.section_count,
            "publishable_section_count": self.publishable_section_count,
            "suppressed_section_count": self.suppressed_section_count,
            "total_body_chars": self.total_body_chars,
            "total_sentences": self.total_sentences,
            "total_paragraphs": self.total_paragraphs,
            "total_list_items": self.total_list_items,
            "current_model_cards": self.current_model_cards,
            "current_truncated_section_count": self.current_truncated_section_count,
            "current_summary_chars_lost": self.current_summary_chars_lost,
            "sources": [source.to_dict() for source in self.sources],
            "alternatives": [alt.to_dict() for alt in self.alternatives],
            "recommendation": self.recommendation.to_dict() if self.recommendation else None,
        }


def build_structure_analysis(
    project_root: str | Path,
    config_path: str | Path,
    config: SyncConfig,
) -> StructureAnalysisReport:
    root = Path(project_root).resolve()
    discovery = discover_artifacts(root, config, config_path=config_path)
    source_metrics: list[SourceMetric] = []
    selected_by_path = {selection.relative_path: selection for selection in discovery.selected}

    publishable_section_count = 0
    section_count = 0
    suppressed_section_count = 0
    total_body_chars = 0
    total_sentences = 0
    total_paragraphs = 0
    total_list_items = 0
    current_truncated_section_count = 0
    current_summary_chars_lost = 0

    for relative_path, selection in selected_by_path.items():
        path = root / relative_path
        if not path.is_file():
            continue
        raw_content = path.read_text(encoding="utf-8")
        sections = split_markdown_sections(raw_content)
        section_metrics: list[SectionMetric] = []
        for section in sections:
            sanitized_content = sanitize_markdown_for_miro(section.content, include_payload_notes=False)
            body = _content_body_without_heading(sanitized_content)
            blocks = _extract_blocks(body)
            paragraph_blocks = [block for block in blocks if block.block_type == "paragraph"]
            list_blocks = [block for block in blocks if block.block_type == "list"]
            table_blocks = [block for block in blocks if block.block_type == "table"]
            quote_blocks = [block for block in blocks if block.block_type == "quote"]
            section_summary = _current_summary_loss(sanitized_content, config)
            metric = SectionMetric(
                artifact_id=f"{relative_path}#{section.slug}",
                title=section.title,
                heading_level=section.heading_level,
                section_path=section.path,
                raw_char_count=len(section.content),
                body_char_count=len(body),
                sentence_count=sum(block.sentence_count for block in blocks),
                paragraph_count=len(paragraph_blocks),
                paragraph_char_count=sum(block.char_count for block in paragraph_blocks),
                paragraph_char_max=max((block.char_count for block in paragraph_blocks), default=0),
                list_block_count=len(list_blocks),
                list_item_count=sum(block.item_count for block in list_blocks),
                list_char_count=sum(block.char_count for block in list_blocks),
                table_block_count=len(table_blocks),
                quote_block_count=len(quote_blocks),
                publishable=_body_has_publishable_content(body),
                rendered_html_char_count=len(_markdown_to_simple_html(sanitized_content)),
                current_summary_chars_lost=section_summary["lost_chars"],
                current_summary_uses_fallback=section_summary["used_fallback"],
                blocks=blocks,
            )
            section_metrics.append(metric)
            section_count += 1
            total_body_chars += metric.body_char_count
            total_sentences += metric.sentence_count
            total_paragraphs += metric.paragraph_count
            total_list_items += metric.list_item_count
            current_summary_chars_lost += metric.current_summary_chars_lost
            if metric.publishable:
                publishable_section_count += 1
            else:
                suppressed_section_count += 1
            if metric.current_summary_chars_lost > 0:
                current_truncated_section_count += 1

        publishable_metrics = [metric for metric in section_metrics if metric.publishable]
        source_metrics.append(
            SourceMetric(
                source_artifact_id=relative_path,
                relative_path=relative_path,
                artifact_class=selection.artifact_class,
                phase_zone=selection.phase_zone,
                workstream=selection.workstream,
                source_title=_source_title_from_path(relative_path),
                section_count=len(section_metrics),
                publishable_section_count=len(publishable_metrics),
                suppressed_section_count=len(section_metrics) - len(publishable_metrics),
                total_body_chars=sum(metric.body_char_count for metric in publishable_metrics),
                total_sentences=sum(metric.sentence_count for metric in publishable_metrics),
                total_paragraphs=sum(metric.paragraph_count for metric in publishable_metrics),
                total_list_items=sum(metric.list_item_count for metric in publishable_metrics),
                sections_over_miro_limit=sum(1 for metric in publishable_metrics if metric.rendered_html_char_count > _MAX_DOC_HTML_CHARS),
                current_truncated_section_count=sum(1 for metric in publishable_metrics if metric.current_summary_chars_lost > 0),
                current_summary_chars_lost=sum(metric.current_summary_chars_lost for metric in publishable_metrics),
                section_metrics=section_metrics,
            )
        )

    alternatives = _estimate_alternative_models(source_metrics)
    recommendation = _recommend_model(
        source_metrics,
        alternatives,
        current_truncated_section_count=current_truncated_section_count,
        current_summary_chars_lost=current_summary_chars_lost,
    )
    return StructureAnalysisReport(
        project_root=str(root),
        config_path=str(Path(config_path)),
        source_count=len(source_metrics),
        section_count=section_count,
        publishable_section_count=publishable_section_count,
        suppressed_section_count=suppressed_section_count,
        total_body_chars=total_body_chars,
        total_sentences=total_sentences,
        total_paragraphs=total_paragraphs,
        total_list_items=total_list_items,
        current_model_cards=publishable_section_count,
        current_truncated_section_count=current_truncated_section_count,
        current_summary_chars_lost=current_summary_chars_lost,
        sources=sorted(source_metrics, key=lambda source: (source.phase_zone, source.workstream, source.relative_path)),
        alternatives=alternatives,
        recommendation=recommendation,
    )


def render_structure_analysis_markdown(report: StructureAnalysisReport) -> str:
    lines = [
        "# Miro Board Mapping Analysis",
        "",
        f"- Project root: `{report.project_root}`",
        f"- Sources analyzed: `{report.source_count}`",
        f"- Total sections: `{report.section_count}`",
        f"- Publishable sections: `{report.publishable_section_count}`",
        f"- Suppressed sections: `{report.suppressed_section_count}`",
        f"- Current doc-card count: `{report.current_model_cards}`",
        f"- Truncated current cards: `{report.current_truncated_section_count}`",
        f"- Current summary chars lost: `{report.current_summary_chars_lost}`",
        "",
        "## Alternatives",
        "",
        "| Model | Cards | Section headers | Paragraph cards | List cards | List-item cards | Sections over Miro limit | Max card body chars |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for alt in report.alternatives:
        lines.append(
            f"| {alt.label} | {alt.total_cards} | {alt.section_header_cards} | {alt.paragraph_cards} | {alt.list_cards} | {alt.list_item_cards} | {alt.sections_over_miro_limit} | {alt.max_card_body_chars} |"
        )
    if report.recommendation is not None:
        lines.extend(
            [
                "",
                "## Recommendation",
                "",
                f"- Recommended model: `{report.recommendation.recommended_model_id}`",
            ]
        )
        for item in report.recommendation.rationale:
            lines.append(f"- {item}")
        if report.recommendation.implementation_notes:
            lines.extend(["", "## Implementation Notes", ""])
            for item in report.recommendation.implementation_notes:
                lines.append(f"- {item}")
    lines.extend(["", "## Source Breakdown", ""])
    for source in report.sources:
        lines.extend(
            [
                f"### {source.source_title}",
                "",
                f"- Path: `{source.relative_path}`",
                f"- Phase/workstream: `{source.phase_zone}` / `{source.workstream}`",
                f"- Sections: `{source.section_count}` total, `{source.publishable_section_count}` publishable, `{source.suppressed_section_count}` suppressed",
                f"- Body chars: `{source.total_body_chars}`",
                f"- Paragraphs: `{source.total_paragraphs}`",
                f"- List items: `{source.total_list_items}`",
                f"- Current truncation loss: `{source.current_summary_chars_lost}` chars across `{source.current_truncated_section_count}` cards",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_structure_analysis(
    project_root: str | Path,
    *,
    json_output_path: str | Path,
    markdown_output_path: str | Path,
    config_path: str | Path,
    config: SyncConfig,
) -> StructureAnalysisReport:
    report = build_structure_analysis(project_root, config_path, config)
    json_path = Path(json_output_path)
    markdown_path = Path(markdown_output_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_structure_analysis_markdown(report), encoding="utf-8")
    return report


def _estimate_alternative_models(sources: list[SourceMetric]) -> list[AlternativeModelEstimate]:
    publishable_sections = [section for source in sources for section in source.section_metrics if section.publishable]
    paragraph_cards = sum(section.paragraph_count for section in publishable_sections)
    list_cards = sum(section.list_block_count for section in publishable_sections)
    list_item_cards = sum(section.list_item_count for section in publishable_sections)
    section_headers = len(publishable_sections)
    max_paragraph_chars = max((section.paragraph_char_max for section in publishable_sections), default=0)
    max_list_block_chars = max((section.list_char_count for section in publishable_sections), default=0)
    max_card_chars = max(max_paragraph_chars, max_list_block_chars)
    section_over_limit = sum(1 for section in publishable_sections if section.rendered_html_char_count > _MAX_DOC_HTML_CHARS)
    return [
        AlternativeModelEstimate(
            model_id="section_summary_cards",
            label="Current section-summary cards",
            total_cards=section_headers,
            section_header_cards=section_headers,
            paragraph_cards=0,
            list_cards=0,
            list_item_cards=0,
            sections_over_miro_limit=section_over_limit,
            max_card_body_chars=max((section.body_char_count for section in publishable_sections), default=0),
            notes=["One card per section; body summarized and truncated."],
        ),
        AlternativeModelEstimate(
            model_id="section_fulltext_cards",
            label="One full-text card per section",
            total_cards=section_headers,
            section_header_cards=section_headers,
            paragraph_cards=0,
            list_cards=0,
            list_item_cards=0,
            sections_over_miro_limit=section_over_limit,
            max_card_body_chars=max((section.body_char_count for section in publishable_sections), default=0),
            notes=["Zero truncation at the renderer level, but large research sections still exceed Miro-friendly card size."],
        ),
        AlternativeModelEstimate(
            model_id="hybrid_heading_paragraph_list_cards",
            label="Section heading + paragraph/list cards",
            total_cards=section_headers + paragraph_cards + list_cards,
            section_header_cards=section_headers,
            paragraph_cards=paragraph_cards,
            list_cards=list_cards,
            list_item_cards=0,
            sections_over_miro_limit=0,
            max_card_body_chars=max_card_chars,
            notes=["Preserves section hierarchy while moving readable body text into child cards."],
        ),
        AlternativeModelEstimate(
            model_id="heading_paragraph_list_item_cards",
            label="Section heading + paragraph + list-item cards",
            total_cards=section_headers + paragraph_cards + list_item_cards,
            section_header_cards=section_headers,
            paragraph_cards=paragraph_cards,
            list_cards=0,
            list_item_cards=list_item_cards,
            sections_over_miro_limit=0,
            max_card_body_chars=max(
                max_paragraph_chars,
                max((max((block.char_count for block in section.blocks if block.block_type == 'list'), default=0) for section in publishable_sections), default=0),
            ),
            notes=["Most readable for review, but produces the highest card count."],
        ),
    ]


def _recommend_model(
    sources: list[SourceMetric],
    alternatives: list[AlternativeModelEstimate],
    *,
    current_truncated_section_count: int,
    current_summary_chars_lost: int,
) -> Recommendation:
    paragraph_model = next(alt for alt in alternatives if alt.model_id == "hybrid_heading_paragraph_list_cards")
    section_model = next(alt for alt in alternatives if alt.model_id == "section_fulltext_cards")
    source_count = len(sources)
    rationale = [
        f"The current section-summary model truncates {current_truncated_section_count} cards and hides {current_summary_chars_lost} characters.",
        f"A zero-truncation one-card-per-section model would still leave {section_model.sections_over_miro_limit} oversized sections that need splitting.",
        f"The hybrid heading-plus-paragraph model keeps hierarchy while capping child card body size at {paragraph_model.max_card_body_chars} characters.",
        f"The estimated card count for the hybrid model is {paragraph_model.total_cards} across {source_count} source documents, which is higher but still structured and reviewable.",
    ]
    notes = [
        "Use source frames as the top container.",
        "Render section headings as lightweight structural cards.",
        "Render each paragraph as its own readable card with zero truncation.",
        "Render bullet groups as dedicated list cards; only split to item-level when a list block is still too dense.",
        "Reserve section-level full-text cards only for very short sections.",
    ]
    return Recommendation(
        recommended_model_id=paragraph_model.model_id,
        rationale=rationale,
        implementation_notes=notes,
    )


def _current_summary_loss(content: str, config: SyncConfig) -> dict[str, Any]:
    paragraph_limit = int(config.layout.summary_paragraph_chars)
    bullet_limit = int(config.layout.summary_bullet_chars)
    max_bullets = max(0, int(config.layout.summary_max_bullets))
    paragraphs = _meaningful_summary_paragraphs(content)
    bullets = _meaningful_summary_bullets(content)
    used_fallback = False
    if not paragraphs and not bullets:
        return {"lost_chars": 0, "used_fallback": used_fallback}
    lost_chars = 0
    if paragraphs:
        source = re.sub(r"\s+", " ", paragraphs[0]).strip()
        rendered = _truncate_text(paragraphs[0], paragraph_limit)
        lost_chars += _lost_chars(source, rendered)
    for bullet in bullets[:max_bullets]:
        source = re.sub(r"\s+", " ", bullet).strip()
        rendered = _truncate_text(bullet, bullet_limit)
        lost_chars += _lost_chars(source, rendered)
    return {"lost_chars": lost_chars, "used_fallback": used_fallback}


def _lost_chars(source: str, rendered: str) -> int:
    stripped = rendered.rstrip("…")
    lost = len(source) - len(stripped)
    if rendered.endswith("…"):
        lost += 1
    return max(lost, 0)


def _extract_blocks(body: str) -> list[BlockMetric]:
    blocks: list[BlockMetric] = []
    if not body.strip():
        return blocks
    chunks = re.split(r"\n\s*\n", body.strip())
    for chunk in chunks:
        lines = [line.rstrip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if all(_is_list_line(line) for line in lines):
            text = " ".join(_strip_list_prefix(line) for line in lines).strip()
            blocks.append(
                BlockMetric(
                    block_type="list",
                    char_count=len(text),
                    sentence_count=_sentence_count(text),
                    item_count=len(lines),
                )
            )
            continue
        if all(line.lstrip().startswith(">") for line in lines):
            text = " ".join(line.lstrip()[1:].strip() for line in lines).strip()
            blocks.append(BlockMetric(block_type="quote", char_count=len(text), sentence_count=_sentence_count(text)))
            continue
        if len(lines) >= 2 and all("|" in line for line in lines):
            text = " ".join(lines).strip()
            blocks.append(BlockMetric(block_type="table", char_count=len(text), sentence_count=_sentence_count(text)))
            continue
        text = re.sub(r"\s+", " ", " ".join(lines)).strip()
        blocks.append(BlockMetric(block_type="paragraph", char_count=len(text), sentence_count=_sentence_count(text)))
    return blocks


def _is_list_line(line: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith(("- ", "* ", "+ ")):
        return True
    return re.match(r"^\d+\.\s+", stripped) is not None


def _strip_list_prefix(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith(("- ", "* ", "+ ")):
        return stripped[2:].strip()
    match = re.match(r"^\d+\.\s+(?P<body>.+)$", stripped)
    if match:
        return match.group("body").strip()
    return stripped


def _sentence_count(text: str) -> int:
    candidates = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return len(candidates)


def _content_body_without_heading(content: str) -> str:
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


def _body_has_publishable_content(body: str) -> bool:
    if not body:
        return False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\*\*(author|date):\*\*", line, flags=re.IGNORECASE):
            continue
        if re.match(r"^[A-Za-z0-9_-]+:\s*$", line):
            continue
        return True
    return False


def _source_title_from_path(relative_path: str) -> str:
    stem = Path(relative_path).stem.replace("-", " ").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in stem.split())


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil((percentile / 100.0) * len(ordered)) - 1))
    return ordered[index]


def summarize_report_metrics(report: StructureAnalysisReport) -> dict[str, Any]:
    publishable_sections = [section for source in report.sources for section in source.section_metrics if section.publishable]
    paragraph_lengths = [block.char_count for section in publishable_sections for block in section.blocks if block.block_type == "paragraph"]
    list_lengths = [block.char_count for section in publishable_sections for block in section.blocks if block.block_type == "list"]
    return {
        "paragraph_length_p50": int(median(paragraph_lengths)) if paragraph_lengths else 0,
        "paragraph_length_p90": _percentile(paragraph_lengths, 90),
        "paragraph_length_p95": _percentile(paragraph_lengths, 95),
        "list_block_length_p50": int(median(list_lengths)) if list_lengths else 0,
        "list_block_length_p90": _percentile(list_lengths, 90),
        "list_block_length_p95": _percentile(list_lengths, 95),
    }
