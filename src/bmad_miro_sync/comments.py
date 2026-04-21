from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
from typing import Any

from .manifest import SyncManifest


DEFAULT_COMMENTS_OUTPUT = "_bmad-output/review-artifacts/miro-comments.md"
DEFAULT_TOPIC = "General feedback"


@dataclass(slots=True)
class NormalizedComment:
    artifact_id: str
    source_artifact_id: str
    section_id: str
    section_title: str
    topic: str
    author: str
    created_at: str
    body: str
    miro_url: str
    published_object_id: str
    published_object_type: str
    published_object_reference: str


@dataclass(slots=True)
class UnresolvedComment:
    incoming_artifact_reference: str
    source_artifact_id: str
    section_id: str
    section_title: str
    topic: str
    author: str
    created_at: str
    body: str
    miro_url: str
    published_object_id: str
    published_object_type: str
    published_object_reference: str
    reason: str


@dataclass(slots=True)
class CommentIngestResult:
    resolved: list[NormalizedComment] = field(default_factory=list)
    unresolved: list[UnresolvedComment] = field(default_factory=list)


def validate_comments_payload(comments_payload: dict[str, Any]) -> None:
    if not isinstance(comments_payload, dict):
        raise ValueError("Comments input must be a JSON object with a 'comments' list.")
    comments = comments_payload.get("comments")
    if not isinstance(comments, list):
        raise ValueError("Comments input must include a 'comments' list.")
    for index, entry in enumerate(comments):
        if not isinstance(entry, dict):
            raise ValueError(f"Each comment entry must be a JSON object. Invalid entry at comments[{index}].")
        if not _comment_entry_has_payload(entry):
            raise ValueError(
                f"Comment entry at comments[{index}] is empty. "
                "Provide at least one populated comment field before running ingest-comments."
            )


def normalize_comments(manifest: SyncManifest, comments_payload: dict[str, Any]) -> CommentIngestResult:
    result = CommentIngestResult()
    if not isinstance(comments_payload, dict):
        return result

    comments = comments_payload.get("comments")
    if not isinstance(comments, list):
        return result

    for raw_entry in comments:
        if not isinstance(raw_entry, dict):
            continue

        incoming_artifact_reference = _non_empty_str(raw_entry.get("artifact_id")) or _non_empty_str(raw_entry.get("section_id"))
        incoming_section_reference = _non_empty_str(raw_entry.get("section_id"))
        artifact_id, manifest_entry, unresolved_reason = _resolve_comment_target(manifest, raw_entry)
        incoming_source_artifact_id = (
            _non_empty_str(raw_entry.get("source_artifact_id"))
            or _artifact_source_hint(incoming_section_reference)
            or _artifact_source_hint(incoming_artifact_reference)
        )

        # Once a manifest entry is resolved, keep grouping/traceability anchored to the
        # canonical source artifact rather than any stale source hint from the payload.
        source_artifact_id = (
            _non_empty_str(manifest_entry.get("source_artifact_id"))
            or _non_empty_str(raw_entry.get("source_artifact_id"))
            or incoming_source_artifact_id
            or _artifact_source_hint(artifact_id)
            or artifact_id
            or ""
        )
        section_id = artifact_id or incoming_section_reference or incoming_artifact_reference or ""
        section_title = (
            _non_empty_str(manifest_entry.get("title"))
            or _non_empty_str(raw_entry.get("section_title"))
            or _last_title_segment(manifest_entry.get("section_title_path"))
            or section_id
            or incoming_artifact_reference
            or "Unknown section"
        )
        author = _non_empty_str(raw_entry.get("author")) or "Unknown"
        created_at = _non_empty_str(raw_entry.get("created_at")) or ""
        body = (_non_empty_str(raw_entry.get("body")) or "").strip()
        topic = _topic_label(raw_entry.get("topic"))
        published_object_id = (
            _non_empty_str(raw_entry.get("published_object_id"))
            or _non_empty_str(manifest_entry.get("item_id"))
            or ""
        )
        published_object_type = (
            _non_empty_str(raw_entry.get("published_object_type"))
            or _non_empty_str(manifest_entry.get("item_type"))
            or ""
        )
        miro_url = (
            _non_empty_str(raw_entry.get("miro_url"))
            or _non_empty_str(raw_entry.get("published_object_url"))
            or _non_empty_str(manifest_entry.get("miro_url"))
            or ""
        )
        published_object_reference = (
            _non_empty_str(raw_entry.get("published_object_reference"))
            or _non_empty_str(manifest_entry.get("target_key"))
            or (f"miro_item:{published_object_id}" if published_object_id else "")
        )

        if artifact_id and manifest_entry:
            result.resolved.append(
                NormalizedComment(
                    artifact_id=artifact_id,
                    source_artifact_id=source_artifact_id,
                    section_id=section_id or artifact_id,
                    section_title=section_title,
                    topic=topic,
                    author=author,
                    created_at=created_at,
                    body=body,
                    miro_url=miro_url,
                    published_object_id=published_object_id,
                    published_object_type=published_object_type,
                    published_object_reference=published_object_reference,
                )
            )
            continue

        result.unresolved.append(
            UnresolvedComment(
                incoming_artifact_reference=incoming_artifact_reference or "missing-artifact-id",
                source_artifact_id=source_artifact_id,
                section_id=section_id,
                section_title=section_title,
                topic=topic,
                author=author,
                created_at=created_at,
                body=body,
                miro_url=miro_url,
                published_object_id=published_object_id,
                published_object_type=published_object_type,
                published_object_reference=published_object_reference,
                reason=unresolved_reason or "No manifest entry matched the incoming artifact reference.",
            )
        )

    return result


def ingest_comments(
    manifest: SyncManifest,
    comments_payload: dict[str, Any],
    *,
    output_path: str | Path,
) -> Path:
    validate_comments_payload(comments_payload)
    normalized = normalize_comments(manifest, comments_payload)
    lines = _render_comments_markdown(normalized)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def _render_comments_markdown(result: CommentIngestResult) -> list[str]:
    lines = ["# Miro Review Feedback", ""]
    if not result.resolved and not result.unresolved:
        lines.extend(
            [
                "_No comments were ingested from Miro._",
                "",
            ]
        )
        return lines

    grouped: dict[str, dict[str, dict[str, list[NormalizedComment]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    section_index: dict[tuple[str, str], NormalizedComment] = {}

    for comment in result.resolved:
        grouped[comment.source_artifact_id][comment.section_id][comment.topic].append(comment)
        section_index.setdefault((comment.source_artifact_id, comment.section_id), comment)

    for source_artifact_id in sorted(grouped):
        lines.append(f"## {source_artifact_id}")
        lines.append("")
        for section_id in sorted(
            grouped[source_artifact_id],
            key=lambda value: (
                section_index[(source_artifact_id, value)].section_title,
                value,
            ),
        ):
            sample = section_index[(source_artifact_id, section_id)]
            lines.append(f"### {sample.section_title}")
            lines.append("")
            lines.extend(_section_traceability_lines(sample))
            lines.append("")
            for topic in sorted(grouped[source_artifact_id][section_id]):
                lines.append(f"#### {topic}")
                lines.append("")
                for comment in sorted(
                    grouped[source_artifact_id][section_id][topic],
                    key=lambda item: (item.created_at, item.author, item.body),
                ):
                    lines.extend(_comment_lines(comment))
                lines.append("")

    if result.unresolved:
        lines.append("## Unresolved Inputs")
        lines.append("")
        lines.append(
            "These comments could not be matched to a synced manifest entry and were not merged into any artifact section."
        )
        lines.append("")
        for comment in sorted(
            result.unresolved,
            key=lambda item: (item.incoming_artifact_reference, item.created_at, item.author, item.body),
        ):
            metadata = _comment_metadata(comment.author, comment.created_at, comment.miro_url)
            lines.extend(_bullet_lines(metadata, comment.body))
            if comment.topic:
                lines.append(f"  Topic: `{comment.topic}`")
            lines.append(f"  Incoming artifact reference: `{comment.incoming_artifact_reference}`")
            if comment.source_artifact_id:
                lines.append(f"  Incoming source artifact: `{comment.source_artifact_id}`")
            if comment.section_id:
                lines.append(f"  Incoming section id: `{comment.section_id}`")
            if comment.section_title:
                lines.append(f"  Incoming section title: `{comment.section_title}`")
            if comment.published_object_id:
                lines.append(f"  Published object: `{comment.published_object_id}`")
            if comment.published_object_reference:
                lines.append(f"  Object reference: `{comment.published_object_reference}`")
            lines.append(f"  Reason: {comment.reason}")
            lines.append("")

    return lines


def _section_traceability_lines(comment: NormalizedComment) -> list[str]:
    lines = [f"Section artifact: `{comment.section_id}`"]
    if comment.published_object_id:
        lines.append(f"Published object: `{comment.published_object_id}`")
    if comment.published_object_type:
        lines.append(f"Published object type: `{comment.published_object_type}`")
    if comment.published_object_reference:
        lines.append(f"Object reference: `{comment.published_object_reference}`")
    if comment.miro_url:
        lines.append(f"Miro link: {comment.miro_url}")
    return lines


def _comment_lines(comment: NormalizedComment) -> list[str]:
    lines = _bullet_lines(
        _comment_metadata(comment.author, comment.created_at, comment.miro_url),
        comment.body,
    )
    if comment.published_object_reference:
        lines.append(f"  Object reference: `{comment.published_object_reference}`")
    return lines


def _comment_metadata(author: str, created_at: str, miro_url: str) -> str:
    metadata = author
    if created_at:
        metadata += f" on {created_at}"
    if miro_url:
        metadata += f" ({miro_url})"
    return metadata


def _bullet_lines(metadata: str, body: str) -> list[str]:
    body_lines = body.splitlines() or [""]
    lines = [f"- {metadata}: {body_lines[0]}"]
    for continuation in body_lines[1:]:
        lines.append(f"  {continuation}")
    return lines


def _last_title_segment(value: Any) -> str:
    if isinstance(value, list) and value:
        return _non_empty_str(value[-1]) or ""
    return ""


def _topic_label(value: Any) -> str:
    topic = _non_empty_str(value)
    if not topic:
        return DEFAULT_TOPIC
    topic = " ".join(segment.strip() for segment in topic.splitlines() if segment.strip())
    topic = topic.lstrip("#").strip()
    return topic or DEFAULT_TOPIC


def _resolve_manifest_entry(
    manifest: SyncManifest,
    raw_entry: dict[str, Any],
    incoming_artifact_reference: str,
) -> tuple[str, dict[str, Any]]:
    if incoming_artifact_reference:
        direct_match = manifest.items.get(incoming_artifact_reference)
        if direct_match:
            return incoming_artifact_reference, direct_match

    source_artifact_id = (
        _non_empty_str(raw_entry.get("source_artifact_id")) or _artifact_source_hint(incoming_artifact_reference)
    )
    section_title = _non_empty_str(raw_entry.get("section_title"))
    artifact_slug = _artifact_slug_hint(incoming_artifact_reference)

    scored_candidates: list[tuple[int, str, dict[str, Any]]] = []
    for candidate_artifact_id, candidate_entry in manifest.items.items():
        candidate_source = _non_empty_str(candidate_entry.get("source_artifact_id"))
        if source_artifact_id and candidate_source != source_artifact_id:
            continue

        score = 0
        if section_title and _section_title_matches(candidate_entry, section_title):
            score += 2
        if artifact_slug and _artifact_slug_hint(candidate_artifact_id) == artifact_slug:
            score += 1
        if score:
            scored_candidates.append((score, candidate_artifact_id, candidate_entry))

    if not scored_candidates:
        return incoming_artifact_reference, {}

    best_score = max(score for score, _, _ in scored_candidates)
    best_matches = [
        (candidate_artifact_id, candidate_entry)
        for score, candidate_artifact_id, candidate_entry in scored_candidates
        if score == best_score
    ]
    if len(best_matches) != 1:
        return incoming_artifact_reference, {}

    return best_matches[0]


def _resolve_comment_target(
    manifest: SyncManifest,
    raw_entry: dict[str, Any],
) -> tuple[str, dict[str, Any], str]:
    artifact_reference = _non_empty_str(raw_entry.get("artifact_id"))
    section_reference = _non_empty_str(raw_entry.get("section_id"))

    section_artifact_id = ""
    section_entry: dict[str, Any] = {}
    if section_reference:
        section_artifact_id, section_entry = _resolve_manifest_entry(manifest, raw_entry, section_reference)

    artifact_artifact_id = ""
    artifact_entry: dict[str, Any] = {}
    if artifact_reference and artifact_reference != section_reference:
        artifact_artifact_id, artifact_entry = _resolve_manifest_entry(manifest, raw_entry, artifact_reference)

    if artifact_reference and section_reference and artifact_reference != section_reference:
        if section_entry and artifact_entry and section_artifact_id != artifact_artifact_id:
            return "", {}, "Incoming artifact_id and section_id resolved to different manifest entries."
        if section_entry:
            return section_artifact_id, section_entry, ""
        return "", {}, "Incoming artifact_id and section_id disagree and could not be reconciled safely."

    if section_reference:
        return section_artifact_id, section_entry, ""
    if artifact_reference:
        return artifact_artifact_id, artifact_entry, ""
    return "", {}, ""


def _section_title_matches(candidate_entry: dict[str, Any], section_title: str) -> bool:
    candidate_titles = {
        _non_empty_str(candidate_entry.get("title")),
        _last_title_segment(candidate_entry.get("section_title_path")),
        _title_tail(_non_empty_str(candidate_entry.get("title"))),
    }
    normalized_title = _non_empty_str(section_title)
    return normalized_title in candidate_titles or _title_tail(normalized_title) in candidate_titles


def _title_tail(value: str) -> str:
    if not value:
        return ""
    return value.split("/")[-1].strip()


def _artifact_source_hint(reference: str) -> str:
    if "#" in reference:
        return reference.split("#", 1)[0].strip()
    return ""


def _artifact_slug_hint(reference: str) -> str:
    if "#" not in reference:
        return ""
    return reference.rsplit("/", 1)[-1].split("#", 1)[-1].strip()


def _non_empty_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _comment_entry_has_payload(entry: dict[str, Any]) -> bool:
    for field_name in (
        "artifact_id",
        "section_id",
        "source_artifact_id",
        "section_title",
        "topic",
        "author",
        "created_at",
        "body",
        "miro_url",
        "published_object_url",
        "published_object_id",
        "published_object_type",
        "published_object_reference",
    ):
        if _non_empty_str(entry.get(field_name)):
            return True
    return False
