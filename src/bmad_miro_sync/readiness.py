from __future__ import annotations

from dataclasses import dataclass, field

from .classifier import classify_artifact, workstream_rank
from .decisions import DecisionRecord


DEFAULT_READINESS_SUMMARY_OUTPUT = "_bmad-output/implementation-artifacts/implementation-readiness.md"
DEFAULT_READINESS_HANDOFF_OUTPUT = "_bmad-output/implementation-artifacts/implementation-handoff.md"
REQUIRED_READINESS_WORKSTREAMS: tuple[str, ...] = ("product", "ux", "architecture", "delivery")
_READY_STATUSES = {"accepted", "resolved"}
_AT_RISK_STATUSES = {"open", "deferred"}


@dataclass(slots=True, frozen=True)
class ReadinessEntry:
    workstream: str
    source_artifact_id: str
    section_id: str
    section_title: str
    topic: str
    status: str
    owner: str
    rationale: str
    follow_up_notes: str
    is_unresolved: bool


@dataclass(slots=True)
class WorkstreamReadinessSummary:
    workstream: str
    state: str
    has_review_evidence: bool
    records: list[ReadinessEntry] = field(default_factory=list)
    blockers: list[ReadinessEntry] = field(default_factory=list)
    deferred_items: list[ReadinessEntry] = field(default_factory=list)
    open_questions: list[ReadinessEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source_artifact_ids: list[str] = field(default_factory=list)

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in ("blocked", "deferred", "open", "accepted", "resolved")}
        for record in self.records:
            counts[record.status] = counts.get(record.status, 0) + 1
        return counts


@dataclass(slots=True)
class ReadinessAggregate:
    overall_state: str
    workstreams: dict[str, WorkstreamReadinessSummary]
    blockers: list[ReadinessEntry] = field(default_factory=list)
    deferred_items: list[ReadinessEntry] = field(default_factory=list)
    open_questions: list[ReadinessEntry] = field(default_factory=list)
    missing_workstreams: list[str] = field(default_factory=list)
    source_artifact_ids: list[str] = field(default_factory=list)


def workstream_for_record(record: DecisionRecord) -> str:
    classification = classify_artifact(record.source_artifact_id or record.section_id)
    if classification.workstream in REQUIRED_READINESS_WORKSTREAMS:
        return classification.workstream

    owner = record.owner.strip().lower()
    if owner in REQUIRED_READINESS_WORKSTREAMS:
        return owner
    return "general"


def aggregate_readiness(records: list[DecisionRecord]) -> ReadinessAggregate:
    workstreams: dict[str, WorkstreamReadinessSummary] = {
        workstream: WorkstreamReadinessSummary(
            workstream=workstream,
            state="at risk",
            has_review_evidence=False,
        )
        for workstream in REQUIRED_READINESS_WORKSTREAMS
    }

    entries = sorted((_entry_from_record(record) for record in records), key=_entry_sort_key)
    blockers = [entry for entry in entries if entry.status == "blocked"]
    deferred_items = [entry for entry in entries if entry.status == "deferred"]
    open_questions = [entry for entry in entries if entry.status == "open"]

    for entry in entries:
        if entry.workstream not in workstreams:
            continue
        summary = workstreams[entry.workstream]
        summary.has_review_evidence = True
        summary.records.append(entry)
        if entry.status == "blocked":
            summary.blockers.append(entry)
        elif entry.status == "deferred":
            summary.deferred_items.append(entry)
        elif entry.status == "open":
            summary.open_questions.append(entry)

    missing_workstreams: list[str] = []
    for workstream in REQUIRED_READINESS_WORKSTREAMS:
        summary = workstreams[workstream]
        summary.source_artifact_ids = _ordered_unique(entry.source_artifact_id for entry in summary.records)
        if not summary.has_review_evidence:
            summary.state = "at risk"
            summary.notes.append("No decision-backed review evidence exists for this workstream.")
            missing_workstreams.append(workstream)
            continue
        if summary.blockers:
            summary.state = "blocked"
            summary.notes.append("Blocked topics remain and must be cleared before implementation handoff.")
            continue
        if summary.deferred_items or summary.open_questions:
            summary.state = "at risk"
            if summary.open_questions:
                summary.notes.append("Open questions remain for this workstream.")
            if summary.deferred_items:
                summary.notes.append("Deferred follow-up remains for this workstream.")
            continue
        summary.state = "ready"

    if blockers:
        overall_state = "blocked"
    elif deferred_items or open_questions or missing_workstreams:
        overall_state = "at risk"
    else:
        overall_state = "ready"

    return ReadinessAggregate(
        overall_state=overall_state,
        workstreams=workstreams,
        blockers=blockers,
        deferred_items=deferred_items,
        open_questions=open_questions,
        missing_workstreams=missing_workstreams,
        source_artifact_ids=_ordered_unique(entry.source_artifact_id for entry in entries),
    )


def render_readiness_summary(aggregate: ReadinessAggregate) -> str:
    lines = [
        "# Implementation Readiness",
        "",
        f"Overall readiness: {aggregate.overall_state.title()}",
        f"Required workstreams covered: {_covered_workstreams_count(aggregate)}/{len(REQUIRED_READINESS_WORKSTREAMS)}",
        f"Blockers: {len(aggregate.blockers)}",
        f"Deferred items: {len(aggregate.deferred_items)}",
        f"Open questions: {len(aggregate.open_questions)}",
        "Missing workstream coverage: " + (_label_list(aggregate.missing_workstreams) or "None"),
        "",
        "## Source Artifacts",
        "",
    ]

    if aggregate.source_artifact_ids:
        for source_artifact_id in aggregate.source_artifact_ids:
            lines.append(f"- `{source_artifact_id}`")
    else:
        lines.append("- No decision records were available.")
    lines.extend(["", "## Review Activity", ""])

    for workstream in REQUIRED_READINESS_WORKSTREAMS:
        summary = aggregate.workstreams[workstream]
        counts = summary.status_counts()
        lines.append(f"### {workstream.title()}")
        lines.append("")
        lines.append(f"Workstream readiness: {summary.state.title()}")
        lines.append(f"Review evidence: {'Present' if summary.has_review_evidence else 'Missing'}")
        lines.append(f"Artifacts reviewed: {', '.join(f'`{artifact}`' for artifact in summary.source_artifact_ids) or 'None'}")
        lines.append(f"Blocked topics: {counts['blocked']}")
        lines.append(f"Deferred topics: {counts['deferred']}")
        lines.append(f"Open topics: {counts['open']}")
        lines.append(f"Accepted topics: {counts['accepted']}")
        lines.append(f"Resolved topics: {counts['resolved']}")
        if summary.notes:
            lines.append("Notes:")
            for note in summary.notes:
                lines.append(f"- {note}")
        if summary.blockers:
            lines.append("Blockers:")
            lines.extend(_render_entry_lines(summary.blockers))
        if summary.deferred_items:
            lines.append("Deferred items:")
            lines.extend(_render_entry_lines(summary.deferred_items))
        if summary.open_questions:
            lines.append("Open questions:")
            lines.extend(_render_entry_lines(summary.open_questions))
        lines.append("")

    lines.extend(["## Readiness Conclusions", ""])
    lines.append(f"- Overall handoff state: {aggregate.overall_state.title()}")
    if aggregate.blockers:
        lines.append("- Blocking issues:")
        lines.extend(_render_entry_lines(aggregate.blockers))
    if aggregate.deferred_items:
        lines.append("- Deferred follow-up:")
        lines.extend(_render_entry_lines(aggregate.deferred_items))
    if aggregate.open_questions:
        lines.append("- Open questions:")
        lines.extend(_render_entry_lines(aggregate.open_questions))
    if aggregate.missing_workstreams:
        lines.append("- Missing review evidence:")
        for workstream in aggregate.missing_workstreams:
            lines.append(f"  - {workstream.title()}")
    if not (aggregate.blockers or aggregate.deferred_items or aggregate.open_questions or aggregate.missing_workstreams):
        lines.append("- All required workstreams have decision-backed evidence and no blocking follow-up remains.")

    return "\n".join(lines).rstrip() + "\n"


def render_handoff_output(aggregate: ReadinessAggregate) -> str:
    lines = [
        "# Implementation Handoff",
        "",
        f"Overall readiness: {aggregate.overall_state.title()}",
        f"Ready for implementation handoff: {'Yes' if aggregate.overall_state == 'ready' else 'No'}",
        "Blocking topics requiring action: " + str(len(aggregate.blockers)),
        "Deferred follow-up items: " + str(len(aggregate.deferred_items)),
        "Open questions: " + str(len(aggregate.open_questions)),
        "Missing workstream coverage: " + (_label_list(aggregate.missing_workstreams) or "None"),
        "",
        "## Source Artifacts",
        "",
    ]

    if aggregate.source_artifact_ids:
        for source_artifact_id in aggregate.source_artifact_ids:
            lines.append(f"- `{source_artifact_id}`")
    else:
        lines.append("- No decision records were available.")

    lines.extend(["", "## Workstream Handoff", ""])
    for workstream in REQUIRED_READINESS_WORKSTREAMS:
        summary = aggregate.workstreams[workstream]
        lines.append(f"### {workstream.title()}")
        lines.append("")
        lines.append(f"Status: {summary.state.title()}")
        if not summary.has_review_evidence:
            lines.append("Action: Gather decision-backed review evidence before implementation planning.")
            lines.append("")
            continue
        if summary.state == "ready":
            lines.append("Action: No follow-up required for implementation handoff.")
            lines.append("")
            continue

        if summary.blockers:
            lines.append("Blocking items:")
            lines.extend(_render_entry_lines(summary.blockers))
        if summary.deferred_items:
            lines.append("Deferred follow-up:")
            lines.extend(_render_entry_lines(summary.deferred_items))
        if summary.open_questions:
            lines.append("Open questions:")
            lines.extend(_render_entry_lines(summary.open_questions))
        lines.append("")

    lines.extend(["## Cross-Workstream Follow-Up", ""])
    if aggregate.blockers:
        lines.append("Blocking items:")
        lines.extend(_render_entry_lines(aggregate.blockers))
    if aggregate.deferred_items:
        lines.append("Deferred follow-up:")
        lines.extend(_render_entry_lines(aggregate.deferred_items))
    if aggregate.open_questions:
        lines.append("Open questions:")
        lines.extend(_render_entry_lines(aggregate.open_questions))
    if aggregate.missing_workstreams:
        lines.append("Missing review evidence:")
        for workstream in aggregate.missing_workstreams:
            lines.append(f"- {workstream.title()}")
    if not (aggregate.blockers or aggregate.deferred_items or aggregate.open_questions or aggregate.missing_workstreams):
        lines.append("No cross-workstream follow-up remains.")

    return "\n".join(lines).rstrip() + "\n"


def _entry_from_record(record: DecisionRecord) -> ReadinessEntry:
    return ReadinessEntry(
        workstream=workstream_for_record(record),
        source_artifact_id=record.source_artifact_id,
        section_id=record.section_id,
        section_title=record.section_title,
        topic=record.topic,
        status=record.status,
        owner=record.owner,
        rationale=record.rationale,
        follow_up_notes=record.follow_up_notes,
        is_unresolved=record.is_unresolved,
    )


def _render_entry_lines(entries: list[ReadinessEntry]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        lines.append(f"- {entry.topic} [{entry.status.title()}]")
        lines.append(f"  Artifact: `{entry.source_artifact_id}`")
        lines.append(f"  Section: `{entry.section_id}`")
        lines.append(f"  Owner: {entry.owner}")
        lines.append(f"  Rationale: {entry.rationale}")
        if entry.follow_up_notes:
            lines.append(f"  Follow-up: {entry.follow_up_notes}")
    return lines


def _covered_workstreams_count(aggregate: ReadinessAggregate) -> int:
    return sum(1 for summary in aggregate.workstreams.values() if summary.has_review_evidence)


def _entry_sort_key(entry: ReadinessEntry) -> tuple[int, str, str, str]:
    return (
        workstream_rank(entry.workstream),
        entry.source_artifact_id,
        entry.section_title,
        entry.topic,
    )


def _ordered_unique(values) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _label_list(values: list[str]) -> str:
    return ", ".join(value.title() for value in values)
