from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


PHASE_ZONE_ORDER: tuple[str, ...] = (
    "analysis",
    "planning",
    "solutioning",
    "implementation_readiness",
    "delivery_feedback",
)

WORKSTREAM_ORDER: tuple[str, ...] = (
    "product",
    "ux",
    "architecture",
    "delivery",
    "general",
)

CANONICAL_SOURCE_NAME_ALIASES: dict[str, str] = {
    "updated-prd": "prd",
}


@dataclass(frozen=True, slots=True)
class ArtifactClassification:
    kind: str
    phase: str
    phase_zone: str
    workstream: str
    collaboration_intent: str


CLASSIFICATION_RULES: tuple[tuple[str, ArtifactClassification], ...] = (
    (
        "product-brief",
        ArtifactClassification(
            kind="product_brief",
            phase="analysis",
            phase_zone="analysis",
            workstream="product",
            collaboration_intent="anchor",
        ),
    ),
    (
        "brainstorm",
        ArtifactClassification(
            kind="brainstorm",
            phase="analysis",
            phase_zone="analysis",
            workstream="product",
            collaboration_intent="anchor",
        ),
    ),
    (
        "research",
        ArtifactClassification(
            kind="research",
            phase="analysis",
            phase_zone="analysis",
            workstream="product",
            collaboration_intent="anchor",
        ),
    ),
    (
        "prfaq",
        ArtifactClassification(
            kind="prfaq",
            phase="analysis",
            phase_zone="analysis",
            workstream="product",
            collaboration_intent="anchor",
        ),
    ),
    (
        "prd-validation-report",
        ArtifactClassification(
            kind="prd_validation_report",
            phase="planning",
            phase_zone="planning",
            workstream="product",
            collaboration_intent="summary",
        ),
    ),
    (
        "updated-prd",
        ArtifactClassification(
            kind="prd",
            phase="planning",
            phase_zone="planning",
            workstream="product",
            collaboration_intent="anchor",
        ),
    ),
    (
        "prd",
        ArtifactClassification(
            kind="prd",
            phase="planning",
            phase_zone="planning",
            workstream="product",
            collaboration_intent="anchor",
        ),
    ),
    (
        "ux-design",
        ArtifactClassification(
            kind="ux_design",
            phase="solutioning",
            phase_zone="solutioning",
            workstream="ux",
            collaboration_intent="anchor",
        ),
    ),
    (
        "architecture",
        ArtifactClassification(
            kind="architecture",
            phase="solutioning",
            phase_zone="solutioning",
            workstream="architecture",
            collaboration_intent="anchor",
        ),
    ),
    (
        "epics",
        ArtifactClassification(
            kind="epics_and_stories",
            phase="solutioning",
            phase_zone="solutioning",
            workstream="delivery",
            collaboration_intent="summary",
        ),
    ),
    (
        "story-validation",
        ArtifactClassification(
            kind="story_validation_report",
            phase="implementation",
            phase_zone="implementation_readiness",
            workstream="delivery",
            collaboration_intent="summary",
        ),
    ),
    (
        "retrospective",
        ArtifactClassification(
            kind="retrospective",
            phase="implementation",
            phase_zone="delivery_feedback",
            workstream="delivery",
            collaboration_intent="summary",
        ),
    ),
)

EXACT_STEM_RULES: dict[str, ArtifactClassification] = {
    "implementation-handoff": ArtifactClassification(
        kind="implementation_handoff",
        phase="implementation",
        phase_zone="implementation_readiness",
        workstream="delivery",
        collaboration_intent="summary",
    ),
    "implementation-readiness": ArtifactClassification(
        kind="readiness_report",
        phase="implementation",
        phase_zone="implementation_readiness",
        workstream="delivery",
        collaboration_intent="summary",
    ),
    "readiness-handoff": ArtifactClassification(
        kind="implementation_handoff",
        phase="implementation",
        phase_zone="implementation_readiness",
        workstream="delivery",
        collaboration_intent="summary",
    ),
    "sprint-status": ArtifactClassification(
        kind="sprint_status",
        phase="implementation",
        phase_zone="implementation_readiness",
        workstream="delivery",
        collaboration_intent="summary",
    ),
    "decision-records": ArtifactClassification(
        kind="decision_records",
        phase="implementation",
        phase_zone="delivery_feedback",
        workstream="delivery",
        collaboration_intent="summary",
    ),
}


def classify_artifact(relative_path: str) -> ArtifactClassification:
    path = Path(relative_path)
    normalized = relative_path.lower()
    lowered_parts = [part.lower() for part in path.parts]
    stem = path.stem.lower()
    if "implementation-artifacts/stories/" in normalized:
        return ArtifactClassification(
            kind="story",
            phase="implementation",
            phase_zone="implementation_readiness",
            workstream="delivery",
            collaboration_intent="summary",
        )
    if "implementation-artifacts" in lowered_parts and _looks_like_story(stem):
        return ArtifactClassification(
            kind="story",
            phase="implementation",
            phase_zone="implementation_readiness",
            workstream="delivery",
            collaboration_intent="summary",
        )
    exact_match = EXACT_STEM_RULES.get(stem)
    if exact_match is not None:
        return exact_match
    for needle, classification in CLASSIFICATION_RULES:
        if needle in normalized:
            return classification
    if "planning-artifacts" in lowered_parts:
        return ArtifactClassification(
            kind="document",
            phase="planning",
            phase_zone="planning",
            workstream="general",
            collaboration_intent="anchor",
        )
    if "implementation-artifacts" in lowered_parts:
        return ArtifactClassification(
            kind="document",
            phase="implementation",
            phase_zone="implementation_readiness",
            workstream="general",
            collaboration_intent="anchor",
        )
    if "analysis" in lowered_parts:
        return ArtifactClassification(
            kind="document",
            phase="analysis",
            phase_zone="analysis",
            workstream="general",
            collaboration_intent="anchor",
        )
    phase = _infer_phase_from_parent(path)
    return ArtifactClassification(
        kind="document",
        phase=phase,
        phase_zone=phase_zone_for_phase(phase),
        workstream="general",
        collaboration_intent="anchor",
    )


def phase_zone_for_phase(phase: str) -> str:
    if phase == "implementation":
        return "implementation_readiness"
    return phase


def phase_zone_rank(phase_zone: str) -> int:
    try:
        return PHASE_ZONE_ORDER.index(phase_zone)
    except ValueError:
        return len(PHASE_ZONE_ORDER)


def workstream_rank(workstream: str) -> int:
    try:
        return WORKSTREAM_ORDER.index(workstream)
    except ValueError:
        return len(WORKSTREAM_ORDER)


def title_from_path(relative_path: str, content: str) -> str:
    first_heading = _first_heading(content)
    if first_heading:
        return first_heading
    stem = Path(relative_path).stem.replace("-", " ").replace("_", " ")
    return stem.title()


def canonical_source_name(name: str) -> str:
    return CANONICAL_SOURCE_NAME_ALIASES.get(name.lower(), name.lower())


def _first_heading(content: str) -> str | None:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _infer_phase_from_parent(path: Path) -> str:
    lowered_parts = [part.lower() for part in path.parts]
    for phase in ("analysis", "planning", "solutioning", "implementation"):
        if phase in lowered_parts:
            return phase
    return "planning"


def _looks_like_story(stem: str) -> bool:
    return re.fullmatch(r"\d+-\d+-[a-z][a-z0-9-]*", stem) is not None
