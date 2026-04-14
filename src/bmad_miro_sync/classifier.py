from __future__ import annotations

from pathlib import Path


KIND_RULES: tuple[tuple[str, str, str], ...] = (
    ("product-brief", "product_brief", "analysis"),
    ("brainstorm", "brainstorm", "analysis"),
    ("research", "research", "analysis"),
    ("prfaq", "prfaq", "analysis"),
    ("prd-validation-report", "prd_validation_report", "planning"),
    ("updated-prd", "prd", "planning"),
    ("prd", "prd", "planning"),
    ("ux-design", "ux_design", "planning"),
    ("architecture", "architecture", "solutioning"),
    ("epics", "epics_and_stories", "solutioning"),
    ("readiness", "readiness_report", "solutioning"),
    ("sprint-status", "sprint_status", "implementation"),
    ("story-validation", "story_validation_report", "implementation"),
    ("retrospective", "retrospective", "implementation"),
)


def classify_artifact(relative_path: str) -> tuple[str, str]:
    path = Path(relative_path)
    normalized = relative_path.lower()
    if "implementation-artifacts/stories/" in normalized:
        return ("story", "implementation")
    for needle, kind, phase in KIND_RULES:
        if needle in normalized:
            return (kind, phase)
    if "planning-artifacts" in normalized:
        return ("document", "planning")
    if "implementation-artifacts" in normalized:
        return ("document", "implementation")
    if "analysis" in normalized:
        return ("document", "analysis")
    return ("document", _infer_phase_from_parent(path))


def title_from_path(relative_path: str, content: str) -> str:
    first_heading = _first_heading(content)
    if first_heading:
        return first_heading
    stem = Path(relative_path).stem.replace("-", " ").replace("_", " ")
    return stem.title()


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
