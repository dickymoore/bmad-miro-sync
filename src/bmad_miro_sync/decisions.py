from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from .comments import DEFAULT_TOPIC, NormalizedComment, UnresolvedComment, normalize_comments
from .manifest import SyncManifest


DEFAULT_DECISION_RECORDS_OUTPUT = "_bmad-output/review-artifacts/decision-records.md"
DEFAULT_DECISION_RECORDS_SIDECAR_OUTPUT = "_bmad-output/review-artifacts/decision-records.json"
DECISION_STATUSES: tuple[str, ...] = ("open", "accepted", "deferred", "resolved", "blocked")
_UNRESOLVED_ALLOWED_STATUSES = {"open", "blocked"}
_AWAITING_TRIAGE = "Awaiting triage"


@dataclass(slots=True, frozen=True)
class DecisionTriageAssignment:
    section_id: str
    topic: str
    status: str
    owner: str
    rationale: str
    source_artifact_id: str = ""
    follow_up_notes: str = ""


@dataclass(slots=True)
class DecisionRecord:
    source_artifact_id: str
    section_id: str
    section_title: str
    topic: str
    status: str
    owner: str
    rationale: str
    follow_up_notes: str = ""
    is_unresolved: bool = False
    incoming_artifact_reference: str = ""
    published_object_id: str = ""
    published_object_type: str = ""
    published_object_reference: str = ""
    miro_url: str = ""
    comments: list[NormalizedComment | UnresolvedComment] = field(default_factory=list)
    unresolved_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DecisionTriageResult:
    records: list[DecisionRecord] = field(default_factory=list)

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in DECISION_STATUSES}
        for record in self.records:
            counts[record.status] += 1
        return counts


@dataclass(slots=True)
class _Bundle:
    source_artifact_id: str
    section_id: str
    section_title: str
    topic: str
    is_unresolved: bool
    incoming_artifact_reference: str = ""
    published_object_id: str = ""
    published_object_type: str = ""
    published_object_reference: str = ""
    miro_url: str = ""
    comments: list[NormalizedComment | UnresolvedComment] = field(default_factory=list)
    unresolved_reasons: list[str] = field(default_factory=list)


def triage_feedback(manifest: SyncManifest, review_payload: dict[str, Any]) -> DecisionTriageResult:
    if not isinstance(review_payload, dict):
        raise ValueError("Review input must be a JSON object with a 'comments' list and optional 'triage' list.")
    if "comments" not in review_payload or not isinstance(review_payload.get("comments"), list):
        raise ValueError("Review input must include a 'comments' list.")

    payload = review_payload
    normalized = normalize_comments(manifest, payload)
    bundles = _bundle_comments(normalized.resolved, normalized.unresolved)
    assignments = _load_assignments(payload.get("triage"))
    bundle_assignments = _resolve_bundle_assignments(bundles, assignments)

    records: list[DecisionRecord] = []
    for index, bundle in enumerate(bundles):
        assignment = bundle_assignments.get(index)
        if assignment is not None:
            status = assignment.status
            owner = assignment.owner
            rationale = assignment.rationale
            follow_up_notes = assignment.follow_up_notes
        else:
            status = "open"
            owner = _AWAITING_TRIAGE
            rationale = _AWAITING_TRIAGE
            follow_up_notes = ""

        if bundle.is_unresolved and status not in _UNRESOLVED_ALLOWED_STATUSES:
            raise ValueError("Unresolved bundles may only be triaged as open or blocked.")

        records.append(
            DecisionRecord(
                source_artifact_id=bundle.source_artifact_id,
                section_id=bundle.section_id,
                section_title=bundle.section_title,
                topic=bundle.topic,
                status=status,
                owner=owner,
                rationale=rationale,
                follow_up_notes=follow_up_notes,
                is_unresolved=bundle.is_unresolved,
                incoming_artifact_reference=bundle.incoming_artifact_reference,
                published_object_id=bundle.published_object_id,
                published_object_type=bundle.published_object_type,
                published_object_reference=bundle.published_object_reference,
                miro_url=bundle.miro_url,
                comments=list(bundle.comments),
                unresolved_reasons=list(bundle.unresolved_reasons),
            )
        )
    return DecisionTriageResult(records=records)


def write_decision_records(result: DecisionTriageResult, *, output_path: str | Path) -> Path:
    lines = _render_decision_records_markdown(result)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def write_decision_sidecar(result: DecisionTriageResult, *, output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(decision_result_to_dict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def decision_result_to_dict(result: DecisionTriageResult) -> dict[str, Any]:
    return {
        "status_counts": result.status_counts(),
        "decision_records": [_decision_record_to_dict(record) for record in result.records],
    }


def decision_result_from_dict(payload: dict[str, Any]) -> DecisionTriageResult:
    if not isinstance(payload, dict):
        raise ValueError("Decision sidecar payload must be a JSON object.")
    raw_records = payload.get("decision_records")
    if not isinstance(raw_records, list):
        raise ValueError("Decision sidecar payload must include a 'decision_records' list.")

    records: list[DecisionRecord] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, dict):
            raise ValueError("Each decision record must be a JSON object.")
        records.append(_decision_record_from_dict(raw_record))
    return DecisionTriageResult(records=records)


def _bundle_comments(
    resolved: list[NormalizedComment],
    unresolved: list[UnresolvedComment],
) -> list[_Bundle]:
    ordered: list[_Bundle] = []
    by_key: dict[tuple[str, str, str, bool], _Bundle] = {}

    for comment in sorted(resolved, key=lambda item: (item.source_artifact_id, item.section_title, item.topic, item.created_at, item.author, item.body)):
        key = (comment.source_artifact_id, comment.section_id, comment.topic, False)
        bundle = by_key.get(key)
        if bundle is None:
            bundle = _Bundle(
                source_artifact_id=comment.source_artifact_id,
                section_id=comment.section_id,
                section_title=comment.section_title,
                topic=comment.topic,
                is_unresolved=False,
                published_object_id=comment.published_object_id,
                published_object_type=comment.published_object_type,
                published_object_reference=comment.published_object_reference,
                miro_url=comment.miro_url,
            )
            by_key[key] = bundle
            ordered.append(bundle)
        bundle.comments.append(comment)

    for comment in sorted(
        unresolved,
        key=lambda item: (item.source_artifact_id, item.section_title, item.topic, item.created_at, item.author, item.body),
    ):
        source_artifact_id = comment.source_artifact_id or _artifact_source_hint(comment.incoming_artifact_reference) or "unresolved-inputs"
        section_id = comment.section_id or comment.incoming_artifact_reference or "missing-artifact-id"
        section_title = comment.section_title or section_id or "Unknown section"
        key = (source_artifact_id, section_id, comment.topic, True)
        bundle = by_key.get(key)
        if bundle is None:
            bundle = _Bundle(
                source_artifact_id=source_artifact_id,
                section_id=section_id,
                section_title=section_title,
                topic=comment.topic,
                is_unresolved=True,
                incoming_artifact_reference=comment.incoming_artifact_reference,
                published_object_id=comment.published_object_id,
                published_object_type=comment.published_object_type,
                published_object_reference=comment.published_object_reference,
                miro_url=comment.miro_url,
            )
            by_key[key] = bundle
            ordered.append(bundle)
        bundle.comments.append(comment)
        if comment.reason and comment.reason not in bundle.unresolved_reasons:
            bundle.unresolved_reasons.append(comment.reason)

    return ordered


def _load_assignments(raw_assignments: Any) -> list[DecisionTriageAssignment]:
    if raw_assignments is None:
        return []
    if not isinstance(raw_assignments, list):
        raise ValueError("Triage input must be a list of assignment objects.")

    assignments: list[DecisionTriageAssignment] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for raw_assignment in raw_assignments:
        if not isinstance(raw_assignment, dict):
            raise ValueError("Each triage assignment must be a JSON object.")

        section_id = _non_empty_str(raw_assignment.get("section_id"))
        raw_topic = _non_empty_str(raw_assignment.get("topic"))
        topic = _topic_label(raw_topic) if raw_topic else ""
        status = _validated_decision_status(
            raw_assignment.get("status"),
            context="triage assignment",
        )
        owner = _non_empty_str(raw_assignment.get("owner"))
        rationale = _non_empty_str(raw_assignment.get("rationale"))
        source_artifact_id = _non_empty_str(raw_assignment.get("source_artifact_id"))
        follow_up_notes = _non_empty_str(raw_assignment.get("follow_up_notes"))

        missing_fields = [
            field_name
            for field_name, value in (
                ("section_id", section_id),
                ("topic", topic),
                ("status", status),
                ("owner", owner),
                ("rationale", rationale),
            )
            if not value
        ]
        if missing_fields:
            raise ValueError("Each triage assignment must include: " + ", ".join(missing_fields) + ".")
        key = (source_artifact_id, section_id, topic)
        if key in seen_keys:
            if source_artifact_id:
                raise ValueError(
                    f"Duplicate triage assignment for {source_artifact_id} / {section_id} / {topic}."
                )
            raise ValueError(f"Duplicate triage assignment for {section_id} / {topic}.")
        seen_keys.add(key)
        assignments.append(
            DecisionTriageAssignment(
                section_id=section_id,
                topic=topic,
                status=status,
                owner=owner,
                rationale=rationale,
                source_artifact_id=source_artifact_id,
                follow_up_notes=follow_up_notes,
            )
        )

    return assignments


def _resolve_bundle_assignments(
    bundles: list[_Bundle],
    assignments: list[DecisionTriageAssignment],
) -> dict[int, DecisionTriageAssignment]:
    bundle_assignments: dict[int, DecisionTriageAssignment] = {}

    for assignment in assignments:
        matching_indexes = [
            index
            for index, bundle in enumerate(bundles)
            if bundle.section_id == assignment.section_id
            and bundle.topic == assignment.topic
            and (
                not assignment.source_artifact_id
                or assignment.source_artifact_id == bundle.source_artifact_id
            )
        ]

        if not matching_indexes:
            raise ValueError(
                f"No grouped bundle matched triage entry for {assignment.section_id} / {assignment.topic}."
            )

        if len(matching_indexes) > 1:
            raise ValueError(
                "Triage entry matched multiple grouped bundles for "
                f"{assignment.section_id} / {assignment.topic}; include source_artifact_id to disambiguate."
            )

        bundle_index = matching_indexes[0]
        if bundle_index in bundle_assignments:
            raise ValueError(
                "Multiple triage entries matched the grouped bundle for "
                f"{assignment.section_id} / {assignment.topic}."
            )
        bundle_assignments[bundle_index] = assignment

    return bundle_assignments


def _render_decision_records_markdown(result: DecisionTriageResult) -> list[str]:
    counts = result.status_counts()
    lines = [
        "# Decision Records",
        "",
        "Open topics: " + str(counts["open"]),
        "Blocked topics: " + str(counts["blocked"]),
        "Deferred topics: " + str(counts["deferred"]),
        "Accepted topics: " + str(counts["accepted"]),
        "Resolved topics: " + str(counts["resolved"]),
        "",
        "## Status Legend",
        "",
        "- Open: Waiting for an explicit decision or more information.",
        "- Blocked: Cannot move forward until an external blocker is cleared.",
        "- Deferred: Agreed to revisit later.",
        "- Accepted: Agreed change to make.",
        "- Resolved: Follow-up is complete and no further action is needed.",
        "",
    ]

    if not result.records:
        lines.extend(
            [
                "_No decision records were produced from the supplied review input._",
                "",
            ]
        )
        return lines

    resolved_records = [record for record in result.records if not record.is_unresolved]
    unresolved_records = [record for record in result.records if record.is_unresolved]

    for source_artifact_id, records in _group_records_by_source(resolved_records).items():
        lines.append(f"## {source_artifact_id}")
        lines.append("")
        lines.extend(_render_source_records(records))

    if unresolved_records:
        lines.append("## Unresolved Inputs")
        lines.append("")
        lines.append("These bundles could not be matched cleanly to a published manifest section and remain visibly unresolved.")
        lines.append("")
        lines.extend(_render_source_records(unresolved_records, show_incoming_source=True))

    return lines


def _group_records_by_source(records: list[DecisionRecord]) -> dict[str, list[DecisionRecord]]:
    grouped: dict[str, list[DecisionRecord]] = defaultdict(list)
    for record in records:
        grouped[record.source_artifact_id].append(record)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def _render_source_records(records: list[DecisionRecord], *, show_incoming_source: bool = False) -> list[str]:
    lines: list[str] = []
    ordered = sorted(records, key=lambda item: (item.section_title, item.section_id, item.topic))
    for section_id in _ordered_section_ids(ordered):
        section_records = [record for record in ordered if record.section_id == section_id]
        sample = section_records[0]
        lines.append(f"### {sample.section_title}")
        lines.append("")
        lines.append(f"Section artifact: `{sample.section_id}`")
        if show_incoming_source and sample.source_artifact_id:
            lines.append(f"Incoming source artifact: `{sample.source_artifact_id}`")
        if sample.incoming_artifact_reference:
            lines.append(f"Incoming artifact reference: `{sample.incoming_artifact_reference}`")
        if sample.published_object_id:
            lines.append(f"Published object: `{sample.published_object_id}`")
        if sample.published_object_type:
            lines.append(f"Published object type: `{sample.published_object_type}`")
        if sample.published_object_reference:
            lines.append(f"Object reference: `{sample.published_object_reference}`")
        if sample.miro_url:
            lines.append(f"Miro link: {sample.miro_url}")
        lines.append("")

        for record in section_records:
            lines.append(f"#### {record.topic}")
            lines.append("")
            lines.append(f"- Status: {record.status.title()}")
            lines.append(f"- Owner: {record.owner}")
            lines.append(f"- Rationale: {record.rationale}")
            if record.follow_up_notes:
                lines.append(f"- Follow-up notes: {record.follow_up_notes}")
            if record.unresolved_reasons:
                for reason in record.unresolved_reasons:
                    lines.append(f"- Resolution blocker: {reason}")
            lines.append("- Comments:")
            for comment in sorted(record.comments, key=lambda item: (item.created_at, item.author, item.body)):
                lines.extend(_comment_lines(comment))
            lines.append("")

    return lines


def _ordered_section_ids(records: list[DecisionRecord]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for record in records:
        if record.section_id in seen:
            continue
        seen.add(record.section_id)
        ordered.append(record.section_id)
    return ordered


def _comment_lines(comment: NormalizedComment | UnresolvedComment) -> list[str]:
    metadata = comment.author
    if comment.created_at:
        metadata += f" on {comment.created_at}"
    if comment.miro_url:
        metadata += f" ({comment.miro_url})"
    body_lines = comment.body.splitlines() or [""]
    lines = [f"  - {metadata}: {body_lines[0]}"]
    for continuation in body_lines[1:]:
        lines.append(f"    {continuation}")
    return lines


def _artifact_source_hint(reference: str) -> str:
    if "#" in reference:
        return reference.split("#", 1)[0].strip()
    return ""


def _topic_label(value: Any) -> str:
    topic = _non_empty_str(value)
    if not topic:
        return DEFAULT_TOPIC
    topic = " ".join(segment.strip() for segment in topic.splitlines() if segment.strip())
    topic = topic.lstrip("#").strip()
    return topic or DEFAULT_TOPIC


def _non_empty_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _validated_decision_status(value: Any, *, context: str) -> str:
    status = _non_empty_str(value).lower()
    if status not in DECISION_STATUSES:
        approved = ", ".join(DECISION_STATUSES)
        raise ValueError(f"Unknown decision status '{status}' in {context}. Approved statuses: {approved}.")
    return status


def _decision_record_to_dict(record: DecisionRecord) -> dict[str, Any]:
    payload = asdict(record)
    payload["comments"] = [_comment_to_dict(comment) for comment in record.comments]
    return payload


def _decision_record_from_dict(payload: dict[str, Any]) -> DecisionRecord:
    comments: list[NormalizedComment | UnresolvedComment] = []
    for raw_comment in payload.get("comments", []):
        if not isinstance(raw_comment, dict):
            raise ValueError("Each serialized comment must be a JSON object.")
        comments.append(_comment_from_dict(raw_comment))

    status = _validated_decision_status(
        payload.get("status"),
        context="serialized decision record",
    )
    is_unresolved = bool(payload.get("is_unresolved", False))
    if is_unresolved and status not in _UNRESOLVED_ALLOWED_STATUSES:
        raise ValueError("Serialized unresolved decision records may only be open or blocked.")

    return DecisionRecord(
        source_artifact_id=_non_empty_str(payload.get("source_artifact_id")),
        section_id=_non_empty_str(payload.get("section_id")),
        section_title=_non_empty_str(payload.get("section_title")),
        topic=_non_empty_str(payload.get("topic")),
        status=status,
        owner=_non_empty_str(payload.get("owner")),
        rationale=_non_empty_str(payload.get("rationale")),
        follow_up_notes=_non_empty_str(payload.get("follow_up_notes")),
        is_unresolved=is_unresolved,
        incoming_artifact_reference=_non_empty_str(payload.get("incoming_artifact_reference")),
        published_object_id=_non_empty_str(payload.get("published_object_id")),
        published_object_type=_non_empty_str(payload.get("published_object_type")),
        published_object_reference=_non_empty_str(payload.get("published_object_reference")),
        miro_url=_non_empty_str(payload.get("miro_url")),
        comments=comments,
        unresolved_reasons=[
            _non_empty_str(reason)
            for reason in payload.get("unresolved_reasons", [])
            if _non_empty_str(reason)
        ],
    )


def _comment_to_dict(comment: NormalizedComment | UnresolvedComment) -> dict[str, Any]:
    payload = asdict(comment)
    payload["kind"] = "unresolved" if isinstance(comment, UnresolvedComment) else "resolved"
    return payload


def _comment_from_dict(payload: dict[str, Any]) -> NormalizedComment | UnresolvedComment:
    kind = _non_empty_str(payload.get("kind")).lower()
    if kind == "unresolved" or "reason" in payload or "incoming_artifact_reference" in payload:
        return UnresolvedComment(
            incoming_artifact_reference=_non_empty_str(payload.get("incoming_artifact_reference")),
            source_artifact_id=_non_empty_str(payload.get("source_artifact_id")),
            section_id=_non_empty_str(payload.get("section_id")),
            section_title=_non_empty_str(payload.get("section_title")),
            topic=_topic_label(payload.get("topic")),
            author=_non_empty_str(payload.get("author")),
            created_at=_non_empty_str(payload.get("created_at")),
            body=_non_empty_str(payload.get("body")),
            miro_url=_non_empty_str(payload.get("miro_url")),
            published_object_id=_non_empty_str(payload.get("published_object_id")),
            published_object_type=_non_empty_str(payload.get("published_object_type")),
            published_object_reference=_non_empty_str(payload.get("published_object_reference")),
            reason=_non_empty_str(payload.get("reason")),
        )

    return NormalizedComment(
        artifact_id=_non_empty_str(payload.get("artifact_id")),
        source_artifact_id=_non_empty_str(payload.get("source_artifact_id")),
        section_id=_non_empty_str(payload.get("section_id")),
        section_title=_non_empty_str(payload.get("section_title")),
        topic=_topic_label(payload.get("topic")),
        author=_non_empty_str(payload.get("author")),
        created_at=_non_empty_str(payload.get("created_at")),
        body=_non_empty_str(payload.get("body")),
        miro_url=_non_empty_str(payload.get("miro_url")),
        published_object_id=_non_empty_str(payload.get("published_object_id")),
        published_object_type=_non_empty_str(payload.get("published_object_type")),
        published_object_reference=_non_empty_str(payload.get("published_object_reference")),
    )
